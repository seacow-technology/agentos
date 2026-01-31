"""NetworkOS - Network tunnel and routing management for AgentOS.

NetworkOS provides unified network tunnel management, supporting:
- Cloudflare Tunnel (primary)
- ngrok (future)
- Tailscale (future)
- Self-hosted tunnels (future)

Key features:
- Centralized tunnel configuration and lifecycle management
- Health monitoring and diagnostics
- Event logging and audit trail
- Public URL → local port forwarding

Usage:
    from agentos.networkos import NetworkOSStore, Tunnel
    from agentos.core.time import utc_now_ms

    store = NetworkOSStore()

    # Create tunnel
    tunnel = Tunnel(
        tunnel_id="tunnel-123",
        provider="cloudflare",
        name="my-tunnel",
        is_enabled=True,
        public_hostname="my-app.trycloudflare.com",
        local_target="localhost:8080",
        mode="http",
        health_status="unknown",
        last_heartbeat_at=None,
        last_error_code=None,
        last_error_message=None,
        created_at=utc_now_ms(),
        updated_at=utc_now_ms()
    )
    store.create_tunnel(tunnel)

    # Update health
    store.update_health(
        tunnel_id="tunnel-123",
        health_status="up",
        error_code=None,
        error_message=None
    )

    # List tunnels
    tunnels = store.list_tunnels(enabled_only=True)
"""

from .store import NetworkOSStore, Tunnel, TunnelEvent

__all__ = [
    'NetworkOSStore',
    'Tunnel',
    'TunnelEvent',
]

__version__ = '0.1.0'
