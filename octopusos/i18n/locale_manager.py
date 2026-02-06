"""Locale Manager - Language localization support for AgentOS CLI"""

import json
from pathlib import Path
from typing import Dict, Optional


class LocaleManager:
    """Manages language localization for AgentOS CLI
    
    Features:
    - Load translations from JSON files
    - Support parameter interpolation (e.g., t("msg", count=5))
    - Fallback to English if translation missing
    - Thread-safe singleton pattern
    """
    
    _instance: Optional["LocaleManager"] = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize locale manager"""
        if self._initialized:
            return
        
        self.current_language = "en"
        self.translations: Dict[str, Dict[str, str]] = {}
        self.locales_dir = Path(__file__).parent / "locales"
        
        # Load default language
        self._load_locale("en")
        self._initialized = True
    
    def _load_locale(self, lang: str) -> bool:
        """Load translations for a specific language
        
        Args:
            lang: Language code (e.g., "en", "zh_CN")
            
        Returns:
            True if loaded successfully, False otherwise
        """
        locale_file = self.locales_dir / f"{lang}.json"
        
        if not locale_file.exists():
            print(f"Warning: Locale file not found: {locale_file}")
            return False
        
        try:
            with open(locale_file, "r", encoding="utf-8") as f:
                self.translations[lang] = json.load(f)
            return True
        except Exception as e:
            print(f"Error loading locale {lang}: {e}")
            return False
    
    def set_language(self, lang: str) -> bool:
        """Set current language
        
        Args:
            lang: Language code (e.g., "en", "zh_CN")
            
        Returns:
            True if language was set successfully
        """
        # Load language if not already loaded
        if lang not in self.translations:
            if not self._load_locale(lang):
                return False
        
        self.current_language = lang
        return True
    
    def get_language(self) -> str:
        """Get current language code"""
        return self.current_language
    
    def translate(self, key: str, **kwargs) -> str:
        """Translate a key to current language
        
        Args:
            key: Translation key (e.g., "cli.interactive.welcome")
            **kwargs: Parameters for interpolation
            
        Returns:
            Translated string with parameters interpolated
            
        Examples:
            >>> t("cli.task.count", count=5)
            "Found 5 tasks"
        """
        # Get translation for current language
        translation = self.translations.get(self.current_language, {}).get(key)
        
        # Fallback to English if not found
        if translation is None and self.current_language != "en":
            translation = self.translations.get("en", {}).get(key)
        
        # Fallback to key itself if still not found
        if translation is None:
            return key
        
        # Interpolate parameters
        if kwargs:
            try:
                return translation.format(**kwargs)
            except KeyError as e:
                print(f"Warning: Missing parameter {e} for key {key}")
                return translation
        
        return translation
    
    def get_available_languages(self) -> Dict[str, str]:
        """Get available languages with their display names
        
        Returns:
            Dict mapping language code to display name
        """
        return {
            "en": "English",
            "zh_CN": "简体中文"
        }


# Global instance
_locale_manager: Optional[LocaleManager] = None


def get_locale_manager() -> LocaleManager:
    """Get global locale manager instance"""
    global _locale_manager
    if _locale_manager is None:
        _locale_manager = LocaleManager()
    return _locale_manager


def set_language(lang: str) -> bool:
    """Set current language
    
    Args:
        lang: Language code (e.g., "en", "zh_CN")
        
    Returns:
        True if language was set successfully
    """
    return get_locale_manager().set_language(lang)


def get_language() -> str:
    """Get current language code"""
    return get_locale_manager().get_language()


def t(key: str, **kwargs) -> str:
    """Translate a key to current language (convenience function)
    
    Args:
        key: Translation key (e.g., "cli.interactive.welcome")
        **kwargs: Parameters for interpolation
        
    Returns:
        Translated string
    """
    return get_locale_manager().translate(key, **kwargs)


def get_available_languages() -> Dict[str, str]:
    """Get available languages with their display names"""
    return get_locale_manager().get_available_languages()
