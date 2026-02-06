"""
Local AI Provider Detection and Installation

检测和安装本地 AI Provider:
- Ollama
- LM Studio
- llama.cpp
"""

import logging
import os
import platform
import shutil
import subprocess
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class ProviderChecker:
    """本地 AI Provider 检测器"""

    def check_ollama(self) -> Tuple[bool, Optional[str]]:
        """
        检测 Ollama 是否Available

        Returns:
            (是否Available, 状态信息)
            - True, "v0.15.2 (Running)" - 服务正在运行
            - True, "Installed, service not running" - 已安装但服务未启动
            - False, "Command not found" - 未安装
        """
        # 方法 1: 检查命令是否存在
        if shutil.which("ollama") is None:
            return False, "Command not found"

        # 方法 2: 检查服务是否运行（尝试连接 API）
        try:
            response = requests.get("http://localhost:11434/api/version", timeout=2)
            if response.status_code == 200:
                version = response.json().get("version", "unknown")
                return True, f"v{version} (Running)"
        except Exception:
            pass

        # 方法 3: 命令存在但服务Not Running
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Ollama 已安装但服务未启动
                return True, "Installed, service not running"
        except Exception as e:
            return False, str(e)

        return False, "Unknown error"

    def check_lm_studio(self) -> Tuple[bool, Optional[str]]:
        """
        检测 LM Studio 是否运行

        Returns:
            (是否运行, 状态信息)
        """
        # 尝试连接 LM Studio API (默认端口 1234)
        try:
            response = requests.get("http://localhost:1234/v1/models", timeout=2)
            if response.status_code == 200:
                models = response.json().get("data", [])
                return True, f"Running ({len(models)} models)"
        except Exception:
            pass

        # 检查进程是否存在
        try:
            result = subprocess.run(
                ["pgrep", "-i", "lm.studio"] if platform.system() != "Windows"
                else ["tasklist", "/FI", "IMAGENAME eq LM Studio.exe"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return True, "Process running"
        except Exception:
            pass

        return False, "Not running"

    def check_llama_cpp(self) -> Tuple[bool, Optional[str]]:
        """
        检测 llama.cpp 是否Available

        Returns:
            (是否Available, 状态信息)
        """
        # 检查 llama-server 命令
        if shutil.which("llama-server"):
            try:
                result = subprocess.run(
                    ["llama-server", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return True, "llama-server available"
            except Exception:
                pass

        # 检查 llama-cli 命令
        if shutil.which("llama-cli"):
            return True, "llama-cli available"

        # 检查旧版本命令名
        if shutil.which("llama"):
            return True, "llama available"

        return False, "Command not found"

    def install_ollama(self) -> bool:
        """
        安装 Ollama (跨平台支持)

        Returns:
            是否安装成功
        """
        system = platform.system()

        try:
            if system in ("Linux", "Darwin"):  # Linux or macOS
                logger.info("使用官方脚本安装 Ollama...")

                # 下载并执行安装脚本
                result = subprocess.run(
                    ["curl", "-fsSL", "https://ollama.com/install.sh"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode != 0:
                    logger.error(f"下载安装脚本失败: {result.stderr}")
                    return False

                # 执行安装脚本
                install_result = subprocess.run(
                    ["sh", "-c", result.stdout],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 分钟超时
                )

                if install_result.returncode == 0:
                    logger.info("Ollama 安装成功")

                    # 尝试启动 Ollama 服务（使用跨平台方法）
                    try:
                        self._start_background_service(["ollama", "serve"])
                        logger.info("Ollama 服务已启动")
                    except Exception as e:
                        logger.warning(f"无法自动启动 Ollama 服务: {e}")

                    return True
                else:
                    logger.error(f"Ollama 安装失败: {install_result.stderr}")
                    return False

            elif system == "Windows":
                logger.info("尝试使用 winget 安装 Ollama...")

                # 检查 winget 是否Available
                if shutil.which("winget") is None:
                    logger.warning("winget 不Available，请手动安装")
                    logger.info("下载地址: https://ollama.com/download/windows")
                    return False

                # 使用 winget 安装
                install_result = subprocess.run(
                    ["winget", "install", "--id", "Ollama.Ollama", "--silent", "--accept-source-agreements"],
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                if install_result.returncode == 0:
                    logger.info("Ollama 安装成功")
                    return True
                else:
                    logger.error(f"Ollama 安装失败: {install_result.stderr}")
                    logger.info("请手动下载安装: https://ollama.com/download/windows")
                    return False

            else:
                logger.error(f"不支持的操作系统: {system}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("安装超时")
            return False
        except Exception as e:
            logger.error(f"安装失败: {e}", exc_info=True)
            return False

    def _start_background_service(self, command: list) -> subprocess.Popen:
        """
        跨平台启动后台服务

        Args:
            command: 要执行的命令列表

        Returns:
            Popen 进程对象
        """
        system = platform.system()

        # 准备启动参数
        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }

        # Windows 需要特殊处理
        if system == "Windows":
            # Windows 使用 creationflags
            # CREATE_NEW_PROCESS_GROUP = 0x00000200
            # DETACHED_PROCESS = 0x00000008
            try:
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            except AttributeError:
                # 如果常量不Available（旧版本 Python），使用数值
                kwargs["creationflags"] = 0x00000200 | 0x00000008
        else:
            # Unix-like 系统使用 start_new_session
            kwargs["start_new_session"] = True

        return subprocess.Popen(command, **kwargs)

    def start_ollama(self, port: int = 11434) -> bool:
        """
        启动 Ollama 服务

        Args:
            port: Ollama 服务端口

        Returns:
            是否启动成功
        """
        try:
            # 检查是否已经运行
            endpoint = f"http://localhost:{port}"
            try:
                response = requests.get(f"{endpoint}/api/version", timeout=2)
                if response.status_code == 200:
                    logger.info(f"Ollama 服务已在运行 ({endpoint})")
                    return True
            except Exception:
                pass

            # 启动服务
            env = os.environ.copy()
            env["OLLAMA_HOST"] = f"127.0.0.1:{port}"

            # 使用跨平台的后台服务启动方法
            system = platform.system()
            kwargs = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "env": env
            }

            if system == "Windows":
                # Windows 使用 creationflags
                try:
                    kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                except AttributeError:
                    # 如果常量不Available，使用数值
                    kwargs["creationflags"] = 0x00000200 | 0x00000008
            else:
                # Unix-like 系统使用 start_new_session
                kwargs["start_new_session"] = True

            subprocess.Popen(["ollama", "serve"], **kwargs)

            # 等待服务启动
            import time
            for i in range(15):  # 最多等待 15 秒
                time.sleep(1)
                try:
                    response = requests.get(f"{endpoint}/api/version", timeout=1)
                    if response.status_code == 200:
                        logger.info(f"Ollama 服务启动成功 ({endpoint})")
                        return True
                except Exception:
                    continue

            logger.warning("Ollama 服务启动超时")
            return False

        except Exception as e:
            logger.error(f"启动 Ollama 失败: {e}", exc_info=True)
            return False

    def verify_ollama_connection(self, port: int = 11434) -> Tuple[bool, Optional[str]]:
        """
        验证 Ollama 连接并获取模型列表

        Args:
            port: Ollama 服务端口

        Returns:
            (是否成功, 错误信息或模型数量)
        """
        try:
            endpoint = f"http://localhost:{port}"
            response = requests.get(f"{endpoint}/api/tags", timeout=5)

            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                model_count = len(models)

                if model_count == 0:
                    return True, "连接成功，但未安装模型"
                else:
                    return True, f"连接成功，发现 {model_count} 个模型"
            else:
                return False, f"API 返回错误: {response.status_code}"

        except Exception as e:
            return False, f"连接失败: {str(e)}"

    def get_ollama_models(self, port: int = 11434) -> list:
        """
        获取已安装的 Ollama 模型列表

        Args:
            port: Ollama 服务端口

        Returns:
            模型列表
        """
        try:
            endpoint = f"http://localhost:{port}"
            response = requests.get(f"{endpoint}/api/tags", timeout=5)

            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return [model.get("name", "") for model in models]
            else:
                return []

        except Exception:
            return []

    def pull_ollama_model(self, model_name: str, port: int = 11434) -> bool:
        """
        下载 Ollama 模型

        Args:
            model_name: 模型名称（如 llama3.2, qwen2.5）
            port: Ollama 服务端口

        Returns:
            是否下载成功
        """
        try:
            logger.info(f"开始下载模型: {model_name}")

            # 使用 ollama pull 命令下载
            env = os.environ.copy()
            env["OLLAMA_HOST"] = f"127.0.0.1:{port}"

            process = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env
            )

            # 读取输出（实时显示进度）
            for line in process.stdout:
                line = line.strip()
                if line:
                    logger.info(line)

            process.wait()

            if process.returncode == 0:
                logger.info(f"模型 {model_name} 下载成功")
                return True
            else:
                logger.error(f"模型 {model_name} 下载失败")
                return False

        except Exception as e:
            logger.error(f"下载模型失败: {e}", exc_info=True)
            return False

    def get_provider_status(self) -> dict:
        """
        获取所有 Provider 的状态

        Returns:
            状态字典
        """
        ollama_available, ollama_info = self.check_ollama()
        lm_studio_available, lm_studio_info = self.check_lm_studio()
        llama_cpp_available, llama_cpp_info = self.check_llama_cpp()

        return {
            "ollama": {
                "available": ollama_available,
                "info": ollama_info,
                "name": "Ollama"
            },
            "lm_studio": {
                "available": lm_studio_available,
                "info": lm_studio_info,
                "name": "LM Studio"
            },
            "llama_cpp": {
                "available": llama_cpp_available,
                "info": llama_cpp_info,
                "name": "llama.cpp"
            }
        }

    def has_any_provider(self) -> bool:
        """
        检查是否有任何Available的 Provider

        Returns:
            是否有Available的 Provider
        """
        status = self.get_provider_status()
        return any(p["available"] for p in status.values())
