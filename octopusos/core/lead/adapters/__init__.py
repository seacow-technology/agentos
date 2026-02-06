"""
Lead Agent Storage Adapters

提供从 AgentOS 数据库（task_audits, tasks 等表）读取数据的适配器层。
"""

from .storage import LeadStorage

__all__ = ["LeadStorage"]
