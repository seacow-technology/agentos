# AgentOS 国际化 (i18n) 功能

## 快速开始

### 用户使用

启动 AgentOS CLI 并切换语言：

```bash
# 1. 启动 Interactive CLI（默认英语）
uv run agentos

# 2. 选择 5) Settings
# 3. 选择 4) Language / 语言
# 4. 选择语言：
#    1) English
#    2) 简体中文
```

语言设置会自动保存，下次启动时生效。

### 开发者使用

在代码中使用翻译功能：

```python
from agentos.i18n import t, set_language, get_available_languages

# 设置语言
set_language("en")   # 英语
set_language("zh_CN")  # 简体中文

# 简单翻译
title = t("cli.interactive.welcome.title")

# 带参数的翻译
message = t("cli.task.list.found", count=5)

# 获取可用语言
languages = get_available_languages()
# 返回: {'en': 'English', 'zh_CN': '简体中文'}
```

## 支持的语言

- **English** (`en`) - 默认语言
- **简体中文** (`zh_CN`)

## 翻译文件

翻译文件位于 `agentos/i18n/locales/`:

```
agentos/i18n/locales/
├── en.json      # 英语翻译
└── zh_CN.json   # 简体中文翻译
```

## 添加新翻译

### 1. 添加翻译键

在 `en.json` 和 `zh_CN.json` 中添加相同的键：

```json
// en.json
{
  "new.feature.title": "New Feature"
}

// zh_CN.json
{
  "new.feature.title": "新功能"
}
```

### 2. 在代码中使用

```python
from agentos.i18n import t
print(t("new.feature.title"))
```

## 键命名规范

使用分层结构：`<module>.<component>.<element>`

示例：
- `cli.interactive.menu.title` - CLI 交互式菜单标题
- `cli.task.new.created` - 任务创建成功消息
- `cli.settings.language.updated` - 语言更新消息

## 配置

语言设置保存在 `~/.agentos/settings.json`:

```json
{
  "language": "en",
  "default_run_mode": "assisted",
  ...
}
```

## 测试

运行快速测试：

```bash
python3 test_i18n_quick.py
```

## 特性

- ✅ 参数插值支持
- ✅ 自动回退到英语（翻译缺失时）
- ✅ 配置持久化
- ✅ 线程安全
- ✅ 单例模式

## 实施文档

详细实施文档请参阅：[I18N_IMPLEMENTATION_COMPLETE.md](../I18N_IMPLEMENTATION_COMPLETE.md)
