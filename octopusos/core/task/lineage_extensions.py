"""Task Manager extensions for Phase B.1 PR-3: Three-way navigation"""

import sqlite3
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class TaskLineageExtensions:
    """Extensions to TaskManager for three-way navigation (task ↔ chat ↔ artifact)"""
    
    def __init__(self, db_path: str):
        """Initialize extensions
        
        Args:
            db_path: Database path
        """
        self.db_path = db_path
    
    def get_related_chats(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all chat sessions related to a task
        
        Args:
            task_id: Task ID
        
        Returns:
            List of chat session dicts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Method 1: task_lineage with kind='chat_session'
            cursor.execute("""
                SELECT DISTINCT l.ref_id as session_id, s.title, s.created_at
                FROM task_lineage l
                JOIN chat_sessions s ON l.ref_id = s.session_id
                WHERE l.task_id = ? AND l.kind = 'chat_session'
                ORDER BY s.created_at DESC
            """, (task_id,))
            
            lineage_chats = cursor.fetchall()
            
            # Method 2: chat_sessions with task_id FK
            cursor.execute("""
                SELECT session_id, title, created_at
                FROM chat_sessions
                WHERE task_id = ?
                ORDER BY created_at DESC
            """, (task_id,))
            
            direct_chats = cursor.fetchall()
            
            # Combine and deduplicate
            session_ids = set()
            results = []
            
            for row in list(lineage_chats) + list(direct_chats):
                session_id = row["session_id"]
                if session_id not in session_ids:
                    session_ids.add(session_id)
                    results.append({
                        "session_id": session_id,
                        "title": row["title"] or "Untitled Chat",
                        "created_at": row["created_at"]
                    })
            
            return results
        
        finally:
            conn.close()
    
    def get_related_artifacts(
        self,
        task_id: str,
        artifact_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all artifacts related to a task
        
        Args:
            task_id: Task ID
            artifact_type: Optional filter by type (summary/requirements/decision)
        
        Returns:
            List of artifact dicts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Method 1: artifacts with task_id FK
            if artifact_type:
                cursor.execute("""
                    SELECT artifact_id, artifact_type, title, content,
                           version, created_at, metadata
                    FROM artifacts
                    WHERE task_id = ? AND artifact_type = ?
                    ORDER BY created_at DESC
                """, (task_id, artifact_type))
            else:
                cursor.execute("""
                    SELECT artifact_id, artifact_type, title, content,
                           version, created_at, metadata
                    FROM artifacts
                    WHERE task_id = ?
                    ORDER BY created_at DESC
                """, (task_id,))
            
            direct_artifacts = cursor.fetchall()
            
            # Method 2: task_lineage with kind='artifact' (future enhancement)
            cursor.execute("""
                SELECT DISTINCT l.ref_id as artifact_id
                FROM task_lineage l
                WHERE l.task_id = ? AND l.kind = 'artifact'
            """, (task_id,))
            
            lineage_artifact_ids = [row["artifact_id"] for row in cursor.fetchall()]
            
            # Fetch artifacts from lineage
            results = []
            for row in direct_artifacts:
                results.append({
                    "artifact_id": row["artifact_id"],
                    "artifact_type": row["artifact_type"],
                    "title": row["title"],
                    "content_preview": row["content"][:200] if row["content"] else "",
                    "version": row["version"],
                    "created_at": row["created_at"]
                })
            
            return results
        
        finally:
            conn.close()
    
    def get_related_tasks_from_chat(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all tasks related to a chat session
        
        Args:
            session_id: Chat session ID
        
        Returns:
            List of task dicts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Method 1: Reverse lookup in task_lineage
            cursor.execute("""
                SELECT DISTINCT t.task_id, t.title, t.status, t.created_at
                FROM tasks t
                JOIN task_lineage l ON t.task_id = l.task_id
                WHERE l.kind = 'chat_session' AND l.ref_id = ?
                ORDER BY t.created_at DESC
            """, (session_id,))
            
            lineage_tasks = cursor.fetchall()
            
            # Method 2: chat_sessions with task_id FK
            cursor.execute("""
                SELECT t.task_id, t.title, t.status, t.created_at
                FROM tasks t
                JOIN chat_sessions s ON s.task_id = t.task_id
                WHERE s.session_id = ?
                ORDER BY t.created_at DESC
            """, (session_id,))
            
            direct_tasks = cursor.fetchall()
            
            # Combine and deduplicate
            task_ids = set()
            results = []
            
            for row in list(lineage_tasks) + list(direct_tasks):
                task_id = row["task_id"]
                if task_id not in task_ids:
                    task_ids.add(task_id)
                    results.append({
                        "task_id": task_id,
                        "title": row["title"],
                        "status": row["status"],
                        "created_at": row["created_at"]
                    })
            
            return results
        
        finally:
            conn.close()
    
    def get_artifacts_from_chat(
        self,
        session_id: str,
        artifact_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all artifacts from a chat session
        
        Args:
            session_id: Chat session ID
            artifact_type: Optional filter by type
        
        Returns:
            List of artifact dicts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            if artifact_type:
                cursor.execute("""
                    SELECT artifact_id, artifact_type, title, content,
                           version, created_at, metadata
                    FROM artifacts
                    WHERE session_id = ? AND artifact_type = ?
                    ORDER BY created_at DESC
                """, (session_id, artifact_type))
            else:
                cursor.execute("""
                    SELECT artifact_id, artifact_type, title, content,
                           version, created_at, metadata
                    FROM artifacts
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                """, (session_id,))
            
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    "artifact_id": row["artifact_id"],
                    "artifact_type": row["artifact_type"],
                    "title": row["title"],
                    "content_preview": row["content"][:200] if row["content"] else "",
                    "version": row["version"],
                    "created_at": row["created_at"]
                })
            
            return results
        
        finally:
            conn.close()
    
    def get_usage_by_artifact(self, artifact_id: str) -> Dict[str, Any]:
        """Get all tasks and chats that use an artifact
        
        Args:
            artifact_id: Artifact ID
        
        Returns:
            Dict with used_by_tasks and used_by_chats
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Get artifact metadata
            cursor.execute("""
                SELECT session_id, task_id, artifact_type
                FROM artifacts
                WHERE artifact_id = ?
            """, (artifact_id,))
            
            artifact = cursor.fetchone()
            if not artifact:
                return {"used_by_tasks": [], "used_by_chats": []}
            
            results = {
                "artifact_type": artifact["artifact_type"],
                "used_by_tasks": [],
                "used_by_chats": []
            }
            
            # Direct associations
            if artifact["task_id"]:
                cursor.execute("""
                    SELECT task_id, title, status
                    FROM tasks
                    WHERE task_id = ?
                """, (artifact["task_id"],))
                
                task = cursor.fetchone()
                if task:
                    results["used_by_tasks"].append({
                        "task_id": task["task_id"],
                        "title": task["title"],
                        "status": task["status"]
                    })
            
            if artifact["session_id"]:
                cursor.execute("""
                    SELECT session_id, title
                    FROM chat_sessions
                    WHERE session_id = ?
                """, (artifact["session_id"],))
                
                chat = cursor.fetchone()
                if chat:
                    results["used_by_chats"].append({
                        "session_id": chat["session_id"],
                        "title": chat["title"]
                    })
            
            # Find via context_snapshot_items (summary used in context)
            cursor.execute("""
                SELECT DISTINCT cs.session_id, s.title
                FROM context_snapshot_items csi
                JOIN context_snapshots cs ON csi.snapshot_id = cs.snapshot_id
                JOIN chat_sessions s ON cs.session_id = s.session_id
                WHERE csi.item_type = 'summary' AND csi.item_id = ?
            """, (artifact_id,))
            
            for row in cursor.fetchall():
                if row["session_id"] != artifact["session_id"]:  # Avoid duplicate
                    results["used_by_chats"].append({
                        "session_id": row["session_id"],
                        "title": row["title"]
                    })
            
            return results
        
        finally:
            conn.close()
