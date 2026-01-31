# Gate: No Semantic Analysis in Search Phase

## Purpose

This gate ensures that the **search phase** outputs **metadata only** and does NOT perform semantic analysis or interpretation of content. This enforces the critical principle that search results are **candidate sources**, not truth or facts.

## Critical Principle

The communication pipeline has three distinct phases with different responsibilities:

### 1. SEARCH Phase (Metadata Only)
- **Purpose**: Find candidate sources
- **Allowed**: `title`, `url`, `snippet` (raw text), `priority_score` (metadata-based)
- **FORBIDDEN**: `summary`, `why_it_matters`, `analysis`, `impact`, `assessment`
- **Why**: Search engines return candidates, not verified facts

### 2. FETCH Phase (Content Only)
- **Purpose**: Retrieve raw content from sources
- **Allowed**: Raw text, links, images, metadata, citations
- **FORBIDDEN**: `summary`, `why_it_matters`, `analysis`, `impact`, `assessment`
- **Why**: Fetch retrieves content but doesn't interpret it

### 3. BRIEF Phase (Synthesis Allowed)
- **Purpose**: Synthesize verified information for human consumption
- **Allowed**: `summary`, `why_it_matters`, `analysis`, `assessment`
- **Why**: Brief runs AFTER verification and is for human understanding

## Forbidden Fields

The gate detects the following semantic analysis fields in search/fetch code:

- `summary` - Descriptive summaries (use `snippet` for raw text)
- `why_it_matters` - Importance/impact explanations
- `analysis` - Content analysis or interpretation
- `impact` - Impact assessments
- `implication` - Implications or consequences
- `importance` - Importance ratings or explanations
- `assessment` - Quality or relevance assessments

## Special Case: priority_reason

The `priority_reason` field has special rules:

✅ **ALLOWED**: Enum values from `PriorityReason`
```python
{
    "priority_score": 85,
    "reasons": [
        PriorityReason.GOV_DOMAIN,      # ✓ Enum value
        PriorityReason.PDF_DOCUMENT,    # ✓ Enum value
        PriorityReason.CURRENT_YEAR,    # ✓ Enum value
    ]
}
```

❌ **FORBIDDEN**: Dynamic text generation
```python
{
    "priority_score": 85,
    "priority_reason": "High authority government source"  # ✗ Dynamic text
}
```

## Files Checked

1. `agentos/core/communication/connectors/web_search.py` - Web search connector
2. `agentos/core/communication/priority/priority_scoring.py` - Priority scoring logic
3. `agentos/core/chat/comm_commands.py` - Communication command handlers (search/fetch only, brief is exempt)

## Whitelisting

The following functions are **exempt** from the gate because they are part of the **brief phase**:

- `_format_brief()` - Formats brief output
- `_generate_importance()` - Generates importance statements
- `handle_brief()` - Brief command handler
- `_execute_brief_pipeline()` - Brief pipeline executor
- `_fetch_and_verify()` - Fetches content for brief (includes nested functions)
- `_multi_query_search()` - Multi-query search for brief
- `_filter_candidates()` - Filters candidates for brief

## Running the Gate

### Standalone
```bash
python3 scripts/gates/gate_no_semantic_in_search.py
```

### As Part of Gate Suite
```bash
bash scripts/gates/run_all_gates.sh
```

## Exit Codes

- **0**: Success - No semantic fields in search phase
- **1**: Failure - Semantic fields detected

## Examples

### ✅ CORRECT - Search Phase

```python
def _search(self, params):
    """Perform web search."""
    results = []
    for item in raw_results:
        results.append({
            "title": item.get("title"),         # ✓ Raw metadata
            "url": item.get("url"),             # ✓ Raw metadata
            "snippet": item.get("snippet"),     # ✓ Raw text
        })

    return {
        "query": params["query"],
        "results": results,
        "total_results": len(results),
        "engine": self.engine,
    }
```

### ✅ CORRECT - Priority Scoring

```python
def calculate_priority_score(url, snippet):
    """Calculate priority based on metadata only."""
    return PriorityScore(
        total_score=85,
        domain_score=40,
        source_type_score=30,
        document_type_score=15,
        recency_score=10,
        reasons=[                               # ✓ Enum values only
            PriorityReason.GOV_DOMAIN,
            PriorityReason.PDF_DOCUMENT,
            PriorityReason.CURRENT_YEAR,
        ],
        metadata={"domain": "example.gov"}
    )
```

### ❌ WRONG - Search Phase with Semantic Fields

```python
def _search(self, params):
    """Perform web search."""
    results = []
    for item in raw_results:
        results.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "summary": "This article discusses...",      # ✗ FORBIDDEN
            "why_it_matters": "Important because...",    # ✗ FORBIDDEN
            "analysis": "The content suggests...",       # ✗ FORBIDDEN
        })

    return {"results": results}
```

## Testing

Unit tests are located at:
```
tests/unit/gates/test_gate_no_semantic_in_search.py
```

Run tests:
```bash
python3 -m pytest tests/unit/gates/test_gate_no_semantic_in_search.py -v
```

## Integration with CI/CD

This gate is part of the gate suite run by `run_all_gates.sh` and should be executed:

1. **Pre-commit**: Recommended via git hooks
2. **CI Pipeline**: As part of automated checks
3. **Manual Review**: Before merging search/fetch changes

## Troubleshooting

### False Positive: Field in Brief Function

If the gate reports a violation in a function that should be exempt (part of brief phase):

1. Check if function is in the whitelist (see "Whitelisting" section)
2. If not, add it to `brief_function_patterns` in `gate_no_semantic_in_search.py`
3. Add a comment explaining why it's exempt

### False Negative: Field Not Detected

If a semantic field is not being detected:

1. Check if field name is in `FORBIDDEN_FIELDS` set
2. Verify the field is being checked (dict keys, assignments, keyword args)
3. Check if file is in `FILES_TO_CHECK` list

## Design Principles

1. **Fail-Safe**: Default to blocking unknown patterns
2. **Explicit**: Clear error messages showing exactly what and where
3. **Phase-Aware**: Understands search vs fetch vs brief phases
4. **Composable**: Part of larger gate suite for system integrity

## Related Documentation

- [Gate System Overview](../../docs/GATE_SYSTEM.md)
- [Communication Architecture](../../docs/architecture/ADR-COMM-001-CommunicationOS-Boundary.md)
- [Priority Scoring Design](../../docs/COMM_BRIEF_IMPLEMENTATION.md)

## Maintenance

When adding new search/fetch functionality:

1. Ensure no semantic fields in return values
2. Use `snippet` for raw text, not `summary`
3. Use `PriorityReason` enum for priority explanations
4. Run gate to verify compliance
5. Add tests if new patterns introduced

## Version History

- **v1.0** (2026-01-31): Initial implementation
  - Detects forbidden semantic fields in search/fetch
  - Exempts brief phase functions
  - Validates priority_reason compliance
  - Integrated into gate suite
