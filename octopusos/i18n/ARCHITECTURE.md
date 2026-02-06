# AgentOS i18n 架构图

## 系统架构

```mermaid
graph TB
    User[用户/User] -->|启动/Start| CLI[CLI Main]
    CLI -->|加载配置/Load Config| Settings[CLISettings]
    Settings -->|初始化语言/Init Language| LocaleMgr[LocaleManager]
    
    LocaleMgr -->|加载翻译/Load| EN[en.json]
    LocaleMgr -->|加载翻译/Load| ZH[zh_CN.json]
    
    Interactive[Interactive CLI] -->|调用/Call| T[t function]
    T -->|查询/Query| LocaleMgr
    LocaleMgr -->|返回翻译/Return| Interactive
    
    Interactive -->|切换语言/Switch| SettingsMenu[Settings Menu]
    SettingsMenu -->|更新/Update| Settings
    Settings -->|保存/Save| ConfigFile[~/.agentos/settings.json]
    SettingsMenu -->|应用/Apply| LocaleMgr
    
    style LocaleMgr fill:#e1f5ff
    style Settings fill:#fff9e6
    style ConfigFile fill:#e8f5e9
```

## 数据流

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Settings
    participant LocaleManager
    participant Interactive
    
    User->>CLI: uv run agentos
    CLI->>Settings: load_settings()
    Settings-->>CLI: language="en"
    CLI->>LocaleManager: set_language("en")
    LocaleManager->>LocaleManager: Load en.json
    CLI->>Interactive: interactive_main()
    
    Interactive->>LocaleManager: t("cli.interactive.welcome.title")
    LocaleManager-->>Interactive: "AgentOS CLI - Task Control Plane"
    Interactive->>User: Display welcome
    
    User->>Interactive: Select 5) Settings
    User->>Interactive: Select 4) Language
    User->>Interactive: Select 2) 简体中文
    
    Interactive->>Settings: set_language("zh_CN")
    Interactive->>Settings: save_settings()
    Settings->>Settings: Write to ~/.agentos/settings.json
    Interactive->>LocaleManager: set_language("zh_CN")
    LocaleManager->>LocaleManager: Load zh_CN.json
    
    Interactive->>LocaleManager: t("cli.interactive.menu.title")
    LocaleManager-->>Interactive: "主菜单"
    Interactive->>User: Display in Chinese
```

## 文件结构

```
AgentOS/
├── agentos/
│   ├── i18n/                    # 国际化模块
│   │   ├── __init__.py         # 导出 API
│   │   ├── locale_manager.py   # LocaleManager 类
│   │   ├── locales/            # 翻译文件
│   │   │   ├── en.json        # 英语
│   │   │   └── zh_CN.json     # 简体中文
│   │   └── README.md          # i18n 文档
│   │
│   ├── config/
│   │   └── cli_settings.py     # ✨ 添加 language 字段
│   │
│   └── cli/
│       ├── main.py             # ✨ 初始化语言
│       └── interactive.py      # ✨ 使用翻译
│
├── ~/.agentos/
│   └── settings.json           # 配置持久化
│
└── I18N_IMPLEMENTATION_COMPLETE.md  # 实施报告
```

## 翻译键层级

```mermaid
graph LR
    Root[Translation Keys] --> CLI[cli.*]
    
    CLI --> Interactive[cli.interactive.*]
    CLI --> Task[cli.task.*]
    CLI --> Settings[cli.settings.*]
    
    Interactive --> Welcome[welcome.*]
    Interactive --> Menu[menu.*]
    
    Task --> New[new.*]
    Task --> List[list.*]
    Task --> Resume[resume.*]
    Task --> Inspect[inspect.*]
    Task --> Approval[approval.*]
    Task --> Plan[plan.*]
    
    Settings --> RunMode[run_mode.*]
    Settings --> Language[language.*]
    Settings --> ModelPolicy[model_policy.*]
    
    style Root fill:#ff9999
    style CLI fill:#ffcc99
    style Task fill:#ffff99
    style Settings fill:#99ff99
```

## 关键组件

### LocaleManager

```python
class LocaleManager:
    """单例模式的语言管理器"""
    
    def __init__(self):
        self.current_language = "en"
        self.translations = {}  # {lang: {key: value}}
    
    def translate(self, key: str, **kwargs) -> str:
        """翻译键，支持参数插值"""
        # 1. 查找当前语言
        # 2. 如果没有，回退到英语
        # 3. 插值参数
        # 4. 返回结果
```

### CLISettings

```python
@dataclass
class CLISettings:
    language: str = "en"
    
    def set_language(self, lang: str):
        self.language = lang
```

### 使用示例

```python
from agentos.i18n import t

# 简单使用
print(t("cli.interactive.welcome.title"))

# 带参数
print(t("cli.task.list.found", count=5))
```

---

**实施日期**: 2026-01-26  
**版本**: 1.0  
**状态**: ✅ 已完成
