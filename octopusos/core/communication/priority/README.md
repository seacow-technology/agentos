# Priority Scoring System

A metadata-based priority scoring system for ranking search results without semantic analysis.

## Overview

This module implements a transparent, rule-based scoring system that ranks search results based on **metadata only**. It does NOT use:
- Page content analysis
- Natural language processing (NLP)
- Semantic understanding
- Content quality assessment

Instead, it uses objective metadata indicators:
- Domain authority (.gov, .edu, .org)
- Source type (whitelisted organizations)
- Document type (PDF, policy documents)
- Publication recency (year extraction from snippets)

## Architecture

### Core Components

1. **PriorityScore** - Pydantic model for score breakdown
2. **SearchResultWithPriority** - Search result with priority annotation
3. **PriorityReason** - Enum of scoring reasons (for transparency)
4. **calculate_priority_score()** - Main scoring function
5. **Trusted Sources Config** - YAML whitelist of authoritative sources

### Scoring Rules

#### 1. Domain Score (0-40 points)

| Domain Type | Score | Reason Code |
|------------|-------|-------------|
| .gov / .gov.au | 40 | GOV_DOMAIN |
| .edu | 25 | EDU_DOMAIN |
| .org | 15 | ORG_DOMAIN |
| Other | 5 | OTHER_DOMAIN |

#### 2. Source Type Score (0-30 points)

| Source Type | Score | Reason Code |
|------------|-------|-------------|
| Official Policy Source (whitelist) | 30 | OFFICIAL_POLICY_SOURCE |
| Recognized NGO (whitelist) | 20 | RECOGNIZED_NGO |
| Other | 5 | GENERAL_SOURCE |

#### 3. Document Type Score (0-30 points, can stack)

| Document Indicator | Score | Reason Code |
|-------------------|-------|-------------|
| URL ends with .pdf | +15 | PDF_DOCUMENT |
| Path contains /policy/ or /legislation/ | +15 | POLICY_PATH |
| Path contains /blog/ or /opinion/ | +0 | BLOG_OPINION |
| Other | 0 | GENERAL_DOCUMENT |

**Note:** Multiple indicators can stack. For example, a PDF in a policy path gets 30 points (15 + 15).

#### 4. Recency Score (0-10 points)

| Recency | Score | Reason Code |
|---------|-------|-------------|
| Current year (2025) in snippet | 10 | CURRENT_YEAR |
| Last year (2024) in snippet | 10 | RECENT_YEAR |
| No date information | 0 | NO_DATE_INFO |

### Maximum Scores

- **Maximum total score:** 110 points
  - Domain: 40
  - Source type: 30
  - Document type: 30 (stacked)
  - Recency: 10

## Usage

### Basic Usage

```python
from agentos.core.communication.priority import calculate_priority_score

# Score a single result
score = calculate_priority_score(
    url="https://aph.gov.au/policy/climate-framework.pdf",
    snippet="Updated January 2025. Climate policy framework.",
    trusted_sources=None  # Uses default empty lists
)

print(f"Total score: {score.total_score}")
print(f"Domain score: {score.domain_score}")
print(f"Reasons: {score.reasons}")
```

### With Trusted Sources

```python
from agentos.core.communication.priority import calculate_priority_score
from agentos.core.communication.config import load_trusted_sources

# Load trusted sources from YAML
trusted_sources = load_trusted_sources()

# Score with trusted sources
score = calculate_priority_score(
    url="https://aph.gov.au/policy/report.pdf",
    snippet="Policy report published 2025.",
    trusted_sources=trusted_sources
)
```

### Scoring Multiple Results

```python
from agentos.core.communication.priority import (
    calculate_priority_score,
    SearchResultWithPriority,
)

results = [
    {"title": "...", "url": "...", "snippet": "..."},
    # ... more results
]

# Score all results
scored_results = []
for result in results:
    score = calculate_priority_score(
        url=result["url"],
        snippet=result["snippet"],
        trusted_sources=None
    )

    scored_result = SearchResultWithPriority(
        title=result["title"],
        url=result["url"],
        snippet=result["snippet"],
        priority_score=score
    )
    scored_results.append(scored_result)

# Sort by priority
scored_results.sort(
    key=lambda x: x.priority_score.total_score,
    reverse=True
)
```

## Configuration

### Trusted Sources

Edit `agentos/core/communication/config/trusted_sources.yaml`:

```yaml
OFFICIAL_POLICY_SOURCES:
  - aph.gov.au
  - whitehouse.gov
  - who.int
  # ... more sources

RECOGNIZED_NGO:
  - greenpeace.org
  - amnesty.org
  - hrw.org
  # ... more NGOs
```

### Loading Configuration

```python
from agentos.core.communication.config import load_trusted_sources

sources = load_trusted_sources()
# Returns: {"official_policy": [...], "recognized_ngo": [...]}
```

## Examples

### Example 1: Government Policy PDF (Maximum Score)

```python
score = calculate_priority_score(
    url="https://aph.gov.au/policy/climate.pdf",
    snippet="Updated 2025. Climate policy framework.",
    trusted_sources={"official_policy": ["aph.gov.au"], "recognized_ngo": []}
)

# Result:
# - Domain: 40 (gov)
# - Source type: 30 (official policy)
# - Document type: 30 (pdf + policy path)
# - Recency: 10 (current year)
# Total: 110 points
```

### Example 2: Educational Institution

```python
score = calculate_priority_score(
    url="https://research.stanford.edu/climate-study",
    snippet="Published in 2024. Climate research study.",
    trusted_sources=None
)

# Result:
# - Domain: 25 (edu)
# - Source type: 5 (general)
# - Document type: 0 (general)
# - Recency: 10 (last year)
# Total: 40 points
```

### Example 3: Blog Post (Minimum Score)

```python
score = calculate_priority_score(
    url="https://example.com/blog/opinion",
    snippet="My thoughts on climate policy.",
    trusted_sources=None
)

# Result:
# - Domain: 5 (other)
# - Source type: 5 (general)
# - Document type: 0 (blog)
# - Recency: 0 (no date)
# Total: 10 points
```

## Testing

Run the test suite:

```bash
python3 -m pytest agentos/core/communication/tests/test_priority_scoring.py -v
```

Run the demo script:

```bash
python3 examples/priority_scoring_demo.py
```

## Design Principles

### 1. Metadata Only

The system uses ONLY metadata that can be extracted without fetching or analyzing page content:
- URL structure
- Domain name
- Document type indicators in URL
- Date patterns in snippets (regex-based)

### 2. No Semantic Analysis

The system does NOT:
- Fetch page content
- Analyze what the content says
- Use NLP or ML models
- Make judgments about content quality
- Understand context or meaning

### 3. Transparency

Every score includes:
- Detailed breakdown by component
- Reason codes explaining the score
- Metadata used in calculation

### 4. Auditability

All scoring decisions are:
- Rule-based (no black box)
- Deterministic (same input = same output)
- Traceable (reason codes)
- Configurable (YAML whitelist)

## Constraints and Limitations

### What This System Does

✅ Ranks results by institutional authority
✅ Prioritizes official sources over blogs
✅ Identifies document types from URLs
✅ Detects recent publications (year-based)
✅ Provides transparent scoring breakdown

### What This System Does NOT Do

❌ Assess content quality or accuracy
❌ Understand what the content says
❌ Verify facts or claims
❌ Detect misinformation
❌ Replace human judgment

### Important Notes

1. **High score ≠ Truth**: A high score indicates institutional authority, not factual accuracy
2. **Low score ≠ False**: Blog posts may contain valuable insights despite low scores
3. **Metadata-based**: Scoring is based on URL structure, not content
4. **Whitelist-dependent**: Source type scores depend on configuration

## API Reference

### calculate_priority_score()

```python
def calculate_priority_score(
    url: str,
    snippet: str,
    trusted_sources: Optional[Dict[str, List[str]]] = None
) -> PriorityScore
```

**Parameters:**
- `url` (str): The URL to score
- `snippet` (str): Search result snippet (for date extraction)
- `trusted_sources` (dict, optional): Whitelist of trusted sources

**Returns:**
- `PriorityScore`: Detailed scoring breakdown

**Raises:**
- None (returns zero score for invalid URLs)

### PriorityScore Model

```python
class PriorityScore(BaseModel):
    total_score: int        # 0-110
    domain_score: int       # 0-40
    source_type_score: int  # 0-30
    document_type_score: int # 0-30
    recency_score: int      # 0-10
    reasons: List[PriorityReason]
    metadata: Dict[str, str]
```

### SearchResultWithPriority Model

```python
class SearchResultWithPriority(BaseModel):
    title: str
    url: str
    snippet: str
    priority_score: PriorityScore
    rank: Optional[int]
```

### PriorityReason Enum

```python
class PriorityReason(str, Enum):
    # Domain reasons
    GOV_DOMAIN = "gov_domain"
    EDU_DOMAIN = "edu_domain"
    ORG_DOMAIN = "org_domain"
    OTHER_DOMAIN = "other_domain"

    # Source type reasons
    OFFICIAL_POLICY_SOURCE = "official_policy"
    RECOGNIZED_NGO = "recognized_ngo"
    GENERAL_SOURCE = "general_source"

    # Document type reasons
    PDF_DOCUMENT = "pdf_document"
    POLICY_PATH = "policy_path"
    BLOG_OPINION = "blog_opinion"
    GENERAL_DOCUMENT = "general_document"

    # Recency reasons
    CURRENT_YEAR = "current_year"
    RECENT_YEAR = "recent_year"
    NO_DATE_INFO = "no_date_info"
```

## Contributing

When modifying the scoring system:

1. **Maintain constraints**: No semantic analysis, metadata only
2. **Update tests**: Add tests for new scoring rules
3. **Update docs**: Document all scoring changes
4. **Preserve transparency**: All scores must be explainable

## License

Part of AgentOS. See main project LICENSE.
