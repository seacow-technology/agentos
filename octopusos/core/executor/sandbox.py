"""
Sandbox - 工作区隔离

使用git worktree提供隔离的执行环境
"""

from pathlib import Path
from typing import Optional, Dict, Any
import tempfile
import shutil

from agentos.core.infra.git_client import GitClientFactory


class Sandbox:
    """执行沙箱 - 使用git worktree隔离"""
    
    def __init__(self, repo_path: Path, base_worktree_dir: Optional[Path] = None):
        """
        初始化sandbox
        
        Args:
            repo_path: Git仓库路径
            base_worktree_dir: worktree基础目录，默认使用temp
        """
        self.repo_path = Path(repo_path)
        self.base_worktree_dir = base_worktree_dir or Path(tempfile.gettempdir()) / "agentos_worktrees"
        self.base_worktree_dir.mkdir(parents=True, exist_ok=True)
        
        self.worktree_path: Optional[Path] = None
        self.branch_name: Optional[str] = None
        self.git_client = GitClientFactory.get_client(repo_path)
    
    def create_worktree(self, run_id: str, branch_name: Optional[str] = None) -> Path:
        """
        创建git worktree
        
        Args:
            run_id: 执行run ID
            branch_name: 分支名，None则使用当前分支
        
        Returns:
            worktree路径
        """
        self.worktree_path = self.base_worktree_dir / f"worktree_{run_id}"
        
        if self.worktree_path.exists():
            # 清理旧的worktree
            self.remove_worktree()
        
        # 创建新分支（如果指定）
        if branch_name:
            self.branch_name = branch_name
            self.git_client.worktree_add(self.worktree_path, new_branch=branch_name)
        else:
            # 使用当前分支
            self.git_client.worktree_add(self.worktree_path)
        
        return self.worktree_path
    
    def remove_worktree(self):
        """删除worktree"""
        if not self.worktree_path:
            return
        
        if self.worktree_path.exists():
            # 移除git worktree
            try:
                self.git_client.worktree_remove(self.worktree_path, force=True)
            except Exception:
                # 即使失败也继续
                pass
            
            # 确保目录被删除
            if self.worktree_path.exists():
                shutil.rmtree(self.worktree_path, ignore_errors=True)
        
        self.worktree_path = None
        self.branch_name = None
    
    def get_worktree_path(self) -> Optional[Path]:
        """获取worktree路径"""
        return self.worktree_path
    
    def is_path_in_worktree(self, file_path: Path) -> bool:
        """检查路径是否在worktree内"""
        if not self.worktree_path:
            return False
        
        try:
            file_path.resolve().relative_to(self.worktree_path.resolve())
            return True
        except ValueError:
            return False
    
    def get_isolation_info(self) -> Dict[str, Any]:
        """获取隔离信息"""
        return {
            "worktree_path": str(self.worktree_path) if self.worktree_path else None,
            "branch_name": self.branch_name,
            "repo_path": str(self.repo_path),
            "isolated": self.worktree_path is not None
        }
    
    def __enter__(self):
        """Context manager入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager退出 - 自动清理"""
        self.remove_worktree()
