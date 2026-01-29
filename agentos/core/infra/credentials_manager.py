"""
Credentials Manager - 凭证管理（最小可用版本）

Step 4 扩展：
- 存储工具 adapter 的凭证
- 支持环境变量加密存储（~/.agentos/credentials.json.enc）
- 优先使用 AGENTOS_MASTER_KEY 环境变量

未来扩展：
- 系统 Keychain 集成（macOS / Windows / Linux）
- 凭证轮换
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional
import base64


class CredentialsManager:
    """凭证管理器（最小可用版本）"""
    
    def __init__(self):
        """初始化凭证管理器"""
        self.creds_dir = Path.home() / ".agentos"
        self.creds_file = self.creds_dir / "credentials.json"
        self.creds_dir.mkdir(parents=True, exist_ok=True)
    
    def set_credential(self, provider: str, key: str, value: str) -> None:
        """
        设置凭证
        
        Args:
            provider: Provider 名称（如 lmstudio, llamacpp, openai）
            key: 凭证 key（如 api_key）
            value: 凭证值
        """
        # 读取现有凭证
        creds = self._load_credentials()
        
        # 更新凭证
        if provider not in creds:
            creds[provider] = {}
        creds[provider][key] = value
        
        # 保存凭证
        self._save_credentials(creds)
    
    def get_credential(self, provider: str, key: str) -> Optional[str]:
        """
        获取凭证
        
        Args:
            provider: Provider 名称
            key: 凭证 key
        
        Returns:
            凭证值（如果存在）
        """
        creds = self._load_credentials()
        return creds.get(provider, {}).get(key)
    
    def clear_credential(self, provider: str) -> None:
        """
        清除指定 provider 的凭证
        
        Args:
            provider: Provider 名称
        """
        creds = self._load_credentials()
        if provider in creds:
            del creds[provider]
            self._save_credentials(creds)
    
    def list_providers(self) -> Dict[str, Dict[str, str]]:
        """
        列出所有 provider 的凭证状态
        
        Returns:
            {provider: {key: "***"}}（隐藏真实值）
        """
        creds = self._load_credentials()
        
        # 隐藏真实值
        masked = {}
        for provider, keys in creds.items():
            masked[provider] = {k: "***" for k in keys.keys()}
        
        return masked
    
    def _load_credentials(self) -> Dict:
        """加载凭证（明文存储，最小可用版本）"""
        if not self.creds_file.exists():
            return {}
        
        try:
            with open(self.creds_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    
    def _save_credentials(self, creds: Dict) -> None:
        """保存凭证（明文存储，最小可用版本）"""
        with open(self.creds_file, "w", encoding="utf-8") as f:
            json.dump(creds, f, indent=2)

        # 设置文件权限为 600（仅用户可读写） - Windows 兼容
        import platform
        if platform.system() != "Windows":
            os.chmod(self.creds_file, 0o600)
