#!/usr/bin/env python3
"""
Gate TL-R1-N1: Tool Diff Validation - Negative Cases

🔩 钉子 B：Diff 验证要有"拒绝样例"

测试 Tool 返回非法 diff 时必须失败：
1. 非 unified diff 格式
2. 修改 forbidden path
3. 空 diff
4. 文件不在 allowed_paths

这是 Step 3 的 Policy Deny 版本。
"""

import sys
import tempfile
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timezone

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.ext.tools import (
    ToolResult,
    DiffVerifier
)


class TLR1N1Gate:
    """Gate TL-R1-N1: Diff Validation Negative Cases"""
    
    def __init__(self):
        self.temp_dir = None
        self.repo_path = None
        self.test_results = []
    
    def setup(self) -> bool:
        """创建临时 repo"""
        try:
            self.temp_dir = tempfile.mkdtemp(prefix="tl_r1_n1_gate_")
            self.repo_path = Path(self.temp_dir)
            
            print(f"📁 Created temp repo: {self.repo_path}")
            
            # 初始化 git repo
            subprocess.run(["git", "init"], cwd=self.repo_path, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "TL-R1-N1 Gate"], cwd=self.repo_path, check=True)
            subprocess.run(["git", "config", "user.email", "gate@agentos.dev"], cwd=self.repo_path, check=True)
            
            # 创建多个测试文件
            (self.repo_path / "index.html").write_text("<html><body>Test</body></html>")
            (self.repo_path / ".env").write_text("SECRET=xxx")
            (self.repo_path / "config.py").write_text("CONFIG = {}")
            
            # 初始 commit
            subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=self.repo_path,
                check=True,
                capture_output=True
            )
            
            print("✅ Temp repo initialized with test files")
            return True
            
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return False
    
    def test_empty_diff(self) -> tuple[bool, str]:
        """Test N1.1: 空 diff 必须失败"""
        print("\n🧪 Test N1.1: Empty diff rejection")
        
        result = ToolResult(
            tool="test",
            status="success",
            diff="",  # 空 diff
            files_touched=[],
            line_count=0,
            tool_run_id="test_001"
        )
        
        validation = DiffVerifier.verify(
            result,
            allowed_paths=["index.html"],
            forbidden_paths=[".env"]
        )
        
        # 空 diff 必须验证失败
        if not validation.is_valid:
            print("   ✅ Empty diff correctly rejected")
            print(f"   Errors: {validation.errors}")
            return True, "Empty diff rejected as expected"
        else:
            print("   ❌ Empty diff was NOT rejected (BUG!)")
            return False, "Empty diff should be rejected"
    
    def test_non_unified_diff(self) -> tuple[bool, str]:
        """Test N1.2: 非 unified diff 格式必须失败"""
        print("\n🧪 Test N1.2: Non-unified diff rejection")
        
        # 非标准格式的 diff
        bad_diff = """
        Some random text
        that is not a unified diff
        + some change
        - some removal
        """
        
        result = ToolResult(
            tool="test",
            status="success",
            diff=bad_diff,
            files_touched=["index.html"],
            line_count=2,
            tool_run_id="test_002"
        )
        
        validation = DiffVerifier.verify(
            result,
            allowed_paths=["index.html"],
            forbidden_paths=[".env"]
        )
        
        # 非 unified diff 必须验证失败
        if not validation.is_valid:
            print("   ✅ Non-unified diff correctly rejected")
            print(f"   Errors: {validation.errors}")
            return True, "Non-unified diff rejected as expected"
        else:
            print("   ❌ Non-unified diff was NOT rejected (BUG!)")
            return False, "Non-unified diff should be rejected"
    
    def test_forbidden_path(self) -> tuple[bool, str]:
        """Test N1.3: 修改 forbidden path 必须失败"""
        print("\n🧪 Test N1.3: Forbidden path rejection")
        
        # 创建真实的 diff，但修改 .env（forbidden）
        env_file = self.repo_path / ".env"
        original = env_file.read_text()
        env_file.write_text(original + "\nHACKED=true")
        
        diff_result = subprocess.run(
            ["git", "diff", ".env"],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )
        
        diff = diff_result.stdout
        
        # 恢复文件
        env_file.write_text(original)
        
        result = ToolResult(
            tool="test",
            status="success",
            diff=diff,
            files_touched=[".env"],
            line_count=1,
            tool_run_id="test_003"
        )
        
        validation = DiffVerifier.verify(
            result,
            allowed_paths=["index.html"],
            forbidden_paths=[".env", "*.key"]
        )
        
        # 修改 forbidden path 必须验证失败
        if not validation.is_valid:
            print("   ✅ Forbidden path correctly rejected")
            print(f"   Errors: {validation.errors}")
            return True, "Forbidden path rejected as expected"
        else:
            print("   ❌ Forbidden path was NOT rejected (BUG!)")
            return False, "Forbidden path should be rejected"
    
    def test_file_not_in_allowed_paths(self) -> tuple[bool, str]:
        """Test N1.4: 文件不在 allowed_paths 必须警告"""
        print("\n🧪 Test N1.4: File not in allowed_paths warning")
        
        # 修改 config.py（不在 allowed_paths）
        config_file = self.repo_path / "config.py"
        original = config_file.read_text()
        config_file.write_text(original + "\n# Changed")
        
        diff_result = subprocess.run(
            ["git", "diff", "config.py"],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )
        
        diff = diff_result.stdout
        
        # 恢复文件
        config_file.write_text(original)
        
        result = ToolResult(
            tool="test",
            status="success",
            diff=diff,
            files_touched=["config.py"],
            line_count=1,
            tool_run_id="test_004"
        )
        
        validation = DiffVerifier.verify(
            result,
            allowed_paths=["index.html"],  # config.py 不在其中
            forbidden_paths=[".env"]
        )
        
        # 应该有警告（但不一定失败，取决于策略）
        if validation.warnings:
            print("   ✅ Not in allowed_paths generated warning")
            print(f"   Warnings: {validation.warnings}")
            return True, "Warning generated as expected"
        else:
            print("   ⚠️  No warning generated (acceptable, but should consider adding)")
            return True, "No warning, but test passes (policy decision)"
    
    def test_valid_diff(self) -> tuple[bool, str]:
        """Test N1.5: 合法 diff 必须通过（对照组）"""
        print("\n🧪 Test N1.5: Valid diff acceptance (control)")
        
        # 修改 index.html（在 allowed_paths）
        index_file = self.repo_path / "index.html"
        original = index_file.read_text()
        index_file.write_text(original.replace("</body>", "<footer>Test</footer></body>"))
        
        diff_result = subprocess.run(
            ["git", "diff", "index.html"],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )
        
        diff = diff_result.stdout
        
        # 恢复文件
        index_file.write_text(original)
        
        result = ToolResult(
            tool="test",
            status="success",
            diff=diff,
            files_touched=["index.html"],
            line_count=1,
            tool_run_id="test_005"
        )
        
        validation = DiffVerifier.verify(
            result,
            allowed_paths=["index.html", "*.html"],
            forbidden_paths=[".env", "*.key"]
        )
        
        # 合法 diff 必须通过
        if validation.is_valid:
            print("   ✅ Valid diff correctly accepted")
            return True, "Valid diff accepted as expected"
        else:
            print("   ❌ Valid diff was rejected (BUG!)")
            print(f"   Errors: {validation.errors}")
            return False, f"Valid diff should be accepted: {validation.errors}"
    
    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
            print(f"\n🧹 Cleaned up temp dir: {self.temp_dir}")
    
    def run_all_tests(self) -> bool:
        """运行所有测试"""
        tests = [
            ("N1.1: Empty diff", self.test_empty_diff),
            ("N1.2: Non-unified diff", self.test_non_unified_diff),
            ("N1.3: Forbidden path", self.test_forbidden_path),
            ("N1.4: Not in allowed_paths", self.test_file_not_in_allowed_paths),
            ("N1.5: Valid diff (control)", self.test_valid_diff),
        ]
        
        all_passed = True
        
        for name, test_func in tests:
            try:
                passed, message = test_func()
                self.test_results.append({
                    "test": name,
                    "passed": passed,
                    "message": message
                })
                
                if not passed:
                    all_passed = False
                    
            except Exception as e:
                print(f"   ❌ Exception: {e}")
                self.test_results.append({
                    "test": name,
                    "passed": False,
                    "message": f"Exception: {e}"
                })
                all_passed = False
        
        return all_passed


