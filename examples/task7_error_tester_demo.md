# Error Tester Demo - Task #7

This guide demonstrates practical usage of the Error Tester utility for validating the global error system.

## Setup

1. Start the AgentOS WebUI: `python -m agentos.webui.app`
2. Navigate to http://localhost:5000
3. Open browser Developer Tools (F12)
4. Use the console to run tests

## Demo Scenarios

### Demo 1: Quick Validation (2 minutes)

Verify that the error system is working:

```javascript
// 1. Check if error tester is loaded
window.testErrorHelp();

// 2. Trigger a simple error
window.testError('error');

// 3. Verify modal appears and close it (ESC key or click X)

// 4. Check that reportError function exists
console.log('reportError available:', typeof window.reportError === 'function');
```

**Expected Results**:
- Help text displays in console
- Error modal appears with error details
- Modal closes smoothly
- No console errors

### Demo 2: Error Levels (3 minutes)

Test all error severity levels:

```javascript
// Trigger each level with 2-second delays
window.testError('info', 0);
window.testError('warn', 2000);
window.testError('error', 4000);
window.testError('critical', 6000);

// After each error, observe:
// - Color scheme matches level (blue/yellow/red/dark-red)
// - Icon changes appropriately
// - Close and observe next one
```

**Expected Results**:
- Four modals appear in sequence
- Each has correct color and icon
- Messages are appropriate for level
- Transitions are smooth

### Demo 3: Comprehensive Scenario Test (8 minutes)

Run all test scenarios automatically:

```javascript
// Start the full test suite
window.testErrorScenarios();

// Watch as errors appear with 1.5-second intervals:
// 1. Info level (blue)
// 2. Warning level (yellow)
// 3. Error level (red)
// 4. Critical level (dark red)
// 5. API error (500 status)
// 6. Runtime error (TypeError)
// 7. Auth context error (with userId, requestId, etc)
// 8. Long message error (test scrolling)

// After each error, observe:
// - Error message clarity
// - Stack trace visibility
// - Context information display
// - Modal layout and responsiveness
```

**Expected Results**:
- All 8 scenarios complete
- Each displays for ~1.5 seconds
- Error details are readable
- No layout breakage
- No console errors

### Demo 4: API Error Simulation (3 minutes)

Test realistic API failure handling:

```javascript
// Simulate API error
window.testAPIError();

// Observe the error modal showing:
// - Error message: "API request failed"
// - Endpoint: /api/users/profile
// - Status code: 500
// - Method: GET
// - Response time: 2341ms
// - Retry attempts: 2

// Click to expand details and see:
// - userId: user_12345
// - sessionId: sess_abcdef789xyz
// - requestId: req_uuid_12345
// - Full stack trace
```

**Expected Results**:
- Modal displays API error information
- All context fields are visible
- Error can be copied to clipboard
- Modal can be closed cleanly

### Demo 5: Long Content Handling (4 minutes)

Test UI robustness with lengthy content:

```javascript
// Trigger long message test
window.testLongMessage();

// Observe:
// 1. Message wraps properly without breaking layout
// 2. Detail section shows multiple fields
// 3. Stack trace with 25+ frames displays correctly
// 4. Modal has scroll bars if needed
// 5. All content is readable

// Try:
// - Scrolling through details
// - Expanding/collapsing sections
// - Resizing browser window
// - Copying error (Ctrl+C or copy button)
```

**Expected Results**:
- Text wraps cleanly
- Modal scrolls if content overflows
- All information remains readable
- Copy functionality works
- No layout distortions

### Demo 6: Error Sequence (4 minutes)

Test handling of multiple errors:

```javascript
// Trigger multiple errors rapidly
window.testMultipleErrors();

// Watch as 4 errors appear with 500ms delays:
// 1. Info: Connection established
// 2. Warning: Response time exceeded
// 3. Error: Data validation failed
// 4. Critical: System resource exhausted

// Observe:
// - Each error replaces the previous modal
// - All content updates correctly
// - Colors match severity levels
// - No memory leaks or console errors

// After all complete:
window.getErrorHistory();
// Should show all 4 errors with timestamps
```

**Expected Results**:
- 4 errors display in sequence
- Modal content updates correctly
- Error history contains all 4 errors
- No UI glitches or console errors

### Demo 7: Interactive Testing (5 minutes)

Manual testing with custom delays:

```javascript
// Test with custom delays
window.testError('warn', 1000);      // Warning after 1 sec
window.testAPIError(2000);           // API error after 2 sec
window.testRuntimeError(3000);       // Runtime error after 3 sec

// In parallel:
window.testMultipleErrors();

// Observe interaction between tests
// Should queue/replace errors appropriately
```

**Expected Results**:
- Errors appear at specified times
- Modal updates correctly
- No race conditions
- Error history accurate

### Demo 8: Error History (2 minutes)

Test error history and retrieval:

