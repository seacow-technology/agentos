# AgentOS Metrics Module

This module provides quality metrics calculation for InfoNeed classification based on audit logs.

## Overview

The InfoNeed Metrics system calculates 6 core metrics to monitor classification quality:

1. **Comm Trigger Rate**: How often external communication is triggered
2. **False Positive Rate**: Unnecessary comm requests
3. **False Negative Rate**: Missed comm opportunities (user corrections)
4. **Ambient Hit Rate**: Accuracy of AMBIENT_STATE classifications
5. **Decision Latency**: Performance metrics (p50, p95, p99, avg)
6. **Decision Stability**: Consistency for similar questions

## Design Principles

- **Audit Log Only**: No semantic analysis or model inference
- **No LLM**: Pure statistical calculations
- **Offline Capable**: Can run as batch job or scheduled task
- **Time Range Support**: Calculate metrics for any time period

## Quick Start

### Python API

```python
from datetime import datetime, timedelta, timezone
from agentos.metrics.info_need_metrics import InfoNeedMetrics

# Calculate metrics for last 24 hours
calculator = InfoNeedMetrics()
metrics = calculator.calculate_metrics()

print(f"Comm Trigger Rate: {metrics['comm_trigger_rate']:.2%}")
print(f"False Positive Rate: {metrics['false_positive_rate']:.2%}")
print(f"False Negative Rate: {metrics['false_negative_rate']:.2%}")

# Calculate metrics for specific time range
end_time = datetime.now(timezone.utc)
start_time = end_time - timedelta(days=7)
metrics = calculator.calculate_metrics(start_time, end_time)
```

### CLI Tool

```bash
# Show metrics for last 24 hours
python -m agentos.cli.metrics show

# Show metrics for last 7 days
python -m agentos.cli.metrics show --last 7d

# Generate report and save to file
python -m agentos.cli.metrics generate --output report.json

# Generate report for specific date range
python -m agentos.cli.metrics generate \
    --start "2025-01-01" \
    --end "2025-01-31" \
    --output jan_report.json

# Export metrics as CSV
python -m agentos.cli.metrics export --last 24h --format csv --output metrics.csv
```

## Metrics Details

### 1. Comm Trigger Rate

**Definition**: Percentage of questions that trigger external communication

**Formula**:
```
comm_trigger_rate = count(decision == "REQUIRE_COMM") / count(all classifications)
```

**Interpretation**:
- High rate (>50%): May indicate overly conservative classification
- Low rate (<10%): May indicate missed external info opportunities
- Target range: 20-30% for typical workloads

### 2. False Positive Rate

**Definition**: Percentage of REQUIRE_COMM decisions that were unnecessary

**Formula**:
```
false_positive_rate =
    count(decision == "REQUIRE_COMM" AND outcome == "unnecessary_comm") /
    count(decision == "REQUIRE_COMM")
```

**Interpretation**:
- High rate (>30%): Classifier is too aggressive, annoying users
- Low rate (<5%): Good precision
- Requires outcome tracking via user feedback

### 3. False Negative Rate

**Definition**: Percentage of non-REQUIRE_COMM decisions that users corrected

**Formula**:
```
false_negative_rate =
    count(decision != "REQUIRE_COMM" AND outcome == "user_corrected") /
    count(decision != "REQUIRE_COMM")
```

**Interpretation**:
- High rate (>20%): Missing valid external info needs
- Low rate (<5%): Good recall
- Requires user correction tracking

### 4. Ambient Hit Rate

**Definition**: Accuracy of AMBIENT_STATE classifications

**Formula**:
```
ambient_hit_rate =
    count(type == "AMBIENT_STATE" AND outcome == "validated") /
    count(type == "AMBIENT_STATE")
```

**Interpretation**:
- High rate (>80%): Ambient state detection is accurate
- Low rate (<50%): Misclassifying ambient state questions

### 5. Decision Latency

**Definition**: Performance metrics for classification decisions

**Metrics**:
- **p50**: Median latency (50th percentile)
- **p95**: 95th percentile latency
- **p99**: 99th percentile latency
- **avg**: Average latency

**Interpretation**:
- Target p50: <100ms (fast path)
- Target p95: <500ms (acceptable for LLM path)
- p99 > 1000ms: Performance issue

### 6. Decision Stability

**Definition**: Consistency of decisions for similar questions

**Formula** (simplified):
```
decision_stability =
    count(similar questions with same decision) /
    count(similar questions)
```

**Current Implementation**: Groups by exact question match
**Future Enhancement**: Use Jaccard similarity or embedding distance

**Interpretation**:
- High rate (>80%): Consistent classifications
- Low rate (<50%): Unstable, may need calibration

## Audit Event Schema

The metrics system expects these audit events in `task_audits` table:

### info_need_classification

Logged when a question is classified:

```json
{
  "event_type": "info_need_classification",
  "payload": {
    "message_id": "msg_abc123",
    "question": "What is the latest Python version?",
    "decision": "REQUIRE_COMM",
    "classified_type": "external_fact_uncertain",
    "confidence_level": "low",
    "latency_ms": 150.5
  }
}
```

### info_need_outcome

Logged when classification outcome is determined:

```json
{
  "event_type": "info_need_outcome",
  "payload": {
    "message_id": "msg_abc123",
    "outcome": "validated",  // or: unnecessary_comm, user_corrected, user_cancelled
    "outcome_timestamp": "2025-01-31T10:30:00Z"
  }
}
```

## Outcome Types

- **validated**: Classification was correct, action was helpful
- **unnecessary_comm**: REQUIRE_COMM was triggered but not needed
- **user_corrected**: Non-REQUIRE_COMM but user wanted external info
- **user_cancelled**: User cancelled the suggested action

## Integration Example

### Logging Classification Events

```python
from agentos.core.audit import log_audit_event
from agentos.core.chat.info_need_classifier import InfoNeedClassifier

# Classify question
classifier = InfoNeedClassifier()
result = classifier.classify("What is the latest Python version?")

# Log classification event
log_audit_event(
    event_type="info_need_classification",
    task_id=task_id,
    metadata={
        "message_id": message_id,
        "question": question,
        "decision": result.decision_action.value,
        "classified_type": result.info_need_type.value,
        "confidence_level": result.confidence_level.value,
        "latency_ms": latency_ms,
    }
)
```

### Logging Outcome Events

```python
# After user feedback or action completion
log_audit_event(
    event_type="info_need_outcome",
    task_id=task_id,
    metadata={
        "message_id": message_id,
        "outcome": "validated",  # or: unnecessary_comm, user_corrected, user_cancelled
        "outcome_timestamp": datetime.now(timezone.utc).isoformat(),
    }
)
```

## Testing

Run unit tests:

```bash
# Run all metrics tests
pytest tests/unit/metrics/

# Run specific test file
pytest tests/unit/metrics/test_info_need_metrics.py

# Run with coverage
pytest tests/unit/metrics/ --cov=agentos.metrics --cov-report=html
```

Test coverage includes:
- Empty data handling
- All 6 core metrics
- Time range filtering
- Data enrichment logic
- Edge cases (missing outcomes, malformed data)

## Scheduled Jobs

### Cron Example

Generate daily metrics report:

```bash
# Add to crontab
0 2 * * * cd /path/to/agentos && python -m agentos.cli.metrics generate --last 24h --output /var/log/metrics/daily_$(date +\%Y\%m\%d).json
```

### Systemd Timer Example

Create `/etc/systemd/system/agentos-metrics.service`:

```ini
[Unit]
Description=AgentOS InfoNeed Metrics Report

[Service]
Type=oneshot
ExecStart=/usr/bin/python -m agentos.cli.metrics generate --last 24h --output /var/log/metrics/daily_report.json
WorkingDirectory=/opt/agentos
User=agentos
```

Create `/etc/systemd/system/agentos-metrics.timer`:

```ini
[Unit]
Description=Daily AgentOS Metrics

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
systemctl enable agentos-metrics.timer
systemctl start agentos-metrics.timer
```

## Output Format

### JSON Report

```json
{
  "period": {
    "start": "2025-01-30T10:00:00+00:00",
    "end": "2025-01-31T10:00:00+00:00"
  },
  "total_classifications": 150,
  "total_outcomes": 120,
  "comm_trigger_rate": 0.25,
  "false_positive_rate": 0.08,
  "false_negative_rate": 0.05,
  "ambient_hit_rate": 0.85,
  "decision_latency": {
    "p50": 95.0,
    "p95": 350.0,
    "p99": 520.0,
    "avg": 125.5,
    "count": 150
  },
  "decision_stability": 0.82,
  "breakdown_by_type": {
    "local_knowledge": {
      "count": 60,
      "percentage": 40.0,
      "avg_latency": 80.0
    },
    "external_fact_uncertain": {
      "count": 40,
      "percentage": 26.7,
      "avg_latency": 200.0
    },
    "AMBIENT_STATE": {
      "count": 30,
      "percentage": 20.0,
      "avg_latency": 100.0
    },
    "opinion": {
      "count": 20,
      "percentage": 13.3,
      "avg_latency": 150.0
    }
  },
  "outcome_distribution": {
    "validated": 90,
    "unnecessary_comm": 10,
    "user_corrected": 8,
    "user_cancelled": 12
  },
  "metadata": {
    "calculated_at": "2025-01-31T10:00:00+00:00",
    "version": "1.0.0"
  }
}
```

### Terminal Output

```
======================================================================
InfoNeed Classification Quality Metrics
======================================================================

Period: 2025-01-30T10:00:00+00:00 to 2025-01-31T10:00:00+00:00
Total Classifications: 150
Total Outcomes: 120

Core Metrics:
  Comm Trigger Rate:     25.00%
  False Positive Rate:   8.00%
  False Negative Rate:   5.00%
  Ambient Hit Rate:      85.00%
  Decision Stability:    82.00%

Decision Latency:
  P50: 95.0ms
  P95: 350.0ms
  P99: 520.0ms
  Avg: 125.5ms

Breakdown by Type:
  local_knowledge                :  60 (40.0%) - avg 80.0ms
  external_fact_uncertain        :  40 (26.7%) - avg 200.0ms
  AMBIENT_STATE                  :  30 (20.0%) - avg 100.0ms
  opinion                        :  20 (13.3%) - avg 150.0ms

Outcome Distribution:
  validated                      :  90
  unnecessary_comm               :  10
  user_corrected                 :   8
  user_cancelled                 :  12

======================================================================
```

## Future Enhancements

1. **Advanced Similarity**: Use Jaccard similarity or embeddings for decision_stability
2. **Confidence Correlation**: Correlate confidence levels with outcome accuracy
3. **Temporal Analysis**: Track metrics over time to detect trends
4. **Alerting**: Trigger alerts when metrics exceed thresholds
5. **Dashboard**: WebUI dashboard for real-time monitoring (see task #21)
6. **Comparative Analysis**: Compare metrics across different time periods

## Related Documentation

- [InfoNeed Classifier](../core/chat/models/info_need.py)
- [Audit System](../core/audit.py)
- [Communication Adapter](../core/chat/communication_adapter.py)

## Support

For questions or issues:
1. Check test examples in `tests/unit/metrics/`
2. Review audit event schema above
3. Check logs for error messages
4. File issue with sample data and error details
