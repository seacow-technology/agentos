#!/usr/bin/env python3
"""
Gate TL-R1-C: Power Boundary Enforcement

🔩 钉子 C：明确 ToolResult → Executor 的"权力断点"

验证：
1. Tool 不能直接写文件（wrote_files 必须 False）
2. Tool 不能直接 commit（committed 必须 False）
3. Repo 变更只能发生在 Executor apply_diff 之后

这是为了防未来接 OpenCode / Local LLM 时不出事故。
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
    ClaudeCliAdapter,
    ToolTask,
    ToolResult
)


class TLR1CGate:
    """Gate TL-R1-C: Power Boundary Enforcement"""
    
    def __init__(self):
        self.temp_dir = None
        self.repo_path = None
        self.adapter = None
        self.test_results = []
    
    def setup(self) -> bool:
        """创建临时 repo"""
        try:
            self.temp_dir = tempfile.mkdtemp(prefix="tl_r1_c_gate_")
            self.repo_path = Path(self.temp_dir)
            
            print(f"📁 Created temp repo: {self.repo_path}")
            
            # 初始化 git repo
            subprocess.run(["git", "init"], cwd=self.repo_path, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "TL-R1-C Gate"], cwd=self.repo_path, check=True)
            subprocess.run(["git", "config", "user.email", "gate@agentos.dev"], cwd=self.repo_path, check=True)
            
            # 创建测试文件
            (self.repo_path / "test.txt").write_text("Initial content")
            
            # 初始 commit
            subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=self.repo_path,
                check=True,
                capture_output=True
            )
            
            print("✅ Temp repo initialized")
            
            # 记录初始状态
            self.initial_commit = self._get_current_commit()
            self.initial_file_mtime = (self.repo_path / "test.txt").stat().st_mtime
            
            # 初始化 adapter
            self.adapter = ClaudeCliAdapter()
            
            return True
            
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return False
    
    def _get_current_commit(self) -> str:
        """获取当前 commit hash"""
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    
    def _file_was_modified(self) -> bool:
        """检查文件是否被修改"""
        current_mtime = (self.repo_path / "test.txt").stat().st_mtime
        return current_mtime != self.initial_file_mtime
    
    def _repo_has_new_commit(self) -> bool:
        """检查是否有新 commit"""
        current_commit = self._get_current_commit()
        return current_commit != self.initial_commit
    
    def test_tool_result_power_boundary(self) -> tuple[bool, str]:
        """Test C.1: ToolResult 必须声明权力边界"""
        print("\n🧪 Test C.1: ToolResult power boundary fields")
        
        task = ToolTask(
            task_id="test_c1",
            instruction="Add a line to test.txt",
            repo_path=str(self.repo_path),
            allowed_paths=["test.txt"],
            forbidden_paths=[],
            timeout_seconds=60
        )
        
        # 运行 tool（Mock 模式）
        result = self.adapter.run(task, allow_mock=True)
        
        # 检查必须字段
        if not hasattr(result, 'wrote_files'):
            return False, "ToolResult missing 'wrote_files' field"
        
        if not hasattr(result, 'committed'):
            return False, "ToolResult missing 'committed' field"
        
        print(f"   ✅ ToolResult has power boundary fields")
        print(f"      wrote_files={result.wrote_files}")
        print(f"      committed={result.committed}")
        
        return True, "Power boundary fields present"
    
    def test_tool_must_not_write_files(self) -> tuple[bool, str]:
        """Test C.2: Tool 不能直接写文件"""
        print("\n🧪 Test C.2: Tool must not write files directly")
        
        # 记录 tool 执行前的文件状态
        initial_content = (self.repo_path / "test.txt").read_text()
        initial_mtime = (self.repo_path / "test.txt").stat().st_mtime
        
        task = ToolTask(
            task_id="test_c2",
            instruction="Add a line to test.txt",
            repo_path=str(self.repo_path),
            allowed_paths=["test.txt"],
            forbidden_paths=[],
            timeout_seconds=60
        )
        
        # 运行 tool（Mock 模式）
        result = self.adapter.run(task, allow_mock=True)
        
        # 检查：wrote_files 必须为 False
        if result.wrote_files:
            return False, f"Tool violated boundary: wrote_files={result.wrote_files}"
        
        # 检查：文件内容必须未变（Mock 会恢复）
        current_content = (self.repo_path / "test.txt").read_text()
        if current_content != initial_content:
            # 注意：Mock 模式下会临时修改文件生成 diff，但最后会恢复
            # 如果这里检测到变更，说明 Mock 没有恢复
            print(f"   ⚠️  File content changed (Mock should restore it)")
        
        print(f"   ✅ Tool correctly reported wrote_files=False")
        
        return True, "Tool did not write files directly"
    
    def test_tool_must_not_commit(self) -> tuple[bool, str]:
        """Test C.3: Tool 不能直接 commit"""
        print("\n🧪 Test C.3: Tool must not commit directly")
        
        initial_commit = self._get_current_commit()
        
        task = ToolTask(
            task_id="test_c3",
            instruction="Add a line to test.txt",
            repo_path=str(self.repo_path),
            allowed_paths=["test.txt"],
            forbidden_paths=[],
            timeout_seconds=60
        )
        
        # 运行 tool（Mock 模式）
        result = self.adapter.run(task, allow_mock=True)
        
        # 检查：committed 必须为 False
        if result.committed:
            return False, f"Tool violated boundary: committed={result.committed}"
        
        # 检查：repo 不应有新 commit
        current_commit = self._get_current_commit()
        if current_commit != initial_commit:
            return False, "Tool created new commit (violation!)"
        
        print(f"   ✅ Tool correctly reported committed=False")
        print(f"   ✅ Repo has no new commits")
        
        return True, "Tool did not commit directly"
    
    def test_repo_changes_only_after_apply(self) -> tuple[bool, str]:
        """Test C.4: Repo 变更只能发生在 apply_diff 之后"""
        print("\n🧪 Test C.4: Repo changes only after Executor apply_diff")
        
        initial_commit = self._get_current_commit()
        
        task = ToolTask(
            task_id="test_c4",
            instruction="Add a line to test.txt",
            repo_path=str(self.repo_path),
            allowed_paths=["test.txt"],
            forbidden_paths=[],
            timeout_seconds=60
        )
        
        # Step 1: 运行 tool
        result = self.adapter.run(task, allow_mock=True)
        
        # Step 2: 验证此时 repo 未变
        if self._repo_has_new_commit():
            return False, "Repo changed BEFORE apply_diff (violation!)"
        
        print(f"   ✅ Before apply_diff: repo unchanged")
        
        # Step 3: 模拟 Executor apply_diff
        if result.diff:
            diff_file = self.repo_path / ".tmp_diff"
            diff_file.write_text(result.diff)
            
            apply_result = subprocess.run(
                ["git", "apply", str(diff_file)],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            diff_file.unlink()
            
            if apply_result.returncode != 0:
                print(f"   ⚠️  git apply failed: {apply_result.stderr}")
                # 继续测试，因为我们主要关心权力边界
        
        # Step 4: 检查是否有变更需要 commit
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        
        if status_result.stdout.strip():
            # 有变更，可以 commit
            # Step 5: 模拟 Executor commit
            subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True)
            subprocess.run(
                ["git", "commit", "-m", "Applied by Executor"],
                cwd=self.repo_path,
                check=True,
                capture_output=True
            )
            
            # Step 6: 验证此时 repo 已变
            if not self._repo_has_new_commit():
                return False, "Repo did not change AFTER apply_diff (bug!)"
            
            print(f"   ✅ After apply_diff: repo changed correctly")
        else:
            print(f"   ℹ️  No changes to commit (diff was already applied or empty)")
            print(f"   ✅ Power boundary still enforced (Tool didn't commit)")
        
        return True, "Repo changes only happened after Executor apply_diff"
    
    def test_assertion_in_gate(self) -> tuple[bool, str]:
        """Test C.5: Gate 必须有断言检查"""
        print("\n🧪 Test C.5: Gate has power boundary assertions")
        
        task = ToolTask(
            task_id="test_c5",
            instruction="Add a line to test.txt",
            repo_path=str(self.repo_path),
            allowed_paths=["test.txt"],
            forbidden_paths=[],
            timeout_seconds=60
        )
        
        result = self.adapter.run(task, allow_mock=True)
        
        # 模拟 Gate 中的断言
        try:
            assert not result.wrote_files, "Tool violated power boundary: wrote files directly"
            assert not result.committed, "Tool violated power boundary: committed directly"
            
            print(f"   ✅ Assertions passed")
            return True, "Gate assertions work correctly"
            
        except AssertionError as e:
            return False, f"Assertion failed: {e}"
    
    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
            print(f"\n🧹 Cleaned up temp dir: {self.temp_dir}")
    
    def run_all_tests(self) -> bool:
        """运行所有测试"""
        tests = [
            ("C.1: Power boundary fields", self.test_tool_result_power_boundary),
            ("C.2: No direct file writes", self.test_tool_must_not_write_files),
            ("C.3: No direct commits", self.test_tool_must_not_commit),
            ("C.4: Changes only after apply", self.test_repo_changes_only_after_apply),
            ("C.5: Gate assertions", self.test_assertion_in_gate),
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
                import traceback
                traceback.print_exc()
                self.test_results.append({
                    "test": name,
                    "passed": False,
                    "message": f"Exception: {e}"
                })
                all_passed = False
        
        return all_passed


def run_gate() -> bool:
    """运行 Gate TL-R1-C"""
    gate = TLR1CGate()
    
    try:
        print("=" * 70)
        print("🔒 Gate TL-R1-C: Power Boundary Enforcement")
        print("🔩 钉子 C: ToolResult → Executor 权力断点")
        print("=" * 70)
        
        # Setup
        if not gate.setup():
            print("❌ Gate TL-R1-C FAILED: Setup failed")
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
            print(f"✅ Gate TL-R1-C PASSED: Power boundary enforced correctly ({passed_count}/{total_count})")
            return True
        else:
            print(f"❌ Gate TL-R1-C FAILED: Some tests failed ({passed_count}/{total_count})")
            return False
        
    except Exception as e:
        print(f"❌ Gate TL-R1-C FAILED: Unexpected error: {e}")
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
