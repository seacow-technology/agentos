"""
Model Selection Helper - 执行引擎的模型选择逻辑

实现优先级：
1. Mode 绑定
2. Stage 绑定（ModelPolicy）
3. Codex 默认
"""

from typing import Tuple, Optional

from agentos.core.model import ModelRegistry, ModelCredentialsError
from agentos.config.cli_settings import load_settings


class ModelSelector:
    """模型选择器（用于执行引擎）"""
    
    def __init__(self):
        """初始化选择器"""
        self.registry = ModelRegistry.get_instance()
        self.settings = load_settings()
    
    def select_model_for_execution(
        self,
        mode_id: Optional[str] = None,
        stage: Optional[str] = None
    ) -> Tuple[str, str]:
        """为执行选择模型
        
        Args:
            mode_id: Mode ID（如 "planning", "implementation", "debug"）
            stage: Stage（如 "intent", "planning", "implementation"）
            
        Returns:
            (model_key, selection_reason)
            - model_key: 格式 "model_id@brand" 或 "model_id"
            - selection_reason: "mode_binding" | "stage_policy" | "default_fallback"
            
        Raises:
            ModelCredentialsError: 选中的模型缺少授权信息
        """
        model_key = None
        selection_reason = None
        
        # 优先级 1: Mode 绑定
        if mode_id and mode_id in self.settings.mode_model_bindings:
            model_key = self.settings.mode_model_bindings[mode_id]
            selection_reason = "mode_binding"
        
        # 优先级 2: Stage 绑定（现有 ModelPolicy）
        elif stage and stage in self.settings.default_model_policy:
            model_key = self.settings.default_model_policy[stage]
            selection_reason = "stage_policy"
        
        # 优先级 3: Codex 作为全局默认
        else:
            model_key = "codex"
            selection_reason = "default_fallback"
        
        # 检查授权
        if "@" in model_key:
            model_id, brand = model_key.split("@", 1)
        else:
            # 如果没有 brand，尝试查找（对于 codex 等单一模型）
            model_id = model_key
            brand = "Codex"  # 默认 codex 的品牌
        
        has_credentials, missing_info = self.registry.check_credentials(brand, model_id)
        if not has_credentials:
            raise ModelCredentialsError(
                f"Model '{model_id}@{brand}' requires credentials: {missing_info}. "
                f"Please run 'Setup Credentials' in Model Management."
            )
        
        return model_key, selection_reason
    
    def get_invocation_method(self, model_key: str) -> str:
        """获取模型调用方式
        
        Args:
            model_key: 模型 key
            
        Returns:
            "cli" 或 "api"
        """
        if "@" in model_key:
            model_id, brand = model_key.split("@", 1)
        else:
            model_id = model_key
            brand = "Codex"
        
        config = self.registry.get_invocation_config(brand, model_id)
        return config.method
