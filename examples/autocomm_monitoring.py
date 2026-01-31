#!/usr/bin/env python3
"""
AutoComm Monitoring Examples

This script demonstrates how to use the new AutoComm observability features
for monitoring and debugging purposes.

Usage:
    python3 examples/autocomm_monitoring.py
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime


class AutoCommMonitor:
    """Monitor and analyze AutoComm execution from logs and database"""

    def __init__(self, log_file: str = None):
        """Initialize monitor with optional log file path"""
        self.log_file = log_file or "logs/agentos.log"

    def parse_log_events(self) -> List[Dict[str, Any]]:
        """Parse AutoComm events from log file

        Returns:
            List of parsed event dictionaries
        """
        events = []

        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    # Look for AutoComm event markers
                    if 'AUTOCOMM_ATTEMPT' in line or \
                       'AUTOCOMM_SUCCESS' in line or \
                       'AUTOCOMM_FAILED' in line:

                        # Parse event type
                        event_type = None
                        if 'AUTOCOMM_ATTEMPT' in line:
                            event_type = 'ATTEMPT'
                        elif 'AUTOCOMM_SUCCESS' in line:
                            event_type = 'SUCCESS'
                        elif 'AUTOCOMM_FAILED' in line:
                            event_type = 'FAILED'

                        # Extract timestamp (assuming standard logging format)
                        timestamp_match = re.search(
                            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',
                            line
                        )
                        timestamp = timestamp_match.group(1) if timestamp_match else None

                        # Extract session_id
                        session_match = re.search(r'session_id["\']:\s*["\']([^"\']+)', line)
                        session_id = session_match.group(1) if session_match else None

                        events.append({
                            'type': event_type,
                            'timestamp': timestamp,
                            'session_id': session_id,
                            'raw_line': line.strip()
                        })

        except FileNotFoundError:
            print(f"Warning: Log file not found: {self.log_file}")

        return events

    def calculate_success_rate(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate AutoComm success rate from events

        Args:
            events: List of parsed event dictionaries

        Returns:
            Dictionary with success rate statistics
        """
        success_count = sum(1 for e in events if e['type'] == 'SUCCESS')
        failure_count = sum(1 for e in events if e['type'] == 'FAILED')
        attempt_count = sum(1 for e in events if e['type'] == 'ATTEMPT')

        total_completed = success_count + failure_count

        return {
            'attempts': attempt_count,
            'successes': success_count,
            'failures': failure_count,
            'success_rate': (success_count / total_completed * 100) if total_completed > 0 else 0,
            'completion_rate': (total_completed / attempt_count * 100) if attempt_count > 0 else 0
        }

    def find_failed_sessions(self, events: List[Dict[str, Any]]) -> List[str]:
        """Find sessions with failed AutoComm executions

        Args:
            events: List of parsed event dictionaries

        Returns:
            List of session IDs with failures
        """
        failed_sessions = set()
        for event in events:
            if event['type'] == 'FAILED' and event['session_id']:
                failed_sessions.add(event['session_id'])

        return list(failed_sessions)

    def generate_report(self) -> str:
        """Generate a monitoring report

        Returns:
            Formatted report string
        """
        events = self.parse_log_events()
        stats = self.calculate_success_rate(events)
        failed_sessions = self.find_failed_sessions(events)

        report = []
        report.append("=" * 60)
        report.append("AutoComm Monitoring Report")
        report.append("=" * 60)
        report.append("")

        report.append("Overall Statistics:")
        report.append(f"  Total Attempts:    {stats['attempts']}")
        report.append(f"  Successes:         {stats['successes']}")
        report.append(f"  Failures:          {stats['failures']}")
        report.append(f"  Success Rate:      {stats['success_rate']:.1f}%")
        report.append(f"  Completion Rate:   {stats['completion_rate']:.1f}%")
        report.append("")

        if failed_sessions:
            report.append(f"Failed Sessions ({len(failed_sessions)}):")
            for session_id in failed_sessions[:10]:  # Show first 10
                report.append(f"  - {session_id}")
            if len(failed_sessions) > 10:
                report.append(f"  ... and {len(failed_sessions) - 10} more")
        else:
            report.append("No failed sessions found.")

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)


