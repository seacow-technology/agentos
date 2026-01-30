"""
Model Registry - 全局模型注册表

负责：
- 管理所有Available模型（本地 + 云端）
- 查询模型列表（动态 API 查询）
- 检测调用方式（CLI vs API）
- 检查授权信息
- 测试连通性
"""

import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# requests 是可选依赖（用于 API 调用）
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None

from agentos.ext.tools.types import ToolHealth


class ModelCredentialsError(Exception):
    """模型授权信息缺失错误"""
    pass


@dataclass
class InvocationConfig:
    """调用配置"""
    method: str  # "cli" or "api"
    cli_command: Optional[str] = None  # CLI 命令模板，如 "codex {prompt}" (已废弃，不安全)
    cli_command_list: Optional[List[str]] = None  # CLI 命令列表模板(推荐), 如 ["codex", "{prompt}"]
    api_endpoint: Optional[str] = None  # API 端点，如 "http://localhost:11434"
    requires_auth: bool = True  # 是否需要鉴权
    auth_env_vars: List[str] = field(default_factory=list)  # 需要的环境变量


@dataclass
class ModelInfo:
    """模型信息"""
    model_id: str
    brand: str  # "Ollama", "OpenAI", "Codex", etc.
    source: str  # "local" or "cloud"
    adapter_type: str
    invocation_method: str  # "cli" or "api"
    is_available: bool
    has_credentials: bool  # 是否配置了授权信息
    last_check: Optional[datetime] = None


