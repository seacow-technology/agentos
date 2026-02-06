"""配置管理器 - 加载和验证 ProjectKB 配置

支持配置:
- scan_paths: 扫描路径列表
- exclude_patterns: 排除模式
- chunk_size: 切片大小限制
- index_weights: 文档类型权重
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class VectorRerankConfig:
    """向量重排序配置 (P2 功能)"""
    
    enabled: bool = False
    provider: str = "local"  # local|openai
    model: str = "sentence-transformers/all-MiniLM-L6-v2"
    candidate_k: int = 50  # 候选集大小
    final_k: int = 10  # 最终返回结果数
    alpha: float = 0.7  # 融合权重 (0-1, 越大越偏向向量分数)


@dataclass
class ProjectKBConfig:
    """ProjectKB 配置"""

    scan_paths: list[str] = field(default_factory=lambda: [
        "docs/**/*.md",
        "README.md",
        "adr/**/*.md",
    ])

    exclude_patterns: list[str] = field(default_factory=lambda: [
        "node_modules/**",
        ".history/**",
        ".git/**",
        "venv/**",
        "__pycache__/**",
    ])

    chunk_size_min: int = 300
    chunk_size_max: int = 800

    index_weights: dict[str, float] = field(default_factory=lambda: {
        "heading": 2.0,
        "first_paragraph": 1.5,
        "code_blocks": 1.2,
    })

    # 文档类型权重 (覆盖默认值)
    doc_type_weights: dict[str, float] = field(default_factory=dict)
    
    # 向量重排序配置 (P2)
    vector_rerank: VectorRerankConfig = field(default_factory=VectorRerankConfig)

    @classmethod
    def from_file(cls, config_path: Path) -> "ProjectKBConfig":
        """从 JSON 文件加载配置

        Args:
            config_path: 配置文件路径

        Returns:
            ProjectKBConfig 对象
        """
        if not config_path.exists():
            return cls()

        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 加载 vector_rerank 配置
        vector_rerank_data = data.get("vector_rerank", {})
        vector_rerank = VectorRerankConfig(
            enabled=vector_rerank_data.get("enabled", False),
            provider=vector_rerank_data.get("provider", "local"),
            model=vector_rerank_data.get("model", "sentence-transformers/all-MiniLM-L6-v2"),
            candidate_k=vector_rerank_data.get("candidate_k", 50),
            final_k=vector_rerank_data.get("final_k", 10),
            alpha=vector_rerank_data.get("alpha", 0.7),
        )
        
        return cls(
            scan_paths=data.get("scan_paths", cls().scan_paths),
            exclude_patterns=data.get("exclude_patterns", cls().exclude_patterns),
            chunk_size_min=data.get("chunk_size", {}).get("min", 300),
            chunk_size_max=data.get("chunk_size", {}).get("max", 800),
            index_weights=data.get("index_weights", cls().index_weights),
            doc_type_weights=data.get("doc_type_weights", {}),
            vector_rerank=vector_rerank,
        )

    def to_file(self, config_path: Path):
        """保存配置到 JSON 文件

        Args:
            config_path: 配置文件路径
        """
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "scan_paths": self.scan_paths,
            "exclude_patterns": self.exclude_patterns,
            "chunk_size": {
                "min": self.chunk_size_min,
                "max": self.chunk_size_max,
            },
            "index_weights": self.index_weights,
        }

        if self.doc_type_weights:
            data["doc_type_weights"] = self.doc_type_weights
        
        # 保存 vector_rerank 配置
        data["vector_rerank"] = {
            "enabled": self.vector_rerank.enabled,
            "provider": self.vector_rerank.provider,
            "model": self.vector_rerank.model,
            "candidate_k": self.vector_rerank.candidate_k,
            "final_k": self.vector_rerank.final_k,
            "alpha": self.vector_rerank.alpha,
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "scan_paths": self.scan_paths,
            "exclude_patterns": self.exclude_patterns,
            "chunk_size_min": self.chunk_size_min,
            "chunk_size_max": self.chunk_size_max,
            "index_weights": self.index_weights,
            "doc_type_weights": self.doc_type_weights,
        }


def get_default_config_path() -> Path:
    """获取默认配置文件路径"""
    return Path(".agentos/kb_config.json")


def load_config(config_path: Optional[Path] = None) -> ProjectKBConfig:
    """加载配置 (如果不存在则返回默认配置)

    Args:
        config_path: 配置文件路径 (None 使用默认)

    Returns:
        ProjectKBConfig 对象
    """
    if config_path is None:
        config_path = get_default_config_path()

    return ProjectKBConfig.from_file(config_path)
