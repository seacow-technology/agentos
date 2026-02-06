"""
AppOS 核心数据模型

定义 App 的元数据、状态、实例等核心数据结构。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Any


class AppStatus(str, Enum):
    """App 状态枚举"""
    INSTALLED = "installed"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class AppManifest:
    """
    App 清单元数据

    定义 App 的基本信息和运行要求
    """
    app_id: str
    name: str
    version: str
    description: str
    author: str
    category: str
    requires_capabilities: List[str]
    entry_module: str
    entry_class: str

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'app_id': self.app_id,
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author,
            'category': self.category,
            'requires_capabilities': self.requires_capabilities,
            'entry_module': self.entry_module,
            'entry_class': self.entry_class,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppManifest':
        """从字典创建"""
        return cls(
            app_id=data['app_id'],
            name=data['name'],
            version=data['version'],
            description=data['description'],
            author=data['author'],
            category=data['category'],
            requires_capabilities=data.get('requires_capabilities', []),
            entry_module=data['entry_module'],
            entry_class=data['entry_class'],
        )


@dataclass
class App:
    """
    已安装的 App 记录

    表示一个已注册到 AppOS 的应用
    """
    app_id: str
    manifest: AppManifest
    status: AppStatus
    installed_at: int  # epoch 毫秒
    updated_at: int    # epoch 毫秒
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'app_id': self.app_id,
            'manifest': self.manifest.to_dict(),
            'status': self.status.value,
            'installed_at': self.installed_at,
            'updated_at': self.updated_at,
            'metadata': self.metadata or {},
        }


@dataclass
class AppInstance:
    """
    运行中的 App 实例

    表示一个 App 的运行时实例
    """
    instance_id: str
    app_id: str
    status: AppStatus
    started_at: int           # epoch 毫秒
    stopped_at: Optional[int] = None  # epoch 毫秒
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'instance_id': self.instance_id,
            'app_id': self.app_id,
            'status': self.status.value,
            'started_at': self.started_at,
            'stopped_at': self.stopped_at,
            'metadata': self.metadata or {},
        }
