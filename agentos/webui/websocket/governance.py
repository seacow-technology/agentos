"""
Governance WebSocket - Real-time governance updates

L-21: Real-time quota usage updates via WebSocket

WS /ws/governance - Real-time governance event stream

Architecture:
- Client connects and subscribes to governance events
- Server pushes quota updates when usage changes
- Client updates UI without page refresh

Event Types:
- quota_update: Quota usage changed
- quota_warning: Quota reached warning threshold (80%)
- quota_denied: Quota exceeded
- governance_event: Other governance events (policy violations, etc.)
"""

import logging
import asyncio
import uuid
from typing import Dict, Set, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agentos.core.capabilities.quota_manager import QuotaManager
from agentos.core.capabilities.registry import CapabilityRegistry
from agentos.core.extensions.registry import ExtensionRegistry

logger = logging.getLogger(__name__)

router = APIRouter()


class GovernanceStreamManager:
    """
    Manages WebSocket connections for governance updates

    Each connection subscribes to governance events.
    When quota usage changes, updates are pushed to all clients.
    """

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self._quota_manager: Optional[QuotaManager] = None
        self._last_state_snapshot: Dict = {}

    def _get_quota_manager(self) -> QuotaManager:
        """Get quota manager instance (lazy initialization)"""
        if self._quota_manager is None:
            self._quota_manager = QuotaManager()
        return self._quota_manager

    async def connect(self, client_id: str, websocket: WebSocket):
        """Accept and register WebSocket connection"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Governance stream client connected: {client_id} (total: {len(self.active_connections)})")

        # Send initial state snapshot
        await self.send_initial_snapshot(client_id, websocket)

    def disconnect(self, client_id: str):
        """Remove WebSocket connection"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Governance stream client disconnected: {client_id} (total: {len(self.active_connections)})")

    async def send_initial_snapshot(self, client_id: str, websocket: WebSocket):
        """Send initial quota snapshot to newly connected client"""
        try:
            quota_manager = self._get_quota_manager()
            quota_states = []

            for quota_id, state in quota_manager.states.items():
                quota_config = quota_manager.quotas.get(quota_id)
                if not quota_config or not quota_config.enabled:
                    continue

                # Calculate status
                status = "ok"
                usage_percent = 0.0

                if quota_config.limit.calls_per_minute:
                    used = max(0, state.used_calls)
                    limit = max(1, quota_config.limit.calls_per_minute)
                    usage_percent = (used / limit) * 100

                    if usage_percent >= 100:
                        status = "denied"
                    elif usage_percent >= 80:
                        status = "warning"

                quota_states.append({
                    "capability_id": quota_id,
                    "status": status,
                    "usage_percent": round(usage_percent, 2),
                    "used_calls": max(0, state.used_calls),
                    "limit_calls": quota_config.limit.calls_per_minute or 0,
                    "last_reset": state.last_reset.isoformat() if state.last_reset else None
                })

            await websocket.send_json({
                "type": "governance_snapshot",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "quotas": quota_states
                }
            })

            # Store snapshot for change detection
            self._last_state_snapshot[client_id] = {q["capability_id"]: q for q in quota_states}

        except Exception as e:
            logger.error(f"Failed to send initial snapshot to {client_id}: {e}", exc_info=True)

    async def broadcast_quota_update(self, capability_id: str, quota_state: Dict):
        """
        Broadcast quota update to all connected clients

        Args:
            capability_id: Capability ID
            quota_state: Current quota state
        """
        if not self.active_connections:
            return

        message = {
            "type": "quota_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "capability_id": capability_id,
                **quota_state
            }
        }

        disconnected_clients = []

        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send quota update to client {client_id}: {e}")
                disconnected_clients.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)

    async def broadcast_governance_event(self, event_type: str, event_data: Dict):
        """
        Broadcast governance event to all connected clients

        Args:
            event_type: Event type (quota_warning, quota_denied, policy_violation, etc.)
            event_data: Event data
        """
        if not self.active_connections:
            return

        message = {
            "type": "governance_event",
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": event_data
        }

        disconnected_clients = []

        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send governance event to client {client_id}: {e}")
                disconnected_clients.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)

    async def poll_quota_changes(self):
        """
        Poll for quota changes and broadcast updates

        This runs in background and checks for quota changes periodically.
        In production, this would be event-driven from the quota manager.
        """
        while True:
            try:
                if not self.active_connections:
                    # No clients connected, skip polling
                    await asyncio.sleep(5)
                    continue

                quota_manager = self._get_quota_manager()

                for quota_id, state in quota_manager.states.items():
                    quota_config = quota_manager.quotas.get(quota_id)
                    if not quota_config or not quota_config.enabled:
                        continue

                    # Calculate current status
                    status = "ok"
                    usage_percent = 0.0

                    if quota_config.limit.calls_per_minute:
                        used = max(0, state.used_calls)
                        limit = max(1, quota_config.limit.calls_per_minute)
                        usage_percent = (used / limit) * 100

                        if usage_percent >= 100:
                            status = "denied"
                        elif usage_percent >= 80:
                            status = "warning"

                    current_state = {
                        "status": status,
                        "usage_percent": round(usage_percent, 2),
                        "used_calls": max(0, state.used_calls),
                        "limit_calls": quota_config.limit.calls_per_minute or 0
                    }

                    # Check if state changed for any client
                    for client_id in list(self.active_connections.keys()):
                        last_snapshot = self._last_state_snapshot.get(client_id, {})
                        last_state = last_snapshot.get(quota_id, {})

                        # Broadcast if changed
                        if (last_state.get("usage_percent") != current_state["usage_percent"] or
                            last_state.get("status") != current_state["status"]):
                            await self.broadcast_quota_update(quota_id, current_state)

                            # Update snapshot
                            if client_id in self._last_state_snapshot:
                                self._last_state_snapshot[client_id][quota_id] = {
                                    "capability_id": quota_id,
                                    **current_state
                                }

                await asyncio.sleep(2)  # Poll every 2 seconds

            except Exception as e:
                logger.error(f"Error in quota polling: {e}", exc_info=True)
                await asyncio.sleep(5)


# Global manager instance
manager = GovernanceStreamManager()


@router.websocket("/governance")
async def websocket_governance(websocket: WebSocket):
    """
    WebSocket governance stream endpoint

    L-21: Real-time quota updates

    Client connection lifecycle:
    1. Connect → receive initial snapshot
    2. Listen → receive updates as quota usage changes
    3. Disconnect → cleanup

    Server-to-client only (no client messages expected).

    Example client usage (JavaScript):
    ```javascript
    const ws = new WebSocket('ws://localhost:8080/ws/governance');
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'quota_update') {
        updateQuotaDisplay(data.data);
      }
    };
    ```
    """
    # Generate unique client ID
    client_id = str(uuid.uuid4())

    await manager.connect(client_id, websocket)

    try:
        # Keep connection alive (server-to-client only)
        while True:
            # Wait for any message (used for keepalive/ping)
            data = await websocket.receive_text()

            # Handle ping/pong
            if data == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}", exc_info=True)
        manager.disconnect(client_id)


@router.get("/governance/status")
async def get_governance_stream_status():
    """
    Get governance stream status (for monitoring)

    Returns number of active WebSocket connections.
    """
    return {
        "active_connections": len(manager.active_connections),
        "polling_enabled": len(manager.active_connections) > 0
    }


# Start background polling task
async def start_quota_polling():
    """Start background quota polling task"""
    asyncio.create_task(manager.poll_quota_changes())
