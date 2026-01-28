"""Tool Adapter Registry - Factory pattern for adapter management."""

from typing import Dict, Type, Optional, List
from pathlib import Path

from .base_adapter import BaseToolAdapter
from .claude_cli_adapter import ClaudeCliAdapter
from .opencode_adapter import OpenCodeAdapter
from .codex_adapter import CodexAdapter
from .openai_chat_adapter import OpenAIChatAdapter
from .ollama_adapter import OllamaAdapter
from .lmstudio_adapter import LMStudioAdapter
from .llamacpp_adapter import LlamaCppAdapter


class AdapterRegistry:
    """
    Centralized registry for tool adapters.
    
    Features:
    - Factory pattern for adapter creation
    - Automatic adapter discovery
    - Capability checking
    """
    
    _adapters: Dict[str, Type[BaseToolAdapter]] = {}
    _instances: Dict[str, BaseToolAdapter] = {}
    
    @classmethod
    def register(
        cls,
        tool_type: str,
        adapter_class: Type[BaseToolAdapter]
    ) -> None:
        """
        Register an adapter class.
        
        Args:
            tool_type: Tool type identifier
            adapter_class: Adapter class to register
        """
        if tool_type in cls._adapters:
            raise ValueError(f"Adapter already registered: {tool_type}")
        
        cls._adapters[tool_type] = adapter_class
    
    @classmethod
    def get_adapter(
        cls,
        tool_type: str,
        **kwargs
    ) -> BaseToolAdapter:
        """
        Get or create adapter instance.
        
        Args:
            tool_type: Tool type identifier
            **kwargs: Additional arguments for adapter initialization
        
        Returns:
            Adapter instance
        """
        # Return cached instance if exists
        if tool_type in cls._instances:
            return cls._instances[tool_type]
        
        # Create new instance
        if tool_type not in cls._adapters:
            raise ValueError(f"Unknown tool type: {tool_type}")
        
        adapter_class = cls._adapters[tool_type]
        instance = adapter_class(**kwargs)
        
        # Cache instance
        cls._instances[tool_type] = instance
        
        return instance
    
    @classmethod
    def list_adapters(cls) -> List[str]:
        """Get list of registered adapter types."""
        return list(cls._adapters.keys())
    
    @classmethod
    def check_available(cls, tool_type: str) -> bool:
        """
        Check if adapter is available (installed and working).
        
        Args:
            tool_type: Tool type identifier
        
        Returns:
            True if adapter is available
        """
        try:
            adapter = cls.get_adapter(tool_type)
            # Try a simple operation to verify it works
            return True
        except Exception:
            return False
    
    @classmethod
    def get_capabilities(cls, tool_type: str) -> Dict:
        """
        Get adapter capabilities.
        
        Args:
            tool_type: Tool type identifier
        
        Returns:
            Dictionary of capabilities
        """
        if tool_type not in cls._adapters:
            return {"available": False}
        
        adapter_class = cls._adapters[tool_type]
        
        return {
            "available": cls.check_available(tool_type),
            "tool_type": tool_type,
            "class_name": adapter_class.__name__,
            "supports_retry": hasattr(adapter_class, "retry"),
            "supports_cost_estimation": hasattr(adapter_class, "estimate_cost")
        }
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached adapter instances."""
        cls._instances.clear()
    
    @classmethod
    def auto_discover(cls) -> None:
        """Auto-discover and register available adapters."""
        # Register built-in adapters
        adapters_to_register = [
            ("claude_cli", ClaudeCliAdapter),
            ("opencode", OpenCodeAdapter),
            ("codex", CodexAdapter),
            # Step 4: Multi-model adapters
            ("openai_chat", OpenAIChatAdapter),
            ("ollama", OllamaAdapter),
            # Step 4 扩展：LM Studio + llama.cpp
            ("lmstudio", LMStudioAdapter),
            ("llamacpp", LlamaCppAdapter),
        ]
        
        for tool_type, adapter_class in adapters_to_register:
            try:
                cls.register(tool_type, adapter_class)
            except ValueError:
                # Already registered
                pass


# Auto-register adapters on module import
AdapterRegistry.auto_discover()


def get_adapter(tool_type: str, **kwargs) -> BaseToolAdapter:
    """
    Convenience function to get adapter.
    
    Args:
        tool_type: Tool type identifier
        **kwargs: Additional arguments
    
    Returns:
        Adapter instance
    """
    return AdapterRegistry.get_adapter(tool_type, **kwargs)


def list_available_tools() -> List[Dict]:
    """
    List all available tools with their capabilities.
    
    Returns:
        List of tool info dictionaries
    """
    tools = []
    
    for tool_type in AdapterRegistry.list_adapters():
        capabilities = AdapterRegistry.get_capabilities(tool_type)
        tools.append({
            "tool_type": tool_type,
            **capabilities
        })
    
    return tools
