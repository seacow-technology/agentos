"""
Rollback - 失败回滚机制

在执行失败时回滚到之前的状态，支持 checksum 验证
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from agentos.core.infra.git_client import GitClientFactory
from agentos.core.time import utc_now_iso



class RollbackManager:
    """管理执行回滚"""
    
    def __init__(self, repo_path: Path):
        """初始化回滚管理器"""
        self.repo_path = Path(repo_path)
        self.rollback_points: List[Dict[str, Any]] = []
        self.git_client = GitClientFactory.get_client(repo_path)
    
    def create_rollback_point(
        self,
        name: str,
        worktree_path: Optional[Path] = None,
        checksums: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        创建回滚点
        
        Args:
            name: 回滚点名称
            worktree_path: worktree路径（如果使用worktree）
            checksums: 文件 checksums（可选）
        
        Returns:
            回滚点信息
        """
        if worktree_path:
            # Worktree模式：记录当前commit
            git_client_wt = GitClientFactory.get_client(worktree_path)
            commit_hash = git_client_wt.get_current_commit()
            
            rollback_point = {
                "name": name,
                "type": "worktree",
                "commit_hash": commit_hash,
                "worktree_path": str(worktree_path),
                "checksums": checksums or {},
                "created_at": utc_now_iso()
            }
        else:
            # 主仓库模式：记录当前commit
            commit_hash = self.git_client.get_current_commit()
            
            rollback_point = {
                "name": name,
                "type": "main_repo",
                "commit_hash": commit_hash,
                "checksums": checksums or {},
                "created_at": utc_now_iso()
            }
        
        self.rollback_points.append(rollback_point)
        return rollback_point
    
    def rollback_to(
        self,
        rollback_point: Dict[str, Any],
        verify_checksums: bool = True
    ) -> Dict[str, Any]:
        """
        回滚到指定点
        
        Args:
            rollback_point: 回滚点信息
            verify_checksums: 是否验证 checksums
        
        Returns:
            回滚结果（包含 success 和 checksums_match）
        """
        try:
            if rollback_point["type"] == "worktree":
                # Worktree模式：重置到commit
                worktree_path = Path(rollback_point["worktree_path"])
                commit_hash = rollback_point["commit_hash"]
                
                git_client_wt = GitClientFactory.get_client(worktree_path)
                git_client_wt.reset(commit_hash, hard=True)
                git_client_wt.clean(force=True, directories=True)
                
                success = True
                
            else:
                # 主仓库模式：重置（危险操作，实际使用时需要确认）
                commit_hash = rollback_point["commit_hash"]
                
                self.git_client.reset(commit_hash, hard=True)
                
                success = True
            
            # 验证 checksums
            checksums_match = True
            current_checksums = {}
            
            if verify_checksums and rollback_point.get("checksums"):
                current_checksums = self._compute_checksums(
                    worktree_path if rollback_point["type"] == "worktree" else self.repo_path
                )
                checksums_match = self._verify_checksums(
                    rollback_point["checksums"],
                    current_checksums
                )
            
            return {
                "success": success,
                "checksums_match": checksums_match,
                "expected_checksums": rollback_point.get("checksums", {}),
                "current_checksums": current_checksums
            }
                
        except Exception as e:
            print(f"Rollback failed: {e}")
            return {
                "success": False,
                "checksums_match": False,
                "error": str(e)
            }
    
    def _compute_checksums(self, repo_path: Path) -> Dict[str, str]:
        """计算当前文件 checksums"""
        checksums = {}
        
        # 只计算特定目录
        target_dirs = ["docs", "examples", "agentos", "tests"]
        
        for dir_name in target_dirs:
            dir_path = repo_path / dir_name
            if not dir_path.exists():
                continue
            
            for file_path in dir_path.rglob("*.py"):
                if file_path.is_file():
                    try:
                        content = file_path.read_bytes()
                        checksum = hashlib.sha256(content).hexdigest()
                        rel_path = str(file_path.relative_to(repo_path))
                        checksums[rel_path] = checksum
                    except Exception:
                        pass
        
        return checksums
    
    def _verify_checksums(
        self,
        expected: Dict[str, str],
        current: Dict[str, str]
    ) -> bool:
        """验证 checksums 是否匹配"""
        # 检查所有期望的文件
        for file_path, expected_checksum in expected.items():
            if file_path not in current:
                return False
            if current[file_path] != expected_checksum:
                return False
        
        return True
    
    def generate_rollback_proof(
        self,
        rollback_result: Dict[str, Any],
        output_file: Path
    ) -> None:
        """
        生成回滚证明文件
        
        Args:
            rollback_result: 回滚结果
            output_file: 输出文件路径
        """
        proof = {
            "rollback_proof_version": "1.0",
            "timestamp": utc_now_iso(),
            "success": rollback_result["success"],
            "checksums_match": rollback_result["checksums_match"],
            "checksums_verified": len(rollback_result.get("expected_checksums", {})),
            "details": rollback_result
        }
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(proof, f, indent=2)
    
    def rollback_to_latest(self) -> Dict[str, Any]:
        """回滚到最新的回滚点"""
        if not self.rollback_points:
            return {"success": False, "error": "No rollback points"}
        
        latest = self.rollback_points[-1]
        return self.rollback_to(latest)
    
    def get_rollback_points(self) -> List[Dict[str, Any]]:
        """获取所有回滚点"""
        return self.rollback_points.copy()
    
    def clear_rollback_points(self):
        """清空回滚点"""
        self.rollback_points.clear()
