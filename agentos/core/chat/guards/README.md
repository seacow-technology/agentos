# Chat Guards - Security Boundary

This module implements the security boundary between Chat and CommunicationOS.

## Overview

The Chat Guards are three mandatory security checks that protect against:
- Data leakage during planning
- Attribution forgery
- Prompt injection via external content

## The Three Guards

### 1. Phase Gate (Highest Priority)

**File**: `phase_gate.py`

Prevents external operations during planning phase.

```python
from agentos.core.chat.guards import PhaseGate, PhaseGateError

try:
    PhaseGate.check("comm.search", "planning")
except PhaseGateError as e:
    print(f"Blocked: {e}")
```

**Rules**:
- Planning phase: No comm.* operations
- Execution phase: All operations allowed
- Unknown phase: Blocked (fail-closed)

---

### 2. Attribution Guard

**File**: `attribution.py`

Enforces proper attribution of external knowledge.

```python
from agentos.core.chat.guards import AttributionGuard, AttributionViolation

# Generate attribution
attribution = AttributionGuard.format_attribution("search", "session_123")

# Validate data
data = {"metadata": {"attribution": attribution}}
AttributionGuard.enforce(data, "session_123")
```

**Rules**:
- All external data must have attribution
- Format: "CommunicationOS (operation) in session {session_id}"
- Session ID must match current session

---

### 3. Content Fence

**File**: `content_fence.py`

Marks and isolates untrusted external content.

```python
from agentos.core.chat.guards import ContentFence

# Wrap external content
wrapped = ContentFence.wrap("External content", "https://example.com")

# Generate LLM warning
llm_prompt = ContentFence.get_llm_prompt_injection(wrapped)

# Display safely
display = ContentFence.unwrap_for_display(wrapped)
```

**Rules**:
- All fetched content marked as UNTRUSTED_EXTERNAL_CONTENT
- Allowed: summarization, citation, reference
- Forbidden: execute instructions, run code, modify system

---

## Usage in Chat Commands

### Step 1: Check Phase Gate

At the start of `execute()`:

```python
def execute(self, args: str, session_id: str, execution_phase: str):
    # Check phase gate first
    try:
        PhaseGate.check(f"comm.{self.command_name}", execution_phase)
    except PhaseGateError as e:
        return {"error": str(e), "blocked": True}

    # Continue...
```

### Step 2: Add Attribution

When formatting responses:

```python
attribution = AttributionGuard.format_attribution("search", session_id)
data = {
    "results": results,
    "metadata": {
        "attribution": attribution
    }
}
AttributionGuard.enforce(data, session_id)
```

### Step 3: Wrap External Content

When fetching content:

```python
content = fetch_url(url)
wrapped = ContentFence.wrap(content, url)

# If passing to LLM
llm_prompt = ContentFence.get_llm_prompt_injection(wrapped)
```

---

## Testing

Run guard tests:

```bash
python3 -m pytest tests/test_guards.py -v
```

All three guards have comprehensive test coverage (22 tests).

---

## Security Guarantees

✅ **Phase Gate**: No external calls during planning
✅ **Attribution Guard**: All external data properly attributed
✅ **Content Fence**: External content marked as untrusted

---

## Integration Checklist

When adding a new comm command:

- [ ] Import guards at top of file
- [ ] Call PhaseGate.check() in execute()
- [ ] Generate attribution with format_attribution()
- [ ] Validate with enforce()
- [ ] Wrap content with ContentFence.wrap()
- [ ] Add guard tests
- [ ] Document integration

---

## References

- [ADR-CHAT-COMM-001-Guards](../../../../docs/adr/ADR-CHAT-COMM-001-Guards.md)
- [Test Suite](../../../../tests/test_guards.py)

---

## Quick Reference

### Import All Guards

```python
from agentos.core.chat.guards import (
    PhaseGate, PhaseGateError,
    AttributionGuard, AttributionViolation,
    ContentFence
)
```

### Full Integration Example

```python
def execute(self, args: str, session_id: str, execution_phase: str):
    # 1. Phase Gate
    try:
        PhaseGate.check("comm.search", execution_phase)
    except PhaseGateError as e:
        return {"error": str(e)}

    # 2. Perform operation
    results = self.search(args)

    # 3. Wrap external content
    wrapped_results = [
        ContentFence.wrap(result, result["url"])
        for result in results
    ]

    # 4. Add attribution
    attribution = AttributionGuard.format_attribution("search", session_id)
    data = {
        "results": wrapped_results,
        "metadata": {"attribution": attribution}
    }

    # 5. Validate
    AttributionGuard.enforce(data, session_id)

    return data
```

---

**Status**: Implemented and Tested ✅
**Tests**: 22/22 passing ✅
**Coverage**: All three guards ✅
