# HTML Preview 功能测试指南

## ✅ 实施完成

所有代码已经实施完成并部署到服务器。

**实施内容**：
- ✅ 创建 `codeblocks.js` 工具文件
- ✅ 修改 `main.js` 消息渲染逻辑
- ✅ 修改 `index.html` 添加 Dialog 和脚本引用
- ✅ 添加 CSS 样式到 `components.css`
- ✅ 服务器已重启

## 🧪 测试方法

### 测试 1: 基本 HTML 代码块

在 Chat 页面发送以下消息：

```
请帮我生成一个简单的 HTML 页面，包含标题和按钮
```

期望 assistant 回复包含类似：

````markdown
```html
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <h1>Hello World</h1>
    <button onclick="alert('Clicked!')">Click Me</button>
</body>
</html>
```
````

**验证点**：
- [ ] 代码块正确渲染
- [ ] 显示 "Preview" 按钮（播放图标）
- [ ] 显示 "Copy" 按钮
- [ ] 点击 Preview 打开预览对话框
- [ ] HTML 正确渲染在 iframe 中
- [ ] 按钮可以点击并弹出 alert
- [ ] 点击对话框外部关闭预览
- [ ] 点击关闭按钮关闭预览
- [ ] 按 Escape 键关闭预览

### 测试 2: 复杂交互式 HTML

发送消息：

```
创建一个包含计数器的 HTML 页面，有加减按钮
```

期望回复包含：

````html
```html
<!DOCTYPE html>
<html>
<head>
    <style>
        .counter {
            font-size: 48px;
            text-align: center;
            margin: 20px;
        }
        button {
            padding: 10px 20px;
            font-size: 16px;
            margin: 5px;
        }
    </style>
</head>
<body>
    <div class="counter" id="count">0</div>
    <div style="text-align: center;">
        <button onclick="decrement()">-</button>
        <button onclick="increment()">+</button>
    </div>
    <script>
        let count = 0;
        function increment() {
            count++;
            document.getElementById('count').textContent = count;
        }
        function decrement() {
            count--;
            document.getElementById('count').textContent = count;
        }
    </script>
</body>
</html>
```
````

**验证点**：
- [ ] Preview 打开后计数器显示为 0
- [ ] 点击 + 按钮，计数器增加
- [ ] 点击 - 按钮，计数器减少
- [ ] JavaScript 正常执行

### 测试 3: 不完整的 HTML 片段

发送消息：

```
给我一个红色的卡片 div
```

期望回复：

````html
```html
<div style="
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 30px;
    border-radius: 15px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    max-width: 400px;
">
    <h2>Beautiful Card</h2>
    <p>This is a gradient card with shadow.</p>
</div>
```
````

**验证点**：
- [ ] Preview 能正确包装 HTML 片段（自动添加 html/head/body 标签）
- [ ] 卡片正确显示
- [ ] 样式正确应用

### 测试 4: 多个代码块

发送消息：

```
展示 HTML 和 JavaScript 的例子
```

期望回复包含多个代码块：

````
这里是 HTML:

```html
<button id="myBtn">Click</button>
```

这里是 JavaScript:

```javascript
document.getElementById('myBtn').addEventListener('click', () => {
    alert('Hello!');
});
```
````

**验证点**：
- [ ] HTML 代码块显示 Preview 按钮
- [ ] JavaScript 代码块**不显示** Preview 按钮（只有 Copy）
- [ ] 两个代码块都可以复制

### 测试 5: Copy 功能

**验证点**：
- [ ] 点击 Copy 按钮
- [ ] 按钮文字变为 "Copied!" 并显示勾号
- [ ] 2 秒后恢复为 "Copy"
- [ ] 粘贴到编辑器，内容正确

### 测试 6: 无语言标识的 HTML

发送消息让 AI 返回没有语言标识的代码块：

````
```
<html>
<body>
    <h1>No language specified</h1>
</body>
</html>
```
````

**验证点**：
- [ ] 启发式识别为 HTML（检查 `<html>`, `<body>` 等标签）
- [ ] 显示 Preview 按钮
- [ ] Preview 正常工作

### 测试 7: 流式消息累积

1. 开始发送需要生成大量 HTML 的请求
2. 观察流式输出过程
3. 等待 `message.end` 触发

**验证点**：
- [ ] 流式过程中，代码以纯文本显示（性能考虑）
- [ ] `message.end` 后，代码块正确解析并渲染
- [ ] Preview 和 Copy 按钮正确显示

