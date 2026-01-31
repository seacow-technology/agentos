# Chat Mode Tests

This directory contains test suites for Chat Mode components, with a focus on security and integration testing.

## Test Suites

### Gate Tests (`test_comm_integration_gates.py`)

Comprehensive security tests for Chat ↔ CommunicationOS integration.

**Purpose**: Validate security boundaries and safety guarantees.

**Coverage**:
- ✅ Phase Gate (6 tests) - Block operations in planning phase
- ✅ SSRF Protection (3 tests) - Block localhost and private IPs
- ✅ Trust Tier (3 tests) - Proper trust tier propagation
- ✅ Attribution (5 tests) - Mandatory attribution enforcement
- ✅ Content Fence (5 tests) - Mark and isolate untrusted content
- ✅ Audit Trail (3 tests) - Complete audit logging
- ✅ Integration (2 tests) - End-to-end workflows

**Total**: 27 tests (all passing)

## Running Tests

### All Gate Tests
```bash
pytest agentos/core/chat/tests/test_comm_integration_gates.py -v
```

### With Coverage Report
```bash
pytest agentos/core/chat/tests/test_comm_integration_gates.py -v \
  --cov=agentos.core.chat.comm_commands \
  --cov=agentos.core.chat.communication_adapter \
  --cov=agentos.core.chat.guards \
  --cov-report=term-missing
```

### Specific Test Category
```bash
# Phase Gate tests only
pytest agentos/core/chat/tests/test_comm_integration_gates.py::TestPhaseGate -v

# SSRF Protection tests only
pytest agentos/core/chat/tests/test_comm_integration_gates.py::TestSSRFProtection -v

# Trust Tier tests only
pytest agentos/core/chat/tests/test_comm_integration_gates.py::TestTrustTier -v

# Attribution tests only
pytest agentos/core/chat/tests/test_comm_integration_gates.py::TestAttribution -v

# Content Fence tests only
pytest agentos/core/chat/tests/test_comm_integration_gates.py::TestContentFence -v

# Audit tests only
pytest agentos/core/chat/tests/test_comm_integration_gates.py::TestAudit -v

# Integration tests only
pytest agentos/core/chat/tests/test_comm_integration_gates.py::TestIntegration -v
```

### Single Test
```bash
pytest agentos/core/chat/tests/test_comm_integration_gates.py::TestPhaseGate::test_comm_search_blocked_in_planning -v
```

## Test Reports

See `GATE_TESTS_REPORT.md` for detailed test results and security verification.

## Test Architecture

### Mocking Strategy

All tests use mocks to avoid real network requests:

```python
@patch('agentos.core.chat.communication_adapter.CommunicationAdapter')
def test_example(mock_adapter_class):
    mock_adapter = Mock()
    mock_adapter.search = AsyncMock(return_value={...})
    mock_adapter_class.return_value = mock_adapter
    # Test logic here
```

### Test Context

All tests provide proper execution context:

```python
context = {
    "session_id": "test_session",
    "task_id": "test_task",
    "execution_phase": "execution"  # or "planning"
}
```

## Adding New Tests

### Phase Gate Tests

Test that operations are blocked/allowed based on execution phase:

```python
def test_new_operation_blocked_in_planning(self):
    context = {"execution_phase": "planning", ...}
    result = Handler.handle_operation(..., context)
    assert result.success is False
    assert "blocked" in result.message.lower()
```

### SSRF Protection Tests

Test that dangerous URLs are blocked:

```python
@patch('agentos.core.chat.communication_adapter.CommunicationAdapter')
def test_dangerous_url_blocked(self, mock_adapter_class):
    mock_adapter.fetch = AsyncMock(return_value={
        "status": "blocked",
        "reason": "SSRF_PROTECTION",
        ...
    })
    result = Handler.handle_fetch(["http://dangerous-url"], context)
    assert result.success is False
```

### Attribution Tests

Test that output includes proper attribution:

```python
@patch('agentos.core.chat.communication_adapter.CommunicationAdapter')
def test_output_has_attribution(self, mock_adapter_class):
    mock_adapter.search = AsyncMock(return_value={
        "metadata": {"attribution": "CommunicationOS (search) in session test"}
    })
    result = Handler.handle_search(["query"], context)
    assert "CommunicationOS" in result.message
    assert "test" in result.message  # session_id
```

## Best Practices

1. **Always Mock External Calls**: Use `@patch` and `AsyncMock` for all network operations
2. **Test Both Success and Failure**: Cover happy path and error conditions
3. **Verify Security Boundaries**: Ensure guards are active and enforcing policies
4. **Check Audit Trail**: Verify that operations are logged correctly
5. **Use Descriptive Names**: Test names should clearly describe what they verify
6. **Include Docstrings**: Explain the purpose of each test

## Continuous Integration

These tests are designed to run in CI/CD pipelines:
- Fast execution (~0.5 seconds)
- No external dependencies
- Deterministic results
- Clear pass/fail signals

## Related Documentation

- **Gate Tests Report**: `GATE_TESTS_REPORT.md` - Detailed test results
- **Guards README**: `../guards/README.md` - Guard implementation details
- **Commands**: `../comm_commands.py` - Command handler implementation
- **Adapter**: `../communication_adapter.py` - Adapter layer implementation

## Support

For questions or issues with tests:
1. Check `GATE_TESTS_REPORT.md` for detailed results
2. Review guard implementation in `../guards/`
3. Examine command handlers in `../comm_commands.py`
4. Check adapter logic in `../communication_adapter.py`

---

**Last Updated**: 2026-01-30
**Test Suite Version**: 1.0
**Status**: ✅ All 27 tests passing
