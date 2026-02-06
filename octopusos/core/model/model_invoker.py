"""
Model Invoker - 统一的模型调用接口

支持：
- CLI 方式调用
- API 方式调用
- 自动根据配置选择调用方式
- 授权检查
"""

import subprocess
import shlex
import logging
from typing import Dict, Any, List

from agentos.core.model import ModelRegistry, InvocationConfig, ModelCredentialsError
from agentos.config.cli_settings import load_settings

logger = logging.getLogger(__name__)


class ModelInvoker:
    """统一的模型调用接口"""
    
    def __init__(self):
        """初始化调用器"""
        self.registry = ModelRegistry.get_instance()
        self.settings = load_settings()
    
    def invoke(self, model_key: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """统一调用接口（自动选择 CLI 或 API）
        
        Args:
            model_key: 模型 key 格式 "model_id@brand" 或 直接 model_id
            prompt: 提示词
            **kwargs: 额外参数
            
        Returns:
            {"response": str, "method": "cli"|"api", "metadata": dict}
            
        Raises:
            ModelCredentialsError: 缺少授权信息
        """
        # 解析 model_key
        if "@" in model_key:
            model_id, brand = model_key.split("@", 1)
        else:
            # 如果没有指定 brand，尝试查找
            model_id = model_key
            brand = self._find_brand_for_model(model_id)
        
        # 检查授权
        has_creds, missing_info = self.registry.check_credentials(brand, model_id)
        if not has_creds:
            raise ModelCredentialsError(
                f"Model '{model_id}@{brand}' requires credentials: {missing_info}"
            )
        
        # 获取调用配置
        config = self.registry.get_invocation_config(brand, model_id)
        
        # 根据配置选择调用方式
        if config.method == "cli":
            return self.invoke_cli(model_id, brand, prompt, config, **kwargs)
        elif config.method == "api":
            return self.invoke_api(model_id, brand, prompt, config, **kwargs)
        else:
            raise ValueError(f"Unknown invocation method: {config.method}")
    
    def invoke_cli(
        self,
        model_id: str,
        brand: str,
        prompt: str,
        config: InvocationConfig,
        **kwargs
    ) -> Dict[str, Any]:
        """CLI 方式调用 - 使用安全的列表形式

        Args:
            model_id: 模型 ID
            brand: 品牌名称
            prompt: 提示词
            config: 调用配置
            **kwargs: 额外参数

        Returns:
            调用结果

        Security:
            使用列表形式避免命令注入攻击。不使用 shell=True。
        """
        # 优先使用安全的 cli_command_list
        if config.cli_command_list:
            cmd = self._build_safe_command_list(
                config.cli_command_list,
                model_id=model_id,
                prompt=prompt,
                **kwargs
            )
        elif config.cli_command:
            # 向后兼容旧的 cli_command，但使用 shlex.quote 保护
            logger.warning(
                f"Using deprecated cli_command for {brand}. "
                "Please migrate to cli_command_list for better security."
            )
            cmd = self._build_legacy_command(
                config.cli_command,
                model_id=model_id,
                prompt=prompt,
                **kwargs
            )
        else:
            raise ValueError(f"CLI command not configured for {model_id}@{brand}")

        try:
            # 执行命令 - 不使用 shell=True
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=kwargs.get("timeout", 60)
            )

            if result.returncode != 0:
                raise RuntimeError(f"CLI command failed: {result.stderr}")

            return {
                "response": result.stdout,
                "method": "cli",
                "metadata": {
                    "command": " ".join(cmd) if isinstance(cmd, list) else cmd,
                    "returncode": result.returncode,
                    "stderr": result.stderr
                }
            }
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"CLI command timed out after {kwargs.get('timeout', 60)}s")
        except Exception as e:
            raise RuntimeError(f"CLI invocation failed: {e}")

    def _build_safe_command_list(
        self,
        template: List[str],
        **kwargs
    ) -> List[str]:
        """安全地构建命令列表

        Args:
            template: 命令模板列表，如 ["codex", "{prompt}"]
            **kwargs: 模板变量

        Returns:
            安全的命令列表
        """
        cmd = []
        for part in template:
            # 替换模板变量，但不执行 shell 展开
            replaced = part
            for key, value in kwargs.items():
                placeholder = f"{{{key}}}"
                if placeholder in replaced:
                    # 将值转换为字符串，但不需要 shlex.quote (列表形式已经安全)
                    replaced = replaced.replace(placeholder, str(value))
            cmd.append(replaced)
        return cmd

    def _build_legacy_command(
        self,
        template: str,
        **kwargs
    ) -> List[str]:
        """为旧的 cli_command 构建安全命令 (向后兼容)

        Args:
            template: 命令模板字符串，如 "codex {prompt}"
            **kwargs: 模板变量

        Returns:
            安全的命令列表

        Note:
            使用 shlex.split 解析，并对用户输入进行转义
        """
        # 首先转义所有用户输入
        safe_kwargs = {k: shlex.quote(str(v)) for k, v in kwargs.items()}

        # 格式化命令字符串
        command_str = template.format(**safe_kwargs)

        # 使用 shlex.split 安全地解析为列表
        try:
            cmd = shlex.split(command_str)
            return cmd
        except ValueError as e:
            raise ValueError(f"Invalid command template: {template}") from e
    
    def invoke_api(
        self, 
        model_id: str, 
        brand: str, 
        prompt: str, 
        config: InvocationConfig,
        **kwargs
    ) -> Dict[str, Any]:
        """API 方式调用
        
        Args:
            model_id: 模型 ID
            brand: 品牌名称
            prompt: 提示词
            config: 调用配置
            **kwargs: 额外参数
            
        Returns:
            调用结果
        """
        if not config.api_endpoint:
            raise ValueError(f"API endpoint not configured for {model_id}@{brand}")
        
        # 根据品牌调用对应的 adapter
        try:
            if brand == "Ollama":
                from agentos.ext.tools.ollama_adapter import OllamaAdapter
                adapter = OllamaAdapter(model_id)
            elif brand == "LMStudio":
                from agentos.ext.tools.lmstudio_adapter import LMStudioAdapter
                adapter = LMStudioAdapter(model_id)
            elif brand == "OpenAI":
                from agentos.ext.tools.openai_chat_adapter import OpenAIChatAdapter
                adapter = OpenAIChatAdapter(model_id)
            else:
                raise ValueError(f"Unsupported brand for API invocation: {brand}")
            
            # 调用 adapter
            # 注意：这里简化了，实际应该调用 adapter.run() 方法
            # 但需要根据具体 adapter 的接口调整
            
            return {
                "response": f"[API call to {model_id}@{brand} - not fully implemented]",
                "method": "api",
                "metadata": {
                    "endpoint": config.api_endpoint,
                    "brand": brand
                }
            }
        except Exception as e:
            raise RuntimeError(f"API invocation failed: {e}")
    
    def _find_brand_for_model(self, model_id: str) -> str:
        """根据模型 ID 查找品牌
        
        Args:
            model_id: 模型 ID
            
        Returns:
            品牌名称
            
        Raises:
            ValueError: 如果找不到对应的品牌
        """
        # 简化实现：遍历所有品牌查找模型
        all_brands = self.registry.list_local_brands() + self.registry.list_cloud_brands()
        
        for brand in all_brands:
            models = self.registry.list_models_by_brand(brand)
            for model in models:
                if model.model_id == model_id:
                    return brand
        
        raise ValueError(f"Cannot find brand for model: {model_id}")
