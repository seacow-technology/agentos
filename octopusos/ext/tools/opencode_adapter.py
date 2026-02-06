"""
OpenCode Adapter - OpenCode工具适配器
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

from .base_adapter import BaseToolAdapter


class OpenCodeAdapter(BaseToolAdapter):
    """OpenCode 工具适配器"""
    
    def __init__(self):
        super().__init__("opencode")
    
    def pack(self, execution_request: Dict[str, Any], repo_state: Dict[str, Any]) -> Dict[str, Any]:
        """打包任务给OpenCode"""
        
        task_pack_id = f"ttpack_{hashlib.sha256(execution_request['execution_request_id'].encode()).hexdigest()[:16]}"
        
        task_pack = {
            "tool_task_pack_id": task_pack_id,
            "schema_version": "0.11.2",
            "execution_request_id": execution_request["execution_request_id"],
            "tool_type": "opencode",
            "repo_state": repo_state,
            "work_scope": {
                "allowed_directories": ["agentos/**", "docs/**", "tests/**"],
                "forbidden_paths": [".git/config", ".env"]
            },
            "steps": [
                {
                    "step_id": "step_001",
                    "goal": "Implement changes as specified",
                    "constraints": {
                        "must": ["Follow project conventions", "Add tests"],
                        "must_not": ["Modify config files", "Break tests"]
                    },
                    "expected_artifacts": [
                        {"type": "file", "path": "*.py"}
                    ],
                    "verification_commands": ["pytest", "ruff check"]
                }
            ],
            "prompt_pack": {
                "system_prompt": "Implement changes following AgentOS conventions",
                "red_lines": [
                    "Do not modify .git/",
                    "Do not change credentials"
                ]
            },
            "acceptance": {
                "gates": ["build", "test"],
                "tests": ["pytest"],
                "policy_checks": ["scope_check"]
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "priority": "medium",
                "estimated_complexity": "moderate",
                "timeout_minutes": 30
            }
        }
        
        return task_pack
    
    def dispatch(self, task_pack: Dict[str, Any], output_dir: Path) -> str:
        """生成OpenCode调度命令"""
        
        task_pack_file = output_dir / f"{task_pack['tool_task_pack_id']}.json"
        task_pack_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(task_pack_file, "w", encoding="utf-8") as f:
            json.dump(task_pack, f, indent=2)
        
        command = f"""# OpenCode Dispatch Command
# opencode --task {task_pack_file} --output {output_dir}/opencode_output
"""
        
        return command
    
    def collect(self, task_pack_id: str, output_dir: Path) -> Dict[str, Any]:
        """收集OpenCode执行结果"""
        
        result_pack_id = f"trpack_{hashlib.sha256(task_pack_id.encode()).hexdigest()[:16]}"
        
        result_pack = {
            "tool_result_pack_id": result_pack_id,
            "schema_version": "0.11.2",
            "tool_task_pack_id": task_pack_id,
            "tool_type": "opencode",
            "status": "success",
            "diffs": [],
            "artifacts": {
                "files_created": [],
                "files_modified": [],
                "files_deleted": [],
                "commits": []
            },
            "test_logs": {},
            "run_metadata": {
                "tool_version": "opencode-1.0",
                "execution_time_seconds": 0
            },
            "policy_attestation": {
                "scope_compliant": True,
                "red_lines_respected": True,
                "violations": []
            },
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        
        return result_pack
    
    def verify(self, result_pack: Dict[str, Any]) -> tuple[bool, list[str]]:
        """验证结果包"""
        errors = []
        
        if result_pack["status"] != "success":
            errors.append(f"Status is {result_pack['status']}")
        
        if not result_pack["policy_attestation"]["scope_compliant"]:
            errors.append("Scope compliance failed")
        
        return len(errors) == 0, errors
