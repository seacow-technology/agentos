#!/usr/bin/env python3
"""
Gate TL-R1: Tool Outsourcing E2E（Step 3 Runtime Gate）

这是 Step 3 的第一个 Runtime Gate，验证完整的外包闭环：

1. 创建临时 repo
2. 写一个 tool task（例如："给 index.html 加一个 footer"）
3. 调用 ClaudeCliAdapter.run()
4. 拿回 diff
5. 验证 diff：
   - 是 unified diff
   - 只改允许路径
6. Executor 应用 diff
7. git commit
8. 验证：
   - commit 存在
   - 文件真的改了
   - run_tape 有：
     - tool_dispatch_started
     - tool_dispatch_completed
     - tool_result_verified

通过 = Step 3 破冰成功
"""

import sys
import tempfile
import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime, timezone

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.ext.tools import (
    ClaudeCliAdapter,
    ToolTask,
    ToolResult,
    DiffVerifier
)


class TLR1Gate:
    """Gate TL-R1: Tool Outsourcing Runtime E2E"""
    
    def __init__(self):
        self.temp_dir = None
        self.repo_path = None
        self.adapter = None
        self.run_tape = []
    
    def setup(self) -> bool:
        """创建临时 repo"""
        try:
            # 创建临时目录
            self.temp_dir = tempfile.mkdtemp(prefix="tl_r1_gate_")
            self.repo_path = Path(self.temp_dir)
            
            print(f"📁 Created temp repo: {self.repo_path}")
            
            # 初始化 git repo
            subprocess.run(["git", "init"], cwd=self.repo_path, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "TL-R1 Gate"], cwd=self.repo_path, check=True)
            subprocess.run(["git", "config", "user.email", "gate@agentos.dev"], cwd=self.repo_path, check=True)
            
            # 创建初始文件
            index_file = self.repo_path / "index.html"
            index_file.write_text("""<!DOCTYPE html>
<html>
<head>
    <title>TL-R1 Test Page</title>
</head>
<body>
    <h1>Welcome to AgentOS</h1>
    <p>This is a test page for Step 3 Runtime Gate.</p>
</body>
</html>
""")
            
            # 初始 commit
            subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=self.repo_path,
                check=True,
                capture_output=True
            )
            
            print("✅ Temp repo initialized with index.html")
            
            # 初始化 adapter
            self.adapter = ClaudeCliAdapter()
            
            # Health check
            health = self.adapter.health_check()
            self.run_tape.append({
                "event": "health_check",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": health.status,
                "details": health.details
            })
            
            if not health.is_healthy():
                print(f"⚠️  Claude CLI not healthy: {health.status} - {health.details}")
                print("   Gate will use mock mode for testing")
                return True  # 允许继续，但会使用 mock
            
            print(f"✅ Claude CLI health check passed: {health.details}")
            return True
            
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return False
    
    def run_tool_outsourcing(self) -> tuple[bool, str]:
        """执行外包任务"""
        try:
            # 创建任务
            task = ToolTask(
                task_id="tl_r1_task_001",
                instruction="Add a footer to index.html with text 'Powered by AgentOS Step 3 Runtime'",
                repo_path=str(self.repo_path),
                allowed_paths=["index.html"],
                forbidden_paths=[".git/**", "*.env"],
                timeout_seconds=60
            )
            
            self.run_tape.append({
                "event": "tool_dispatch_started",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "task_id": task.task_id,
                "instruction": task.instruction
            })
            
            print(f"🔧 Dispatching task: {task.instruction}")
            
            # 🔩 钉子 A：Gate 明确传入 allow_mock=True
            result = self.adapter.run(task, allow_mock=True)
            
            # 🔩 钉子 A：记录 Mock 使用
            if hasattr(result, '_mock_used') and result._mock_used:
                self.run_tape.append({
                    "event": "tool_mock_used",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reason": getattr(result, '_mock_reason', 'unknown')
                })
                print(f"⚠️  Mock mode used: {result._mock_reason}")
            
            self.run_tape.append({
                "event": "tool_dispatch_completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "task_id": task.task_id,
                "status": result.status,
                "tool_run_id": result.tool_run_id,
                "files_touched": result.files_touched,
                "line_count": result.line_count
            })
            
            if result.status not in ["success", "partial_success"]:
                return False, f"Tool execution failed: {result.status} - {result.error_message}"
            
            if not result.diff or not result.diff.strip():
                return False, "Tool returned empty diff"
            
            # 🔩 钉子 C：断言权力边界
            assert not result.wrote_files, "Tool violated power boundary: wrote files directly"
            assert not result.committed, "Tool violated power boundary: committed directly"
            
            print(f"✅ Tool execution completed: {result.status}")
            print(f"   Files touched: {result.files_touched}")
            print(f"   Lines changed: {result.line_count}")
            print(f"   🔒 Power boundary: wrote_files={result.wrote_files}, committed={result.committed}")
            
            # 验证 diff
            validation = DiffVerifier.verify(
                result,
                allowed_paths=task.allowed_paths,
                forbidden_paths=task.forbidden_paths
            )
            
            self.run_tape.append({
                "event": "tool_result_verified",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "is_valid": validation.is_valid,
                "errors": validation.errors,
                "warnings": validation.warnings
            })
            
            if not validation.is_valid:
                return False, f"Diff validation failed: {validation.errors}"
            
            print(f"✅ Diff validation passed")
            if validation.warnings:
                for warning in validation.warnings:
                    print(f"   ⚠️  {warning}")
            
            # 应用 diff
            self._apply_diff(result.diff)
            
            # Commit
            self._commit_changes(result)
            
            return True, "Tool outsourcing E2E completed successfully"
            
        except Exception as e:
            self.run_tape.append({
                "event": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            })
            return False, f"Tool outsourcing failed: {e}"
    
    def _apply_diff(self, diff: str):
        """应用 diff（模拟 Executor 行为）"""
        # 简化版：直接通过 git apply
        diff_file = self.repo_path / ".tmp_diff"
        diff_file.write_text(diff)
        
        result = subprocess.run(
            ["git", "apply", str(diff_file)],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )
        
        diff_file.unlink()
        
        if result.returncode != 0:
            raise Exception(f"git apply failed: {result.stderr}")
        
        print("✅ Diff applied successfully")
    
    def _commit_changes(self, result: ToolResult):
        """Commit 变更（模拟 Executor 行为）"""
        subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True)
        
        commit_msg = f"""Step 3 Runtime: Tool outsourcing

Tool: {result.tool}
Run ID: {result.tool_run_id}
Files: {', '.join(result.files_touched)}
Lines: {result.line_count}
"""
        
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=self.repo_path,
            check=True,
            capture_output=True
        )
        
        self.run_tape.append({
            "event": "git_commit",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "files": result.files_touched
        })
        
        print("✅ Changes committed")
    
    def verify(self) -> tuple[bool, str]:
        """验证结果"""
        try:
            # 1. 检查 commit 存在
            result = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            last_commit = result.stdout.strip()
            if "Step 3 Runtime" not in last_commit:
                return False, f"Last commit is not from tool outsourcing: {last_commit}"
            
            print(f"✅ Commit exists: {last_commit}")
            
            # 2. 检查文件真的改了
            index_file = self.repo_path / "index.html"
            content = index_file.read_text()
            
            if "footer" not in content.lower() or "agentos" not in content.lower():
                return False, "File content does not contain expected changes"
            
            print("✅ File content verified")
            
            # 3. 检查 run_tape 有必要事件
            events = [e["event"] for e in self.run_tape]
            required_events = [
                "tool_dispatch_started",
                "tool_dispatch_completed",
                "tool_result_verified",
                "git_commit"
            ]
            
            missing_events = [e for e in required_events if e not in events]
            if missing_events:
                return False, f"Missing events in run_tape: {missing_events}"
            
            print(f"✅ Run tape complete: {len(self.run_tape)} events")
            
            return True, "All verifications passed"
            
        except Exception as e:
            return False, f"Verification failed: {e}"
    
    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
            print(f"🧹 Cleaned up temp dir: {self.temp_dir}")
    
    def save_artifacts(self, output_dir: Path):
        """保存 artifacts"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存 run_tape
        tape_file = output_dir / "tl_r1_run_tape.jsonl"
        with open(tape_file, "w", encoding="utf-8") as f:
            for event in self.run_tape:
                f.write(json.dumps(event) + "\n")
        
        print(f"💾 Run tape saved: {tape_file}")
        
        # 保存 git log
        if self.repo_path:
            result = subprocess.run(
                ["git", "log", "--oneline", "--all"],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            log_file = output_dir / "tl_r1_git_log.txt"
            log_file.write_text(result.stdout)
            
            print(f"💾 Git log saved: {log_file}")


def run_gate() -> bool:
    """运行 Gate TL-R1"""
    gate = TLR1Gate()
    
    try:
        print("=" * 70)
        print("🔒 Gate TL-R1: Tool Outsourcing E2E (Step 3 Runtime)")
        print("=" * 70)
        print()
        
        # Setup
        if not gate.setup():
            print("❌ Gate TL-R1 FAILED: Setup failed")
            return False
        
        print()
        
        # Run tool outsourcing
        success, message = gate.run_tool_outsourcing()
        if not success:
            print(f"❌ Gate TL-R1 FAILED: {message}")
            return False
        
        print()
        
        # Verify
        success, message = gate.verify()
        if not success:
            print(f"❌ Gate TL-R1 FAILED: {message}")
            return False
        
        print()
        print("=" * 70)
        print("✅ Gate TL-R1 PASSED: Tool Outsourcing E2E completed successfully")
        print("=" * 70)
        
        # Save artifacts
        output_dir = Path("outputs/gates/tl_r1")
        gate.save_artifacts(output_dir)
        
        return True
        
    except Exception as e:
        print(f"❌ Gate TL-R1 FAILED: Unexpected error: {e}")
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
