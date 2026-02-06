"""
Lead Agent Contract Mapper

负责在不同数据格式之间转换：
- Storage 聚合数据 <-> Miner 输入格式
- Miner 输出格式 <-> Dedupe 存储格式
"""

from .mapper import ContractMapper, StorageToMinerMapper, MinerToDedupeMapper

__all__ = [
    "ContractMapper",
    "StorageToMinerMapper",
    "MinerToDedupeMapper"
]