class ModelRegistry:
    """全局模型注册表（单例）"""
    
    _instance: Optional["ModelRegistry"] = None
    
    # 品牌定义
    LOCAL_BRANDS = ["Ollama", "LMStudio", "llamacpp"]
    CLOUD_BRANDS = ["OpenAI", "Anthropic", "Codex", "Claude-Code-CLI", "GenericCloud"]
    
    # 默认调用配置（按品牌）
    DEFAULT_INVOCATION_CONFIGS = {
        "Ollama": InvocationConfig(
            method="api",
            api_endpoint="http://localhost:11434",
            requires_auth=False,
        ),
        "LMStudio": InvocationConfig(
            method="api",
            api_endpoint="http://localhost:1234",
            requires_auth=False,
        ),
        "llamacpp": InvocationConfig(
            method="cli",
            cli_command_list=["llama-cpp-cli", "--model", "{model_id}", "--prompt", "{prompt}"],
            requires_auth=False,
        ),
        "OpenAI": InvocationConfig(
            method="api",
            api_endpoint="https://api.openai.com/v1",
            requires_auth=True,
            auth_env_vars=["OPENAI_API_KEY"],
        ),
        "Anthropic": InvocationConfig(
            method="api",
            api_endpoint="https://api.anthropic.com/v1",
            requires_auth=True,
            auth_env_vars=["ANTHROPIC_API_KEY"],
        ),
        "Codex": InvocationConfig(
            method="cli",
            cli_command_list=["codex", "{prompt}"],
            requires_auth=True,
            auth_env_vars=["CODEX_API_KEY"],  # 可能需要的授权
        ),
        "Claude-Code-CLI": InvocationConfig(
            method="cli",
            cli_command_list=["claude-code-cli", "{prompt}"],
            requires_auth=True,
            auth_env_vars=["ANTHROPIC_API_KEY"],
        ),
    }
    
    def __init__(self):
        """初始化注册表"""
        self._cache: Dict[str, List[ModelInfo]] = {}
        self._cache_timestamp: Dict[str, datetime] = {}
        self._cache_ttl = 300  # 缓存 5 分钟
    
    @classmethod
    def get_instance(cls) -> "ModelRegistry":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def list_local_brands(self) -> List[str]:
        """列出本地品牌"""
        return self.LOCAL_BRANDS.copy()
    
    def list_cloud_brands(self) -> List[str]:
        """列出云端品牌"""
        return self.CLOUD_BRANDS.copy()
    
    def list_models_by_brand(self, brand: str, force_refresh: bool = False) -> List[ModelInfo]:
        """查询某品牌下的模型列表
        
        Args:
            brand: 品牌名称
            force_refresh: 是否强制刷新缓存
            
        Returns:
            模型列表
        """
        # 检查缓存
        if not force_refresh and brand in self._cache:
            cached_time = self._cache_timestamp.get(brand)
            if cached_time and (datetime.now() - cached_time).total_seconds() < self._cache_ttl:
                return self._cache[brand]
        
        # 根据品牌查询模型
        models = []
        
        if brand == "Ollama":
            models = self._query_ollama_models()
        elif brand == "LMStudio":
            models = self._query_lmstudio_models()
        elif brand == "llamacpp":
            models = self._query_llamacpp_models()
        elif brand == "OpenAI":
            models = self._query_openai_models()
        elif brand == "Anthropic":
            models = self._query_anthropic_models()
        elif brand == "Codex":
            models = self._query_codex_models()
        elif brand == "Claude-Code-CLI":
            models = self._query_claude_code_cli_models()
        else:
            models = []
        
        # 更新缓存
        self._cache[brand] = models
        self._cache_timestamp[brand] = datetime.now()
        
        return models
    
    def get_invocation_config(self, brand: str, model_id: str) -> InvocationConfig:
        """获取模型调用配置
        
        Args:
            brand: 品牌名称
            model_id: 模型 ID
            
        Returns:
            调用配置
        """
        # 尝试从用户配置加载（Phase 5 实现）
        # 这里先返回默认配置
        return self.DEFAULT_INVOCATION_CONFIGS.get(
            brand,
            InvocationConfig(method="api", requires_auth=False)
        )
    
    def check_credentials(self, brand: str, model_id: str) -> Tuple[bool, str]:
        """检查授权信息是否配置
        
        Args:
            brand: 品牌名称
            model_id: 模型 ID
            
        Returns:
            (has_credentials, missing_info)
        """
        config = self.get_invocation_config(brand, model_id)
        
        if not config.requires_auth:
            return True, ""
        
        # 检查环境变量
        missing_vars = []
        for env_var in config.auth_env_vars:
            if not os.environ.get(env_var):
                missing_vars.append(env_var)
        
        if missing_vars:
            return False, f"Missing: {', '.join(missing_vars)}"
        
        return True, ""
    
    def test_connectivity(self, brand: str, model_id: str) -> ToolHealth:
        """测试单个模型连通性
        
        Args:
            brand: 品牌名称
            model_id: 模型 ID
            
        Returns:
            健康状态
        """
        # 检查授权
        has_creds, missing_info = self.check_credentials(brand, model_id)
        if not has_creds:
            return ToolHealth(
                status="auth_failed",
                details=missing_info
            )
        
        # 根据品牌调用对应的 adapter
        try:
            if brand == "Ollama":
                return self._test_ollama_connectivity(model_id)
            elif brand == "LMStudio":
                return self._test_lmstudio_connectivity(model_id)
            elif brand == "llamacpp":
                return self._test_llamacpp_connectivity(model_id)
            elif brand == "OpenAI":
                return self._test_openai_connectivity(model_id)
            elif brand == "Codex":
                return self._test_codex_connectivity(model_id)
            else:
                return ToolHealth(
                    status="not_configured",
                    details=f"Unknown brand: {brand}"
                )
        except Exception as e:
            return ToolHealth(
                status="unreachable",
                details=f"Test failed: {str(e)}"
            )
    
    def test_all_models(self) -> Dict[str, ToolHealth]:
        """批量测试所有模型
        
        Returns:
            {model_key: health_status}
        """
        results = {}
        
        for brand in self.LOCAL_BRANDS + self.CLOUD_BRANDS:
            models = self.list_models_by_brand(brand)
            for model in models:
                key = f"{model.model_id}@{brand}"
                results[key] = self.test_connectivity(brand, model.model_id)
        
        return results
    
    # ========== 私有方法：查询模型列表 ==========
    
    def _query_ollama_models(self) -> List[ModelInfo]:
        """查询 Ollama 模型列表"""
        if not HAS_REQUESTS:
            # 如果没有 requests，跳过 API 查询
            return []
        
        try:
            host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
            response = requests.get(f"{host}/api/tags", timeout=5)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            models = []
            
            for m in data.get("models", []):
                model_id = m["name"]
                models.append(ModelInfo(
                    model_id=model_id,
                    brand="Ollama",
                    source="local",
                    adapter_type="ollama",
                    invocation_method="api",
                    is_available=True,
                    has_credentials=True,  # Ollama 不需要授权
                    last_check=datetime.now()
                ))
            
            return models
        except Exception:
            return []
    
    def _query_lmstudio_models(self) -> List[ModelInfo]:
        """查询 LM Studio 模型列表"""
        if not HAS_REQUESTS:
            # 如果没有 requests，跳过 API 查询
            return []
        
        try:
            host = os.environ.get("LMSTUDIO_HOST", "http://localhost:1234")
            response = requests.get(f"{host}/v1/models", timeout=5)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            models = []
            
            for m in data.get("data", []):
                model_id = m["id"]
                models.append(ModelInfo(
                    model_id=model_id,
                    brand="LMStudio",
                    source="local",
                    adapter_type="lmstudio",
                    invocation_method="api",
                    is_available=True,
                    has_credentials=True,
                    last_check=datetime.now()
                ))
            
            return models
        except Exception:
            return []
    
    def _query_llamacpp_models(self) -> List[ModelInfo]:
        """查询 llama.cpp 模型列表（本地文件扫描）"""
        # 简化实现：返回预定义的常见模型
        return [
            ModelInfo(
                model_id="llama-3-8b",
                brand="llamacpp",
                source="local",
                adapter_type="llamacpp",
                invocation_method="cli",
                is_available=False,  # 需要用户手动配置
                has_credentials=True,
                last_check=datetime.now()
            )
        ]
    
    def _query_openai_models(self) -> List[ModelInfo]:
        """查询 OpenAI 模型列表"""
        # 预定义常见模型（避免频繁 API 调用）
        has_key = bool(os.environ.get("OPENAI_API_KEY"))
        
        common_models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
        models = []
        
        for model_id in common_models:
            models.append(ModelInfo(
                model_id=model_id,
                brand="OpenAI",
                source="cloud",
                adapter_type="openai_chat",
                invocation_method="api",
                is_available=has_key,
                has_credentials=has_key,
                last_check=datetime.now()
            ))
        
        return models
    
    def _query_anthropic_models(self) -> List[ModelInfo]:
        """查询 Anthropic 模型列表"""
        has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        
        common_models = ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-sonnet-20240229"]
        models = []
        
        for model_id in common_models:
            models.append(ModelInfo(
                model_id=model_id,
                brand="Anthropic",
                source="cloud",
                adapter_type="anthropic",
                invocation_method="api",
                is_available=has_key,
                has_credentials=has_key,
                last_check=datetime.now()
            ))
        
        return models
    
    def _query_codex_models(self) -> List[ModelInfo]:
        """查询 Codex 模型列表"""
        # Codex 是单一模型
        has_codex = self._check_cli_available("codex")
        
        return [
            ModelInfo(
                model_id="codex",
                brand="Codex",
                source="cloud",
                adapter_type="codex",
                invocation_method="cli",
                is_available=has_codex,
                has_credentials=has_codex,  # CLI 工具已登录
                last_check=datetime.now()
            )
        ]
    
    def _query_claude_code_cli_models(self) -> List[ModelInfo]:
        """查询 Claude Code CLI 模型列表"""
        has_cli = self._check_cli_available("claude-code-cli")
        
        return [
            ModelInfo(
                model_id="claude-code-cli",
                brand="Claude-Code-CLI",
                source="cloud",
                adapter_type="claude_cli",
                invocation_method="cli",
                is_available=has_cli,
                has_credentials=has_cli,
                last_check=datetime.now()
            )
        ]
    
    # ========== 私有方法：连通性测试 ==========
    
    def _test_ollama_connectivity(self, model_id: str) -> ToolHealth:
        """测试 Ollama 连通性"""
        try:
            from agentos.ext.tools.ollama_adapter import OllamaAdapter
            adapter = OllamaAdapter(model_id)
            return adapter.health_check()
        except Exception as e:
            return ToolHealth(status="unreachable", details=str(e))
    
    def _test_lmstudio_connectivity(self, model_id: str) -> ToolHealth:
        """测试 LM Studio 连通性"""
        try:
            from agentos.ext.tools.lmstudio_adapter import LMStudioAdapter
            adapter = LMStudioAdapter(model_id)
            return adapter.health_check()
        except Exception as e:
            return ToolHealth(status="unreachable", details=str(e))
    
    def _test_llamacpp_connectivity(self, model_id: str) -> ToolHealth:
        """测试 llama.cpp 连通性"""
        try:
            from agentos.ext.tools.llamacpp_adapter import LlamaCppAdapter
            adapter = LlamaCppAdapter(model_id)
            return adapter.health_check()
        except Exception as e:
            return ToolHealth(status="unreachable", details=str(e))
    
    def _test_openai_connectivity(self, model_id: str) -> ToolHealth:
        """测试 OpenAI 连通性"""
        try:
            from agentos.ext.tools.openai_chat_adapter import OpenAIChatAdapter
            adapter = OpenAIChatAdapter(model_id)
            return adapter.health_check()
        except Exception as e:
            return ToolHealth(status="unreachable", details=str(e))
    
    def _test_codex_connectivity(self, model_id: str) -> ToolHealth:
        """测试 Codex CLI 连通性"""
        if not self._check_cli_available("codex"):
            return ToolHealth(
                status="not_configured",
                details="codex CLI not found in PATH"
            )
        
        # 简单的版本检查
        try:
            result = subprocess.run(
                ["codex", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return ToolHealth(status="connected", details="codex CLI available")
            else:
                return ToolHealth(status="unreachable", details="codex CLI failed")
        except Exception as e:
            return ToolHealth(status="unreachable", details=str(e))
    
    def _check_cli_available(self, command: str) -> bool:
        """检查 CLI 命令是否Available"""
        try:
            result = subprocess.run(
                ["which", command],
                capture_output=True,
                text=True,
                timeout=2
            )
            return result.returncode == 0
        except Exception:
            return False
