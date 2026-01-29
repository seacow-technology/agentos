"""
Unified Schema Validator Service (Layer 1)

VALIDATION LAYER: Schema / Structure
职责：结构合法性检查

统一的 Schema 校验入口，消除 CLI 和 Core 之间的校验分裂。

IMPORTANT: This is Layer 1 (Structure).
It does NOT cover:
    - ❌ Layer 2: Business Rules (OpenPlanVerifier)
    - ❌ Layer 3: Dry Executor RED LINE (DryExecutorValidator)

Schema 只关心：
    - ✅ JSON 结构合法性
    - ✅ 必填字段存在性
    - ✅ 类型正确性
    - ✅ 基础约束（枚举、数组长度）

Schema 不关心：
    - ❌ 业务语义（planning mode 能不能有 diff）
    - ❌ 安全风险（路径有没有伪造）
    - ❌ 审计完整性（有没有 evidence_refs）

Architecture Decision:
    三层验证不对齐是设计选择，不是缺陷。
    见：docs/architecture/VALIDATION_LAYERS.md

Design Principles:
- Single Source of Truth: 所有 schema 校验走这个服务
- 支持按名称校验（validate_by_name）和按路径校验（validate_by_path）
- 清晰的错误定位路径
- 支持 schema 版本解析

Usage:
    from agentos.core.verify.schema_validator_service import SchemaValidatorService

    service = SchemaValidatorService()
    is_valid, errors = service.validate_by_name(data, "factpack")
    is_valid, errors = service.validate_by_path(data, schema_path)
"""

import json
from pathlib import Path
from typing import Any, Optional

from jsonschema import Draft7Validator

from . import schema_validator as sv


class SchemaValidatorService:
    """统一的 Schema 校验服务"""

    def __init__(self, schema_root: Optional[Path] = None):
        """
        初始化 Schema Validator Service

        Args:
            schema_root: Schema 文件根目录（默认使用 agentos/schemas）
        """
        if schema_root is None:
            schema_root = Path(__file__).parent.parent.parent / "schemas"
        self.schema_root = schema_root

        # Schema 名称到验证函数的映射
        self._validators = {
            "factpack": sv.validate_factpack,
            "agent_spec": sv.validate_agent_spec,
            "memory_item": sv.validate_memory_item,
            "memory_pack": sv.validate_memory_pack,
            "task_definition": sv.validate_task_definition,
            "review_pack": sv.validate_review_pack,
            "execution_policy": sv.validate_execution_policy,
        }

    def validate_by_name(self, data: dict, schema_name: str) -> tuple[bool, list[str]]:
        """
        通过 schema 名称验证数据

        Args:
            data: 要验证的数据
            schema_name: schema 名称（如 "factpack", "agent_spec"）

        Returns:
            (is_valid, errors): 验证结果和错误列表
        """
        validator_func = self._validators.get(schema_name)
        if not validator_func:
            return False, [f"Unknown schema: {schema_name}"]

        return validator_func(data)

    def validate_by_path(
        self,
        data: dict,
        schema_path: Path
    ) -> tuple[bool, list[str]]:
        """
        通过 schema 文件路径验证数据

        Args:
            data: 要验证的数据
            schema_path: schema 文件路径（绝对或相对）

        Returns:
            (is_valid, errors): 验证结果和错误列表
        """
        try:
            # 如果是相对路径，从 schema_root 解析
            if not schema_path.is_absolute():
                schema_path = self.schema_root / schema_path

            with open(schema_path, encoding="utf-8") as f:
                schema = json.load(f)

            return self._validate_against_schema(data, schema)

        except FileNotFoundError:
            return False, [f"Schema file not found: {schema_path}"]
        except json.JSONDecodeError as e:
            return False, [f"Invalid schema JSON: {str(e)}"]
        except Exception as e:
            return False, [f"Schema validation error: {str(e)}"]

    def validate_file_by_name(
        self,
        file_path: Path,
        schema_name: str
    ) -> tuple[bool, list[str]]:
        """
        验证 JSON 文件（通过 schema 名称）

        Args:
            file_path: 要验证的 JSON 文件路径
            schema_name: schema 名称

        Returns:
            (is_valid, errors): 验证结果和错误列表
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            return self.validate_by_name(data, schema_name)
        except FileNotFoundError:
            return False, [f"File not found: {file_path}"]
        except json.JSONDecodeError as e:
            return False, [f"Invalid JSON: {str(e)}"]
        except Exception as e:
            return False, [f"Error reading file: {str(e)}"]

    def validate_file_by_path(
        self,
        file_path: Path,
        schema_path: Path
    ) -> tuple[bool, list[str]]:
        """
        验证 JSON 文件（通过 schema 路径）

        Args:
            file_path: 要验证的 JSON 文件路径
            schema_path: schema 文件路径

        Returns:
            (is_valid, errors): 验证结果和错误列表
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            return self.validate_by_path(data, schema_path)
        except FileNotFoundError:
            return False, [f"File not found: {file_path}"]
        except json.JSONDecodeError as e:
            return False, [f"Invalid JSON: {str(e)}"]
        except Exception as e:
            return False, [f"Error reading file: {str(e)}"]

    def _validate_against_schema(
        self,
        data: dict,
        schema: dict
    ) -> tuple[bool, list[str]]:
        """
        直接针对 schema dict 验证

        Args:
            data: 要验证的数据
            schema: JSON Schema dict

        Returns:
            (is_valid, errors): 验证结果和错误列表
        """
        try:
            validator = Draft7Validator(schema)
            errors_list = list(validator.iter_errors(data))

            if not errors_list:
                return True, []

            error_messages = []
            for error in errors_list:
                path = ".".join(str(p) for p in error.path) if error.path else "root"
                error_messages.append(f"{path}: {error.message}")

            return False, error_messages
        except Exception as e:
            return False, [f"Schema validation error: {str(e)}"]


# 向后兼容：提供类似旧 API 的接口
class SchemaValidator(SchemaValidatorService):
    """
    向后兼容的 SchemaValidator 类（wrapper）

    ⚠️  Deprecated: 请使用 SchemaValidatorService
    """

    @staticmethod
    def validate(data: dict, schema_name: str) -> tuple[bool, list]:
        """向后兼容方法"""
        service = SchemaValidatorService()
        return service.validate_by_name(data, schema_name)

    @staticmethod
    def validate_against_schema(data: dict, schema: dict) -> tuple[bool, list]:
        """向后兼容方法"""
        service = SchemaValidatorService()
        return service._validate_against_schema(data, schema)

    def validate_file_against_schema(
        self,
        data_path: Path,
        schema_path: Path
    ) -> bool:
        """
        向后兼容方法（为 intent_builder CLI）

        Returns:
            bool: 是否通过验证（失败时打印错误）
        """
        is_valid, errors = self.validate_file_by_path(data_path, schema_path)

        if not is_valid:
            for error in errors:
                print(f"   ❌ {error}")

        return is_valid
