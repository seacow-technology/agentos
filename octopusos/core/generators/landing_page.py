"""Landing Page Generator - 从模板生成 Landing Page 的执行计划

Wave-1 改造：
- planning 输出 JSON Plan
- implementation 从 Plan 渲染内容
- 模板只保留骨架
"""

from pathlib import Path
from typing import Dict, Any, List
import json

from .landing_page_plan import LandingPagePlan, create_default_agentos_plan


class LandingPageGenerator:
    """Landing Page 生成器
    
    提供预制的 6 步执行计划，用于创建 demo landing page
    """
    
    def __init__(self):
        # 模板在 agentos/templates/landing_page/
        # 当前文件在 agentos/core/generators/landing_page.py
        # 需要向上两级再进入 templates
        current_file = Path(__file__)  # agentos/core/generators/landing_page.py
        agentos_dir = current_file.parent.parent.parent  # agentos/
        self.template_dir = agentos_dir / "templates" / "landing_page"
    
    def generate_planning_output(self, nl_input: str) -> str:
        """生成 planning 阶段的输出（Wave-1: JSON Plan + 人类可读摘要）
        
        Args:
            nl_input: 自然语言输入
            
        Returns:
            str: Planning 输出（JSON + 文本摘要）
        """
        # 创建 JSON Plan
        plan = create_default_agentos_plan()
        plan_json = plan.to_json()
        
        # 人类可读摘要
        summary = f"""
# Landing Page Implementation Plan

## Input Analysis
- **User Request**: {nl_input}
- **Project Type**: Static HTML Landing Page
- **Tech Stack**: HTML + CSS (no build tools needed)

## Content Plan (JSON)

```json
{plan_json}
```

## Page Structure
The landing page will include 5 main sections:
1. **Hero Section**: {plan.hero.title} - {plan.hero.tagline}
2. **Features Section**: {len(plan.features)} feature cards
3. **Architecture Section**: Visual diagram of system architecture
4. **Use Cases Section**: {len(plan.use_cases)} use case examples
5. **Footer**: Links and tagline

## Implementation Checklist (6 Steps)

### Step 1: Initialize Skeleton
- Create basic HTML structure with placeholders
- Add meta tags and link to CSS
- Create empty CSS file
- **Commit Message**: "chore: init landing skeleton"

### Step 2: Add Hero Section
- Render hero from JSON Plan
- Add title, tagline, description from plan.hero
- Add CTA buttons with plan.hero.cta_*
- **Commit Message**: "feat: add hero section"

### Step 3: Add Features Section
- Render {len(plan.features)} feature cards from plan.features
- Each card shows icon, title, description from JSON
- **Commit Message**: "feat: add features section"

### Step 4: Add Architecture Section
- Create visual architecture diagram (static)
- Show AgentOS execution flow
- **Commit Message**: "feat: add architecture section"

### Step 5: Add Use Cases Section
- Render {len(plan.use_cases)} use case cards from plan.use_cases
- Each card shows icon, title, description from JSON
- **Commit Message**: "feat: add use cases section"

### Step 6: Add Footer and Polish
- Create footer with tagline from plan.footer_tagline
- Add responsive design for mobile
- Polish overall styling
- **Commit Message**: "feat: add footer and polish"

## Design Principles
- **Data-Driven**: Content rendered from JSON Plan
- **Responsive**: Works on desktop, tablet, and mobile
- **Modern**: Uses CSS Grid, Flexbox, and modern colors
- **No Dependencies**: Pure HTML/CSS, minimal JavaScript for rendering

## Success Criteria
✅ Content rendered from JSON Plan
✅ All 5 sections present and styled
✅ Responsive design (mobile breakpoint at 768px)
✅ Can be opened directly in browser
✅ Clear git history with 6 commits
"""
        return summary
    
    def generate_execution_steps(self) -> List[Dict[str, Any]]:
        """生成 6 个执行步骤（Wave-1: 从 Plan 渲染内容）
        
        Returns:
            List[Dict]: 步骤列表
        """
        from .template_renderer import TemplateRenderer
        
        # 创建默认 Plan
        plan = create_default_agentos_plan()
        
        # 读取模板 CSS（保持不变）
        template_css = (self.template_dir / "style.css").read_text(encoding="utf-8")
        template_readme = (self.template_dir / "README.md").read_text(encoding="utf-8")
        
        steps = [
            {
                "step_id": "step_01_init",
                "description": "Initialize landing page skeleton",
                "commit_message": "chore: init landing skeleton",
                "files": {
                    "index.html": self._get_skeleton_html(),
                    "style.css": "/* Landing Page Styles */\n\n",
                    "README.md": "# Landing Page\n\nCreated by AgentOS\n",
                    "plan.json": plan.to_json()  # 保存 Plan 到文件
                }
            },
            {
                "step_id": "step_02_hero",
                "description": "Add hero section (rendered from plan.json)",
                "commit_message": "feat: add hero section",
                "files": {
                    "index.html": self._build_incremental_html(
                        [TemplateRenderer.render_hero_section(plan)]
                    ),
                    "style.css": self._extract_css_up_to(template_css, "/* Features Section */")
                }
            },
            {
                "step_id": "step_03_features",
                "description": "Add features section (rendered from plan.json)",
                "commit_message": "feat: add features section",
                "files": {
                    "index.html": self._build_incremental_html([
                        TemplateRenderer.render_hero_section(plan),
                        TemplateRenderer.render_features_section(plan)
                    ]),
                    "style.css": self._extract_css_up_to(template_css, "/* Architecture Section */")
                }
            },
            {
                "step_id": "step_04_architecture",
                "description": "Add architecture section",
                "commit_message": "feat: add architecture section",
                "files": {
                    "index.html": self._build_incremental_html([
                        TemplateRenderer.render_hero_section(plan),
                        TemplateRenderer.render_features_section(plan),
                        TemplateRenderer.render_architecture_section()
                    ]),
                    "style.css": self._extract_css_up_to(template_css, "/* Use Cases Section */")
                }
            },
            {
                "step_id": "step_05_use_cases",
                "description": "Add use cases section (rendered from plan.json)",
                "commit_message": "feat: add use cases section",
                "files": {
                    "index.html": self._build_incremental_html([
                        TemplateRenderer.render_hero_section(plan),
                        TemplateRenderer.render_features_section(plan),
                        TemplateRenderer.render_architecture_section(),
                        TemplateRenderer.render_use_cases_section(plan)
                    ]),
                    "style.css": self._extract_css_up_to(template_css, "/* Footer */")
                }
            },
            {
                "step_id": "step_06_footer",
                "description": "Add footer and polish (rendered from plan.json)",
                "commit_message": "feat: add footer and polish",
                "files": {
                    "index.html": TemplateRenderer.render_full_page(plan),
                    "style.css": template_css,
                    "README.md": template_readme
                }
            }
        ]
        
        return steps
    
    def _get_skeleton_html(self) -> str:
        """获取骨架 HTML"""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgentOS - AI Execution Operating System</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <!-- Sections will be added in subsequent steps -->
    <!-- Content will be rendered from plan.json -->
</body>
</html>
"""
    
    def _build_incremental_html(self, sections: List[str]) -> str:
        """构建渐进式 HTML（从 sections 列表）"""
        sections_html = "\n\n".join(sections)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgentOS - AI Execution Operating System</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
{sections_html}
</body>
</html>
"""
    
    def _extract_css_up_to(self, css: str, marker: str) -> str:
        """提取 CSS 直到指定标记"""
        if marker in css:
            return css[:css.index(marker)]
        return css


# 单例实例
_generator = None

def get_landing_page_generator() -> LandingPageGenerator:
    """获取 Landing Page Generator 单例"""
    global _generator
    if _generator is None:
        _generator = LandingPageGenerator()
    return _generator
