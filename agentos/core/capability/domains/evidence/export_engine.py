"""
Export Engine for AgentOS v3

Evidence export for compliance audits and legal discovery.

Core Responsibilities:
1. Query evidence based on filters
2. Export to multiple formats (JSON, PDF, CSV, HTML)
3. Generate human-readable audit reports
4. Manage temporary export files (with expiration)
5. Cryptographic verification (SHA256 hashes)

Design Principles:
- Multiple export formats for different use cases
- Audit-ready reports (PDF with metadata)
- Automatic cleanup of expired exports
- Complete traceability (who exported what when)

Export Formats:
- JSON: Machine-readable, full fidelity
- PDF: Human-readable audit report
- CSV: Spreadsheet analysis (Excel-compatible)
- HTML: Web-friendly report

Schema: v51 (evidence_exports)
"""

import logging
import json
import csv
import os
import sqlite3
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Any
from ulid import ULID

from agentos.core.capability.domains.evidence.models import (
    Evidence,
    ExportQuery,
    ExportPackage,
    ExportFormat,
    OperationType,
    hash_content,
)
from agentos.core.capability.domains.evidence.evidence_collector import (
    get_evidence_collector,
)
from agentos.core.time import utc_now_ms, from_epoch_ms
from agentos.core.db.registry_db import get_db

logger = logging.getLogger(__name__)


# ===================================================================
# Exceptions
# ===================================================================

class ExportError(Exception):
    """Raised when export fails"""
    pass


class UnsupportedFormatError(Exception):
    """Raised when export format not supported"""
    pass


class ExportNotFoundError(Exception):
    """Raised when export record not found"""
    pass


# ===================================================================
# Export Engine
# ===================================================================

