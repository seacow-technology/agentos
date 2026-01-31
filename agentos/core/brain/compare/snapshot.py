"""
Graph Snapshot - 图谱快照管理

功能：
1. 创建快照：capture_snapshot()
2. 查询快照：list_snapshots()
3. 加载快照：load_snapshot()
4. 删除快照：delete_snapshot()

快照触发场景：
- 手动触发（用户调用 /brain snapshot）
- 定时触发（每天 00:00）
- 索引大变更后（增量超过 10%）
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Dict
import json
from agentos.core.time import utc_now_iso



@dataclass
class SnapshotSummary:
    """快照摘要"""
    snapshot_id: str
    timestamp: str
    description: Optional[str]

    entity_count: int
    edge_count: int
    evidence_count: int

    coverage_percentage: float
    blind_spot_count: int

    graph_version: str


@dataclass
class SnapshotEntity:
    """快照实体"""
    entity_id: str
    entity_type: str
    entity_key: str
    entity_name: str

    evidence_count: int
    coverage_sources: List[str]
    is_blind_spot: bool
    blind_spot_severity: Optional[float]


@dataclass
class SnapshotEdge:
    """快照边"""
    edge_id: str
    src_entity_id: str
    dst_entity_id: str
    edge_type: str

    evidence_count: int
    evidence_types: List[str]


@dataclass
class Snapshot:
    """完整快照"""
    summary: SnapshotSummary
    entities: List[SnapshotEntity]
    edges: List[SnapshotEdge]


def capture_snapshot(
    store,  # SQLiteStore
    description: Optional[str] = None
) -> str:
    """
    创建当前图谱的快照

    触发场景：
    - 手动触发（用户调用 /brain snapshot）
    - 定时触发（每天 00:00）
    - 索引大变更后（增量超过 10%）

    Args:
        store: BrainOS 数据库
        description: 快照描述（可选）

    Returns:
        snapshot_id: 快照 ID
    """
    conn = store.connect()
    cursor = conn.cursor()

    # 1. 生成快照 ID
    timestamp = utc_now_iso()
    snapshot_id = f"snapshot_{timestamp.replace(':', '').replace('.', '_').replace('-', '_')}"

    # 2. 获取当前 graph_version
    cursor.execute("""
        SELECT graph_version FROM build_metadata
        ORDER BY id DESC LIMIT 1
    """)
    build_row = cursor.fetchone()
    graph_version = build_row[0] if build_row else "unknown"

    # 3. 统计当前状态
    cursor.execute("SELECT COUNT(*) FROM entities")
    entity_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM edges")
    edge_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM evidence")
    evidence_count = cursor.fetchone()[0]

    # 覆盖度（简化计算）
    cursor.execute("""
        SELECT COUNT(DISTINCT e.id)
        FROM entities e
        JOIN edges eg ON eg.src_entity_id = e.id OR eg.dst_entity_id = e.id
        JOIN evidence ev ON ev.edge_id = eg.id
    """)
    covered_count = cursor.fetchone()[0]
    coverage_percentage = (covered_count / entity_count * 100) if entity_count > 0 else 0.0

    # 简化的覆盖度计算（按证据类型）
    git_coverage = 0.0
    doc_coverage = 0.0
    code_coverage = 0.0

    # 盲区（暂时简化为没有证据的实体）
    cursor.execute("""
        SELECT COUNT(*)
        FROM entities e
        WHERE NOT EXISTS (
            SELECT 1 FROM edges eg
            JOIN evidence ev ON ev.edge_id = eg.id
            WHERE eg.src_entity_id = e.id OR eg.dst_entity_id = e.id
        )
    """)
    blind_spot_count = cursor.fetchone()[0]
    high_risk_blind_spot_count = 0  # 暂时简化

    # 4. 插入快照记录
    cursor.execute("""
        INSERT INTO brain_snapshots (
            id, timestamp, description,
            entity_count, edge_count, evidence_count,
            coverage_percentage, git_coverage, doc_coverage, code_coverage,
            blind_spot_count, high_risk_blind_spot_count,
            graph_version, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        snapshot_id, timestamp, description or "",
        entity_count, edge_count, evidence_count,
        coverage_percentage, git_coverage, doc_coverage, code_coverage,
        blind_spot_count, high_risk_blind_spot_count,
        graph_version, "system"
    ))

    # 5. 复制实体
    cursor.execute("""
        INSERT INTO brain_snapshot_entities (
            snapshot_id, entity_id, entity_type, entity_key, entity_name,
            evidence_count, coverage_sources, is_blind_spot, blind_spot_severity
        )
        SELECT
            ? as snapshot_id,
            CAST(e.id AS TEXT),
            e.type,
            e.key,
            e.name,
            COALESCE((
                SELECT COUNT(DISTINCT ev.id)
                FROM edges eg
                JOIN evidence ev ON ev.edge_id = eg.id
                WHERE eg.src_entity_id = e.id OR eg.dst_entity_id = e.id
            ), 0) as evidence_count,
            '[]' as coverage_sources,
            CASE WHEN NOT EXISTS (
                SELECT 1 FROM edges eg
                JOIN evidence ev ON ev.edge_id = eg.id
                WHERE eg.src_entity_id = e.id OR eg.dst_entity_id = e.id
            ) THEN 1 ELSE 0 END as is_blind_spot,
            NULL as blind_spot_severity
        FROM entities e
    """, (snapshot_id,))

    # 6. 复制边
    cursor.execute("""
        INSERT INTO brain_snapshot_edges (
            snapshot_id, edge_id, src_entity_id, dst_entity_id, edge_type,
            evidence_count, evidence_types
        )
        SELECT
            ? as snapshot_id,
            CAST(e.id AS TEXT),
            CAST(e.src_entity_id AS TEXT),
            CAST(e.dst_entity_id AS TEXT),
            e.type,
            COALESCE((
                SELECT COUNT(DISTINCT ev.id)
                FROM evidence ev
                WHERE ev.edge_id = e.id
            ), 0) as evidence_count,
            '[]' as evidence_types
        FROM edges e
    """, (snapshot_id,))

    conn.commit()

    return snapshot_id


