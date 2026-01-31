"""
WebUI Daemon Manager - 后台服务管理

管理 WebUI 的后台启动、停止和状态检查
"""

import os
import sys
import subprocess
import time
import logging
from pathlib import Path
from typing import Optional, Tuple

from agentos.core.utils.process import terminate_process, kill_process, is_process_running

logger = logging.getLogger(__name__)


def load_env_file(env_file: Path) -> dict:
    """
    从.env文件加载环境变量

    Args:
        env_file: .env文件路径

    Returns:
        环境变量字典
    """
    env_vars = {}
    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释
                    if not line or line.startswith('#'):
                        continue
                    # 解析 KEY=VALUE 格式
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
        except Exception as e:
            logger.warning(f"Failed to load .env file: {e}")
    return env_vars


class WebUIDaemon:
    """WebUI 后台服务管理器"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        """
        初始化 Daemon Manager

        Args:
            host: 绑定主机
            port: 绑定端口
        """
        self.host = host
        self.port = port

        # PID 文件路径
        self.pid_file = Path.home() / ".agentos" / "webui.pid"
        self.log_file = Path.home() / ".agentos" / "webui.log"

        # 确保目录存在
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)

    def is_running(self) -> Tuple[bool, Optional[int]]:
        """
        检查 WebUI 是否正在运行

        Returns:
            (是否运行, PID)
        """
        if not self.pid_file.exists():
            return False, None

        try:
            pid = int(self.pid_file.read_text().strip())

            # 检查进程是否存在
            if is_process_running(pid):
                return True, pid
            else:
                # 进程不存在，清理 PID 文件
                self.pid_file.unlink(missing_ok=True)
                return False, None

        except (ValueError, FileNotFoundError):
            return False, None

    def start(self, background: bool = True) -> bool:
        """
        启动 WebUI 服务

        Args:
            background: 是否后台运行

        Returns:
            是否成功启动
        """
        # 检查是否已运行
        is_running, pid = self.is_running()
        if is_running:
            logger.info(f"WebUI already running at PID {pid}")
            return True

        try:
            if background:
                # 后台启动
                self._start_background()
            else:
                # 前台启动
                self._start_foreground()

            return True

        except Exception as e:
            logger.error(f"Failed to start WebUI: {e}", exc_info=True)
            return False

    def _start_background(self):
        """后台启动 WebUI"""
        logger.info(f"Starting WebUI in background at {self.host}:{self.port}")

        # 加载.env文件中的环境变量
        project_root = Path(__file__).parent.parent.parent  # agentos/webui/daemon.py -> AgentOS/
        env_file = project_root / ".env"

        # 合并当前环境变量和.env文件变量
        env = os.environ.copy()
        env_vars = load_env_file(env_file)
        env.update(env_vars)

        if env_vars:
            logger.info(f"Loaded {len(env_vars)} variables from {env_file}")
        else:
            logger.warning(f".env file not found or empty at {env_file}")

        # 使用 uvicorn 命令启动
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "agentos.webui.app:app",
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--log-level",
            "warning",  # 后台运行时减少日志
        ]

        # 打开日志文件
        log_fd = open(self.log_file, "a", encoding="utf-8")

        # 启动进程，传递环境变量
        process = subprocess.Popen(
            cmd,
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            env=env,  # 传递环境变量
            start_new_session=True,  # 创建新会话，避免被父进程杀死
        )

        # 保存 PID
        self.pid_file.write_text(str(process.pid))

        # 等待一小段时间确认启动
        time.sleep(1)

        # 验证进程是否仍在运行
        if process.poll() is None:
            logger.info(f"WebUI started successfully at PID {process.pid}")
            logger.info(f"WebUI URL: http://{self.host}:{self.port}")
            logger.info(f"WebUI logs: {self.log_file}")
        else:
            raise RuntimeError("WebUI process exited immediately")

    def _start_foreground(self):
        """前台启动 WebUI"""
        import uvicorn

        uvicorn.run(
            "agentos.webui.app:app",
            host=self.host,
            port=self.port,
            log_level="info",
        )

    def stop(self) -> bool:
        """
        停止 WebUI 服务

        Returns:
            是否成功停止
        """
        is_running, pid = self.is_running()

        if not is_running:
            logger.info("WebUI is not running")
            return True

        try:
            logger.info(f"Stopping WebUI at PID {pid}")

            # 终止进程 (最多等待 5 秒)
            terminate_process(pid, timeout=5.0)

            # 清理 PID 文件
            self.pid_file.unlink(missing_ok=True)

            logger.info("WebUI stopped successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to stop WebUI: {e}", exc_info=True)
            return False

    def restart(self) -> bool:
        """
        重启 WebUI 服务

        Returns:
            是否成功重启
        """
        self.stop()
        time.sleep(1)
        return self.start()

    def status(self) -> dict:
        """
        获取 WebUI 状态

        Returns:
            状态信息字典
        """
        is_running, pid = self.is_running()

        status = {
            "running": is_running,
            "pid": pid,
            "host": self.host,
            "port": self.port,
            "url": f"http://{self.host}:{self.port}" if is_running else None,
            "log_file": str(self.log_file) if self.log_file.exists() else None,
        }

        return status


def auto_start_webui(host: str = "127.0.0.1", port: int = 8080) -> bool:
    """
    自动启动 WebUI (如果Not Running)

    Args:
        host: 绑定主机
        port: 绑定端口

    Returns:
        是否成功启动或已在运行
    """
    try:
        daemon = WebUIDaemon(host=host, port=port)

        is_running, pid = daemon.is_running()

        if is_running:
            logger.debug(f"WebUI already running at PID {pid}")
            return True

        # 启动
        return daemon.start(background=True)

    except Exception as e:
        logger.debug(f"Failed to auto-start WebUI: {e}")
        return False
