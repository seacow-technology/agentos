# 高级代码块功能测试指南

## ✅ Phase 2-4 功能实施完成

**实施时间**: 2026-01-28
**版本**: v24

---

## 🎯 实施功能清单

### Phase 2（短期）
- ✅ **"Open in new tab" 按钮** - 在新标签页打开 HTML 预览
- ✅ **Console 输出显示** - 显示 iframe 内的 console.log/error/warn/info
- ✅ **行号显示** - Prism Line Numbers 插件集成
- ✅ **代码折叠** - 超过 20 行的代码块可折叠/展开

### Phase 3（中期）
- ✅ **代码格式化** - Prettier 集成（支持 HTML/JS/CSS/JSON/TS）
- ✅ **全屏预览** - Preview Dialog 全屏模式
- ✅ **导出功能** - 下载代码为文件

### Phase 4（长期 - 延后）
- ⚠️ **实时代码编辑** - 需要集成 Monaco Editor（延后）
- ⚠️ **主题切换** - 代码块主题切换（延后）
- ⚠️ **历史记录** - 记录预览过的 HTML（延后）
- ⚠️ **多文件支持** - HTML/CSS/JS 分离（延后）
- ⚠️ **分享链接** - 需要后端支持（延后）

---

## 🧪 测试步骤

### 测试 1: 代码格式化功能

1. 在 Chat 页面发送：
```
请写一个简单的 JavaScript 函数
```

2. AI 回复后，检查代码块：
   - [ ] 代码块显示 "Format" 按钮（仅限 HTML/JS/CSS/JSON/TS）
   - [ ] 点击 "Format" 按钮
   - [ ] 代码被格式化（使用 Prettier）
   - [ ] 按钮显示 "Formatted!" 反馈（绿色）
   - [ ] 2 秒后按钮恢复原状

### 测试 2: 代码下载功能

1. 找到任意代码块
2. 点击 "Download" 按钮
3. 验证：
   - [ ] 文件自动下载
   - [ ] 文件名格式: `code-{timestamp}.{ext}`
   - [ ] 文件扩展名正确（.js/.py/.html/.css 等）
   - [ ] 文件内容与代码块一致
   - [ ] 无多余空格或字符

### 测试 3: 代码折叠功能

1. 在 Chat 页面发送：
```
请写一个 50 行的 Python 脚本
```

2. AI 回复后，检查：
   - [ ] 代码块显示 "Collapse" 按钮（仅限 > 20 行）
   - [ ] 默认状态: 折叠（max-height: 300px）
   - [ ] 点击 "Collapse" 切换到展开状态
   - [ ] 按钮文本切换: "Collapse" ↔ "Expand"
   - [ ] 再次点击恢复折叠状态

### 测试 4: 行号显示

