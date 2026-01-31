"""
Lead Findings Deduplication Store

负责 lead_findings 表的幂等 upsert 和去重逻辑。
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from agentos.core.time import utc_now


logger = logging.getLogger(__name__)


class LeadFinding:
    """
    Lead Agent 发现的风险/问题

    Attributes:
        fingerprint: 唯一指纹（用于去重）
        code: 规则代码（如 "IDLE_TASK_3D"）
        severity: 严重级别（LOW, MEDIUM, HIGH, CRITICAL）
        title: 发现标题
        description: 详细描述
        window_kind: 扫描窗口（24h, 7d）
        first_seen_at: 首次发现时间
        last_seen_at: 最后发现时间
        count: 重复发现次数
        evidence: 证据数据（任意字典）
        linked_task_id: 关联的 follow-up task ID
    """

    def __init__(
        self,
        fingerprint: str,
        code: str,
        severity: str,
        title: str,
        description: Optional[str],
        window_kind: str,
        first_seen_at: Optional[datetime] = None,
        last_seen_at: Optional[datetime] = None,
        count: int = 1,
        evidence: Optional[Dict] = None,
        linked_task_id: Optional[str] = None,
    ):
        self.fingerprint = fingerprint
        self.code = code
        self.severity = severity
        self.title = title
        self.description = description
        self.window_kind = window_kind
        self.first_seen_at = first_seen_at or utc_now()
        self.last_seen_at = last_seen_at or utc_now()
        self.count = count
        self.evidence = evidence or {}
        self.linked_task_id = linked_task_id

    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "LeadFinding":
        """从数据库行创建 LeadFinding 对象"""
        return cls(
            fingerprint=row["fingerprint"],
            code=row["code"],
            severity=row["severity"],
            title=row["title"],
            description=row["description"],
            window_kind=row["window_kind"],
            first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
            last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
            count=row["count"],
            evidence=json.loads(row["evidence_json"]) if row["evidence_json"] else {},
            linked_task_id=row["linked_task_id"],
        )

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "fingerprint": self.fingerprint,
            "code": self.code,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "window_kind": self.window_kind,
            "first_seen_at": self.first_seen_at.isoformat(),
            "last_seen_at": self.last_seen_at.isoformat(),
            "count": self.count,
            "evidence": self.evidence,
            "linked_task_id": self.linked_task_id,
        }


class LeadFindingStore:
    """
    Lead Findings 存储层

    实现 fingerprint 幂等去重逻辑：
    - 如果 fingerprint 存在：更新 last_seen_at, count += 1
    - 如果不存在：插入新记录
    """

    def __init__(self, db_path: Path):
        """
        初始化 LeadFindingStore

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        logger.info(f"LeadFindingStore initialized with db: {db_path}")

    def upsert_finding(
        self,
        finding: LeadFinding,
        cursor: Optional[sqlite3.Cursor] = None
    ) -> bool:
        """
        幂等 upsert：通过 fingerprint 去重

        逻辑：
        - 如果 fingerprint 存在：更新 last_seen_at, count += 1
        - 如果不存在：插入新记录（first_seen_at = last_seen_at = now）

        Args:
            finding: LeadFinding 对象
            cursor: 可选的数据库游标（用于事务）

        Returns:
            True 表示新建记录，False 表示更新已有记录
        """
        own_connection = cursor is None
        if own_connection:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

        try:
            # 序列化 evidence
            evidence_json = json.dumps(finding.evidence, ensure_ascii=False)

            # 先检查记录是否存在（用于判断是 INSERT 还是 UPDATE）
            cursor.execute(
                "SELECT 1 FROM lead_findings WHERE fingerprint = ?",
                (finding.fingerprint,)
            )
            exists = cursor.fetchone() is not None

            # 原子 upsert（SQLite 3.24+）
            # INSERT ... ON CONFLICT(fingerprint) DO UPDATE
            cursor.execute(
                """
                INSERT INTO lead_findings (
                    fingerprint, code, severity, title, description,
                    window_kind, first_seen_at, last_seen_at, count,
                    evidence_json, linked_task_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    count = lead_findings.count + 1,
                    evidence_json = excluded.evidence_json
                """,
                (
                    finding.fingerprint,
                    finding.code,
                    finding.severity,
                    finding.title,
                    finding.description,
                    finding.window_kind,
                    finding.first_seen_at.isoformat(),
                    finding.last_seen_at.isoformat(),
                    finding.count,
                    evidence_json,
                    finding.linked_task_id,
                ),
            )

            # 判断是新建还是更新
            is_new = not exists

            if own_connection:
                conn.commit()

            action = "inserted" if is_new else "updated"
            logger.debug(
                f"Finding {action}: {finding.fingerprint} "
                f"(code={finding.code}, severity={finding.severity})"
            )

            return is_new

        except Exception as e:
            logger.error(f"Failed to upsert finding: {e}", exc_info=True)
            if own_connection:
                conn.rollback()
            raise

        finally:
            if own_connection:
                conn.close()

    def link_task(
        self,
        fingerprint: str,
        task_id: str,
        cursor: Optional[sqlite3.Cursor] = None
    ) -> None:
        """
        关联创建的 follow-up task

        Args:
            fingerprint: Finding 的 fingerprint
            task_id: 创建的 task ID
            cursor: 可选的数据库游标（用于事务）
        """
        own_connection = cursor is None
        if own_connection:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE lead_findings
                SET linked_task_id = ?
                WHERE fingerprint = ?
                """,
                (task_id, fingerprint),
            )

            if own_connection:
                conn.commit()

            logger.debug(f"Linked task {task_id} to finding {fingerprint}")

        except Exception as e:
            logger.error(f"Failed to link task: {e}", exc_info=True)
            if own_connection:
                conn.rollback()
            raise

        finally:
            if own_connection:
                conn.close()

    def get_finding(
        self,
        fingerprint: str,
        cursor: Optional[sqlite3.Cursor] = None
    ) -> Optional[LeadFinding]:
        """
        获取单个 finding

        Args:
            fingerprint: Finding 的 fingerprint
            cursor: 可选的数据库游标

        Returns:
            LeadFinding 对象，如果不存在返回 None
        """
        own_connection = cursor is None
        if own_connection:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT * FROM lead_findings
                WHERE fingerprint = ?
                """,
                (fingerprint,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return LeadFinding.from_db_row(row)

        finally:
            if own_connection:
                conn.close()

    def get_recent_findings(
        self,
        limit: int = 100,
        severity: Optional[str] = None,
        window_kind: Optional[str] = None,
    ) -> List[LeadFinding]:
        """
        获取最近的 findings

        Args:
            limit: 返回数量限制
            severity: 可选的严重级别过滤
            window_kind: 可选的窗口类型过滤

        Returns:
            LeadFinding 对象列表（按 last_seen_at 降序）
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 构建查询
            sql = "SELECT * FROM lead_findings WHERE 1=1"
            params = []

            if severity:
                sql += " AND severity = ?"
                params.append(severity)

            if window_kind:
                sql += " AND window_kind = ?"
                params.append(window_kind)

            sql += " ORDER BY last_seen_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(sql, params)

            rows = cursor.fetchall()
            return [LeadFinding.from_db_row(row) for row in rows]

        finally:
            conn.close()

    def get_unlinked_findings(
        self,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> List[LeadFinding]:
        """
        获取未关联 task 的 findings（需要创建 follow-up task）

        Args:
            severity: 可选的严重级别过滤
            limit: 返回数量限制

        Returns:
            LeadFinding 对象列表（按 severity 和 last_seen_at 排序）
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 构建查询
            sql = """
                SELECT * FROM lead_findings
                WHERE linked_task_id IS NULL
            """
            params = []

            if severity:
                sql += " AND severity = ?"
                params.append(severity)

            sql += """
                ORDER BY
                    CASE severity
                        WHEN 'CRITICAL' THEN 1
                        WHEN 'HIGH' THEN 2
                        WHEN 'MEDIUM' THEN 3
                        WHEN 'LOW' THEN 4
                    END,
                    last_seen_at DESC
                LIMIT ?
            """
            params.append(limit)

            cursor.execute(sql, params)

            rows = cursor.fetchall()
            return [LeadFinding.from_db_row(row) for row in rows]

        finally:
            conn.close()

    def get_stats(self) -> Dict:
        """
        获取 findings 统计信息

        Returns:
            统计字典：
            {
                "total_findings": int,
                "by_severity": {"CRITICAL": 1, "HIGH": 2, ...},
                "by_window": {"24h": 5, "7d": 3, ...},
                "unlinked_count": int,
            }
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 总数
            cursor.execute("SELECT COUNT(*) as total FROM lead_findings")
            total = cursor.fetchone()["total"]

            # 按严重级别统计
            cursor.execute(
                """
                SELECT severity, COUNT(*) as count
                FROM lead_findings
                GROUP BY severity
                """
            )
            by_severity = {row["severity"]: row["count"] for row in cursor.fetchall()}

            # 按窗口统计
            cursor.execute(
                """
                SELECT window_kind, COUNT(*) as count
                FROM lead_findings
                GROUP BY window_kind
                """
            )
            by_window = {row["window_kind"]: row["count"] for row in cursor.fetchall()}

            # 未关联 task 数量
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM lead_findings
                WHERE linked_task_id IS NULL
                """
            )
            unlinked = cursor.fetchone()["count"]

            return {
                "total_findings": total,
                "by_severity": by_severity,
                "by_window": by_window,
                "unlinked_count": unlinked,
            }

        finally:
            conn.close()
