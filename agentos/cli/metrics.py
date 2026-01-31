"""
CLI tool for InfoNeed metrics calculation and reporting

Usage:
    python -m agentos.cli.metrics generate --output report.json
    python -m agentos.cli.metrics show --last 24h
    python -m agentos.cli.metrics show --start "2025-01-01" --end "2025-01-31"
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentos.core.time import utc_now
from agentos.metrics.info_need_metrics import (
    InfoNeedMetrics,
    generate_metrics_report,
    print_metrics_summary,
)


def parse_time_duration(duration_str: str) -> timedelta:
    """
    Parse time duration string (e.g., "24h", "7d", "1w")

    Args:
        duration_str: Duration string

    Returns:
        timedelta object

    Raises:
        ValueError: If format is invalid
    """
    duration_str = duration_str.strip().lower()

    # Extract number and unit
    import re
    match = re.match(r'^(\d+)([hdw])$', duration_str)
    if not match:
        raise ValueError(
            f"Invalid duration format: {duration_str}. "
            f"Expected format: <number><unit> (e.g., 24h, 7d, 1w)"
        )

    value = int(match.group(1))
    unit = match.group(2)

    if unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    elif unit == 'w':
        return timedelta(weeks=value)
    else:
        raise ValueError(f"Unknown time unit: {unit}")


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse timestamp string in ISO format

    Args:
        timestamp_str: Timestamp string (ISO 8601 format)

    Returns:
        datetime object with UTC timezone

    Raises:
        ValueError: If format is invalid
    """
    try:
        # Try parsing with timezone
        dt = datetime.fromisoformat(timestamp_str)
        if dt.tzinfo is None:
            # Assume UTC if no timezone specified
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        # Try common date formats
        for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        raise ValueError(
            f"Invalid timestamp format: {timestamp_str}. "
            f"Expected ISO 8601 format (e.g., 2025-01-31 or 2025-01-31T10:30:00)"
        )


