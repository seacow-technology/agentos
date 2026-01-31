"""
AppOS - 应用层组合与交付

AppOS 提供面向用户的应用层组合与交付能力，
把 6OS 的能力按用户场景编排成可用产品。

核心概念：
- App: 场景化应用，由 manifest.yaml 定义
- AppInstance: 运行中的 App 实例
- AppOSService: App 管理服务
- AppRuntime: App 运行时引擎

使用示例：
    from agentos.core.appos import AppOSService

    # 初始化服务
    service = AppOSService()

    # 列出已安装的 App
    apps = service.list_apps()

    # 启动 App
    instance_id = service.start_app("personal_assistant")

    # 获取状态
    status = service.get_app_status("personal_assistant")

    # 停止 App
    service.stop_app("personal_assistant")
"""
from .models import AppStatus, AppManifest, App, AppInstance
from .store import AppOSStore
from .runtime import AppBase, AppRuntime
from .service import AppOSService
from .manifest import load_manifest, validate_manifest

__all__ = [
    # 枚举和数据模型
    'AppStatus',
    'AppManifest',
    'App',
    'AppInstance',

    # 核心类
    'AppOSStore',
    'AppBase',
    'AppRuntime',
    'AppOSService',

    # 工具函数
    'load_manifest',
    'validate_manifest',
]

__version__ = '1.0.0'
