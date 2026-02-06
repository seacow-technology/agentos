"""
AppOS Manifest 解析和验证

负责加载和验证 App 的 manifest.yaml 文件
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Union
from .models import AppManifest


def load_manifest(path: Union[str, Path, Dict[str, Any]]) -> AppManifest:
    """
    加载 App manifest

    Args:
        path: manifest.yaml 文件路径或字典

    Returns:
        AppManifest 对象

    Raises:
        FileNotFoundError: manifest 文件不存在
        ValueError: manifest 格式不正确
    """
    if isinstance(path, dict):
        # 直接从字典创建
        data = path
    else:
        # 从文件加载
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Manifest file not found: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

    # 验证并创建 AppManifest
    validate_manifest(data)
    return AppManifest.from_dict(data)


def validate_manifest(data: Dict[str, Any]) -> None:
    """
    验证 manifest 结构

    Args:
        data: manifest 数据字典

    Raises:
        ValueError: manifest 格式不正确
    """
    if not isinstance(data, dict):
        raise ValueError("Manifest must be a dictionary")

    # 必填字段
    required_fields = [
        'app_id',
        'name',
        'version',
        'description',
        'author',
        'category',
        'entry_module',
        'entry_class',
    ]

    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
        if not isinstance(data[field], str):
            raise ValueError(f"Field '{field}' must be a string")
        if not data[field].strip():
            raise ValueError(f"Field '{field}' cannot be empty")

    # app_id 格式验证
    app_id = data['app_id']
    if not app_id.replace('_', '').replace('-', '').isalnum():
        raise ValueError(f"Invalid app_id '{app_id}': must contain only letters, numbers, '_', and '-'")

    # requires_capabilities 验证
    if 'requires_capabilities' in data:
        if not isinstance(data['requires_capabilities'], list):
            raise ValueError("requires_capabilities must be a list")
        for cap in data['requires_capabilities']:
            if not isinstance(cap, str):
                raise ValueError("Each capability must be a string")

    # version 格式验证（简单的 semver 检查）
    version = data['version']
    parts = version.split('.')
    if len(parts) < 2 or len(parts) > 3:
        raise ValueError(f"Invalid version '{version}': must be in format X.Y or X.Y.Z")
    for part in parts:
        if not part.isdigit():
            raise ValueError(f"Invalid version '{version}': each part must be a number")

    # category 验证
    valid_categories = [
        'productivity',
        'communication',
        'development',
        'utility',
        'entertainment',
        'business',
        'education',
        'other',
    ]
    if data['category'] not in valid_categories:
        raise ValueError(f"Invalid category '{data['category']}': must be one of {valid_categories}")
