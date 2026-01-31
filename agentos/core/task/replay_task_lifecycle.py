"""
Task Lifecycle Replay Tool

运维回放工具：回放任务完整生命周期，用于调试和审计。

Features:
- 回放任务状态转换历史
- 展示事件日志时间线
- 显示审计记录
- 生成生命周期摘要

Usage:
    from agentos.core.task.replay_task_lifecycle import TaskLifecycleReplayer
    from agentos.core.storage.paths import component_db_path

    replayer = TaskLifecycleReplayer(str(component_db_path('agentos')))
    result = replayer.replay_task('task-123')
    print(result['summary'])
"""

import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path


class TaskLifecycleReplayer:
    """任务生命周期回放工具"""

    def __init__(self, db_path: str):
        """
        初始化回放器

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        if not Path(db_path).exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

    def replay_task(self, task_id: str) -> Dict[str, Any]:
        """
        回放单个任务的完整生命周期

        Args:
            task_id: 任务ID

        Returns:
            dict: {
                'task_info': 任务基本信息,
                'timeline': 时间线事件列表（按时间排序）,
                'summary': 生命周期摘要
            }
        """
        # 1. 读取任务基本信息
        task_info = self._get_task_info(task_id)

        # 2. 读取状态转换历史
        transitions = self._get_transitions(task_id)

        # 3. 读取事件日志
        events = self._get_events(task_id)

        # 4. 读取审计日志
        audits = self._get_audits(task_id)

        # 5. 合并时间线
        timeline = self._merge_timeline(transitions, events, audits)

        # 6. 生成摘要
        summary = self._generate_summary(task_info, timeline)

        return {
            'task_info': task_info,
            'timeline': timeline,
            'summary': summary
        }

    def _get_task_info(self, task_id: str) -> Dict[str, Any]:
        """获取任务基本信息"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT
                    task_id, title, description, status, priority,
                    exit_reason, retry_count, max_retries,
                    created_at, updated_at, metadata
                FROM tasks
                WHERE task_id = ?
            """, (task_id,))

            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Task {task_id} not found")

            return {
                'task_id': row['task_id'],
                'title': row['title'],
                'description': row['description'],
                'status': row['status'],
                'priority': row['priority'],
                'exit_reason': row['exit_reason'],
                'retry_count': row['retry_count'],
                'max_retries': row['max_retries'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'metadata': json.loads(row['metadata']) if row['metadata'] else {}
            }
        finally:
            conn.close()

    def _get_transitions(self, task_id: str) -> List[Dict[str, Any]]:
        """获取状态转换历史"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT
                    from_status, to_status, actor, reason,
                    metadata, created_at
                FROM task_state_transitions
                WHERE task_id = ?
                ORDER BY created_at ASC
            """, (task_id,))

            transitions = []
            for row in cursor.fetchall():
                transitions.append({
                    'type': 'transition',
                    'from_status': row['from_status'],
                    'to_status': row['to_status'],
                    'actor': row['actor'],
                    'reason': row['reason'],
                    'metadata': json.loads(row['metadata']) if row['metadata'] else {},
                    'timestamp': row['created_at']
                })

            return transitions
        finally:
            conn.close()

    def _get_events(self, task_id: str) -> List[Dict[str, Any]]:
        """获取事件日志"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 尝试从 task_events 表读取
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='task_events'
            """)

            if cursor.fetchone():
                cursor.execute("""
                    SELECT
                        event_type, event_seq, event_data,
                        created_at
                    FROM task_events
                    WHERE task_id = ?
                    ORDER BY event_seq ASC
                """, (task_id,))

                events = []
                for row in cursor.fetchall():
                    events.append({
                        'type': 'event',
                        'event_type': row['event_type'],
                        'event_seq': row['event_seq'],
                        'event_data': json.loads(row['event_data']) if row['event_data'] else {},
                        'timestamp': row['created_at']
                    })

                return events
            else:
                return []
        finally:
            conn.close()

    def _get_audits(self, task_id: str) -> List[Dict[str, Any]]:
        """获取审计日志"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT
                    event_type, level, payload, created_at
                FROM task_audits
                WHERE task_id = ?
                ORDER BY created_at ASC
            """, (task_id,))

            audits = []
            for row in cursor.fetchall():
                audits.append({
                    'type': 'audit',
                    'event_type': row['event_type'],
                    'level': row['level'],
                    'payload': json.loads(row['payload']) if row['payload'] else {},
                    'timestamp': row['created_at']
                })

            return audits
        finally:
            conn.close()

    def _merge_timeline(
        self,
        transitions: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        audits: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """合并所有事件到统一时间线"""
        timeline = transitions + events + audits

        # 按时间排序
        timeline.sort(key=lambda x: x['timestamp'])

        return timeline

    def _generate_summary(
        self,
        task_info: Dict[str, Any],
        timeline: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成生命周期摘要"""
        # 统计各类事件数量
        event_counts = {
            'transitions': 0,
            'events': 0,
            'audits': 0
        }

        for item in timeline:
            item_type = item['type']
            if item_type == 'transition':
                event_counts['transitions'] += 1
            elif item_type == 'event':
                event_counts['events'] += 1
            elif item_type == 'audit':
                event_counts['audits'] += 1

        # 计算生命周期时长
        if timeline:
            first_timestamp = timeline[0]['timestamp']
            last_timestamp = timeline[-1]['timestamp']

            try:
                first_dt = datetime.fromisoformat(first_timestamp.replace('Z', '+00:00'))
                last_dt = datetime.fromisoformat(last_timestamp.replace('Z', '+00:00'))
                duration_seconds = (last_dt - first_dt).total_seconds()
            except:
                duration_seconds = None
        else:
            duration_seconds = None

        # 状态转换序列
        status_sequence = []
        for item in timeline:
            if item['type'] == 'transition':
                status_sequence.append(item['to_status'])

        return {
            'task_id': task_info['task_id'],
            'title': task_info['title'],
            'current_status': task_info['status'],
            'exit_reason': task_info['exit_reason'],
            'retry_count': task_info['retry_count'],
            'total_events': len(timeline),
            'event_counts': event_counts,
            'duration_seconds': duration_seconds,
            'status_sequence': status_sequence,
            'created_at': task_info['created_at'],
            'updated_at': task_info['updated_at']
        }

    def replay_multiple_tasks(self, task_ids: List[str]) -> Dict[str, Any]:
        """
        批量回放多个任务

        Args:
            task_ids: 任务ID列表

        Returns:
            dict: 每个任务的回放结果
        """
        results = {}
        errors = {}

        for task_id in task_ids:
            try:
                results[task_id] = self.replay_task(task_id)
            except Exception as e:
                errors[task_id] = str(e)

        return {
            'results': results,
            'errors': errors,
            'summary': {
                'total': len(task_ids),
                'successful': len(results),
                'failed': len(errors)
            }
        }

    def format_text_output(self, result: Dict[str, Any]) -> str:
        """
        格式化为文本输出

        Args:
            result: replay_task() 的返回结果

        Returns:
            str: 格式化的文本
        """
        lines = []

        # 任务基本信息
        task_info = result['task_info']
        lines.append("=" * 80)
        lines.append(f"Task Lifecycle Replay: {task_info['task_id']}")
        lines.append("=" * 80)
        lines.append(f"Title: {task_info['title']}")
        lines.append(f"Status: {task_info['status']}")
        if task_info['exit_reason']:
            lines.append(f"Exit Reason: {task_info['exit_reason']}")
        lines.append(f"Created: {task_info['created_at']}")
        lines.append(f"Updated: {task_info['updated_at']}")
        lines.append("")

        # 摘要
        summary = result['summary']
        lines.append("-" * 80)
        lines.append("Summary")
        lines.append("-" * 80)
        lines.append(f"Total Events: {summary['total_events']}")
        lines.append(f"  - Transitions: {summary['event_counts']['transitions']}")
        lines.append(f"  - Events: {summary['event_counts']['events']}")
        lines.append(f"  - Audits: {summary['event_counts']['audits']}")

        if summary['duration_seconds'] is not None:
            lines.append(f"Duration: {summary['duration_seconds']:.2f} seconds")

        if summary['status_sequence']:
            lines.append(f"Status Sequence: {' → '.join(summary['status_sequence'])}")

        lines.append("")

        # 时间线
        lines.append("-" * 80)
        lines.append("Timeline")
        lines.append("-" * 80)

        for i, event in enumerate(result['timeline'], 1):
            timestamp = event['timestamp']
            event_type = event['type']

            if event_type == 'transition':
                lines.append(
                    f"{i:3d}. [{timestamp}] TRANSITION: "
                    f"{event['from_status']} → {event['to_status']}"
                )
                if event['reason']:
                    lines.append(f"     Reason: {event['reason']}")
                if event['actor']:
                    lines.append(f"     Actor: {event['actor']}")

            elif event_type == 'event':
                lines.append(
                    f"{i:3d}. [{timestamp}] EVENT: "
                    f"{event['event_type']} (seq={event['event_seq']})"
                )

            elif event_type == 'audit':
                lines.append(
                    f"{i:3d}. [{timestamp}] AUDIT [{event['level'].upper()}]: "
                    f"{event['event_type']}"
                )
                if event['payload']:
                    payload_str = json.dumps(event['payload'], indent=2)
                    for line in payload_str.split('\n'):
                        lines.append(f"     {line}")

            lines.append("")

        return '\n'.join(lines)


# CLI support
if __name__ == "__main__":
    import sys
    import argparse
    from agentos.core.storage.paths import component_db_path

    parser = argparse.ArgumentParser(description='Replay task lifecycle')
    parser.add_argument('task_id', help='Task ID to replay')
    parser.add_argument('--db', default=None, help='Database path (default: component_db_path("agentos"))')
    parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format')

    args = parser.parse_args()

    # Use unified storage path if not specified
    if args.db is None:
        args.db = str(component_db_path("agentos"))

    try:
        replayer = TaskLifecycleReplayer(args.db)
        result = replayer.replay_task(args.task_id)

        if args.format == 'json':
            print(json.dumps(result, indent=2))
        else:
            print(replayer.format_text_output(result))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
