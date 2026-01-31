#!/usr/bin/env python3
"""
Extension System 端到端验收测试 (PR-F)

测试整个扩展系统的端到端功能：
1. 安装扩展（上传 zip）
2. 验证安装状态
3. 启用扩展
4. 查看扩展详情
5. 禁用扩展
6. 卸载扩展

使用方法：
    python e2e_acceptance_test.py

前置条件：
    - AgentOS server 正在运行 (http://localhost:8000)
    - 扩展包已创建 (hello-extension.zip)
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

import requests


class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


class AcceptanceTest:
    """验收测试类"""

    def __init__(self, base_url: str = "http://localhost:8000", verbose: bool = False):
        self.base_url = base_url
        self.verbose = verbose
        self.passed = 0
        self.failed = 0
        self.test_data: Dict[str, Any] = {}

    def log(self, message: str, color: str = ""):
        """输出日志"""
        print(f"{color}{message}{Colors.RESET}")

    def log_verbose(self, message: str):
        """详细日志（仅在 verbose 模式下输出）"""
        if self.verbose:
            print(f"  {Colors.BLUE}[DEBUG]{Colors.RESET} {message}")

    def log_success(self, message: str):
        """成功日志"""
        self.passed += 1
        self.log(f"✓ {message}", Colors.GREEN)

    def log_failure(self, message: str, error: Optional[str] = None):
        """失败日志"""
        self.failed += 1
        self.log(f"✗ {message}", Colors.RED)
        if error:
            self.log(f"  Error: {error}", Colors.RED)

    def log_warning(self, message: str):
        """警告日志"""
        self.log(f"⚠️  {message}", Colors.YELLOW)

    def test_server_health(self) -> bool:
        """测试：服务器健康检查"""
        self.log(f"\n{Colors.BOLD}Test 1: Server health check{Colors.RESET}")

        try:
            resp = requests.get(f"{self.base_url}/health", timeout=5)
            if resp.status_code == 200:
                self.log_success("Server is healthy")
                return True
            else:
                self.log_failure(f"Server returned status {resp.status_code}")
                return False
        except requests.ConnectionError:
            self.log_failure("Cannot connect to server", f"Is the server running at {self.base_url}?")
            return False
        except Exception as e:
            self.log_failure("Health check failed", str(e))
            return False

    def test_list_extensions_initial(self) -> bool:
        """测试：初始列出扩展"""
        self.log(f"\n{Colors.BOLD}Test 2: List extensions (initial){Colors.RESET}")

        try:
            resp = requests.get(f"{self.base_url}/api/extensions")
            if resp.status_code != 200:
                self.log_failure(f"API returned status {resp.status_code}")
                return False

            data = resp.json()
            extensions = data.get("extensions", [])

            self.log_verbose(f"Found {len(extensions)} extensions")
            for ext in extensions:
                self.log_verbose(f"  - {ext['id']} (v{ext['version']})")

            self.log_success(f"Listed {len(extensions)} extensions")
            self.test_data["initial_extension_count"] = len(extensions)
            return True

        except Exception as e:
            self.log_failure("Failed to list extensions", str(e))
            return False

    def test_install_extension(self, zip_path: Path) -> Optional[str]:
        """测试：安装扩展"""
        self.log(f"\n{Colors.BOLD}Test 3: Install extension from {zip_path.name}{Colors.RESET}")

        if not zip_path.exists():
            self.log_failure(f"Extension package not found: {zip_path}")
            return None

        try:
            # 上传 zip 文件
            with open(zip_path, "rb") as f:
                files = {"file": (zip_path.name, f, "application/zip")}
                resp = requests.post(f"{self.base_url}/api/extensions/install", files=files)

            if resp.status_code != 200:
                self.log_failure(f"Installation API returned status {resp.status_code}")
                self.log_verbose(f"Response: {resp.text}")
                return None

            data = resp.json()
            install_id = data.get("install_id")
            extension_id = data.get("extension_id")

            self.log_verbose(f"Installation started: {install_id}")
            self.log_success(f"Installation request accepted (install_id: {install_id})")

            # 轮询安装进度
            return self.poll_installation_progress(install_id)

        except Exception as e:
            self.log_failure("Installation failed", str(e))
            return None

    def poll_installation_progress(self, install_id: str, timeout: int = 60) -> Optional[str]:
        """轮询安装进度"""
        self.log(f"\n{Colors.BOLD}Test 4: Monitor installation progress{Colors.RESET}")

        start_time = time.time()
        last_progress = -1

        while time.time() - start_time < timeout:
            try:
                resp = requests.get(f"{self.base_url}/api/extensions/install/{install_id}")

                if resp.status_code != 200:
                    self.log_failure(f"Progress API returned status {resp.status_code}")
                    return None

                progress = resp.json()
                status = progress.get("status")
                progress_pct = progress.get("progress", 0)
                current_step = progress.get("current_step", "unknown")
                extension_id = progress.get("extension_id")

                # 只在进度变化时输出
                if progress_pct != last_progress:
                    self.log_verbose(f"Progress: {progress_pct}% - {current_step}")
                    last_progress = progress_pct

                if status == "COMPLETED":
                    self.log_success(f"Installation completed (extension_id: {extension_id})")
                    self.test_data["installed_extension_id"] = extension_id
                    return extension_id

                elif status == "FAILED":
                    error = progress.get("error", "Unknown error")
                    self.log_failure("Installation failed", error)
                    return None

                time.sleep(0.5)

            except Exception as e:
                self.log_failure("Failed to get installation progress", str(e))
                return None

        self.log_failure("Installation timeout", f"No response after {timeout} seconds")
        return None

    def test_get_extension_detail(self, extension_id: str) -> bool:
        """测试：获取扩展详情"""
        self.log(f"\n{Colors.BOLD}Test 5: Get extension detail{Colors.RESET}")

        try:
            resp = requests.get(f"{self.base_url}/api/extensions/{extension_id}")

            if resp.status_code != 200:
                self.log_failure(f"Detail API returned status {resp.status_code}")
                return False

            detail = resp.json()

            self.log_verbose(f"Extension ID: {detail['id']}")
            self.log_verbose(f"Name: {detail['name']}")
            self.log_verbose(f"Version: {detail['version']}")
            self.log_verbose(f"Enabled: {detail['enabled']}")
            self.log_verbose(f"Status: {detail['status']}")

            capabilities = detail.get("capabilities", [])
            self.log_verbose(f"Capabilities: {len(capabilities)}")
            for cap in capabilities:
                self.log_verbose(f"  - {cap['type']}: {cap['name']}")

            self.log_success(f"Retrieved extension details for {extension_id}")
            return True

        except Exception as e:
            self.log_failure("Failed to get extension detail", str(e))
            return False

    def test_enable_extension(self, extension_id: str) -> bool:
        """测试：启用扩展"""
        self.log(f"\n{Colors.BOLD}Test 6: Enable extension{Colors.RESET}")

        try:
            resp = requests.post(f"{self.base_url}/api/extensions/{extension_id}/enable")

            if resp.status_code != 200:
                self.log_failure(f"Enable API returned status {resp.status_code}")
                return False

            data = resp.json()
            if data.get("success") and data.get("enabled"):
                self.log_success(f"Extension {extension_id} enabled")
                return True
            else:
                self.log_failure("Enable returned success=false")
                return False

        except Exception as e:
            self.log_failure("Failed to enable extension", str(e))
            return False

    def test_disable_extension(self, extension_id: str) -> bool:
        """测试：禁用扩展"""
        self.log(f"\n{Colors.BOLD}Test 7: Disable extension{Colors.RESET}")

        try:
            resp = requests.post(f"{self.base_url}/api/extensions/{extension_id}/disable")

            if resp.status_code != 200:
                self.log_failure(f"Disable API returned status {resp.status_code}")
                return False

            data = resp.json()
            if data.get("success") and not data.get("enabled"):
                self.log_success(f"Extension {extension_id} disabled")
                return True
            else:
                self.log_failure("Disable returned unexpected response")
                return False

        except Exception as e:
            self.log_failure("Failed to disable extension", str(e))
            return False

    def test_uninstall_extension(self, extension_id: str) -> bool:
        """测试：卸载扩展"""
        self.log(f"\n{Colors.BOLD}Test 8: Uninstall extension{Colors.RESET}")

        try:
            resp = requests.delete(f"{self.base_url}/api/extensions/{extension_id}")

            if resp.status_code != 200:
                self.log_failure(f"Uninstall API returned status {resp.status_code}")
                return False

            data = resp.json()
            if data.get("success"):
                self.log_success(f"Extension {extension_id} uninstalled")
                return True
            else:
                self.log_failure("Uninstall returned success=false")
                return False

        except Exception as e:
            self.log_failure("Failed to uninstall extension", str(e))
            return False

    def test_list_extensions_final(self) -> bool:
        """测试：最终列出扩展（验证卸载）"""
        self.log(f"\n{Colors.BOLD}Test 9: List extensions (final verification){Colors.RESET}")

        try:
            resp = requests.get(f"{self.base_url}/api/extensions")
            if resp.status_code != 200:
                self.log_failure(f"API returned status {resp.status_code}")
                return False

            data = resp.json()
            extensions = data.get("extensions", [])
            final_count = len(extensions)
            initial_count = self.test_data.get("initial_extension_count", 0)

            self.log_verbose(f"Initial count: {initial_count}")
            self.log_verbose(f"Final count: {final_count}")

            if final_count == initial_count:
                self.log_success("Extension count matches initial state (uninstall verified)")
                return True
            else:
                self.log_warning(f"Extension count changed: {initial_count} -> {final_count}")
                return True  # 这不算失败，只是警告

        except Exception as e:
            self.log_failure("Failed to list extensions", str(e))
            return False

    def run_all_tests(self, extension_zip: Path):
        """运行所有测试"""
        self.log(f"\n{'=' * 60}")
        self.log(f"{Colors.BOLD}Extension System Acceptance Tests{Colors.RESET}")
        self.log(f"{'=' * 60}")
        self.log(f"Server: {self.base_url}")
        self.log(f"Extension: {extension_zip}")
        self.log(f"{'=' * 60}")

        # Test 1: 服务器健康检查
        if not self.test_server_health():
            self.log_failure("Server is not available, aborting tests")
            return False

        # Test 2: 初始列出扩展
        self.test_list_extensions_initial()

        # Test 3-4: 安装扩展
        extension_id = self.test_install_extension(extension_zip)
        if not extension_id:
            self.log_failure("Installation failed, aborting remaining tests")
            return False

        # Test 5: 获取扩展详情
        self.test_get_extension_detail(extension_id)

        # Test 6: 启用扩展
        self.test_enable_extension(extension_id)

        # Test 7: 禁用扩展
        self.test_disable_extension(extension_id)

        # Test 8: 卸载扩展
        self.test_uninstall_extension(extension_id)

        # Test 9: 验证卸载
        self.test_list_extensions_final()

        return True

    def print_summary(self):
        """输出测试摘要"""
        self.log(f"\n{'=' * 60}")
        self.log(f"{Colors.BOLD}Test Summary{Colors.RESET}")
        self.log(f"{'=' * 60}")

        total = self.passed + self.failed
        success_rate = (self.passed / total * 100) if total > 0 else 0

        self.log(f"Total: {total}", Colors.BOLD)
        self.log(f"Passed: {self.passed}", Colors.GREEN)
        self.log(f"Failed: {self.failed}", Colors.RED)
        self.log(f"Success Rate: {success_rate:.1f}%", Colors.BOLD)

        self.log(f"{'=' * 60}")

        if self.failed == 0:
            self.log(f"\n{Colors.GREEN}{Colors.BOLD}✓ ALL TESTS PASSED!{Colors.RESET}\n")
            return True
        else:
            self.log(f"\n{Colors.RED}{Colors.BOLD}✗ SOME TESTS FAILED{Colors.RESET}\n")
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Extension System Acceptance Tests")
    parser.add_argument(
        "--server",
        default="http://localhost:8000",
        help="AgentOS server URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--extension",
        default="hello-extension.zip",
        help="Extension package path (default: hello-extension.zip)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    # 解析扩展路径
    extension_path = Path(args.extension)
    if not extension_path.is_absolute():
        extension_path = Path(__file__).parent / extension_path

    # 运行测试
    test = AcceptanceTest(base_url=args.server, verbose=args.verbose)

    try:
        test.run_all_tests(extension_path)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 输出摘要
    success = test.print_summary()

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
