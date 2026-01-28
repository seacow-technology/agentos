"""Codex Tool Adapter - Microsoft Codex integration."""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from .base_adapter import BaseToolAdapter
from agentos.core.infra.tool_executor import ToolExecutor


class CodexAdapter(BaseToolAdapter):
    """Adapter for Microsoft Codex tool."""
    
    TOOL_TYPE = "codex"
    
    def __init__(self, codex_path: Optional[str] = None):
        """
        Initialize Codex adapter.
        
        Args:
            codex_path: Path to codex executable (default: search in PATH)
        """
        self.codex_path = codex_path or "codex"
        self._verify_installation()
    
    def _verify_installation(self) -> None:
        """Verify Codex is installed."""
        if not ToolExecutor.check_tool_available(self.codex_path):
            raise RuntimeError(f"Codex not available at {self.codex_path}")
    
    def pack(
        self,
        execution_request: Dict[str, Any],
        repo_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Pack execution request into Codex task format.
        
        Args:
            execution_request: Execution request dictionary
            repo_state: Current repository state
        
        Returns:
            Tool task pack
        """
        task_pack_id = f"ttpack_codex_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Extract operations
        operations = execution_request.get("allowed_operations", [])
        
        # Build Codex task configuration
        task_config = {
            "intent_id": execution_request.get("intent_id"),
            "operations": operations,
            "context": {
                "repo_path": repo_state.get("repo_path"),
                "current_branch": repo_state.get("current_branch"),
                "file_tree": repo_state.get("file_tree", [])
            }
        }
        
        task_pack = {
            "tool_task_pack_id": task_pack_id,
            "schema_version": "0.12.0",
            "tool_type": self.TOOL_TYPE,
            "execution_request_id": execution_request["execution_request_id"],
            "task_config": task_config,
            "metadata": {
                "timeout_minutes": 30,
                "priority": "normal",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        }
        
        return task_pack
    
    def dispatch(
        self,
        task_pack: Dict[str, Any],
        output_dir: Path
    ) -> str:
        """
        Generate Codex dispatch command.
        
        Args:
            task_pack: Tool task pack
            output_dir: Output directory
        
        Returns:
            Command string to execute
        """
        task_pack_path = output_dir / f"{task_pack['tool_task_pack_id']}.json"
        
        # Save task pack
        with open(task_pack_path, "w", encoding="utf-8") as f:
            json.dump(task_pack, f, indent=2)
        
        # Build Codex command
        cmd = [
            self.codex_path,
            "execute",
            "--task", str(task_pack_path),
            "--output", str(output_dir)
        ]
        
        return " ".join(cmd)
    
    def collect(
        self,
        task_pack_id: str,
        output_dir: Path
    ) -> Dict[str, Any]:
        """
        Collect Codex execution results.
        
        Args:
            task_pack_id: Task pack identifier
            output_dir: Output directory
        
        Returns:
            Tool result pack
        """
        # Look for result file
        result_file = output_dir / f"{task_pack_id}_result.json"
        
        if not result_file.exists():
            return {
                "tool_result_pack_id": f"trpack_{task_pack_id}",
                "schema_version": "0.12.0",
                "tool_task_pack_id": task_pack_id,
                "tool_type": self.TOOL_TYPE,
                "status": "failed",
                "error": "Result file not found",
                "collected_at": datetime.now(timezone.utc).isoformat()
            }
        
        # Load result
        with open(result_file, "r", encoding="utf-8") as f:
            codex_result = json.load(f)
        
        # Convert to standard result pack
        result_pack = {
            "tool_result_pack_id": f"trpack_{task_pack_id}",
            "schema_version": "0.12.0",
            "tool_task_pack_id": task_pack_id,
            "tool_type": self.TOOL_TYPE,
            "status": codex_result.get("status", "completed"),
            "artifacts": codex_result.get("artifacts", []),
            "run_metadata": {
                "execution_time_seconds": codex_result.get("duration", 0),
                "cost_usd": codex_result.get("cost", 0.0),
                "tokens_used": codex_result.get("tokens", 0)
            },
            "collected_at": datetime.now(timezone.utc).isoformat()
        }
        
        if "error" in codex_result:
            result_pack["error"] = codex_result["error"]
        
        return result_pack
    
    def verify(
        self,
        result_pack: Dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """
        Verify Codex result pack.
        
        Args:
            result_pack: Tool result pack
        
        Returns:
            Tuple of (valid, errors)
        """
        errors = []
        
        # Check required fields
        required_fields = [
            "tool_result_pack_id",
            "tool_task_pack_id",
            "tool_type",
            "status"
        ]
        
        for field in required_fields:
            if field not in result_pack:
                errors.append(f"Missing required field: {field}")
        
        # Check tool type
        if result_pack.get("tool_type") != self.TOOL_TYPE:
            errors.append(f"Invalid tool_type: {result_pack.get('tool_type')}")
        
        # Check status
        valid_statuses = ["completed", "failed", "timeout"]
        if result_pack.get("status") not in valid_statuses:
            errors.append(f"Invalid status: {result_pack.get('status')}")
        
        return len(errors) == 0, errors
