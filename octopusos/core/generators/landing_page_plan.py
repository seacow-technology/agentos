"""Landing Page Plan Schema

定义 planning 阶段输出的 JSON 结构
"""

from dataclasses import dataclass
from typing import List, Dict, Any
import json


@dataclass
class HeroSection:
    """Hero 区域内容"""
    title: str
    tagline: str
    description: str
    cta_primary: str
    cta_secondary: str
    cta_primary_link: str = "#features"
    cta_secondary_link: str = "https://github.com/yourusername/agentos"


@dataclass
class FeatureItem:
    """单个 Feature 项"""
    icon: str  # emoji 图标
    title: str
    description: str


@dataclass
class UseCaseItem:
    """单个 Use Case 项"""
    icon: str
    title: str
    description: str


@dataclass
class LandingPagePlan:
    """Landing Page 完整计划
    
    这个结构由 planning mode 生成，由 implementation mode 使用
    """
    hero: HeroSection
    features: List[FeatureItem]
    use_cases: List[UseCaseItem]
    footer_tagline: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "hero": {
                "title": self.hero.title,
                "tagline": self.hero.tagline,
                "description": self.hero.description,
                "cta_primary": self.hero.cta_primary,
                "cta_secondary": self.hero.cta_secondary,
                "cta_primary_link": self.hero.cta_primary_link,
                "cta_secondary_link": self.hero.cta_secondary_link,
            },
            "features": [
                {
                    "icon": f.icon,
                    "title": f.title,
                    "description": f.description
                }
                for f in self.features
            ],
            "use_cases": [
                {
                    "icon": uc.icon,
                    "title": uc.title,
                    "description": uc.description
                }
                for uc in self.use_cases
            ],
            "footer_tagline": self.footer_tagline
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LandingPagePlan':
        """从字典创建"""
        hero = HeroSection(
            title=data["hero"]["title"],
            tagline=data["hero"]["tagline"],
            description=data["hero"]["description"],
            cta_primary=data["hero"]["cta_primary"],
            cta_secondary=data["hero"]["cta_secondary"],
            cta_primary_link=data["hero"].get("cta_primary_link", "#features"),
            cta_secondary_link=data["hero"].get("cta_secondary_link", "https://github.com")
        )
        
        features = [
            FeatureItem(
                icon=f["icon"],
                title=f["title"],
                description=f["description"]
            )
            for f in data["features"]
        ]
        
        use_cases = [
            UseCaseItem(
                icon=uc["icon"],
                title=uc["title"],
                description=uc["description"]
            )
            for uc in data["use_cases"]
        ]
        
        return cls(
            hero=hero,
            features=features,
            use_cases=use_cases,
            footer_tagline=data["footer_tagline"]
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'LandingPagePlan':
        """从 JSON 字符串创建"""
        data = json.loads(json_str)
        return cls.from_dict(data)


def create_default_agentos_plan() -> LandingPagePlan:
    """创建 AgentOS 的默认 landing page plan"""
    return LandingPagePlan(
        hero=HeroSection(
            title="AgentOS",
            tagline="From Natural Language to Auditable Execution",
            description="An OS-level governance layer for AI execution that enables agents to \"get things done\" without losing control.",
            cta_primary="Learn More",
            cta_secondary="View on GitHub"
        ),
        features=[
            FeatureItem(
                icon="🔒",
                title="Mode System",
                description="Strong runtime constraints that prevent unauthorized operations. Only implementation mode can write code."
            ),
            FeatureItem(
                icon="📝",
                title="Full Audit Trail",
                description="Every operation is logged to run_tape.jsonl with timestamps, inputs, outputs, and hashes."
            ),
            FeatureItem(
                icon="🔄",
                title="Worktree Isolation",
                description="All execution happens in isolated git worktrees, keeping your main workspace clean and safe."
            ),
            FeatureItem(
                icon="⏪",
                title="Rollback Support",
                description="Clear git commits for each step allow you to rollback to any point in the execution history."
            ),
        ],
        use_cases=[
            UseCaseItem(
                icon="🚀",
                title="Automated Development",
                description="Let AI agents create features, fix bugs, and refactor code - all with full audit trails and rollback capabilities."
            ),
            UseCaseItem(
                icon="🔍",
                title="Code Analysis",
                description="Analyze codebases, generate documentation, and extract insights without worrying about accidental modifications."
            ),
            UseCaseItem(
                icon="🛠️",
                title="Infrastructure Automation",
                description="Automate DevOps tasks with confidence, knowing every operation is logged and can be reviewed or rolled back."
            ),
        ],
        footer_tagline="Making AI execution reliable, controlled, and accountable."
    )
