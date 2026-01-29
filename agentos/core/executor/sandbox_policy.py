"""Sandbox Policy - 沙箱策略加载与校验

加载、验证和查询 sandbox_policy.json。
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import jsonschema


class PolicyDeniedError(Exception):
    """策略拒绝异常"""
    
    def __init__(self, message: str, operation: str, reason: str, rule_id: Optional[str] = None):
        """
        初始化策略拒绝异常
        
        Args:
            message: 错误消息
            operation: 被拒绝的操作
            reason: 拒绝原因
            rule_id: 触发拒绝的规则ID（可选）
        """
        super().__init__(message)
        self.operation = operation
        self.reason = reason
        self.rule_id = rule_id


class SandboxPolicy:
    """沙箱策略"""
    
    def __init__(self, policy_data: Dict[str, Any]):
        """
        初始化沙箱策略
        
        Args:
            policy_data: 策略数据（已验证）
        """
        self.policy_data = policy_data
        self.policy_id = policy_data["policy_id"]
        self.schema_version = policy_data["schema_version"]
        self.allowlist = policy_data["allowlist"]
        self.allowed_git_operations = policy_data.get("allowed_git_operations", ["git_add", "git_commit"])
        self.limits = policy_data.get("limits", {})
    
    def is_operation_allowed(self, operation: str) -> bool:
        """
        检查操作是否允许
        
        Args:
            operation: 操作类型（如 "write", "update", "patch"）
        
        Returns:
            是否允许
        """
        allowed_ops = self.allowlist.get("file_operations", [])
        return operation in allowed_ops
    
    def assert_operation_allowed(self, operation: str, params: Optional[Dict[str, Any]] = None) -> None:
        """
        断言操作允许（否则抛出 PolicyDeniedError）
        
        Args:
            operation: 操作类型 (e.g., "write_file", "git_commit")
            params: 操作参数（可选，用于路径检查）
        
        Raises:
            PolicyDeniedError: 操作不允许
        """
        # P0-钉子1: 直接验证真实 action 名称，无映射绕过
        
        # Git 操作单独验证
        if operation in self.allowed_git_operations:
            return
        
        # 文件操作必须在 allowlist 中
        allowed_file_ops = self.allowlist.get("file_operations", [])
        
        if operation not in allowed_file_ops:
            # 未知操作必须拒绝（封死绕过）
            raise PolicyDeniedError(
                message=f"Operation '{operation}' is not allowed by policy",
                operation=operation,
                reason=f"Operation not in allowlist. Allowed file_operations: {allowed_file_ops}, allowed git_operations: {self.allowed_git_operations}",
                rule_id=f"{self.policy_id}:unknown_operation"
            )
        
        # 检查路径（如果提供）
        if params and "path" in params:
            path = params["path"]
            if not self.is_path_allowed(path):
                raise PolicyDeniedError(
                    message=f"Path '{path}' is not allowed by policy",
                    operation=operation,
                    reason=f"Path not in allowlist. Allowed patterns: {self.allowlist.get('paths', [])}",
                    rule_id=f"{self.policy_id}:paths"
                )
    
    def is_path_allowed(self, path: str) -> bool:
        """
        检查路径是否在允许列表中
        
        Args:
            path: 文件路径
        
        Returns:
            是否允许
        """
        import fnmatch
        
        allowed_paths = self.allowlist.get("paths", [])
        
        for pattern in allowed_paths:
            if fnmatch.fnmatch(path, pattern):
                return True
        
        return False
    
    def get_max_file_size(self) -> Optional[float]:
        """获取最大文件大小（MB）"""
        return self.limits.get("max_file_size_mb")
    
    def get_max_files(self) -> Optional[int]:
        """获取最大文件数"""
        return self.limits.get("max_files")
    
    def get_timeout(self) -> Optional[int]:
        """获取超时时间（秒）"""
        return self.limits.get("timeout_seconds")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.policy_data.copy()


class SandboxPolicyLoader:
    """沙箱策略加载器"""
    
    def __init__(self, schema_path: Optional[Path] = None):
        """
        初始化加载器
        
        Args:
            schema_path: Schema 文件路径（可选）
        """
        self.schema_path = schema_path or self._get_default_schema_path()
        self.schema = self._load_schema()
    
    def _get_default_schema_path(self) -> Path:
        """获取默认 schema 路径"""
        return Path(__file__).parent.parent.parent / "schemas" / "executor" / "sandbox_policy.schema.json"
    
    def _load_schema(self) -> Dict[str, Any]:
        """加载 JSON Schema"""
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema not found: {self.schema_path}")
        
        with open(self.schema_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def load(self, policy_path: Path) -> SandboxPolicy:
        """
        加载并验证策略文件
        
        Args:
            policy_path: 策略文件路径
        
        Returns:
            SandboxPolicy 实例
        
        Raises:
            FileNotFoundError: 文件不存在
            jsonschema.ValidationError: 验证失败
        """
        if not policy_path.exists():
            raise FileNotFoundError(f"Policy file not found: {policy_path}")
        
        with open(policy_path, "r", encoding="utf-8") as f:
            policy_data = json.load(f)
        
        # 验证 schema
        jsonschema.validate(policy_data, self.schema)
        
        return SandboxPolicy(policy_data)
    
    def validate(self, policy_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        验证策略数据
        
        Args:
            policy_data: 策略数据
        
        Returns:
            (is_valid, errors)
        """
        try:
            jsonschema.validate(policy_data, self.schema)
            return True, []
        except jsonschema.ValidationError as e:
            return False, [str(e)]


def load_sandbox_policy(policy_path: Path) -> SandboxPolicy:
    """
    加载沙箱策略（便捷函数）
    
    Args:
        policy_path: 策略文件路径
    
    Returns:
        SandboxPolicy 实例
    """
    loader = SandboxPolicyLoader()
    return loader.load(policy_path)
