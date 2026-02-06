"""Git Client - 统一的 Git 操作适配层

禁止在业务逻辑中直接使用 subprocess。
所有 git 操作必须通过此 GitClient。
"""

from pathlib import Path
from typing import List, Optional, Union
from datetime import datetime
import io

from git import Repo
from git.exc import GitCommandError


class GitClient:
    """Git 操作客户端 - 使用 GitPython"""
    
    def __init__(self, repo_path: Path):
        """
        初始化 GitClient
        
        Args:
            repo_path: Git 仓库路径
        """
        self.repo_path = Path(repo_path)
        self.repo = Repo(str(repo_path))
    
    def init_repo(self) -> None:
        """初始化 git repo（如果不存在）"""
        if not (self.repo_path / ".git").exists():
            Repo.init(str(self.repo_path))
            self.repo = Repo(str(self.repo_path))
    
    def add(self, paths: Union[List[str], str]) -> None:
        """
        添加文件到暂存区
        
        Args:
            paths: 文件路径列表或单个路径
        """
        if isinstance(paths, str):
            paths = [paths]
        
        self.repo.index.add(paths)
    
    def add_all(self) -> None:
        """添加所有变更到暂存区"""
        self.repo.git.add(A=True)
    
    def commit(self, message: str) -> str:
        """
        提交变更
        
        Args:
            message: 提交消息
        
        Returns:
            commit hash (完整 40 字符)
        """
        commit = self.repo.index.commit(message)
        return commit.hexsha
    
    def get_head_sha(self) -> str:
        """获取 HEAD commit SHA"""
        return self.repo.head.commit.hexsha
    
    def get_commit_range(self, base: str, head: str) -> List[str]:
        """
        获取从 base 到 head 的所有 commit SHAs（不包含 base）
        
        Args:
            base: 起始 commit SHA
            head: 结束 commit SHA
        
        Returns:
            commit SHAs 列表（从旧到新）
        """
        # 使用 git rev-list 获取 commit 列表
        commits_str = self.repo.git.rev_list(f"{base}..{head}", reverse=True)
        if not commits_str.strip():
            return []
        return commits_str.strip().split('\n')
    
    def get_short_sha(self, sha: Optional[str] = None) -> str:
        """
        获取短 SHA (8 字符)
        
        Args:
            sha: commit SHA，None 则使用 HEAD
        
        Returns:
            短 SHA
        """
        if sha is None:
            sha = self.get_head_sha()
        return sha[:8]
    
    def format_patch(self, base: str, head: str, output_file: Path) -> None:
        """
        生成 patch 文件
        
        Args:
            base: 基础 commit
            head: 目标 commit
            output_file: 输出文件路径
        """
        # 使用 GitPython 的 format-patch
        patch_content = self.repo.git.format_patch(
            f"{base}..{head}",
            stdout=True
        )
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(patch_content)
    
    def format_patch_multiple(self, base: str, head: str, output_dir: Path) -> List[Path]:
        """
        生成多个 patch 文件（每个 commit 一个）
        
        Args:
            base: 基础 commit
            head: 目标 commit
            output_dir: 输出目录
        
        Returns:
            生成的 patch 文件列表
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用 format-patch 生成独立文件（自动编号）
        # git format-patch base..head -o output_dir
        self.repo.git.format_patch(
            f"{base}..{head}",
            o=str(output_dir)
        )
        
        # 返回生成的 patch 文件（按顺序）
        patch_files = sorted(output_dir.glob("*.patch"))
        return patch_files
    
    def apply_patch(self, patch_file: Path) -> None:
        """
        应用 patch 文件
        
        Args:
            patch_file: patch 文件路径
        """
        # 使用 git am 应用 patch（直接传递文件路径）
        self.repo.git.am(str(patch_file))
    
    def get_commit_count(self) -> int:
        """获取当前分支的 commit 数量"""
        return sum(1 for _ in self.repo.iter_commits())
    
    def get_commit_log(self, count: int = 10) -> List[dict]:
        """
        获取 commit 日志
        
        Args:
            count: 数量
        
        Returns:
            commit 列表
        """
        commits = []
        for commit in self.repo.iter_commits(max_count=count):
            commits.append({
                "sha": commit.hexsha,
                "short_sha": commit.hexsha[:8],
                "message": commit.message.strip(),
                "author": str(commit.author),
                "date": datetime.fromtimestamp(commit.committed_date).isoformat()
            })
        return commits
    
    def checkout(self, ref: str) -> None:
        """
        切换到指定 ref
        
        Args:
            ref: branch/tag/commit
        """
        self.repo.git.checkout(ref)
    
    def get_file_hash(self, file_path: Path) -> str:
        """
        获取文件的 git hash (blob hash)
        
        Args:
            file_path: 文件路径（相对于 repo root）
        
        Returns:
            git blob hash
        """
        # 计算 blob hash
        content = file_path.read_bytes()
        return self.repo.odb.store(
            io.BytesIO(b"blob %d\0" % len(content) + content)
        ).hexsha
    
    def diff_cached(self, output_file: Path) -> None:
        """
        生成暂存区的 diff
        
        Args:
            output_file: 输出文件路径
        """
        diff_content = self.repo.git.diff(cached=True)
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(diff_content)
    
    def status(self) -> dict:
        """
        获取仓库状态
        
        Returns:
            状态字典
        """
        return {
            "branch": self.repo.active_branch.name if not self.repo.head.is_detached else "detached",
            "is_dirty": self.repo.is_dirty(),
            "untracked_files": self.repo.untracked_files,
            "modified_files": [item.a_path for item in self.repo.index.diff(None)],
            "staged_files": [item.a_path for item in self.repo.index.diff("HEAD")]
        }
    
    def create_worktree(self, worktree_path: Path, branch: Optional[str] = None) -> None:
        """
        创建 git worktree
        
        Args:
            worktree_path: worktree 路径
            branch: 分支名（可选）
        """
        if branch:
            self.repo.git.worktree("add", "-b", branch, str(worktree_path))
        else:
            self.repo.git.worktree("add", str(worktree_path))
    
    def worktree_add(self, worktree_path: Path, new_branch: Optional[str] = None) -> None:
        """别名：创建 worktree"""
        self.create_worktree(worktree_path, new_branch)
    
    def remove_worktree(self, worktree_path: Path, force: bool = True) -> None:
        """
        删除 git worktree
        
        Args:
            worktree_path: worktree 路径
            force: 强制删除
        """
        args = ["remove", str(worktree_path)]
        if force:
            args.append("--force")
        
        try:
            self.repo.git.worktree(*args)
        except GitCommandError:
            # 即使失败也继续
            pass
    
    def worktree_remove(self, worktree_path: Path, force: bool = True) -> None:
        """别名：删除 worktree"""
        self.remove_worktree(worktree_path, force)
    
    def get_current_commit(self) -> str:
        """获取当前 commit hash"""
        return self.repo.head.commit.hexsha
    
    def reset(self, commit: str, hard: bool = False) -> None:
        """
        重置到指定 commit
        
        Args:
            commit: commit hash 或 ref
            hard: 是否硬重置
        """
        if hard:
            self.repo.git.reset("--hard", commit)
        else:
            self.repo.git.reset(commit)
    
    def clean(self, force: bool = False, directories: bool = False) -> None:
        """
        清理未跟踪的文件
        
        Args:
            force: 强制清理
            directories: 清理目录
        """
        args = ["clean"]
        if force:
            args.append("-f")
        if directories:
            args.append("-d")
        
        self.repo.git.clean(*args)


class GitClientFactory:
    """GitClient 工厂"""
    
    _instances = {}
    
    @classmethod
    def get_client(cls, repo_path: Path) -> GitClient:
        """
        获取 GitClient 实例（单例）
        
        Args:
            repo_path: 仓库路径
        
        Returns:
            GitClient 实例
        """
        repo_path = Path(repo_path).resolve()
        
        if repo_path not in cls._instances:
            cls._instances[repo_path] = GitClient(repo_path)
        
        return cls._instances[repo_path]
