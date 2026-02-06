"""Model management command handlers."""

from agentos.core.command import (
    CommandMetadata,
    CommandContext,
    CommandResult,
    CommandCategory,
    CommandRegistry,
)
from agentos.core.model import ModelRegistry


def register_model_commands(registry: CommandRegistry) -> None:
    """注册模型相关命令到统一注册表
    
    Args:
        registry: 命令注册表实例
    """
    
    # model:select - 选择模型（三级导航入口）
    registry.register(CommandMetadata(
        id="model:select",
        title="Select Model",
        hint="Choose a model (local/cloud)",
        category=CommandCategory.MODEL,
        handler=_handle_model_select,
    ))
    
    # model:test_single - 测试单个模型
    registry.register(CommandMetadata(
        id="model:test_single",
        title="Test Model",
        hint="Test connectivity of a single model",
        category=CommandCategory.MODEL,
        handler=_handle_test_single,
        needs_arg=True,
    ))
    
    # model:test_brand - 测试品牌下所有模型
    registry.register(CommandMetadata(
        id="model:test_brand",
        title="Test Brand Models",
        hint="Test all models from a brand",
        category=CommandCategory.MODEL,
        handler=_handle_test_brand,
        needs_arg=True,
    ))
    
    # model:test_all - 测试所有模型
    registry.register(CommandMetadata(
        id="model:test_all",
        title="Test All Models",
        hint="Test connectivity of all configured models",
        category=CommandCategory.MODEL,
        handler=_handle_test_all,
    ))
    
    # model:bind_mode - 为 mode 绑定模型
    registry.register(CommandMetadata(
        id="model:bind_mode",
        title="Bind Mode to Model",
        hint="Configure which model a mode uses",
        category=CommandCategory.MODEL,
        handler=_handle_bind_mode,
    ))
    
    # model:bind_stage - 为 stage 绑定模型
    registry.register(CommandMetadata(
        id="model:bind_stage",
        title="Bind Stage to Model",
        hint="Configure which model a stage uses",
        category=CommandCategory.MODEL,
        handler=_handle_bind_stage,
    ))
    
    # model:configure_invocation - 配置调用方式
    registry.register(CommandMetadata(
        id="model:configure_invocation",
        title="Configure Invocation",
        hint="Choose CLI or API invocation method",
        category=CommandCategory.MODEL,
        handler=_handle_configure_invocation,
    ))
    
    # model:setup_credentials - 配置授权信息
    registry.register(CommandMetadata(
        id="model:setup_credentials",
        title="Setup Credentials",
        hint="Configure API keys and authentication",
        category=CommandCategory.MODEL,
        handler=_handle_setup_credentials,
    ))


# ========== 命令处理器实现 ==========

def _handle_model_select(context: CommandContext, **kwargs) -> CommandResult:
    """处理模型选择命令（UI 导航入口）"""
    # 实际逻辑在 UI 层处理（推送 ModelSelector 屏幕）
    return CommandResult.success(summary="Opening model selector...")


def _handle_test_single(context: CommandContext, model_key: str = None, **kwargs) -> CommandResult:
    """测试单个模型连通性
    
    Args:
        model_key: 格式 "model_id@brand"，如 "gpt-4@OpenAI"
    """
    if not model_key:
        return CommandResult.failure("Missing model_key argument")
    
    try:
        # 解析 model_key
        if "@" not in model_key:
            return CommandResult.failure(f"Invalid model_key format: {model_key}. Expected 'model_id@brand'")
        
        model_id, brand = model_key.split("@", 1)
        
        # 执行连通性测试
        registry = ModelRegistry.get_instance()
        health = registry.test_connectivity(brand, model_id)
        
        return CommandResult.success(
            data={"model_id": model_id, "brand": brand, "health": health},
            summary=f"{health.status}: {health.details}"
        )
    except Exception as e:
        return CommandResult.failure(f"Test failed: {e}")


def _handle_test_brand(context: CommandContext, brand: str = None, **kwargs) -> CommandResult:
    """测试品牌下所有模型"""
    if not brand:
        return CommandResult.failure("Missing brand argument")
    
    try:
        registry = ModelRegistry.get_instance()
        models = registry.list_models_by_brand(brand)
        
        if not models:
            return CommandResult.success(
                data=[],
                summary=f"No models found for brand: {brand}"
            )
        
        # 测试每个模型
        results = []
        for model in models:
            health = registry.test_connectivity(brand, model.model_id)
            results.append({
                "model_id": model.model_id,
                "status": health.status,
                "details": health.details
            })
        
        connected_count = sum(1 for r in results if r["status"] == "connected")
        
        return CommandResult.success(
            data=results,
            summary=f"Tested {len(results)} models from {brand}: {connected_count} connected"
        )
    except Exception as e:
        return CommandResult.failure(f"Test failed: {e}")


def _handle_test_all(context: CommandContext, **kwargs) -> CommandResult:
    """测试所有模型"""
    try:
        registry = ModelRegistry.get_instance()
        results = registry.test_all_models()
        
        connected_count = sum(1 for h in results.values() if h.status == "connected")
        total_count = len(results)
        
        return CommandResult.success(
            data=results,
            summary=f"Tested {total_count} models: {connected_count} connected"
        )
    except Exception as e:
        return CommandResult.failure(f"Test failed: {e}")


def _handle_bind_mode(context: CommandContext, **kwargs) -> CommandResult:
    """为 mode 绑定模型（UI 导航入口）"""
    # 实际逻辑在 UI 层处理
    return CommandResult.success(summary="Opening mode binding screen...")


def _handle_bind_stage(context: CommandContext, **kwargs) -> CommandResult:
    """为 stage 绑定模型（UI 导航入口）"""
    # 实际逻辑在 UI 层处理
    return CommandResult.success(summary="Opening stage binding screen...")


def _handle_configure_invocation(context: CommandContext, **kwargs) -> CommandResult:
    """配置调用方式（UI 导航入口）"""
    # 实际逻辑在 UI 层处理
    return CommandResult.success(summary="Opening invocation config screen...")


def _handle_setup_credentials(context: CommandContext, **kwargs) -> CommandResult:
    """配置授权信息（UI 导航入口）"""
    # 实际逻辑在 UI 层处理
    return CommandResult.success(summary="Opening credentials setup screen...")
