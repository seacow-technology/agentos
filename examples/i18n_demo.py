#!/usr/bin/env python3
"""
AgentOS i18n 使用示例

演示如何在 AgentOS 中使用国际化功能
"""

from agentos.i18n import t, set_language, get_available_languages, get_language


def demo_basic_translation():
    """基础翻译演示"""
    print("=" * 60)
    print("1. 基础翻译演示")
    print("=" * 60)
    
    # 英语
    set_language("en")
    print(f"\nCurrent language: {get_language()}")
    print(f"Welcome: {t('cli.interactive.welcome.title')}")
    print(f"Menu: {t('cli.interactive.menu.title')}")
    
    # 中文
    set_language("zh_CN")
    print(f"\n当前语言: {get_language()}")
    print(f"欢迎: {t('cli.interactive.welcome.title')}")
    print(f"菜单: {t('cli.interactive.menu.title')}")


def demo_parameter_interpolation():
    """参数插值演示"""
    print("\n" + "=" * 60)
    print("2. 参数插值演示")
    print("=" * 60)
    
    # 英语
    set_language("en")
    print(f"\nEnglish:")
    print(f"  {t('cli.task.list.found', count=5)}")
    print(f"  {t('cli.task.new.task_id', task_id='abc123')}")
    
    # 中文
    set_language("zh_CN")
    print(f"\n中文:")
    print(f"  {t('cli.task.list.found', count=5)}")
    print(f"  {t('cli.task.new.task_id', task_id='abc123')}")


def demo_available_languages():
    """Available语言列表演示"""
    print("\n" + "=" * 60)
    print("3. Available语言列表")
    print("=" * 60)
    
    languages = get_available_languages()
    print(f"\nSupported languages:")
    for code, name in languages.items():
        print(f"  {code}: {name}")


def demo_settings_integration():
    """配置集成演示"""
    print("\n" + "=" * 60)
    print("4. 配置集成演示")
    print("=" * 60)
    
    from agentos.config import load_settings, save_settings
    
    # 加载设置
    settings = load_settings()
    print(f"\nCurrent language in settings: {settings.language}")
    
    # 更改语言
    original_lang = settings.language
    settings.set_language("zh_CN")
    save_settings(settings)
    print(f"Updated language to: {settings.language}")
    
    # 重新加载验证
    settings2 = load_settings()
    print(f"Reloaded language: {settings2.language}")
    
    # 恢复原始语言
    settings2.set_language(original_lang)
    save_settings(settings2)
    print(f"\nRestored original language: {original_lang}")


def demo_fallback_behavior():
    """回退行为演示"""
    print("\n" + "=" * 60)
    print("5. 回退行为演示")
    print("=" * 60)
    
    # 尝试不存在的键
    set_language("en")
    print(f"\nTrying non-existent key:")
    result = t("non.existent.key")
    print(f"  Result: {result}")
    print(f"  (Returns the key itself when translation not found)")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("AgentOS i18n 功能演示")
    print("AgentOS i18n Feature Demo")
    print("=" * 60)
    
    demo_basic_translation()
    demo_parameter_interpolation()
    demo_available_languages()
    demo_settings_integration()
    demo_fallback_behavior()
    
    print("\n" + "=" * 60)
    print("演示完成 / Demo Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
