"""
BrainOS Governance Layer - P4

提供决策记录、治理规则、审计和责任追溯功能。

核心模块：
- decision_record: 决策记录数据模型
- decision_recorder: 决策记录生成器
- rule_engine: 治理规则引擎
- replay: 决策回放系统
- signoff: 决策签字系统

Database Schema:
- Schema is managed by migration scripts
- See: agentos/store/migrations/schema_v36_decision_records.sql
- Tables: decision_records, decision_signoffs
"""

from .decision_record import (
    DecisionRecord,
    DecisionType,
    DecisionStatus,
    GovernanceAction,
    RuleTrigger,
    DecisionSignoff,
)

__all__ = [
    'DecisionRecord',
    'DecisionType',
    'DecisionStatus',
    'GovernanceAction',
    'RuleTrigger',
    'DecisionSignoff',
]
