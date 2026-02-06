"""Extended Task Manager with advanced queries for UI interfaces"""

import sqlite3
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone

from agentos.core.task import TaskManager
from agentos.core.task.models import Task


class TaskManagerExtended(TaskManager):
    """Extended Task Manager with advanced query capabilities for UI interfaces"""
    
    def list_tasks_paginated(
        self,
        offset: int = 0,
        limit: int = 50,
        status_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        sort_by: str = "updated_at",
        order: str = "DESC"
    ) -> Tuple[List[Task], int]:
        """
        List tasks with pagination and filtering
        
        Args:
            offset: Starting offset
            limit: Maximum number of tasks to return
            status_filter: Filter by status (None = all)
            search_query: Search in task title
            sort_by: Column to sort by
            order: Sort order (ASC/DESC)
            
        Returns:
            Tuple of (task_list, total_count)
        """
        conn = self._get_conn()
        
        # Build WHERE clause
        where_clauses = []
        params = []
        
        if status_filter:
            where_clauses.append("status = ?")
            params.append(status_filter)
        
        if search_query:
            where_clauses.append("title LIKE ?")
            params.append(f"%{search_query}%")
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Get total count
        count_sql = f"SELECT COUNT(*) as count FROM tasks WHERE {where_sql}"
        cursor = conn.cursor()
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()[0]
        
        # Get tasks
        # Validate sort_by and order to prevent SQL injection
        allowed_sort_columns = ["task_id", "title", "status", "created_at", "updated_at"]
        if sort_by not in allowed_sort_columns:
            sort_by = "updated_at"
        
        order = order.upper()
        if order not in ["ASC", "DESC"]:
            order = "DESC"
        
        tasks_sql = f"""
            SELECT task_id, title, status, session_id, created_at, updated_at, created_by, metadata
            FROM tasks
            WHERE {where_sql}
            ORDER BY {sort_by} {order}
            LIMIT ? OFFSET ?
        """
        
        cursor.execute(tasks_sql, params + [limit, offset])
        rows = cursor.fetchall()
        
        tasks = []
        for row in rows:
            import json
            task = Task(
                task_id=row[0],
                title=row[1],
                status=row[2],
                session_id=row[3],
                created_at=row[4],
                updated_at=row[5],
                created_by=row[6],
                metadata=json.loads(row[7]) if row[7] else {},
            )
            tasks.append(task)
        
        conn.close()
        return tasks, total_count
    
    def get_task_stats(self) -> Dict[str, int]:
        """
        Get task statistics by status
        
        Returns:
            Dictionary with status counts
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM tasks
            GROUP BY status
        """)
        
        stats = {}
        total = 0
        for row in cursor.fetchall():
            status = row[0]
            count = row[1]
            stats[status] = count
            total += count
        
        stats["total"] = total
        
        conn.close()
        return stats
    
    def get_task_audits_paginated(
        self,
        task_id: str,
        offset: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get task audit logs with pagination
        
        Args:
            task_id: Task ID
            offset: Starting offset
            limit: Maximum number of audits to return
            
        Returns:
            List of audit log entries
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT audit_id, event_type, created_at, level, payload, payload
            FROM task_audits
            WHERE task_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (task_id, limit, offset))
        
        audits = []
        for row in cursor.fetchall():
            import json
            payload = json.loads(row[5]) if row[5] else {}
            audit = {
                "audit_id": row[0],
                "event_type": row[1],
                "timestamp": row[2],  # created_at mapped to timestamp
                "created_at": row[2],
                "level": row[3],
                "message": payload.get("message", ""),  # Extract from payload
                "payload": payload,
            }
            audits.append(audit)
        
        conn.close()
        return audits
    
    def get_task_agents(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get task agent execution records
        
        Args:
            task_id: Task ID
            
        Returns:
            List of agent execution records
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT agent_id, agent_type, started_at, ended_at, status, output, error
            FROM task_agents
            WHERE task_id = ?
            ORDER BY started_at DESC
        """, (task_id,))
        
        agents = []
        for row in cursor.fetchall():
            import json
            agent = {
                "agent_id": row[0],
                "agent_type": row[1],
                "started_at": row[2],
                "ended_at": row[3],
                "status": row[4],
                "output": json.loads(row[5]) if row[5] else None,
                "error": row[6],
            }
            agents.append(agent)
        
        conn.close()
        return agents
    
    def watch_task_logs(self, task_id: str, last_timestamp: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get new task logs since last_timestamp (for watch mode)
        
        Args:
            task_id: Task ID
            last_timestamp: Only return logs after this timestamp
            
        Returns:
            List of new log entries
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        if last_timestamp:
            cursor.execute("""
                SELECT audit_id, event_type, timestamp, level, message, payload
                FROM task_audits
                WHERE task_id = ? AND timestamp > ?
                ORDER BY timestamp ASC
            """, (task_id, last_timestamp))
        else:
            # Return last 50 logs
            cursor.execute("""
                SELECT audit_id, event_type, timestamp, level, message, payload
                FROM task_audits
                WHERE task_id = ?
                ORDER BY timestamp DESC
                LIMIT 50
            """, (task_id,))
        
        logs = []
        for row in cursor.fetchall():
            import json
            log = {
                "audit_id": row[0],
                "event_type": row[1],
                "timestamp": row[2],
                "level": row[3],
                "message": row[4],
                "payload": json.loads(row[5]) if row[5] else {},
            }
            logs.append(log)
        
        conn.close()
        
        # If we got all logs, reverse to chronological order
        if not last_timestamp:
            logs.reverse()
        
        return logs