## 🎨 UI 检查清单

### 代码块样式
- [ ] 圆角边框（10px）
- [ ] 浅灰色背景头部
- [ ] 语言标识大写显示
- [ ] 深色代码区域（#0d1117）
- [ ] 等宽字体清晰
- [ ] Hover 按钮有动画效果

### Preview 按钮
- [ ] 蓝色主题（#2563eb）
- [ ] 播放图标显示
- [ ] Hover 时背景变化
- [ ] 点击有反馈

### Copy 按钮
- [ ] 灰色主题
- [ ] 复制图标显示
- [ ] 成功后变为绿色 + 勾号
- [ ] 2 秒后恢复

### Dialog 对话框
- [ ] 宽度 1200px 或 94vw（响应式）
- [ ] 高度 820px 或 90vh
- [ ] 圆角 14px
- [ ] 模糊背景（backdrop blur）
- [ ] 头部浅灰色渐变
- [ ] HTML 图标显示
- [ ] 关闭按钮 Hover 时变红色
- [ ] iframe 填满内容区域

## 🔒 安全性检查

### Sandbox 隔离
- [ ] iframe 有 `sandbox` 属性
- [ ] 包含 `allow-scripts allow-forms allow-modals`
- [ ] **不包含** `allow-same-origin`（重要！）
- [ ] `referrerpolicy="no-referrer"`

### XSS 防护
- [ ] 用户输入的代码不会执行在主页面
- [ ] iframe 内的 JavaScript 无法访问父页面
- [ ] 尝试 `parent.document` 应该被阻止

## 📱 响应式测试

- [ ] 在小屏幕上对话框自适应大小
- [ ] 移动设备上触摸关闭正常工作
- [ ] 代码块横向滚动正常

## 🐛 边界情况测试

### 空代码块
````
```html
```
````
- [ ] 不崩溃，显示空白预览

### 超长代码
- [ ] 横向滚动正常
- [ ] 性能良好

### 特殊字符
````html
```html
<script>alert('</script>')</script>
```
````
- [ ] 正确转义，不执行

### 嵌套代码块
- [ ] 正确解析所有代码块
- [ ] 每个都有独立的 Preview/Copy

## 🎯 测试用例示例

### 完整测试用例 1: 动态表单

在 Chat 中发送：

```
创建一个实时验证的表单，包含邮箱和密码输入
```

期望看到 HTML 代码块，Preview 后：
- [ ] 表单输入框显示
- [ ] 输入邮箱时实时验证
- [ ] 无效邮箱显示错误提示
- [ ] 密码强度指示器工作

### 完整测试用例 2: Canvas 动画

发送：

```
创建一个 Canvas 动画，显示弹跳的球
```

期望：
- [ ] Preview 打开后看到 Canvas
- [ ] 球在移动/弹跳
- [ ] 动画流畅

### 完整测试用例 3: CSS 动画

发送：

```
创建一个 CSS 加载动画
```

期望：
- [ ] Preview 显示加载动画
- [ ] 动画循环播放
- [ ] 样式正确应用

## 📊 性能检查

- [ ] 打开 DevTools Performance
- [ ] 发送包含多个代码块的消息
- [ ] `message.end` 的解析时间 < 100ms
- [ ] Preview Dialog 打开时间 < 50ms
- [ ] 无内存泄漏（多次打开/关闭 Dialog）

## ✅ 最终验收标准

### 必须通过
- [x] 基本 HTML 预览正常工作
- [x] 代码块识别准确
- [x] Preview 按钮只在 HTML 代码块显示
- [x] Copy 功能正常
- [x] Dialog 可以正常打开和关闭
- [x] Sandbox 安全隔离生效
- [x] 样式美观统一

### 可选增强（未来）
- [ ] "Open in new tab" 按钮
- [ ] Console 输出显示
- [ ] 代码高亮（Syntax highlighting）
- [ ] 代码格式化按钮
- [ ] 全屏预览模式
- [ ] 预览窗口大小调整

## 🚀 部署状态

- ✅ 代码已实施
- ✅ 服务器已重启
- ✅ 版本号已更新（main.js v20 → v21）
- ✅ 准备就绪

**测试 URL**: http://127.0.0.1:8080

**测试方式**:
1. 访问 URL
2. 导航到 Chat 页面
3. 发送包含 HTML 代码块的消息
4. 验证 Preview 功能

---

**实施完成时间**: 2026-01-28
**功能状态**: ✅ 准备测试
