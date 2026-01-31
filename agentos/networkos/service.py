"""NetworkOS Service - 统一的 Tunnel 管理接口"""

import logging
import uuid
from typing import Optional, List, Dict, Any, Callable
from agentos.networkos.store import NetworkOSStore, Tunnel
from agentos.networkos.providers.cloudflare import CloudflareTunnelManager
from agentos.core.time import utc_now_ms

logger = logging.getLogger(__name__)


class NetworkOSService:
    """NetworkOS 统一服务"""

    def __init__(self, store: Optional[NetworkOSStore] = None):
        self.store = store or NetworkOSStore()
        self._tunnel_managers: Dict[str, CloudflareTunnelManager] = {}

    def create_tunnel(
        self,
        provider: str,
        name: str,
        public_hostname: str,
        local_target: str,
        token: str,
        mode: str = "http"
    ) -> str:
        """创建新 tunnel

        Args:
            provider: cloudflare, ngrok, etc.
            name: tunnel 名称
            public_hostname: 公网域名
            local_target: 本地目标（如 http://127.0.0.1:8000）
            token: provider token
            mode: http, tcp, https

        Returns:
            tunnel_id
        """
        tunnel_id = str(uuid.uuid4())
        now = utc_now_ms()

        tunnel = Tunnel(
            tunnel_id=tunnel_id,
            provider=provider,
            name=name,
            is_enabled=False,
            public_hostname=public_hostname,
            local_target=local_target,
            mode=mode,
            health_status="unknown",
            last_heartbeat_at=None,
            last_error_code=None,
            last_error_message=None,
            created_at=now,
            updated_at=now
        )

        self.store.create_tunnel(tunnel)

        # Save token securely
        self.store.save_token(tunnel_id, token)

        logger.info(f"Created tunnel: {tunnel_id} ({name})")
        return tunnel_id

    def _get_token(self, tunnel_id: str) -> str:
        """Get tunnel token (prioritizes secret_ref over legacy token)

        Strategy:
        1. Try secret_ref first (recommended path)
        2. Fall back to legacy token (with warning)
        3. Raise error if neither available

        Returns:
            Token string

        Raises:
            ValueError: If no token found
            NotImplementedError: If secure storage not integrated yet
        """
        # 1. Try secret_ref (recommended)
        secret_ref = self.store.get_tunnel_secret_ref(tunnel_id)
        if secret_ref:
            # TODO: Integrate with secure storage
            # from agentos.webui.secrets import SecretStore
            # secret_store = SecretStore()
            # token = secret_store.get_secret(secret_ref)
            # if token:
            #     return token
            raise NotImplementedError(
                f"Secure storage integration needed for secret_ref: {secret_ref}. "
                f"Please run: agentos networkos migrate-secrets {tunnel_id}"
            )

        # 2. Fall back to legacy token (deprecated)
        token = self.store.get_tunnel_token_legacy(tunnel_id)
        if token:
            logger.warning(
                f"Tunnel {tunnel_id} using legacy token storage. "
                f"Run migration: agentos networkos migrate-secrets {tunnel_id}"
            )
            return token

        # 3. No token found
        raise ValueError(f"No token found for tunnel {tunnel_id}")

    def start_tunnel(self, tunnel_id: str) -> bool:
        """启动 tunnel"""
        tunnel = self.store.get_tunnel(tunnel_id)
        if not tunnel:
            logger.error(f"Tunnel not found: {tunnel_id}")
            return False

        if tunnel.provider == "cloudflare":
            try:
                token = self._get_token(tunnel_id)
            except ValueError as e:
                logger.error(str(e))
                return False
            except NotImplementedError as e:
                logger.error(str(e))
                return False

            manager = CloudflareTunnelManager(
                tunnel_id=tunnel.tunnel_id,
                tunnel_name=tunnel.name,
                token=token,
                local_target=tunnel.local_target,
                store=self.store
            )

            if manager.start():
                self._tunnel_managers[tunnel_id] = manager
                self.store.set_enabled(tunnel_id, True)
                return True
            return False
        else:
            logger.error(f"Unsupported provider: {tunnel.provider}")
            return False

    def stop_tunnel(self, tunnel_id: str) -> None:
        """停止 tunnel"""
        manager = self._tunnel_managers.get(tunnel_id)
        if manager:
            manager.stop()
            del self._tunnel_managers[tunnel_id]

        self.store.set_enabled(tunnel_id, False)

    def list_tunnels(self) -> List[Tunnel]:
        """列出所有 tunnel"""
        return self.store.list_tunnels()

    def get_tunnel_status(self, tunnel_id: str) -> Optional[Dict[str, Any]]:
        """获取 tunnel 详细状态"""
        tunnel = self.store.get_tunnel(tunnel_id)
        if not tunnel:
            return None

        # 获取最近事件
        events = self.store.get_recent_events(tunnel_id, limit=10)

        return {
            "tunnel": tunnel,
            "is_running": tunnel_id in self._tunnel_managers,
            "recent_events": events
        }

    def delete_tunnel(self, tunnel_id: str) -> bool:
        """删除 tunnel"""
        # Stop if running
        if tunnel_id in self._tunnel_managers:
            self.stop_tunnel(tunnel_id)

        # Delete from database
        try:
            self.store.delete_tunnel(tunnel_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete tunnel {tunnel_id}: {e}")
            return False

    def get_running_tunnels(self) -> List[str]:
        """获取所有运行中的 tunnel ID"""
        return list(self._tunnel_managers.keys())

    def shutdown_all(self) -> None:
        """关闭所有 tunnel（用于优雅退出）"""
        logger.info("Shutting down all tunnels...")
        for tunnel_id in list(self._tunnel_managers.keys()):
            self.stop_tunnel(tunnel_id)
        logger.info("All tunnels stopped")

    def migrate_tunnel_secrets(
        self,
        tunnel_id: Optional[str] = None,
        secure_storage_save_fn: Optional[Callable[[str, str], None]] = None
    ) -> int:
        """Migrate tunnel secrets from plaintext token to secret_ref

        Args:
            tunnel_id: Specific tunnel ID to migrate, or None to migrate all
            secure_storage_save_fn: Function to save to secure storage (key, value) -> None
                                   If None, uses default SecretStore

        Returns:
            Number of tunnels migrated

        Raises:
            NotImplementedError: If secure storage integration is not available
        """
        # Use default secure storage if not provided
        if secure_storage_save_fn is None:
            try:
                from agentos.webui.secrets import SecretStore
                secret_store = SecretStore()

                def default_save_fn(key: str, value: str):
                    # Save to secure storage with networkos provider namespace
                    secret_store.save_secret(key, value)

                secure_storage_save_fn = default_save_fn
            except ImportError as e:
                raise NotImplementedError(
                    "Secure storage integration required. "
                    "Please ensure agentos.webui.secrets module is available."
                ) from e

        # Migrate specific tunnel or all tunnels
        if tunnel_id:
            success = self.store.migrate_token_to_secret_ref(
                tunnel_id,
                secure_storage_save_fn
            )
            return 1 if success else 0
        else:
            # Get all unmigrated tunnels
            unmigrated = self.store.list_unmigrated_tunnels()
            count = 0
            for tid in unmigrated:
                try:
                    success = self.store.migrate_token_to_secret_ref(
                        tid,
                        secure_storage_save_fn
                    )
                    if success:
                        count += 1
                except Exception as e:
                    logger.error(f"Failed to migrate tunnel {tid}: {e}")
            return count

    def get_migration_status(self) -> Dict[str, Any]:
        """Get migration status for all tunnels

        Returns:
            Dict with migration statistics and unmigrated tunnel IDs
        """
        all_tunnels = self.store.list_tunnels()
        unmigrated = self.store.list_unmigrated_tunnels()

        return {
            "total_tunnels": len(all_tunnels),
            "migrated_count": len(all_tunnels) - len(unmigrated),
            "unmigrated_count": len(unmigrated),
            "unmigrated_tunnel_ids": unmigrated,
            "migration_complete": len(unmigrated) == 0
        }
