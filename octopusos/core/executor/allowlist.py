"""
Allowlist管理 - 定义允许的执行操作 (v0.12)

只允许预定义的安全操作，禁止任意shell执行
v0.12 新增: npm/pip install, 环境变量设置
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
from enum import Enum


class RiskLevel(Enum):
    """Operation risk levels."""
    SAFE = "safe"  # Read-only, no side effects
    LOW = "low"  # Modifies files in repo
    MEDIUM = "medium"  # Installs packages, modifies env
    HIGH = "high"  # Network access, system changes


class Allowlist:
    """管理允许的执行操作allowlist (v0.12)"""
    
    def __init__(self):
        """初始化allowlist，v0.12扩展集"""
        # 文件操作：只能在repo内
        self.file_operations = {
            "write": {
                "executor": self._op_file_write,
                "risk": RiskLevel.LOW
            },
            "update": {
                "executor": self._op_file_update,
                "risk": RiskLevel.LOW
            },
            "patch": {
                "executor": self._op_file_patch,
                "risk": RiskLevel.LOW
            },
        }
        
        # 检查命令：只读，allowlist命令
        self.check_commands = {
            "lint": {
                "executable": "ruff",
                "allowed_args": ["check", "."],
                "risk": RiskLevel.SAFE
            },
            "test": {
                "executable": "pytest",
                "allowed_args": ["-v"],
                "risk": RiskLevel.SAFE
            },
            "build": {
                "executable": "python",
                "allowed_args": ["-m", "build"],
                "risk": RiskLevel.SAFE
            },
        }
        
        # Git操作：严格模板
        self.git_operations = {
            "create_branch": {
                "executor": self._op_git_branch,
                "risk": RiskLevel.LOW
            },
            "commit": {
                "executor": self._op_git_commit,
                "risk": RiskLevel.LOW
            },
        }
        
        # v0.12: Package management (MEDIUM risk)
        self.package_operations = {
            "npm_install": {
                "executable": "npm",
                "allowed_args": ["install"],
                "allow_package_names": True,
                "risk": RiskLevel.MEDIUM
            },
            "pip_install": {
                "executable": "pip",
                "allowed_args": ["install"],
                "allow_package_names": True,
                "risk": RiskLevel.MEDIUM
            },
            "pip_install_requirements": {
                "executable": "pip",
                "allowed_args": ["install", "-r", "requirements.txt"],
                "risk": RiskLevel.MEDIUM
            },
        }
        
        # v0.12: Environment variables (MEDIUM risk)
        self.env_operations = {
            "set_env": {
                "executor": self._op_set_env,
                "risk": RiskLevel.MEDIUM
            },
            "unset_env": {
                "executor": self._op_unset_env,
                "risk": RiskLevel.MEDIUM
            },
        }
    
    def is_allowed(
        self,
        operation_type: str,
        operation_id: Optional[str] = None
    ) -> bool:
        """检查操作是否被允许"""
        # v0.12: 简化检查，支持单参数调用
        if operation_id is None:
            # operation_type 就是操作本身 (如 "file_write")
            return self._check_operation_exists(operation_type)
        
        if operation_type == "file_operation":
            return operation_id in self.file_operations
        elif operation_type == "check_command":
            return operation_id in self.check_commands
        elif operation_type == "git_operation":
            return operation_id in self.git_operations
        elif operation_type == "package_operation":
            return operation_id in self.package_operations
        elif operation_type == "env_operation":
            return operation_id in self.env_operations
        return False
    
    def _check_operation_exists(self, op_name: str) -> bool:
        """检查操作名称是否存在于任何类别"""
        all_ops = (
            list(self.file_operations.keys()) +
            list(self.check_commands.keys()) +
            list(self.git_operations.keys()) +
            list(self.package_operations.keys()) +
            list(self.env_operations.keys())
        )
        return op_name in all_ops
    
    def get_executor(self, operation_type: str, operation_id: str):
        """获取操作的执行器函数"""
        if operation_type == "file_operation":
            return self.file_operations.get(operation_id, {}).get("executor")
        elif operation_type == "git_operation":
            return self.git_operations.get(operation_id, {}).get("executor")
        elif operation_type == "env_operation":
            return self.env_operations.get(operation_id, {}).get("executor")
        return None
    
    def get_risk_level(self, operation_type: str, operation_id: str) -> RiskLevel:
        """获取操作的风险等级"""
        operation_map = {
            "file_operation": self.file_operations,
            "check_command": self.check_commands,
            "git_operation": self.git_operations,
            "package_operation": self.package_operations,
            "env_operation": self.env_operations,
        }
        
        ops = operation_map.get(operation_type, {})
        op_data = ops.get(operation_id, {})
        return op_data.get("risk", RiskLevel.HIGH)
    
    def requires_container(self, operation_type: str, operation_id: str) -> bool:
        """检查操作是否需要容器沙箱"""
        risk = self.get_risk_level(operation_type, operation_id)
        # MEDIUM 及以上风险需要容器
        return risk in [RiskLevel.MEDIUM, RiskLevel.HIGH]
    
    def get_command_spec(self, command_id: str) -> Optional[Dict[str, Any]]:
        """获取检查命令规格"""
        return self.check_commands.get(command_id)
    
    def get_package_spec(self, package_id: str) -> Optional[Dict[str, Any]]:
        """获取包管理操作规格"""
        return self.package_operations.get(package_id)
    
    # ===== 文件操作实现 =====
    
    def _op_file_write(self, file_path: Path, content: str, **kwargs) -> Dict[str, Any]:
        """写入新文件（仅repo内）"""
        return {
            "operation": "file_write",
            "file_path": str(file_path),
            "action": "write_content",
            "content_length": len(content)
        }
    
    def _op_file_update(self, file_path: Path, content: str, **kwargs) -> Dict[str, Any]:
        """更新现有文件"""
        return {
            "operation": "file_update",
            "file_path": str(file_path),
            "action": "replace_content",
            "content_length": len(content)
        }
    
    def _op_file_patch(self, file_path: Path, patch: str, **kwargs) -> Dict[str, Any]:
        """应用patch到文件"""
        return {
            "operation": "file_patch",
            "file_path": str(file_path),
            "action": "apply_patch",
            "patch_lines": len(patch.splitlines())
        }
    
    # ===== Git操作实现 =====
    
    def _op_git_branch(self, branch_name: str, **kwargs) -> Dict[str, Any]:
        """创建git分支"""
        return {
            "operation": "git_create_branch",
            "branch_name": branch_name,
            "action": "create_branch"
        }
    
    def _op_git_commit(self, message: str, files: List[str], **kwargs) -> Dict[str, Any]:
        """创建git commit"""
        return {
            "operation": "git_commit",
            "message": message,
            "files": files,
            "action": "create_commit"
        }
    
    # ===== v0.12: 环境变量操作 =====
    
    def _op_set_env(self, var_name: str, var_value: str, **kwargs) -> Dict[str, Any]:
        """设置环境变量"""
        # 禁止敏感变量
        forbidden = ["PATH", "HOME", "USER", "SHELL"]
        if var_name.upper() in forbidden:
            raise ValueError(f"Cannot modify protected env var: {var_name}")
        
        return {
            "operation": "set_env",
            "var_name": var_name,
            "var_value": var_value,
            "action": "set_environment_variable"
        }
    
    def _op_unset_env(self, var_name: str, **kwargs) -> Dict[str, Any]:
        """取消设置环境变量"""
        return {
            "operation": "unset_env",
            "var_name": var_name,
            "action": "unset_environment_variable"
        }
    
    def list_all_operations(self) -> Dict[str, List[str]]:
        """列出所有允许的操作"""
        return {
            "file_operations": list(self.file_operations.keys()),
            "check_commands": list(self.check_commands.keys()),
            "git_operations": list(self.git_operations.keys()),
            "package_operations": list(self.package_operations.keys()),
            "env_operations": list(self.env_operations.keys())
        }
