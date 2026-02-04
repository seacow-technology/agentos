"""
Ops Assistant - Governance Reference Implementation

This is NOT an operations tool. This is a demonstration of Execution Trust.

The value of Ops Assistant is NOT its features, but its governance behavior.
It exists to prove that governance is real, not just documentation.

Key Principle:
- Ops Assistant can only REQUEST operations
- Ops Assistant cannot DECIDE execution
- Ops Assistant cannot write security logic
- Ops Assistant must "fail gracefully" and often

When Ops Assistant is denied, it should explain WHY, not try to bypass.
"""

from .queries import StatusQueries
from .actions import SystemActions
from .client import GovernanceAPIClient

__all__ = [
    "StatusQueries",
    "SystemActions",
    "GovernanceAPIClient",
]
