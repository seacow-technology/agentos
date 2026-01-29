"""Container Client - 容器引擎适配层

封装 Docker/Podman 操作，隔离 subprocess 使用。
这是系统边界：允许调用外部容器引擎。
"""

from pathlib import Path
from typing import Optional, Literal, Tuple
from enum import Enum
import subprocess


class ContainerEngine(Enum):
    """支持的容器引擎"""
    DOCKER = "docker"
    PODMAN = "podman"
    NONE = "none"


class ContainerClient:
    """容器引擎客户端"""
    
    def __init__(self, engine: ContainerEngine):
        """
        初始化容器客户端
        
        Args:
            engine: 容器引擎类型
        """
        self.engine = engine
    
    def check_available(self) -> bool:
        """检查引擎是否可用"""
        if self.engine == ContainerEngine.NONE:
            return False
        
        try:
            result = subprocess.run(
                [self.engine.value, "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def create_container(
        self,
        name: str,
        image: str,
        volumes: dict[str, dict],
        working_dir: str,
        auto_remove: bool = True
    ) -> str:
        """
        创建容器
        
        Args:
            name: 容器名称
            image: 镜像名称
            volumes: 卷挂载 {host_path: {'bind': container_path, 'mode': 'ro'}}
            working_dir: 工作目录
            auto_remove: 退出后自动删除
        
        Returns:
            容器 ID
        
        Raises:
            RuntimeError: 创建失败
        """
        cmd = [
            self.engine.value,
            "run",
            "-d",  # Detached
            "--name", name,
            "-w", working_dir
        ]
        
        # 添加卷挂载
        for host_path, mount_info in volumes.items():
            bind_path = mount_info['bind']
            mode = mount_info.get('mode', 'rw')
            cmd.extend(["-v", f"{host_path}:{bind_path}:{mode}"])
        
        if auto_remove:
            cmd.append("--rm")

        # Keep container running (跨平台兼容)
        import os
        cmd.extend([image, "tail", "-f", os.devnull])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Container creation failed: {result.stderr}")
        
        return result.stdout.strip()
    
    def exec_command(
        self,
        container_id: str,
        command: list[str],
        timeout: Optional[int] = None
    ) -> Tuple[int, str, str]:
        """
        在容器中执行命令
        
        Args:
            container_id: 容器 ID
            command: 命令列表
            timeout: 超时时间（秒）
        
        Returns:
            (returncode, stdout, stderr)
        """
        cmd = [self.engine.value, "exec", container_id] + command
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 124, "", "Command timed out"
        except Exception as e:
            return 1, "", str(e)
    
    def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """
        停止容器
        
        Args:
            container_id: 容器 ID
            timeout: 超时时间（秒）
        
        Returns:
            是否成功
        """
        try:
            result = subprocess.run(
                [self.engine.value, "stop", container_id],
                capture_output=True,
                timeout=timeout
            )
            return result.returncode == 0
        except Exception:
            return False


class ContainerClientFactory:
    """容器客户端工厂"""
    
    @staticmethod
    def detect_engine(prefer: Optional[str] = None) -> ContainerEngine:
        """
        检测可用的容器引擎
        
        Args:
            prefer: 首选引擎 ("docker" 或 "podman")
        
        Returns:
            可用的引擎类型
        """
        if prefer:
            client = ContainerClient(ContainerEngine(prefer))
            if client.check_available():
                return ContainerEngine(prefer)
        
        # Try docker first
        client = ContainerClient(ContainerEngine.DOCKER)
        if client.check_available():
            return ContainerEngine.DOCKER
        
        # Try podman
        client = ContainerClient(ContainerEngine.PODMAN)
        if client.check_available():
            return ContainerEngine.PODMAN
        
        return ContainerEngine.NONE
    
    @classmethod
    def get_client(cls, prefer_engine: Optional[str] = None) -> ContainerClient:
        """
        获取容器客户端
        
        Args:
            prefer_engine: 首选引擎
        
        Returns:
            容器客户端实例
        """
        engine = cls.detect_engine(prefer_engine)
        return ContainerClient(engine)
