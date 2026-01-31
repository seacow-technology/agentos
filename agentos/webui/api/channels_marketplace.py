"""Channels Marketplace API - Channel marketplace and management endpoints.

This module provides REST API endpoints for managing communication channels:
- List all available channels (from registry)
- Get/update channel configuration
- Enable/disable channels
- Test channel connectivity
- Get channel events and health status

Part of CommunicationOS Channel Management WebUI (Task #7)
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from agentos.communicationos.registry import ChannelRegistry, ChannelConfigStore
from agentos.communicationos.manifest import ChannelManifest
from agentos.core.time import utc_now
from agentos.webui.api.contracts import (
    success,
    error,
    not_found_error,
    validation_error,
    ReasonCode,
)
from agentos.webui.api.time_format import iso_z

logger = logging.getLogger(__name__)

router = APIRouter()

# Global service instances
_registry: Optional[ChannelRegistry] = None
_config_store: Optional[ChannelConfigStore] = None


def get_registry() -> ChannelRegistry:
    """Get or create the channel registry instance.

    Returns:
        ChannelRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ChannelRegistry()
        logger.info("ChannelRegistry initialized")
    return _registry


def get_config_store() -> ChannelConfigStore:
    """Get or create the channel config store instance.

    Returns:
        ChannelConfigStore instance
    """
    global _config_store
    if _config_store is None:
        _config_store = ChannelConfigStore()
        logger.info("ChannelConfigStore initialized")
    return _config_store


# ============================================
# Request/Response Models
# ============================================

class ChannelSummary(BaseModel):
    """Channel summary for list view"""
    id: str
    name: str
    icon: str
    description: str
    provider: Optional[str] = None
    capabilities: List[str]
    status: str  # enabled, disabled, error, needs_setup
    enabled: bool
    security_mode: str
    last_heartbeat_at: Optional[int] = None
    privacy_badges: List[str]


class ChannelListResponse(BaseModel):
    """Channel list response"""
    channels: List[ChannelSummary]
    total: int


class ChannelDetailResponse(BaseModel):
    """Detailed channel information"""
    manifest: Dict[str, Any]
    config: Optional[Dict[str, Any]] = None
    status: Dict[str, Any]
    recent_events: List[Dict[str, Any]]
    audit_log: List[Dict[str, Any]]


class ChannelConfigRequest(BaseModel):
    """Request to update channel configuration"""
    config: Dict[str, Any] = Field(..., description="Channel configuration")
    performed_by: Optional[str] = Field(None, description="User performing the action")


class ChannelActionRequest(BaseModel):
    """Request for channel actions (enable/disable)"""
    performed_by: Optional[str] = Field(None, description="User performing the action")


class ChannelTestRequest(BaseModel):
    """Request to test channel connectivity"""
    test_type: str = Field("basic", description="Type of test: basic, webhook, send")
    test_data: Optional[Dict[str, Any]] = Field(None, description="Test-specific data")


# ============================================
# Channels List and Detail
# ============================================