def cmd_generate(args):
    """Generate metrics report and save to file"""
    # Parse time range
    if args.last:
        duration = parse_time_duration(args.last)
        end_time = utc_now()
        start_time = end_time - duration
    else:
        start_time = parse_timestamp(args.start) if args.start else None
        end_time = parse_timestamp(args.end) if args.end else None

    # Generate report
    print(f"Generating InfoNeed metrics report...")
    print(f"  Period: {start_time or 'default'} to {end_time or 'now'}")
    print(f"  Output: {args.output}")
    print()

    try:
        metrics = generate_metrics_report(
            output_path=args.output,
            start_time=start_time,
            end_time=end_time
        )

        print(f"✅ Metrics report generated: {args.output}")
        print()

        # Print summary if verbose
        if args.verbose:
            print_metrics_summary(metrics)

        return 0

    except Exception as e:
        print(f"❌ Error generating metrics: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_show(args):
    """Show metrics in terminal"""
    # Parse time range
    if args.last:
        duration = parse_time_duration(args.last)
        end_time = utc_now()
        start_time = end_time - duration
    else:
        start_time = parse_timestamp(args.start) if args.start else None
        end_time = parse_timestamp(args.end) if args.end else None

    # Calculate metrics
    try:
        calculator = InfoNeedMetrics()
        metrics = calculator.calculate_metrics(start_time, end_time)

        # Print summary
        print_metrics_summary(metrics)

        return 0

    except Exception as e:
        print(f"❌ Error calculating metrics: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_export(args):
    """Export metrics in different formats"""
    # Parse time range
    if args.last:
        duration = parse_time_duration(args.last)
        end_time = utc_now()
        start_time = end_time - duration
    else:
        start_time = parse_timestamp(args.start) if args.start else None
        end_time = parse_timestamp(args.end) if args.end else None

    # Calculate metrics
    try:
        calculator = InfoNeedMetrics()
        metrics = calculator.calculate_metrics(start_time, end_time)

        # Export based on format
        if args.format == 'json':
            output = json.dumps(metrics, indent=2, ensure_ascii=False)
        elif args.format == 'csv':
            # Simple CSV export of core metrics
            output = "metric,value\n"
            output += f"total_classifications,{metrics.get('total_classifications', 0)}\n"
            output += f"comm_trigger_rate,{metrics.get('comm_trigger_rate', 0):.4f}\n"
            output += f"false_positive_rate,{metrics.get('false_positive_rate', 0):.4f}\n"
            output += f"false_negative_rate,{metrics.get('false_negative_rate', 0):.4f}\n"
            output += f"ambient_hit_rate,{metrics.get('ambient_hit_rate', 0):.4f}\n"
            output += f"decision_stability,{metrics.get('decision_stability', 0):.4f}\n"

            latency = metrics.get('decision_latency', {})
            output += f"latency_p50,{latency.get('p50', 0):.2f}\n"
            output += f"latency_p95,{latency.get('p95', 0):.2f}\n"
            output += f"latency_p99,{latency.get('p99', 0):.2f}\n"
            output += f"latency_avg,{latency.get('avg', 0):.2f}\n"
        else:
            print(f"❌ Unknown format: {args.format}", file=sys.stderr)
            return 1

        # Write to file or stdout
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"✅ Metrics exported to: {args.output}")
        else:
            print(output)

        return 0

    except Exception as e:
        print(f"❌ Error exporting metrics: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def main():
    """Main entry point for CLI"""
    parser = argparse.ArgumentParser(
        description="InfoNeed Classification Metrics Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate report for last 24 hours
  python -m agentos.cli.metrics generate --output report.json

  # Show metrics for last 7 days
  python -m agentos.cli.metrics show --last 7d

  # Generate report for specific date range
  python -m agentos.cli.metrics generate --start "2025-01-01" --end "2025-01-31" --output jan_report.json

  # Export metrics as CSV
  python -m agentos.cli.metrics export --last 24h --format csv --output metrics.csv
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Generate command
    parser_generate = subparsers.add_parser(
        'generate',
        help='Generate metrics report and save to file'
    )
    parser_generate.add_argument(
        '--output', '-o',
        default='metrics_report.json',
        help='Output file path (default: metrics_report.json)'
    )
    parser_generate.add_argument(
        '--last',
        help='Calculate metrics for last N hours/days/weeks (e.g., 24h, 7d, 1w)'
    )
    parser_generate.add_argument(
        '--start',
        help='Start timestamp (ISO format: 2025-01-31 or 2025-01-31T10:30:00)'
    )
    parser_generate.add_argument(
        '--end',
        help='End timestamp (ISO format)'
    )
    parser_generate.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Print detailed summary after generation'
    )

    # Show command
    parser_show = subparsers.add_parser(
        'show',
        help='Show metrics in terminal'
    )
    parser_show.add_argument(
        '--last',
        default='24h',
        help='Calculate metrics for last N hours/days/weeks (default: 24h)'
    )
    parser_show.add_argument(
        '--start',
        help='Start timestamp (ISO format)'
    )
    parser_show.add_argument(
        '--end',
        help='End timestamp (ISO format)'
    )
    parser_show.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show verbose output'
    )

    # Export command
    parser_export = subparsers.add_parser(
        'export',
        help='Export metrics in different formats'
    )
    parser_export.add_argument(
        '--format', '-f',
        choices=['json', 'csv'],
        default='json',
        help='Export format (default: json)'
    )
    parser_export.add_argument(
        '--output', '-o',
        help='Output file path (default: stdout)'
    )
    parser_export.add_argument(
        '--last',
        default='24h',
        help='Calculate metrics for last N hours/days/weeks (default: 24h)'
    )
    parser_export.add_argument(
        '--start',
        help='Start timestamp (ISO format)'
    )
    parser_export.add_argument(
        '--end',
        help='End timestamp (ISO format)'
    )
    parser_export.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show verbose output'
    )

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if args.command == 'generate':
        return cmd_generate(args)
    elif args.command == 'show':
        return cmd_show(args)
    elif args.command == 'export':
        return cmd_export(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