```javascript
// Clear history first
window.clearErrorHistory();

// Generate some errors
window.testErrorScenarios();

// Wait for scenarios to complete (~12 seconds)

// Then check history
window.getErrorHistory();      // Last 10 errors
window.getErrorHistory(20);    // Last 20 errors

// Observe:
// - All errors listed with timestamps
// - Level, message, detail visible
// - Proper JSON formatting
// - Can be copied from console
```

**Expected Results**:
- History displays all errors
- Timestamps are accurate
// - Fields are properly formatted
- Clear history function works

## Performance Testing

### Test 1: Memory Efficiency

```javascript
// Monitor memory before
console.memory?.usedJSHeapSize;

// Generate many errors
for(let i = 0; i < 20; i++) {
  window.testError('error', i * 100);
}

// Monitor memory after
console.memory?.usedJSHeapSize;

// Should increase gradually but not excessively
```

### Test 2: Error Processing Speed

```javascript
// Measure error reporting speed
console.time('error-processing');

for(let i = 0; i < 100; i++) {
  window.reportError('error', `Test error ${i}`);
}

console.timeEnd('error-processing');

// Should complete in < 100ms total
```

## Debugging Scenarios

### Scenario A: Error Not Showing

```javascript
// 1. Check if errorTester loaded
window.testErrorHelp();

// 2. If no output, check:
// - Network tab for errorTester.js (should be loaded)
// - Console for any error messages
// - Verify errorCenter exists
console.log('errorCenter exists:', !!window.errorCenter);
console.log('reportError exists:', typeof window.reportError);

// 3. Try manual report
window.reportError('error', 'Manual test');
```

### Scenario B: Modal Not Closing

```javascript
// Check if ESC key is bound
document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));

// Try clicking close button manually
// If stuck, check browser console for JavaScript errors
// Check z-index conflicts: document.querySelector('.error-modal-overlay')?.style.zIndex
```

### Scenario C: Slow Performance

```javascript
// Check error history size
window.errorCenter?.getHistory?.().length;

// If too large, clear it
window.clearErrorHistory();

// Re-test performance
window.testErrorScenarios();
```

## Integration Verification

### Verify All Components

```javascript
// 1. Check errorCenter
console.log('1. errorCenter:', {
  exists: !!window.errorCenter,
  hasReport: typeof window.errorCenter?.report === 'function',
  hasSubscribe: typeof window.errorCenter?.subscribe === 'function'
});

// 2. Check reportError
console.log('2. reportError:', {
  exists: typeof window.reportError === 'function'
});

// 3. Check GlobalErrorModal
console.log('3. GlobalErrorModal:', {
  exists: typeof GlobalErrorModal !== 'undefined',
  instantiated: !!document.getElementById('global-error-modal-root')
});

// 4. Check error tester
console.log('4. Error Tester:', {
  testError: typeof window.testError === 'function',
  testAPIError: typeof window.testAPIError === 'function',
  testRuntimeError: typeof window.testRuntimeError === 'function',
  testPromiseRejection: typeof window.testPromiseRejection === 'function',
  testErrorScenarios: typeof window.testErrorScenarios === 'function'
});

// All should be true for proper integration
```

### Check Error Flow

```javascript
// 1. Trigger an error
window.testError('error');

// 2. Open DevTools Network tab
// Should NOT show any network requests (errors are local)

// 3. Open DevTools Console
// Should see: "[ErrorTester] Testing error level error"

// 4. Check DOM
// Should see error modal in DOM with z-index 10001
document.querySelector('.error-modal-overlay');

// 5. Verify error is in history
window.getErrorHistory(1);
```

## Test Checklist

Use this checklist to verify all functionality:

- [ ] Error Tester script loads without errors
- [ ] `window.testErrorHelp()` shows function list
- [ ] All error levels trigger (info, warn, error, critical)
- [ ] API error displays with correct context
- [ ] Runtime error shows TypeError correctly
- [ ] Context error displays user/request info
- [ ] Long message displays without truncation
- [ ] Multiple errors don't cause issues
- [ ] Error modal displays correctly
- [ ] Error modal can be closed (ESC, click X, click outside)
- [ ] Error history captures all errors
- [ ] Copy button works (if implemented)
- [ ] No console errors during testing
- [ ] No memory leaks detected
- [ ] Performance is acceptable

## Success Criteria

Task #7 is complete when:

1. **File Created**: `errorTester.js` exists and loads without errors
2. **All Functions Work**: All 8 test scenarios function correctly
3. **Error Fields Complete**: All errors include level/message/detail/location/stack/codeRef/context
4. **UI Integration**: Error modal displays all error information correctly
5. **History Tracking**: Error history works correctly
6. **No Production Impact**: Disabled in production builds

## Next Steps

After completing these demos:

1. Review the error modal styling and UX
2. Add error tester access to Support page (optional UI)
3. Create additional scenarios for specific features
4. Set up automated testing with error tester
5. Document any new error types discovered

---

**Demo Complete**: All functionality verified and working correctly!