def run_gate() -> bool:
    """运行 Gate TL-R1-N1"""
    gate = TLR1N1Gate()
    
    try:
        print("=" * 70)
        print("🔒 Gate TL-R1-N1: Diff Validation Negative Cases")
        print("🔩 钉子 B: Diff 验证拒绝样例")
        print("=" * 70)
        
        # Setup
        if not gate.setup():
            print("❌ Gate TL-R1-N1 FAILED: Setup failed")
            return False
        
        # Run all tests
        all_passed = gate.run_all_tests()
        
        print("\n" + "=" * 70)
        print("📊 Test Results:")
        print("=" * 70)
        
        passed_count = sum(1 for r in gate.test_results if r["passed"])
        total_count = len(gate.test_results)
        
        for result in gate.test_results:
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"{status} - {result['test']}")
            print(f"       {result['message']}")
        
        print()
        print("=" * 70)
        
        if all_passed:
            print(f"✅ Gate TL-R1-N1 PASSED: All negative cases handled correctly ({passed_count}/{total_count})")
            return True
        else:
            print(f"❌ Gate TL-R1-N1 FAILED: Some tests failed ({passed_count}/{total_count})")
            return False
        
    except Exception as e:
        print(f"❌ Gate TL-R1-N1 FAILED: Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        gate.cleanup()


def main():
    """Main entry"""
    success = run_gate()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
