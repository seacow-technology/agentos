"""Cloudflare Tunnel Provider"""

import logging
import subprocess
import threading
import time
import json
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class CloudflareTunnelManager:
    """管理 Cloudflare Tunnel 生命周期"""

    def __init__(
        self,
        tunnel_id: str,
        tunnel_name: str,
        token: str,  # Cloudflare Tunnel Token
        local_target: str,
        store  # NetworkOSStore
    ):
        self.tunnel_id = tunnel_id
        self.tunnel_name = tunnel_name
        self.token = token
        self.local_target = local_target
        self.store = store

        self.process: Optional[subprocess.Popen] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self._should_stop = False

    def start(self) -> bool:
        """启动 tunnel

        Returns:
            True 如果启动成功
        """
        if self.process and self.process.poll() is None:
            logger.warning(f"Tunnel {self.tunnel_name} already running")
            return True

        try:
            # 检查 cloudflared 是否安装
            if not self._check_cloudflared():
                logger.error("cloudflared not found. Install: brew install cloudflared")
                self._log_event("error", "cloudflared_not_found", "cloudflared not installed")
                return False

            # 启动 cloudflared
            cmd = [
                "cloudflared",
                "tunnel",
                "--no-autoupdate",
                "run",
                "--token", self.token
            ]

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # 更新状态
            self.store.update_health(
                self.tunnel_id,
                health_status="up",
                error_code=None,
                error_message=None
            )
            self._log_event("info", "tunnel_start", f"Tunnel {self.tunnel_name} started")

            # 启动监控线程
            self._should_stop = False
            self.monitor_thread = threading.Thread(target=self._monitor_process, daemon=True)
            self.monitor_thread.start()

            return True

        except Exception as e:
            logger.error(f"Failed to start tunnel: {e}", exc_info=True)
            self._log_event("error", "tunnel_start_failed", str(e))
            self.store.update_health(
                self.tunnel_id,
                health_status="down",
                error_code="START_FAILED",
                error_message=str(e)
            )
            return False

    def stop(self) -> None:
        """停止 tunnel"""
        self._should_stop = True

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception as e:
                logger.error(f"Error stopping tunnel: {e}")
            finally:
                self.process = None

        self.store.update_health(
            self.tunnel_id,
            health_status="down",
            error_code="STOPPED",
            error_message="Manually stopped"
        )
        self._log_event("info", "tunnel_stop", f"Tunnel {self.tunnel_name} stopped")

    def is_running(self) -> bool:
        """检查 tunnel 是否运行"""
        return self.process is not None and self.process.poll() is None

    def _check_cloudflared(self) -> bool:
        """检查 cloudflared 是否安装"""
        try:
            result = subprocess.run(
                ["cloudflared", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def _monitor_process(self) -> None:
        """监控进程输出和健康状态"""
        while not self._should_stop:
            if not self.process or self.process.poll() is not None:
                # 进程已退出
                exit_code = self.process.returncode if self.process else -1
                logger.warning(f"Tunnel process exited with code {exit_code}")

                # 读取错误输出
                stderr = ""
                if self.process and self.process.stderr:
                    try:
                        stderr = self.process.stderr.read()
                    except:
                        pass

                self.store.update_health(
                    self.tunnel_id,
                    health_status="down",
                    error_code=f"EXIT_{exit_code}",
                    error_message=stderr[:500] if stderr else "Process exited"
                )
                self._log_event(
                    "error",
                    "cloudflared_exit",
                    f"Process exited with code {exit_code}",
                    {"exit_code": exit_code, "stderr": stderr[:500]}
                )
                break

            # 读取 stdout（cloudflared 输出连接日志）
            if self.process.stdout:
                try:
                    line = self.process.stdout.readline()
                    if line:
                        self._parse_cloudflared_output(line)
                except:
                    pass

            time.sleep(1)

    def _parse_cloudflared_output(self, line: str) -> None:
        """解析 cloudflared 输出，提取健康信息"""
        # Cloudflared 输出示例：
        # {"level":"info","time":"...","message":"Connection established"}
        try:
            if "error" in line.lower():
                self._log_event("warn", "cloudflared_warning", line[:200])
        except:
            pass

    def _log_event(
        self,
        level: str,
        event_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录事件到 DB"""
        import uuid
        from agentos.core.time import utc_now_ms

        event = {
            'event_id': str(uuid.uuid4()),
            'tunnel_id': self.tunnel_id,
            'level': level,
            'event_type': event_type,
            'message': message,
            'data_json': json.dumps(data) if data else None,
            'created_at': utc_now_ms()
        }

        try:
            self.store.append_event(event)
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
