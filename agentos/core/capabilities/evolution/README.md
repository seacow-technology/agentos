# Evolution Decision Engine (Phase E3)

## Overview

The Evolution Decision Engine proposes trust evolution actions based on Trust Trajectory and Risk Timeline. It is a core component of AgentOS Phase E (Trust Evolution).

**Key Principle**: This engine **PROPOSES** actions but **NEVER EXECUTES** them. All proposals require Human Review (Phase E4) before execution.

## Architecture

```
┌─────────────────┐
│  E1: Risk       │
│  Timeline       │────┐
└─────────────────┘    │
                       ├──> ┌─────────────────┐
┌─────────────────┐    │    │  E3: Evolution  │    ┌─────────────────┐
│  E2: Trust      │────┤    │  Decision       │───>│  E4: Human      │
│  Trajectory     │    │    │  Engine         │    │  Review Queue   │
└─────────────────┘    │    └─────────────────┘    └─────────────────┘
                       │
┌─────────────────┐    │
│  Capability     │────┘
│  Audit Trail    │
└─────────────────┘
```

## Evolution Actions

### 1. PROMOTE (Upgrade Trust)

**Conditions**:
- Risk Score < 30 (LOW tier)
- Trust Trajectory: STABLE
- 50+ successful executions
- 30+ stable days
- Zero violations
- Clean sandbox record

**Consequences**:
- Lower approval frequency
- Wider execution window
- Allow higher tier requests

**Review Level**: HIGH_PRIORITY

### 2. FREEZE (Freeze Trust)

**Conditions**:
- Trust Trajectory: DEGRADING
- Max 5 violations

**Consequences**:
- Block new permissions
- Maintain existing capabilities
- Mandatory sandbox

**Review Level**: STANDARD

### 3. REVOKE (Revoke Trust)

**Triggers** (any one triggers REVOKE):
- Risk Score >= 70 (HIGH)
- Sandbox violation
- 3+ policy denials in 24h
- Human flag
- Trust Trajectory: CRITICAL

**Consequences**:
- Disable automatic execution
- Must restart Phase D
- Full human review required

**Review Level**: CRITICAL

## Red Lines

1. ❌ **No Silent REVOKE**: All revocations must be audited and explained
2. ❌ **No Auto-Promote to HIGH**: Extensions with risk_score >= 70 cannot auto-promote
3. ❌ **No Unexplained Decisions**: Every decision must have complete causal chain
4. ❌ **No Direct Execution**: Engine only proposes, never executes

## Usage

### Python API

```python
from agentos.core.capabilities.evolution import EvolutionEngine
from agentos.store import get_db_path

# Initialize engine
engine = EvolutionEngine(get_db_path())

# Propose evolution action
decision = engine.propose_action("my_extension", "*")

# Access decision details
print(f"Action: {decision.action.value}")
print(f"Risk Score: {decision.risk_score}")
print(f"Review Level: {decision.review_level.value}")
print(f"Explanation:\n{decision.explanation}")

# Get decision history
history = engine.get_decision_history("my_extension", limit=10)
for record in history:
    print(f"{record.action} - {record.status} - {record.created_at}")
```

### Command Line

```bash
# Evaluate extension
python tools/run_evolution_decision.py --extension my_ext

# Get JSON output
python tools/run_evolution_decision.py --extension my_ext --json

# View decision history
python tools/run_evolution_decision.py --extension my_ext --history

# Verify HIGH risk protection
python tools/run_evolution_decision.py --extension high_risk_ext --expect-no-auto-promote
```

## Components

### Core Files

- `__init__.py` - Module exports
- `models.py` - Data models (EvolutionDecision, EvolutionAction, etc.)
- `actions.py` - Action conditions and evaluation logic
- `engine.py` - Main evolution decision engine

### Database Schema

- `evolution_decisions` - Decision records with full context
- `evolution_audit` - Audit trail for all evolution events
- `evolution_metrics` - Aggregated metrics for monitoring

Schema version: v71 (`schema_v71_evolution_decisions.sql`)

### Tools

- `run_evolution_decision.py` - CLI tool for evaluating extensions
- `run_evolution_acceptance_tests.sh` - Acceptance test suite

### Documentation

- `README.md` - This file
- `docs/governance/EVOLUTION_ACTIONS.md` - Detailed action documentation with real examples

## Testing

### Run Unit Tests

```bash
pytest tests/unit/core/capabilities/evolution/test_evolution_engine.py -v
```

### Run Acceptance Tests

```bash
./tools/run_evolution_acceptance_tests.sh
```

### Test Coverage

The test suite validates:
1. ✅ PROMOTE conditions (2 tests)
2. ✅ FREEZE conditions (1 test)
3. ✅ REVOKE conditions (3 tests)
4. ✅ No auto-promote to HIGH risk (2 tests)
5. ✅ Explanation completeness (2 tests)
6. ✅ Audit trail completeness (2 tests)

Total: 13 tests, all passing

## Decision Lifecycle

```
1. Evidence Gathering
   ├── E1: Risk Score (risk_scorer.calculate_risk)
   ├── E2: Trust Trajectory (trust_tier_engine.get_tier)
   ├── Execution History (capability_audit table)
   └── Violation History (task_audits table)

2. Condition Evaluation
   ├── evaluate_promote()
   ├── evaluate_freeze()
   └── evaluate_revoke()

3. Action Selection
   └── Priority: REVOKE > FREEZE > PROMOTE > NONE

4. Decision Construction
   ├── Build causal chain
   ├── Generate explanation
   └── Determine review level

5. Recording
   ├── Insert into evolution_decisions table
   ├── Emit audit event
   └── Return decision object

6. Human Review (Phase E4)
   ├── PROPOSED → APPROVED → EXECUTED
   ├── PROPOSED → REJECTED
   └── PROPOSED → EXPIRED
```

## Integration Points

### Inputs (Dependencies)

- **E1 (Risk Timeline)**: Provides risk scores and historical data
- **E2 (Trust Trajectory)**: Provides trust state and trends
- **Capability Audit**: Execution history and success rates
- **Task Audits**: Violation and policy denial records

### Outputs (Used By)

- **E4 (Human Review)**: Proposed decisions for approval/rejection
- **E5 (Policy Integration)**: Approved actions to enforce
- **Audit System**: Complete decision trail for compliance

## Monitoring

### Key Metrics

```sql
-- Decision rate by action
SELECT action, COUNT(*) as count
FROM evolution_decisions
WHERE created_at >= datetime('now', '-7 days')
GROUP BY action;

-- Approval rate
SELECT
    COUNT(CASE WHEN status = 'APPROVED' THEN 1 END) * 100.0 / COUNT(*) as approval_rate
FROM evolution_decisions
WHERE review_level IN ('HIGH_PRIORITY', 'CRITICAL');

-- Average decision age
SELECT
    AVG(julianday('now') - julianday(created_at)) as avg_age_days
FROM evolution_decisions
WHERE status = 'PROPOSED';
```

## Version

Evolution Decision Engine v1.0 (Phase E3)
Last Updated: 2024-02-02
Status: ✅ Implemented & Tested

## Next Steps

- [ ] E4: Human Review Queue implementation
- [ ] E5: Trust × Policy integration
- [ ] E6: Phase E final gate testing
- [ ] Integrate with governance UI
- [ ] Add real-time monitoring dashboard