@router.get("/api/channels-marketplace", tags=["channels_marketplace"])
async def list_channels() -> Dict[str, Any]:
    """List all available channels.

    Returns:
        List of channel summaries with status information

    Example response:
    ```json
    {
      "ok": true,
      "data": {
        "channels": [
          {
            "id": "whatsapp_twilio",
            "name": "WhatsApp (Twilio)",
            "icon": "whatsapp",
            "description": "WhatsApp Business API via Twilio",
            "provider": "Twilio",
            "capabilities": ["inbound_text", "outbound_text"],
            "status": "enabled",
            "enabled": true,
            "security_mode": "chat_only",
            "privacy_badges": ["No Auto Provisioning", "Chat-only"]
          }
        ],
        "total": 1
      }
    }
    ```
    """
    try:
        registry = get_registry()
        config_store = get_config_store()

        # Get all manifests from registry
        manifests = registry.list_manifests()

        # Get status for each channel
        channels = []
        for manifest in manifests:
            status_info = config_store.get_status(manifest.id)

            # If no status exists, channel needs setup
            if not status_info:
                status = "needs_setup"
                enabled = False
                last_heartbeat_at = None
            else:
                status = status_info["status"]
                enabled = status_info["enabled"]
                last_heartbeat_at = status_info.get("last_heartbeat_at")

            channels.append({
                "id": manifest.id,
                "name": manifest.name,
                "icon": manifest.icon,
                "description": manifest.description,
                "provider": manifest.provider,
                "capabilities": [c.value for c in manifest.capabilities],
                "status": status,
                "enabled": enabled,
                "security_mode": manifest.security_defaults.mode.value,
                "last_heartbeat_at": last_heartbeat_at,
                "privacy_badges": manifest.privacy_badges,
            })

        return success({
            "channels": channels,
            "total": len(channels)
        })

    except Exception as e:
        logger.error(f"Failed to list channels: {str(e)}", exc_info=True)
        raise error(
            "Failed to retrieve channels",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.get("/api/channels-marketplace/{channel_id}", tags=["channels_marketplace"])
async def get_channel_detail(channel_id: str) -> Dict[str, Any]:
    """Get detailed information for a specific channel.

    Args:
        channel_id: Channel identifier

    Returns:
        Detailed channel information including manifest, config, status, and events
    """
    try:
        registry = get_registry()
        config_store = get_config_store()

        # Get manifest
        manifest = registry.get_manifest(channel_id)
        if not manifest:
            raise not_found_error("Channel", channel_id)

        # Get configuration (if exists)
        config = config_store.get_config(channel_id)

        # Get status
        status_info = config_store.get_status(channel_id)
        if not status_info:
            status_info = {
                "channel_id": channel_id,
                "enabled": False,
                "status": "needs_setup",
                "last_error": None,
                "last_heartbeat_at": None,
            }

        # Get recent events
        recent_events = config_store.get_recent_events(channel_id, limit=10)

        # Get audit log
        audit_log = config_store.get_audit_log(channel_id, limit=20)

        return success({
            "manifest": manifest.to_dict(),
            "config": config,
            "status": status_info,
            "recent_events": recent_events,
            "audit_log": audit_log,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get channel {channel_id}: {str(e)}", exc_info=True)
        raise error(
            f"Failed to retrieve channel {channel_id}",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


# ============================================
# Configuration Management
# ============================================

@router.get("/api/channels-marketplace/{channel_id}/config", tags=["channels_marketplace"])
async def get_channel_config(channel_id: str) -> Dict[str, Any]:
    """Get configuration for a specific channel.

    Args:
        channel_id: Channel identifier

    Returns:
        Channel configuration (secrets will be masked)
    """
    try:
        registry = get_registry()
        config_store = get_config_store()

        # Verify channel exists
        manifest = registry.get_manifest(channel_id)
        if not manifest:
            raise not_found_error("Channel", channel_id)

        # Get configuration
        config = config_store.get_config(channel_id)

        # Mask secret fields
        if config:
            masked_config = config.copy()
            for field in manifest.required_config_fields:
                if field.secret and field.name in masked_config:
                    masked_config[field.name] = "***MASKED***"
            config = masked_config

        return success({
            "channel_id": channel_id,
            "config": config or {},
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get config for {channel_id}: {str(e)}", exc_info=True)
        raise error(
            f"Failed to retrieve configuration for {channel_id}",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.put("/api/channels-marketplace/{channel_id}/config", tags=["channels_marketplace"])
async def update_channel_config(
    channel_id: str,
    request: ChannelConfigRequest
) -> Dict[str, Any]:
    """Update configuration for a specific channel.

    Args:
        channel_id: Channel identifier
        request: Configuration update request

    Returns:
        Success message and updated status
    """
    try:
        registry = get_registry()
        config_store = get_config_store()

        # Verify channel exists
        manifest = registry.get_manifest(channel_id)
        if not manifest:
            raise not_found_error("Channel", channel_id)

        # Validate configuration
        is_valid, error_msg = manifest.validate_config(request.config)
        if not is_valid:
            raise validation_error(
                f"Invalid configuration: {error_msg}",
                hint="Check required fields and format"
            )

        # Save configuration
        config_store.save_config(
            channel_id=channel_id,
            config=request.config,
            performed_by=request.performed_by or "webui_user"
        )

        logger.info(f"Channel {channel_id} configuration updated")

        return success({
            "channel_id": channel_id,
            "message": "Configuration updated successfully",
            "status": "needs_setup"  # After config update, channel needs to be enabled
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update config for {channel_id}: {str(e)}", exc_info=True)
        raise error(
            f"Failed to update configuration for {channel_id}",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


# ============================================
# Channel Actions
# ============================================

@router.post("/api/channels-marketplace/{channel_id}/enable", tags=["channels_marketplace"])
async def enable_channel(
    channel_id: str,
    request: ChannelActionRequest = Body(...)
) -> Dict[str, Any]:
    """Enable a channel.

    Args:
        channel_id: Channel identifier
        request: Action request with performer info

    Returns:
        Success message and updated status
    """
    try:
        registry = get_registry()
        config_store = get_config_store()

        # Verify channel exists
        manifest = registry.get_manifest(channel_id)
        if not manifest:
            raise not_found_error("Channel", channel_id)

        # Verify configuration exists
        config = config_store.get_config(channel_id)
        if not config:
            raise validation_error(
                "Channel must be configured before enabling",
                hint="Update channel configuration first"
            )

        # Validate configuration
        is_valid, error_msg = manifest.validate_config(config)
        if not is_valid:
            raise validation_error(
                f"Current configuration is invalid: {error_msg}",
                hint="Update configuration and try again"
            )

        # Enable channel
        config_store.set_enabled(
            channel_id=channel_id,
            enabled=True,
            performed_by=request.performed_by or "webui_user"
        )

        logger.info(f"Channel {channel_id} enabled")

        return success({
            "channel_id": channel_id,
            "enabled": True,
            "message": f"Channel {manifest.name} enabled successfully"
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable channel {channel_id}: {str(e)}", exc_info=True)
        raise error(
            f"Failed to enable channel {channel_id}",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.post("/api/channels-marketplace/{channel_id}/disable", tags=["channels_marketplace"])
async def disable_channel(
    channel_id: str,
    request: ChannelActionRequest = Body(...)
) -> Dict[str, Any]:
    """Disable a channel.

    Args:
        channel_id: Channel identifier
        request: Action request with performer info

    Returns:
        Success message and updated status
    """
    try:
        registry = get_registry()
        config_store = get_config_store()

        # Verify channel exists
        manifest = registry.get_manifest(channel_id)
        if not manifest:
            raise not_found_error("Channel", channel_id)

        # Disable channel
        config_store.set_enabled(
            channel_id=channel_id,
            enabled=False,
            performed_by=request.performed_by or "webui_user"
        )

        logger.info(f"Channel {channel_id} disabled")

        return success({
            "channel_id": channel_id,
            "enabled": False,
            "message": f"Channel {manifest.name} disabled successfully"
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable channel {channel_id}: {str(e)}", exc_info=True)
        raise error(
            f"Failed to disable channel {channel_id}",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.post("/api/channels-marketplace/{channel_id}/test", tags=["channels_marketplace"])
async def test_channel(
    channel_id: str,
    request: ChannelTestRequest = Body(...)
) -> Dict[str, Any]:
    """Test channel connectivity and configuration.

    Args:
        channel_id: Channel identifier
        request: Test request with test type and data

    Returns:
        Test results
    """
    try:
        registry = get_registry()
        config_store = get_config_store()

        # Verify channel exists
        manifest = registry.get_manifest(channel_id)
        if not manifest:
            raise not_found_error("Channel", channel_id)

        # Verify configuration exists
        config = config_store.get_config(channel_id)
        if not config:
            raise validation_error(
                "Channel must be configured before testing",
                hint="Update channel configuration first"
            )

        # Validate configuration
        is_valid, error_msg = manifest.validate_config(config)
        if not is_valid:
            return success({
                "channel_id": channel_id,
                "test_type": request.test_type,
                "success": False,
                "message": f"Configuration validation failed: {error_msg}",
                "timestamp": iso_z(utc_now())
            })

        # TODO: Implement actual connectivity tests based on test_type
        # For now, just validate configuration
        logger.info(f"Channel {channel_id} test: {request.test_type}")

        # Log test event
        config_store.log_event(
            channel_id=channel_id,
            event_type="test",
            status="success",
            metadata={"test_type": request.test_type}
        )

        return success({
            "channel_id": channel_id,
            "test_type": request.test_type,
            "success": True,
            "message": "Configuration is valid. Channel is ready for use.",
            "timestamp": iso_z(utc_now())
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test channel {channel_id}: {str(e)}", exc_info=True)
        raise error(
            f"Failed to test channel {channel_id}",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


# ============================================
# Events and Health
# ============================================

@router.get("/api/channels-marketplace/{channel_id}/events", tags=["channels_marketplace"])
async def get_channel_events(
    channel_id: str,
    limit: int = Query(10, description="Maximum number of events", ge=1, le=100)
) -> Dict[str, Any]:
    """Get recent events for a channel.

    Args:
        channel_id: Channel identifier
        limit: Maximum number of events to return

    Returns:
        List of recent events

    Example response:
    ```json
    {
      "ok": true,
      "data": {
        "channel_id": "whatsapp_twilio",
        "events": [
          {
            "event_type": "message_received",
            "message_id": "msg123",
            "status": "success",
            "created_at": 1706789400000
          }
        ],
        "total": 1
      }
    }
    ```
    """
    try:
        registry = get_registry()
        config_store = get_config_store()

        # Verify channel exists
        manifest = registry.get_manifest(channel_id)
        if not manifest:
            raise not_found_error("Channel", channel_id)

        # Get events
        events = config_store.get_recent_events(channel_id, limit=limit)

        return success({
            "channel_id": channel_id,
            "events": events,
            "total": len(events)
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get events for {channel_id}: {str(e)}", exc_info=True)
        raise error(
            f"Failed to retrieve events for {channel_id}",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )
