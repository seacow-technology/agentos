"""
Lock - 租约锁机制

防止并发执行冲突
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from agentos.core.time import utc_now, utc_now_iso



class ExecutionLock:
    """执行锁 - 防止并发执行"""
    
    def __init__(self, lock_dir: Path):
        """初始化锁管理器"""
        self.lock_dir = Path(lock_dir)
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_lock: Optional[Dict[str, Any]] = None
        self.lock_file: Optional[Path] = None
    
    def acquire(self, run_id: str, repo_hash: str, ttl_seconds: int = 3600) -> bool:
        """
        获取锁
        
        Args:
            run_id: 执行run ID
            repo_hash: 仓库hash（用于识别同一仓库）
            ttl_seconds: 锁TTL（秒）
        
        Returns:
            是否成功获取锁
        """
        lock_file = self.lock_dir / f"{repo_hash}.lock"
        
        # 检查是否已有锁
        if lock_file.exists():
            try:
                with open(lock_file, "r", encoding="utf-8") as f:
                    existing_lock = json.load(f)
                
                # 检查是否过期
                expires_at = datetime.fromisoformat(existing_lock["expires_at"])
                if utc_now() < expires_at:
                    # 锁仍然有效
                    return False
                
                # 锁已过期，可以获取
            except (json.JSONDecodeError, KeyError, ValueError):
                # 锁文件损坏，忽略
                pass
        
        # 创建新锁
        lock_data = {
            "run_id": run_id,
            "repo_hash": repo_hash,
            "acquired_at": utc_now_iso(),
            "expires_at": (utc_now() + timedelta(seconds=ttl_seconds)).isoformat(),
            "ttl_seconds": ttl_seconds
        }
        
        with open(lock_file, "w", encoding="utf-8") as f:
            json.dump(lock_data, f, indent=2)
        
        self.current_lock = lock_data
        self.lock_file = lock_file
        
        return True
    
    def release(self):
        """释放当前锁"""
        if self.lock_file and self.lock_file.exists():
            self.lock_file.unlink()
        
        self.current_lock = None
        self.lock_file = None
    
    def extend(self, additional_seconds: int = 3600) -> bool:
        """延长锁的TTL"""
        if not self.current_lock or not self.lock_file:
            return False
        
        # 更新过期时间
        self.current_lock["expires_at"] = (
            utc_now() + timedelta(seconds=additional_seconds)
        ).isoformat()
        
        with open(self.lock_file, "w", encoding="utf-8") as f:
            json.dump(self.current_lock, f, indent=2)
        
        return True
    
    def is_locked(self, repo_hash: str) -> bool:
        """检查仓库是否被锁"""
        lock_file = self.lock_dir / f"{repo_hash}.lock"
        
        if not lock_file.exists():
            return False
        
        try:
            with open(lock_file, "r", encoding="utf-8") as f:
                lock_data = json.load(f)
            
            expires_at = datetime.fromisoformat(lock_data["expires_at"])
            return utc_now() < expires_at
            
        except (json.JSONDecodeError, KeyError, ValueError):
            return False
    
    def get_lock_info(self, repo_hash: str) -> Optional[Dict[str, Any]]:
        """获取锁信息"""
        lock_file = self.lock_dir / f"{repo_hash}.lock"
        
        if not lock_file.exists():
            return None
        
        try:
            with open(lock_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, KeyError):
            return None
    
    def __enter__(self):
        """Context manager入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager退出 - 自动释放锁"""
        self.release()