def list_snapshots(store, limit: int = 10) -> List[SnapshotSummary]:
    """
    列出所有快照（按时间倒序）

    Args:
        store: BrainOS 数据库
        limit: 返回数量限制

    Returns:
        快照摘要列表
    """
    conn = store.connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id, timestamp, description,
            entity_count, edge_count, evidence_count,
            coverage_percentage, blind_spot_count,
            graph_version
        FROM brain_snapshots
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))

    snapshots = []
    for row in cursor.fetchall():
        snapshots.append(SnapshotSummary(
            snapshot_id=row[0],
            timestamp=row[1],
            description=row[2],
            entity_count=row[3],
            edge_count=row[4],
            evidence_count=row[5],
            coverage_percentage=row[6],
            blind_spot_count=row[7],
            graph_version=row[8]
        ))

    return snapshots


def load_snapshot(store, snapshot_id: str) -> Snapshot:
    """
    加载完整快照数据

    Args:
        store: BrainOS 数据库
        snapshot_id: 快照 ID

    Returns:
        完整快照对象

    Raises:
        ValueError: 快照不存在
    """
    conn = store.connect()
    cursor = conn.cursor()

    # 1. 加载摘要
    cursor.execute("""
        SELECT
            id, timestamp, description,
            entity_count, edge_count, evidence_count,
            coverage_percentage, blind_spot_count,
            graph_version
        FROM brain_snapshots
        WHERE id = ?
    """, (snapshot_id,))

    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Snapshot not found: {snapshot_id}")

    summary = SnapshotSummary(
        snapshot_id=row[0],
        timestamp=row[1],
        description=row[2],
        entity_count=row[3],
        edge_count=row[4],
        evidence_count=row[5],
        coverage_percentage=row[6],
        blind_spot_count=row[7],
        graph_version=row[8]
    )

    # 2. 加载实体
    cursor.execute("""
        SELECT
            entity_id, entity_type, entity_key, entity_name,
            evidence_count, coverage_sources, is_blind_spot, blind_spot_severity
        FROM brain_snapshot_entities
        WHERE snapshot_id = ?
    """, (snapshot_id,))

    entities = []
    for row in cursor.fetchall():
        entities.append(SnapshotEntity(
            entity_id=row[0],
            entity_type=row[1],
            entity_key=row[2],
            entity_name=row[3],
            evidence_count=row[4],
            coverage_sources=json.loads(row[5]) if row[5] else [],
            is_blind_spot=bool(row[6]),
            blind_spot_severity=row[7]
        ))

    # 3. 加载边
    cursor.execute("""
        SELECT
            edge_id, src_entity_id, dst_entity_id, edge_type,
            evidence_count, evidence_types
        FROM brain_snapshot_edges
        WHERE snapshot_id = ?
    """, (snapshot_id,))

    edges = []
    for row in cursor.fetchall():
        edges.append(SnapshotEdge(
            edge_id=row[0],
            src_entity_id=row[1],
            dst_entity_id=row[2],
            edge_type=row[3],
            evidence_count=row[4],
            evidence_types=json.loads(row[5]) if row[5] else []
        ))

    return Snapshot(
        summary=summary,
        entities=entities,
        edges=edges
    )


def delete_snapshot(store, snapshot_id: str) -> bool:
    """
    删除快照

    Args:
        store: BrainOS 数据库
        snapshot_id: 快照 ID

    Returns:
        是否成功删除
    """
    conn = store.connect()
    cursor = conn.cursor()

    # 1. 删除实体
    cursor.execute("DELETE FROM brain_snapshot_entities WHERE snapshot_id = ?", (snapshot_id,))

    # 2. 删除边
    cursor.execute("DELETE FROM brain_snapshot_edges WHERE snapshot_id = ?", (snapshot_id,))

    # 3. 删除快照记录
    cursor.execute("DELETE FROM brain_snapshots WHERE id = ?", (snapshot_id,))

    deleted = cursor.rowcount > 0

    conn.commit()

    return deleted