def example_grep_commands():
    """Print example grep commands for monitoring"""
    print("=" * 60)
    print("Example Grep Commands for AutoComm Monitoring")
    print("=" * 60)
    print()

    commands = [
        {
            "description": "Count total AutoComm attempts",
            "command": 'grep "AUTOCOMM_ATTEMPT" logs/agentos.log | wc -l'
        },
        {
            "description": "Count successful executions",
            "command": 'grep "AUTOCOMM_SUCCESS" logs/agentos.log | wc -l'
        },
        {
            "description": "Count failed executions",
            "command": 'grep "AUTOCOMM_FAILED" logs/agentos.log | wc -l'
        },
        {
            "description": "Find all ImportError failures",
            "command": 'grep "AUTOCOMM_FAILED" logs/agentos.log | grep "ImportError"'
        },
        {
            "description": "Monitor AutoComm in real-time",
            "command": 'tail -f logs/agentos.log | grep --line-buffered "AUTOCOMM"'
        },
        {
            "description": "Find AutoComm events for specific session",
            "command": 'grep "session-123" logs/agentos.log | grep "AUTOCOMM"'
        }
    ]

    for i, cmd in enumerate(commands, 1):
        print(f"{i}. {cmd['description']}")
        print(f"   $ {cmd['command']}")
        print()


def example_sql_queries():
    """Print example SQL queries for database monitoring"""
    print("=" * 60)
    print("Example SQL Queries for AutoComm Monitoring")
    print("=" * 60)
    print()

    queries = [
        {
            "description": "Count failed AutoComm executions",
            "sql": """
SELECT COUNT(*) as failure_count
FROM messages
WHERE metadata->>'auto_comm_attempted' = 'true'
  AND metadata->>'auto_comm_failed' = 'true';
            """
        },
        {
            "description": "Count successful AutoComm executions",
            "sql": """
SELECT COUNT(*) as success_count
FROM messages
WHERE metadata->>'auto_comm_attempted' = 'true'
  AND metadata->>'auto_comm_failed' = 'false';
            """
        },
        {
            "description": "Calculate AutoComm success rate",
            "sql": """
SELECT
    COUNT(*) FILTER (WHERE metadata->>'auto_comm_failed' = 'false') as successes,
    COUNT(*) FILTER (WHERE metadata->>'auto_comm_failed' = 'true') as failures,
    COUNT(*) as total_attempts,
    ROUND(
        COUNT(*) FILTER (WHERE metadata->>'auto_comm_failed' = 'false')::numeric
        / COUNT(*)::numeric * 100,
        2
    ) as success_rate_pct
FROM messages
WHERE metadata->>'auto_comm_attempted' = 'true';
            """
        },
        {
            "description": "Find recent failed AutoComm executions",
            "sql": """
SELECT
    session_id,
    created_at,
    metadata->>'auto_comm_error_type' as error_type,
    metadata->>'auto_comm_error' as error_message
FROM messages
WHERE metadata->>'auto_comm_attempted' = 'true'
  AND metadata->>'auto_comm_failed' = 'true'
ORDER BY created_at DESC
LIMIT 10;
            """
        },
        {
            "description": "Find sessions with most AutoComm failures",
            "sql": """
SELECT
    session_id,
    COUNT(*) as failure_count,
    MAX(created_at) as last_failure
FROM messages
WHERE metadata->>'auto_comm_attempted' = 'true'
  AND metadata->>'auto_comm_failed' = 'true'
GROUP BY session_id
ORDER BY failure_count DESC
LIMIT 10;
            """
        }
    ]

    for i, query in enumerate(queries, 1):
        print(f"{i}. {query['description']}")
        print(query['sql'])
        print()


def main():
    """Main entry point"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "AutoComm Observability Examples" + " " * 16 + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    # Show grep commands
    example_grep_commands()

    print()

    # Show SQL queries
    example_sql_queries()

    print()

    # Try to generate report from logs
    print("=" * 60)
    print("Attempting to Generate Report from Logs")
    print("=" * 60)
    print()

    monitor = AutoCommMonitor()
    report = monitor.generate_report()
    print(report)
    print()

    print("=" * 60)
    print("Monitoring Setup Complete")
    print("=" * 60)
    print()
    print("Tips:")
    print("  1. Use the grep commands above to monitor logs in real-time")
    print("  2. Use the SQL queries to analyze historical data")
    print("  3. Set up alerts for success rate < 80%")
    print("  4. Create a dashboard to visualize trends over time")
    print()


if __name__ == "__main__":
    main()