1. 检查任意代码块
2. 验证：
   - [ ] 代码块左侧显示行号
   - [ ] 行号从 1 开始
   - [ ] 行号与代码行对齐
   - [ ] 行号右侧有分隔线
   - [ ] 行号颜色为灰色 (#969896)

### 测试 5: "Open in new tab" 功能

1. 在 Chat 页面发送：
```
创建一个简单的 HTML 页面，包含一个按钮
```

2. AI 回复后：
   - [ ] 点击 HTML 代码块的 "Preview" 按钮
   - [ ] Preview Dialog 打开
   - [ ] 点击 "New Tab" 按钮
   - [ ] 新浏览器标签页打开
   - [ ] 新标签页显示相同的 HTML 内容
   - [ ] 新标签页中的 HTML 可以正常交互

### 测试 6: Console 输出显示

1. 在 Chat 页面发送：
```html
创建一个 HTML 页面，点击按钮后在 console 输出信息：
- console.log("Hello")
- console.warn("Warning")
- console.error("Error")
- console.info("Info")
```

2. AI 回复后：
   - [ ] 点击 "Preview" 按钮打开 Preview Dialog
   - [ ] 点击 "Console" 按钮
   - [ ] Console 面板从底部滑出（高度 200px）
   - [ ] 显示 "Console is ready" 提示
   - [ ] 在预览中点击按钮触发 console 输出
   - [ ] Console 面板显示所有输出
   - [ ] 不同类型显示不同颜色:
     - log: 白色 (#cccccc)
     - info: 蓝色 (#58a6ff)
     - warn: 黄色 (#d29922)
     - error: 红色 (#f85149)
   - [ ] 每条消息显示时间戳
   - [ ] 点击 "Clear" 按钮清空 Console
   - [ ] 再次点击 "Console" 按钮隐藏面板

### 测试 7: 全屏预览

1. 打开任意 HTML 预览
2. 点击 "Fullscreen" 按钮
3. 验证：
   - [ ] Preview Dialog 进入全屏模式
   - [ ] 占据整个屏幕
   - [ ] 按 ESC 或点击 "Fullscreen" 退出全屏
   - [ ] 关闭 Dialog 时自动退出全屏

### 测试 8: 组合功能测试

1. 创建一个复杂的 HTML 页面（> 20 行，包含 console 输出）
2. 验证所有功能同时工作：
   - [ ] Format 按钮格式化 HTML
   - [ ] Download 按钮下载 HTML 文件
   - [ ] Collapse 按钮折叠/展开代码
   - [ ] Preview 按钮打开预览
   - [ ] Console 显示输出
   - [ ] New Tab 打开新标签页
   - [ ] Fullscreen 进入全屏
   - [ ] Copy 按钮复制原始代码

### 测试 9: 多语言支持

测试不同语言的代码块功能：

1. **JavaScript**:
   - [ ] Format 按钮可用
   - [ ] Download 生成 .js 文件
   - [ ] 语法高亮正确

2. **Python**:
   - [ ] Format 按钮不可用（Prettier 不支持）
   - [ ] Download 生成 .py 文件
   - [ ] 语法高亮正确

3. **HTML**:
   - [ ] Format 按钮可用
   - [ ] Preview 按钮可用
   - [ ] Download 生成 .html 文件

4. **CSS**:
   - [ ] Format 按钮可用
   - [ ] Download 生成 .css 文件
   - [ ] 语法高亮正确

5. **JSON**:
   - [ ] Format 按钮可用
   - [ ] Download 生成 .json 文件
   - [ ] 语法高亮正确

### 测试 10: 边界情况

1. **空代码块**:
   - [ ] 所有按钮正常工作
   - [ ] Download 下载空文件
   - [ ] Format 不报错

2. **超长代码块**（> 100 行）:
   - [ ] Collapse 功能正常
   - [ ] 滚动条正常显示
   - [ ] 行号正确显示到最后一行

3. **特殊字符**:
   - [ ] 代码中的 <, >, &, ", ' 正确显示
   - [ ] Copy 复制的代码包含所有特殊字符
   - [ ] Download 文件包含所有特殊字符

4. **无语言标识的代码块**:
   - [ ] 使用 fallback 语言（clike）
   - [ ] 所有按钮正常工作
   - [ ] 不显示 Preview 按钮

---

## 📊 功能验收清单

### 功能完整性
- [ ] 所有 Phase 2 功能正常工作
- [ ] 所有 Phase 3 功能正常工作
- [ ] 按钮图标清晰可见
- [ ] 按钮 hover 效果正常
- [ ] 所有点击交互响应
- [ ] 无 JavaScript 错误

### UI/UX 质量
- [ ] 按钮布局合理，不拥挤
- [ ] 颜色搭配协调
- [ ] 图标大小一致
- [ ] 响应式设计（不同屏幕尺寸）
- [ ] 无视觉冲突
- [ ] 动画流畅（折叠、Console 滑出等）

### 性能要求
- [ ] 代码格式化响应时间 < 500ms
- [ ] Console 消息显示延迟 < 100ms
- [ ] 全屏切换响应时间 < 100ms
- [ ] 下载功能响应时间 < 200ms
- [ ] 无内存泄漏
- [ ] 多次使用后性能稳定

### 兼容性
- [ ] Chrome/Edge 浏览器正常工作
- [ ] Firefox 浏览器正常工作
- [ ] Safari 浏览器正常工作（如果可用）
- [ ] 不同操作系统正常工作

---

## 🐛 已知限制

1. **Console 输出**:
   - 只能捕获 console.log/error/warn/info
   - 不捕获 console.table/trace/group 等
   - 对象显示为 JSON 字符串

2. **代码格式化**:
   - 只支持 HTML/JS/CSS/JSON/TS
   - 格式化失败不会提示详细错误

3. **全屏模式**:
   - 部分旧浏览器可能不支持 Fullscreen API
   - iOS Safari 全屏支持有限

4. **Blob URLs**:
   - "Open in new tab" 生成的 URL 5 秒后失效
   - 无法保存为书签

---

## 🚀 部署状态

- ✅ 代码已实施
- ✅ 代码已提交 (commit: 89a8810)
- ⏳ 待测试
- ⏳ 待服务器重启

**测试 URL**: http://127.0.0.1:8080

**快速测试**：
1. 访问 Chat 页面
2. 发送: `"写一个 HTML 表单，包含 console.log 输出"`
3. 测试所有新功能：Format, Download, Collapse, Preview, Console, New Tab, Fullscreen

---

## 📝 实施总结

### 已完成功能（Phase 2-3）:
1. ✅ 代码格式化（Prettier）
2. ✅ 代码下载
3. ✅ 代码折叠
4. ✅ 行号显示
5. ✅ Console 输出
6. ✅ 新标签页打开
7. ✅ 全屏预览

### 延后功能（Phase 4）:
1. ⚠️ 实时代码编辑 - 需要 Monaco Editor（~5MB）
2. ⚠️ 主题切换 - 功能规划完整，待实施
3. ⚠️ 历史记录 - 功能规划完整，待实施
4. ⚠️ 多文件支持 - 需要架构重构
5. ⚠️ 分享链接 - 需要后端 API

### 技术实现:
- Prettier 2.8.8（standalone + 4 parsers）
- Prism Line Numbers Plugin 1.29.0
- Fullscreen API（原生）
- Blob URLs（原生）
- postMessage API（原生）

### 文件修改:
- `index.html`: 添加按钮和 Console 面板，更新版本到 v24
- `main.js`: 增强 ensurePreviewDialog()，添加辅助函数
- `components.css`: 添加所有新功能样式
- `codeblocks.js`: 无需修改（已支持新按钮）

---

**实施完成**: 2026-01-28
**状态**: ✅ 准备测试
