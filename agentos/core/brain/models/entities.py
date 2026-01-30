"""
BrainOS Entity Models

定义 BrainOS 中的实体类型。

所有实体遵循统一结构：
- id: 全局唯一标识符
- type: 实体类型
- key: 业务唯一键（如文件路径、commit hash）
- name: 显示名称
- attrs_json: 扩展属性（JSON）

v0.1 实体类型：
1. Repo - 仓库
2. File - 文件
3. Symbol - 代码符号（类/函数/变量）
4. Doc - 文档
5. Commit - Git 提交
6. Term - 领域术语
7. Capability - 能力/特性

TODO v0.2+:
- Module（模块/包）
- Test（测试用例）
- Issue/PR（问题/拉取请求）
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum
import json


class EntityType(str, Enum):
    """实体类型枚举"""
    REPO = "repo"
    FILE = "file"
    SYMBOL = "symbol"
    DOC = "doc"
    COMMIT = "commit"
    TERM = "term"
    CAPABILITY = "capability"


@dataclass
class Entity:
    """
    BrainOS 基础实体

    所有实体的基类，定义通用字段和行为。

    Attributes:
        id: 全局唯一标识符（UUID 或自增）
        type: 实体类型（见 EntityType）
        key: 业务唯一键（如 file path, commit hash）
        name: 显示名称
        attrs: 扩展属性字典

    Frozen Contract:
        - 实体创建后不可修改原仓库内容
        - 所有字段必须可序列化为 JSON
    """
    id: str
    type: EntityType
    key: str
    name: str
    attrs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type.value,
            "key": self.key,
            "name": self.name,
            "attrs": self.attrs,
        }

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict())


@dataclass
class Repo(Entity):
    """
    仓库实体

    Attributes:
        remote_url: 远程仓库 URL
        local_path: 本地路径
        default_branch: 默认分支
    """
    def __init__(self, id: str, key: str, name: str, **attrs):
        super().__init__(
            id=id,
            type=EntityType.REPO,
            key=key,
            name=name,
            attrs=attrs
        )


@dataclass
class File(Entity):
    """
    文件实体

    Attributes:
        path: 相对于仓库根的路径
        extension: 文件扩展名
        size: 文件大小（字节）
        last_modified: 最后修改时间
    """
    def __init__(self, id: str, key: str, name: str, **attrs):
        super().__init__(
            id=id,
            type=EntityType.FILE,
            key=key,
            name=name,
            attrs=attrs
        )


@dataclass
class Symbol(Entity):
    """
    代码符号实体（类、函数、变量等）

    Attributes:
        symbol_type: 符号类型（class/function/variable）
        file_path: 所在文件路径
        line_number: 行号
        signature: 函数/方法签名
    """
    def __init__(self, id: str, key: str, name: str, **attrs):
        super().__init__(
            id=id,
            type=EntityType.SYMBOL,
            key=key,
            name=name,
            attrs=attrs
        )


@dataclass
class Doc(Entity):
    """
    文档实体

    Attributes:
        doc_type: 文档类型（adr/readme/guide/api）
        format: 格式（markdown/rst/txt）
        path: 文档路径
        section: 章节标题（可选）
    """
    def __init__(self, id: str, key: str, name: str, **attrs):
        super().__init__(
            id=id,
            type=EntityType.DOC,
            key=key,
            name=name,
            attrs=attrs
        )


@dataclass
class Commit(Entity):
    """
    Git 提交实体

    Attributes:
        hash: commit hash (SHA-1)
        author: 作者
        date: 提交日期
        message: 提交消息
        files_changed: 变更文件数
    """
    def __init__(self, id: str, key: str, name: str, **attrs):
        super().__init__(
            id=id,
            type=EntityType.COMMIT,
            key=key,
            name=name,
            attrs=attrs
        )


@dataclass
class Term(Entity):
    """
    领域术语实体

    Attributes:
        term: 术语文本
        category: 分类（technical/business/domain）
        definition: 定义（可选）
        aliases: 别名列表
    """
    def __init__(self, id: str, key: str, name: str, **attrs):
        super().__init__(
            id=id,
            type=EntityType.TERM,
            key=key,
            name=name,
            attrs=attrs
        )


@dataclass
class Capability(Entity):
    """
    能力/特性实体

    Attributes:
        capability_type: 能力类型（feature/api/integration）
        status: 状态（planned/implemented/deprecated）
        version: 引入版本
        description: 描述
    """
    def __init__(self, id: str, key: str, name: str, **attrs):
        super().__init__(
            id=id,
            type=EntityType.CAPABILITY,
            key=key,
            name=name,
            attrs=attrs
        )
