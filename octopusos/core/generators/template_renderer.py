"""Template Renderer - 从 JSON Plan 渲染 HTML 内容

Wave-1: 模板只保留骨架，内容从 Plan 动态生成
"""

from typing import Dict, Any
from .landing_page_plan import LandingPagePlan


class TemplateRenderer:
    """模板渲染器"""
    
    @staticmethod
    def render_hero_section(plan: LandingPagePlan) -> str:
        """渲染 Hero 区域"""
        return f"""    <!-- Hero Section -->
    <section id="hero">
        <div class="container">
            <h1>{plan.hero.title}</h1>
            <p class="tagline">{plan.hero.tagline}</p>
            <p class="description">{plan.hero.description}</p>
            <div class="cta-buttons">
                <a href="{plan.hero.cta_primary_link}" class="btn btn-primary">{plan.hero.cta_primary}</a>
                <a href="{plan.hero.cta_secondary_link}" class="btn btn-secondary">{plan.hero.cta_secondary}</a>
            </div>
        </div>
    </section>"""
    
    @staticmethod
    def render_features_section(plan: LandingPagePlan) -> str:
        """渲染 Features 区域"""
        feature_cards = "\n".join([
            f"""                <div class="feature-card">
                    <div class="feature-icon">{feature.icon}</div>
                    <h3>{feature.title}</h3>
                    <p>{feature.description}</p>
                </div>"""
            for feature in plan.features
        ])
        
        return f"""    <!-- Features Section -->
    <section id="features">
        <div class="container">
            <h2>Core Features</h2>
            <div class="features-grid">
{feature_cards}
            </div>
        </div>
    </section>"""
    
    @staticmethod
    def render_architecture_section() -> str:
        """渲染 Architecture 区域（静态）"""
        return """    <!-- Architecture Section -->
    <section id="architecture">
        <div class="container">
            <h2>Architecture</h2>
            <div class="architecture-diagram">
                <div class="arch-layer">
                    <div class="arch-box">Natural Language Input</div>
                </div>
                <div class="arch-arrow">↓</div>
                <div class="arch-layer">
                    <div class="arch-box">ModeSelector</div>
                </div>
                <div class="arch-arrow">↓</div>
                <div class="arch-layer">
                    <div class="arch-box">Pipeline Runner</div>
                </div>
                <div class="arch-arrow">↓</div>
                <div class="arch-layer">
                    <div class="arch-box">Executor Engine</div>
                </div>
                <div class="arch-arrow">↓</div>
                <div class="arch-layer">
                    <div class="arch-box">Auditable Output</div>
                </div>
            </div>
            <p class="architecture-description">
                AgentOS provides an OS-level governance layer that sits between AI agents and your systems,
                ensuring every operation is controlled, auditable, and reversible.
            </p>
        </div>
    </section>"""
    
    @staticmethod
    def render_use_cases_section(plan: LandingPagePlan) -> str:
        """渲染 Use Cases 区域"""
        use_case_cards = "\n".join([
            f"""                <div class="use-case-card">
                    <h3>{uc.icon} {uc.title}</h3>
                    <p>{uc.description}</p>
                </div>"""
            for uc in plan.use_cases
        ])
        
        return f"""    <!-- Use Cases Section -->
    <section id="use-cases">
        <div class="container">
            <h2>Use Cases</h2>
            <div class="use-cases-grid">
{use_case_cards}
            </div>
        </div>
    </section>"""
    
    @staticmethod
    def render_footer(plan: LandingPagePlan) -> str:
        """渲染 Footer"""
        return f"""    <!-- Footer -->
    <footer id="footer">
        <div class="container">
            <div class="footer-content">
                <div class="footer-section">
                    <h4>AgentOS</h4>
                    <p>{plan.footer_tagline}</p>
                </div>
                <div class="footer-section">
                    <h4>Links</h4>
                    <ul>
                        <li><a href="https://github.com/yourusername/agentos">GitHub</a></li>
                        <li><a href="https://github.com/yourusername/agentos/docs">Documentation</a></li>
                        <li><a href="https://github.com/yourusername/agentos/issues">Issues</a></li>
                    </ul>
                </div>
                <div class="footer-section">
                    <h4>Community</h4>
                    <ul>
                        <li><a href="#">Discord</a></li>
                        <li><a href="#">Twitter</a></li>
                        <li><a href="#">Blog</a></li>
                    </ul>
                </div>
            </div>
            <div class="footer-bottom">
                <p>&copy; 2026 AgentOS Team. Licensed under MIT.</p>
            </div>
        </div>
    </footer>"""
    
    @staticmethod
    def render_full_page(plan: LandingPagePlan) -> str:
        """渲染完整页面"""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{plan.hero.title} - {plan.hero.tagline}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
{TemplateRenderer.render_hero_section(plan)}

{TemplateRenderer.render_features_section(plan)}

{TemplateRenderer.render_architecture_section()}

{TemplateRenderer.render_use_cases_section(plan)}

{TemplateRenderer.render_footer(plan)}
</body>
</html>
"""