class ExportEngine:
    """
    Evidence export engine for compliance and audit.

    Supports multiple formats for different use cases.

    Example:
        engine = ExportEngine()

        # Export to JSON
        export_id = engine.export(
            query=ExportQuery(
                agent_id="chat_agent",
                start_time_ms=start,
                end_time_ms=end
            ),
            format=ExportFormat.JSON,
            exported_by="compliance_officer"
        )

        # Get export package
        package = engine.get_export(export_id)
        print(f"Exported {package.evidence_count} records to {package.file_path}")

        # Export to PDF report
        export_id = engine.export(
            query=ExportQuery(operation_type=OperationType.ACTION),
            format=ExportFormat.PDF,
            exported_by="auditor"
        )
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        export_dir: Optional[str] = None,
    ):
        """
        Initialize export engine.

        Args:
            db_path: Optional database path
            export_dir: Optional export directory (default: /tmp/agentos_exports)
        """
        self.db_path = db_path
        self._db_conn = None
        self._evidence_collector = get_evidence_collector(db_path)

        # Export directory
        if export_dir is None:
            export_dir = "/tmp/agentos_exports"
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

        self._ensure_tables()
        logger.debug(f"ExportEngine initialized (export_dir: {self.export_dir})")

    def _get_db(self):
        """Get database connection"""
        if self.db_path:
            if not self._db_conn:
                self._db_conn = sqlite3.connect(self.db_path)
                self._db_conn.row_factory = sqlite3.Row
            return self._db_conn
        else:
            return get_db()

    def _execute_sql(self, sql: str, params=None):
        """Execute SQL with parameters"""
        conn = self._get_db()
        if params:
            return conn.execute(sql, params)
        else:
            return conn.execute(sql)

    def _ensure_tables(self):
        """Ensure export tables exist"""
        try:
            self._execute_sql("SELECT 1 FROM evidence_exports LIMIT 1")
        except Exception as e:
            logger.warning(f"evidence_exports table may not exist: {e}")
            self._create_minimal_schema()

    def _create_minimal_schema(self):
        """Create minimal export schema for testing"""
        logger.info("Creating minimal export schema")
        conn = self._get_db()

        # Evidence exports table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence_exports (
                export_id TEXT PRIMARY KEY,
                query_json TEXT NOT NULL,
                format TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                file_hash TEXT NOT NULL,
                exported_by TEXT NOT NULL,
                exported_at_ms INTEGER NOT NULL,
                expires_at_ms INTEGER
            )
        """)

        # Create index
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_export_by "
            "ON evidence_exports(exported_by, exported_at_ms DESC)"
        )

        conn.commit()
        logger.info("Minimal export schema created")

    # ===================================================================
    # Core Export API
    # ===================================================================

    def export(
        self,
        query: ExportQuery,
        format: ExportFormat = ExportFormat.JSON,
        exported_by: str = "system",
        expires_in_hours: Optional[int] = 24,
    ) -> str:
        """
        Export evidence based on query.

        Args:
            query: Evidence query specification
            format: Export format (JSON, PDF, CSV, HTML)
            exported_by: Agent initiating export
            expires_in_hours: Hours until export file expires (None = never)

        Returns:
            export_id: Unique export identifier

        Raises:
            ExportError: If export fails
            UnsupportedFormatError: If format not supported
        """
        logger.info(
            f"Exporting evidence in {format.value} format for {exported_by}"
        )

        # Generate export ID
        export_id = f"export-{ULID()}"
        exported_at_ms = utc_now_ms()

        # Calculate expiration
        expires_at_ms = None
        if expires_in_hours:
            expires_at_ms = exported_at_ms + (expires_in_hours * 60 * 60 * 1000)

        try:
            # Query evidence
            evidences = self._query_evidence(query)

            if not evidences:
                logger.warning("No evidence found matching query")

            # Export to format
            if format == ExportFormat.JSON:
                file_path = self._export_json(export_id, evidences)
            elif format == ExportFormat.PDF:
                file_path = self._export_pdf(export_id, evidences, query)
            elif format == ExportFormat.CSV:
                file_path = self._export_csv(export_id, evidences)
            elif format == ExportFormat.HTML:
                file_path = self._export_html(export_id, evidences, query)
            else:
                raise UnsupportedFormatError(f"Format {format} not supported")

            # Calculate file metadata
            file_size_bytes = os.path.getsize(file_path)
            with open(file_path, "rb") as f:
                file_hash = hash_content(f.read().decode("utf-8", errors="ignore"))

            # Calculate time range
            time_range_ms = None
            if evidences:
                timestamps = [e.timestamp_ms for e in evidences]
                time_range_ms = max(timestamps) - min(timestamps)

            # Create export package
            package = ExportPackage(
                export_id=export_id,
                query=query,
                format=format,
                exported_by=exported_by,
                exported_at_ms=exported_at_ms,
                expires_at_ms=expires_at_ms,
                file_path=str(file_path),
                file_size_bytes=file_size_bytes,
                file_hash=file_hash,
                evidence_count=len(evidences),
                time_range_ms=time_range_ms,
            )

            # Store export record
            self._store_export(package)

            logger.info(
                f"Exported {len(evidences)} evidence records to {file_path} "
                f"(export_id: {export_id})"
            )

            return export_id

        except Exception as e:
            logger.error(f"Export {export_id} failed: {e}")
            raise ExportError(f"Export failed: {e}") from e

    def _query_evidence(self, query: ExportQuery) -> List[Evidence]:
        """
        Query evidence based on export query.

        Args:
            query: Export query

        Returns:
            List of Evidence records
        """
        return self._evidence_collector.query(
            agent_id=query.agent_id,
            operation_type=query.operation_type,
            capability_id=query.capability_id,
            decision_id=None,  # Not in ExportQuery
            start_time_ms=query.start_time_ms,
            end_time_ms=query.end_time_ms,
            limit=query.limit or 1000,
        )

    # ===================================================================
    # Format Exporters
    # ===================================================================

    def _export_json(self, export_id: str, evidences: List[Evidence]) -> Path:
        """
        Export to JSON format.

        Args:
            export_id: Export ID
            evidences: Evidence records

        Returns:
            Path to JSON file
        """
        file_path = self.export_dir / f"{export_id}.json"

        # Convert to JSON
        data = {
            "export_id": export_id,
            "exported_at_ms": utc_now_ms(),
            "evidence_count": len(evidences),
            "evidences": [e.model_dump() for e in evidences],
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.debug(f"Exported JSON to {file_path}")
        return file_path

    def _export_pdf(
        self, export_id: str, evidences: List[Evidence], query: ExportQuery
    ) -> Path:
        """
        Export to PDF format (human-readable audit report).

        NOTE: This is a simplified implementation. Production would use
        a proper PDF library like reportlab or weasyprint.

        Args:
            export_id: Export ID
            evidences: Evidence records
            query: Query used for export

        Returns:
            Path to PDF file (currently text file)
        """
        file_path = self.export_dir / f"{export_id}.pdf.txt"

        # Generate report (as text for now)
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("AgentOS Evidence Audit Report")
        report_lines.append("=" * 80)
        report_lines.append("")
        report_lines.append(f"Export ID: {export_id}")
        report_lines.append(
            f"Generated: {from_epoch_ms(utc_now_ms()).isoformat()}"
        )
        report_lines.append(f"Evidence Count: {len(evidences)}")
        report_lines.append("")

        # Query details
        report_lines.append("Query Filters:")
        if query.agent_id:
            report_lines.append(f"  Agent: {query.agent_id}")
        if query.operation_type:
            report_lines.append(f"  Operation Type: {query.operation_type.value}")
        if query.capability_id:
            report_lines.append(f"  Capability: {query.capability_id}")
        if query.start_time_ms:
            report_lines.append(
                f"  Start Time: {from_epoch_ms(query.start_time_ms).isoformat()}"
            )
        if query.end_time_ms:
            report_lines.append(
                f"  End Time: {from_epoch_ms(query.end_time_ms).isoformat()}"
            )
        report_lines.append("")
        report_lines.append("-" * 80)
        report_lines.append("")

        # Evidence details
        for idx, evidence in enumerate(evidences, 1):
            report_lines.append(f"Evidence #{idx}")
            report_lines.append(f"  ID: {evidence.evidence_id}")
            report_lines.append(
                f"  Timestamp: {from_epoch_ms(evidence.timestamp_ms).isoformat()}"
            )
            report_lines.append(
                f"  Operation: {evidence.operation['type']} - {evidence.operation['capability_id']}"
            )
            report_lines.append(f"  Agent: {evidence.context.get('agent_id', 'unknown')}")

            # Input/Output summaries
            if evidence.input.get("params_summary"):
                report_lines.append(f"  Input: {evidence.input['params_summary']}")
            if evidence.output.get("result_summary"):
                report_lines.append(f"  Output: {evidence.output['result_summary']}")

            # Integrity
            report_lines.append(f"  Integrity Hash: {evidence.integrity.hash[:16]}...")

            report_lines.append("")

        report_lines.append("-" * 80)
        report_lines.append("End of Report")
        report_lines.append("=" * 80)

        with open(file_path, "w") as f:
            f.write("\n".join(report_lines))

        logger.debug(f"Exported PDF report to {file_path}")
        return file_path

    def _export_csv(self, export_id: str, evidences: List[Evidence]) -> Path:
        """
        Export to CSV format (for spreadsheet analysis).

        Args:
            export_id: Export ID
            evidences: Evidence records

        Returns:
            Path to CSV file
        """
        file_path = self.export_dir / f"{export_id}.csv"

        # Define CSV columns
        columns = [
            "evidence_id",
            "timestamp_ms",
            "timestamp_iso",
            "operation_type",
            "capability_id",
            "operation_id",
            "agent_id",
            "session_id",
            "project_id",
            "decision_id",
            "input_hash",
            "output_hash",
            "integrity_hash",
            "provenance_host",
        ]

        # Write CSV
        with open(file_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()

            for evidence in evidences:
                row = {
                    "evidence_id": evidence.evidence_id,
                    "timestamp_ms": evidence.timestamp_ms,
                    "timestamp_iso": from_epoch_ms(evidence.timestamp_ms).isoformat(),
                    "operation_type": evidence.operation["type"],
                    "capability_id": evidence.operation["capability_id"],
                    "operation_id": evidence.operation["id"],
                    "agent_id": evidence.context.get("agent_id", ""),
                    "session_id": evidence.context.get("session_id", ""),
                    "project_id": evidence.context.get("project_id", ""),
                    "decision_id": evidence.context.get("decision_id", ""),
                    "input_hash": evidence.input.get("params_hash", ""),
                    "output_hash": evidence.output.get("result_hash", ""),
                    "integrity_hash": evidence.integrity.hash,
                    "provenance_host": evidence.provenance.host,
                }
                writer.writerow(row)

        logger.debug(f"Exported CSV to {file_path}")
        return file_path

    def _export_html(
        self, export_id: str, evidences: List[Evidence], query: ExportQuery
    ) -> Path:
        """
        Export to HTML format (web-friendly report).

        Args:
            export_id: Export ID
            evidences: Evidence records
            query: Query used for export

        Returns:
            Path to HTML file
        """
        file_path = self.export_dir / f"{export_id}.html"

        # Generate HTML report
        html_lines = []
        html_lines.append("<!DOCTYPE html>")
        html_lines.append("<html>")
        html_lines.append("<head>")
        html_lines.append("  <title>AgentOS Evidence Report</title>")
        html_lines.append("  <style>")
        html_lines.append("    body { font-family: Arial, sans-serif; margin: 20px; }")
        html_lines.append("    h1 { color: #333; }")
        html_lines.append("    table { border-collapse: collapse; width: 100%; }")
        html_lines.append("    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }")
        html_lines.append("    th { background-color: #f2f2f2; }")
        html_lines.append("    .hash { font-family: monospace; font-size: 0.9em; }")
        html_lines.append("  </style>")
        html_lines.append("</head>")
        html_lines.append("<body>")
        html_lines.append("  <h1>AgentOS Evidence Audit Report</h1>")
        html_lines.append(f"  <p><strong>Export ID:</strong> {export_id}</p>")
        html_lines.append(
            f"  <p><strong>Generated:</strong> {from_epoch_ms(utc_now_ms()).isoformat()}</p>"
        )
        html_lines.append(f"  <p><strong>Evidence Count:</strong> {len(evidences)}</p>")

        # Query details
        html_lines.append("  <h2>Query Filters</h2>")
        html_lines.append("  <ul>")
        if query.agent_id:
            html_lines.append(f"    <li><strong>Agent:</strong> {query.agent_id}</li>")
        if query.operation_type:
            html_lines.append(
                f"    <li><strong>Operation Type:</strong> {query.operation_type.value}</li>"
            )
        if query.capability_id:
            html_lines.append(
                f"    <li><strong>Capability:</strong> {query.capability_id}</li>"
            )
        html_lines.append("  </ul>")

        # Evidence table
        html_lines.append("  <h2>Evidence Records</h2>")
        html_lines.append("  <table>")
        html_lines.append("    <tr>")
        html_lines.append("      <th>ID</th>")
        html_lines.append("      <th>Timestamp</th>")
        html_lines.append("      <th>Operation</th>")
        html_lines.append("      <th>Agent</th>")
        html_lines.append("      <th>Integrity Hash</th>")
        html_lines.append("    </tr>")

        for evidence in evidences:
            html_lines.append("    <tr>")
            html_lines.append(f"      <td>{evidence.evidence_id}</td>")
            html_lines.append(
                f"      <td>{from_epoch_ms(evidence.timestamp_ms).isoformat()}</td>"
            )
            html_lines.append(
                f"      <td>{evidence.operation['type']}<br/>{evidence.operation['capability_id']}</td>"
            )
            html_lines.append(
                f"      <td>{evidence.context.get('agent_id', 'unknown')}</td>"
            )
            html_lines.append(
                f"      <td class='hash'>{evidence.integrity.hash[:16]}...</td>"
            )
            html_lines.append("    </tr>")

        html_lines.append("  </table>")
        html_lines.append("</body>")
        html_lines.append("</html>")

        with open(file_path, "w") as f:
            f.write("\n".join(html_lines))

        logger.debug(f"Exported HTML to {file_path}")
        return file_path

    # ===================================================================
    # Export Management
    # ===================================================================

    def _store_export(self, package: ExportPackage):
        """
        Store export record in database.

        Args:
            package: Export package to store
        """
        conn = self._get_db()

        query_json = package.query.model_dump_json()

        conn.execute(
            """
            INSERT INTO evidence_exports (
                export_id,
                query_json,
                format,
                file_path,
                file_size_bytes,
                file_hash,
                exported_by,
                exported_at_ms,
                expires_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                package.export_id,
                query_json,
                package.format.value,
                package.file_path,
                package.file_size_bytes,
                package.file_hash,
                package.exported_by,
                package.exported_at_ms,
                package.expires_at_ms,
            ),
        )

        conn.commit()

    def get_export(self, export_id: str) -> Optional[ExportPackage]:
        """
        Get export package by ID.

        Args:
            export_id: Export ID

        Returns:
            ExportPackage if found, None otherwise
        """
        conn = self._get_db()
        cursor = conn.execute(
            """
            SELECT * FROM evidence_exports WHERE export_id = ?
            """,
            (export_id,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        # Parse query
        query = ExportQuery.model_validate_json(row["query_json"])

        return ExportPackage(
            export_id=row["export_id"],
            query=query,
            format=ExportFormat(row["format"]),
            exported_by=row["exported_by"],
            exported_at_ms=row["exported_at_ms"],
            expires_at_ms=row["expires_at_ms"],
            file_path=row["file_path"],
            file_size_bytes=row["file_size_bytes"],
            file_hash=row["file_hash"],
            evidence_count=0,  # Not stored in DB
        )

    def cleanup_expired_exports(self) -> int:
        """
        Clean up expired export files.

        Returns:
            Number of exports cleaned up
        """
        conn = self._get_db()
        now_ms = utc_now_ms()

        # Find expired exports
        cursor = conn.execute(
            """
            SELECT export_id, file_path FROM evidence_exports
            WHERE expires_at_ms IS NOT NULL AND expires_at_ms < ?
            """,
            (now_ms,),
        )

        cleaned_count = 0
        for row in cursor.fetchall():
            export_id = row["export_id"]
            file_path = row["file_path"]

            # Delete file
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"Deleted expired export file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete expired export file {file_path}: {e}")

            # Delete record
            conn.execute(
                "DELETE FROM evidence_exports WHERE export_id = ?",
                (export_id,),
            )

            cleaned_count += 1

        conn.commit()

        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired exports")

        return cleaned_count

    # ===================================================================
    # Statistics
    # ===================================================================

    def get_stats(self) -> Dict[str, Any]:
        """
        Get export statistics.

        Returns:
            Statistics dict
        """
        conn = self._get_db()

        stats = {}

        # Total exports
        cursor = conn.execute("SELECT COUNT(*) as count FROM evidence_exports")
        stats["total_exports"] = cursor.fetchone()["count"]

        # Exports by format
        cursor = conn.execute(
            "SELECT format, COUNT(*) as count FROM evidence_exports GROUP BY format"
        )
        for row in cursor.fetchall():
            stats[f"exports_{row['format']}"] = row["count"]

        # Active exports (not expired)
        cursor = conn.execute(
            """
            SELECT COUNT(*) as count FROM evidence_exports
            WHERE expires_at_ms IS NULL OR expires_at_ms > ?
            """,
            (utc_now_ms(),),
        )
        stats["active_exports"] = cursor.fetchone()["count"]

        # Total export size
        cursor = conn.execute("SELECT SUM(file_size_bytes) as total FROM evidence_exports")
        total_bytes = cursor.fetchone()["total"] or 0
        stats["total_size_bytes"] = total_bytes
        stats["total_size_mb"] = total_bytes / (1024 * 1024)

        return stats


# ===================================================================
# Global Singleton
# ===================================================================

_export_engine_instance: Optional[ExportEngine] = None


def get_export_engine(
    db_path: Optional[str] = None, export_dir: Optional[str] = None
) -> ExportEngine:
    """
    Get global ExportEngine singleton.

    Args:
        db_path: Optional database path
        export_dir: Optional export directory

    Returns:
        Singleton ExportEngine instance
    """
    global _export_engine_instance
    if _export_engine_instance is None:
        _export_engine_instance = ExportEngine(db_path=db_path, export_dir=export_dir)
    return _export_engine_instance
