"""
Trust Trajectory Engine

Converts Risk Timeline into Trust Trajectory with time inertia.
Prevents "one success = trust / one failure = death" scenarios.

Core Principles:
- Trust states evolve gradually over time
- Transitions must be sequential (no jumping)
- All state changes have audit trail with explain
- Time inertia prevents instant changes
"""

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from agentos.core.time.clock import utc_now, utc_now_ms, parse_db_time
from .state import TrustState, TrustTransition, TrustTrajectoryInfo, TrajectoryRule


class TrustTrajectoryEngine:
    """
    Trust Trajectory Engine.

    Responsibilities:
    - Track trust state evolution over time
    - Enforce sequential state transitions
    - Calculate time inertia
    - Generate transition explanations
    - Integrate with Risk Timeline (E1)
    """

    def __init__(self, db_path: str):
        """
        Initialize trust trajectory engine.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._rules_cache: Optional[List[TrajectoryRule]] = None

    def get_current_state(
        self,
        extension_id: str,
        action_id: str = "*"
    ) -> Optional[TrustState]:
        """
        Get current trust state for extension/action.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier (default: "*" for all)

        Returns:
            Current trust state or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT current_state FROM trust_states
                WHERE extension_id = ? AND action_id = ?
            """, (extension_id, action_id))

            row = cursor.fetchone()
            if row:
                return TrustState(row[0])

        return None

    def get_trajectory_info(
        self,
        extension_id: str,
        action_id: str = "*"
    ) -> Optional[TrustTrajectoryInfo]:
        """
        Get complete trajectory information for extension/action.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier

        Returns:
            Trust trajectory info or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get current state
            cursor = conn.execute("""
                SELECT * FROM trust_states
                WHERE extension_id = ? AND action_id = ?
            """, (extension_id, action_id))

            row = cursor.fetchone()
            if not row:
                return None

            # Calculate time in state
            from datetime import timezone
            state_entered_at = datetime.fromtimestamp(row["state_entered_at_ms"] / 1000, tz=timezone.utc)
            time_in_state = (utc_now() - state_entered_at).total_seconds()

            # Calculate inertia score (higher = more stable)
            # Based on time in state and success rate
            time_factor = min(time_in_state / (7 * 24 * 3600), 1.0)  # Max at 1 week
            successes = row["consecutive_successes"]
            failures = row["consecutive_failures"]
            total_events = successes + failures + 1  # Avoid division by zero
            success_rate = successes / total_events
            inertia_score = (time_factor * 0.6) + (success_rate * 0.4)

            # Get last transition
            last_transition = self._get_last_transition(extension_id, action_id)

            return TrustTrajectoryInfo(
                state=TrustState(row["current_state"]),
                extension_id=extension_id,
                action_id=action_id,
                consecutive_successes=row["consecutive_successes"],
                consecutive_failures=row["consecutive_failures"],
                policy_rejections=row["policy_rejections"],
                high_risk_events=row["high_risk_events"],
                time_in_state=time_in_state,
                inertia_score=inertia_score,
                last_transition=last_transition,
                calculated_at=utc_now()
            )

    def record_event(
        self,
        extension_id: str,
        action_id: str,
        event_type: str,
        risk_score: float,
        policy_decision: Optional[str] = None
    ) -> Tuple[TrustState, Optional[TrustTransition]]:
        """
        Record an execution event and update trajectory.

        Event types:
        - "success": Successful execution
        - "failure": Execution failure
        - "policy_rejection": Policy denied execution
        - "high_risk": High-risk event detected

        Args:
            extension_id: Extension identifier
            action_id: Action identifier
            event_type: Type of event
            risk_score: Risk score at time of event
            policy_decision: Policy decision if applicable

        Returns:
            Tuple of (current_state, transition_record or None)
        """
        with sqlite3.connect(self.db_path) as conn:
            # Initialize state if not exists
            self._ensure_state_exists(conn, extension_id, action_id)

            # Update metrics based on event
            self._update_metrics(conn, extension_id, action_id, event_type)

            # Get updated state info
            cursor = conn.execute("""
                SELECT * FROM trust_states
                WHERE extension_id = ? AND action_id = ?
            """, (extension_id, action_id))

            row = cursor.fetchone()
            current_state = TrustState(row[2])  # current_state column

            # Check for state transition
            context = {
                "consecutive_successes": row[3],
                "consecutive_failures": row[4],
                "policy_rejections": row[5],
                "high_risk_events": row[6],
                "time_in_state_hours": (utc_now_ms() - row[7]) / (1000 * 3600)
            }

            transition = self._check_transition(
                conn,
                extension_id,
                action_id,
                current_state,
                context,
                event_type,
                risk_score,
                policy_decision
            )

            conn.commit()

            if transition:
                return transition.new_state, transition
            else:
                return current_state, None

    def simulate_trajectory(
        self,
        extension_id: str,
        action_id: str,
        events: List[Dict]
    ) -> List[Dict]:
        """
        Simulate trajectory with sequence of events.

        Useful for testing and demonstration.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier
            events: List of event dictionaries with:
                - event_type: Event type
                - risk_score: Risk score
                - policy_decision: Optional policy decision

        Returns:
            List of trajectory snapshots after each event
        """
        snapshots = []

        for event in events:
            state, transition = self.record_event(
                extension_id,
                action_id,
                event["event_type"],
                event["risk_score"],
                event.get("policy_decision")
            )

            info = self.get_trajectory_info(extension_id, action_id)
            snapshot = {
                "event": event,
                "state": state.value,
                "transition": transition.to_dict() if transition else None,
                "trajectory": info.to_dict() if info else None
            }
            snapshots.append(snapshot)

        return snapshots

    def get_transition_history(
        self,
        extension_id: str,
        action_id: str = "*",
        limit: int = 30
    ) -> List[Dict]:
        """
        Get transition history for extension/action.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier
            limit: Maximum number of records

        Returns:
            List of transition records
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT * FROM trust_transitions
                WHERE extension_id = ? AND action_id = ?
                ORDER BY created_at_ms DESC
                LIMIT ?
            """, (extension_id, action_id, limit))

            transitions = []
            for row in cursor:
                transitions.append({
                    "transition_id": row["transition_id"],
                    "extension_id": row["extension_id"],
                    "action_id": row["action_id"],
                    "old_state": row["old_state"],
                    "new_state": row["new_state"],
                    "trigger_event": row["trigger_event"],
                    "explain": row["explain"],
                    "risk_context": json.loads(row["risk_context_json"]),
                    "policy_context": json.loads(row["policy_context_json"]),
                    "created_at_ms": row["created_at_ms"]
                })

            return transitions

    def _ensure_state_exists(
        self,
        conn: sqlite3.Connection,
        extension_id: str,
        action_id: str
    ) -> None:
        """
        Ensure trust state record exists, create if needed.

        New extensions start in EARNING state.

        Args:
            conn: Database connection
            extension_id: Extension identifier
            action_id: Action identifier
        """
        cursor = conn.execute("""
            SELECT 1 FROM trust_states
            WHERE extension_id = ? AND action_id = ?
        """, (extension_id, action_id))

        if not cursor.fetchone():
            now_ms = utc_now_ms()
            conn.execute("""
                INSERT INTO trust_states (
                    extension_id, action_id, current_state,
                    consecutive_successes, consecutive_failures,
                    policy_rejections, high_risk_events,
                    state_entered_at_ms, last_event_at_ms, updated_at_ms
                ) VALUES (?, ?, 'EARNING', 0, 0, 0, 0, ?, ?, ?)
            """, (extension_id, action_id, now_ms, now_ms, now_ms))

    def _update_metrics(
        self,
        conn: sqlite3.Connection,
        extension_id: str,
        action_id: str,
        event_type: str
    ) -> None:
        """
        Update state metrics based on event.

        Args:
            conn: Database connection
            extension_id: Extension identifier
            action_id: Action identifier
            event_type: Event type
        """
        now_ms = utc_now_ms()

        if event_type == "success":
            conn.execute("""
                UPDATE trust_states
                SET consecutive_successes = consecutive_successes + 1,
                    consecutive_failures = 0,
                    last_event_at_ms = ?,
                    updated_at_ms = ?
                WHERE extension_id = ? AND action_id = ?
            """, (now_ms, now_ms, extension_id, action_id))

        elif event_type == "failure":
            conn.execute("""
                UPDATE trust_states
                SET consecutive_failures = consecutive_failures + 1,
                    consecutive_successes = 0,
                    last_event_at_ms = ?,
                    updated_at_ms = ?
                WHERE extension_id = ? AND action_id = ?
            """, (now_ms, now_ms, extension_id, action_id))

        elif event_type == "policy_rejection":
            conn.execute("""
                UPDATE trust_states
                SET policy_rejections = policy_rejections + 1,
                    consecutive_successes = 0,
                    last_event_at_ms = ?,
                    updated_at_ms = ?
                WHERE extension_id = ? AND action_id = ?
            """, (now_ms, now_ms, extension_id, action_id))

        elif event_type == "high_risk":
            conn.execute("""
                UPDATE trust_states
                SET high_risk_events = high_risk_events + 1,
                    consecutive_successes = 0,
                    last_event_at_ms = ?,
                    updated_at_ms = ?
                WHERE extension_id = ? AND action_id = ?
            """, (now_ms, now_ms, extension_id, action_id))

    def _check_transition(
        self,
        conn: sqlite3.Connection,
        extension_id: str,
        action_id: str,
        current_state: TrustState,
        context: Dict,
        event_type: str,
        risk_score: float,
        policy_decision: Optional[str]
    ) -> Optional[TrustTransition]:
        """
        Check if state should transition based on rules.

        Args:
            conn: Database connection
            extension_id: Extension identifier
            action_id: Action identifier
            current_state: Current trust state
            context: Current metrics context
            event_type: Triggering event type
            risk_score: Risk score
            policy_decision: Policy decision

        Returns:
            Transition record if state changed, None otherwise
        """
        # Load rules
        rules = self._load_rules()

        # Find applicable rules for current state
        applicable_rules = [
            r for r in rules
            if r.from_state == current_state and
            current_state.can_transition_to(r.to_state)
        ]

        # Sort by priority
        applicable_rules.sort(key=lambda r: r.priority)

        # Check rules in priority order
        for rule in applicable_rules:
            if rule.evaluate(context):
                # Execute transition
                transition = self._execute_transition(
                    conn,
                    extension_id,
                    action_id,
                    current_state,
                    rule.to_state,
                    event_type,
                    rule,
                    context,
                    risk_score,
                    policy_decision
                )
                return transition

        return None

    def _execute_transition(
        self,
        conn: sqlite3.Connection,
        extension_id: str,
        action_id: str,
        old_state: TrustState,
        new_state: TrustState,
        trigger_event: str,
        rule: TrajectoryRule,
        context: Dict,
        risk_score: float,
        policy_decision: Optional[str]
    ) -> TrustTransition:
        """
        Execute state transition with full audit trail.

        Args:
            conn: Database connection
            extension_id: Extension identifier
            action_id: Action identifier
            old_state: Previous state
            new_state: New state
            trigger_event: Event that triggered transition
            rule: Rule that triggered transition
            context: Metrics context
            risk_score: Risk score
            policy_decision: Policy decision

        Returns:
            Transition record
        """
        transition_id = str(uuid.uuid4())
        now_ms = utc_now_ms()

        # Generate explain
        explain = self._generate_explain(
            old_state,
            new_state,
            trigger_event,
            rule,
            context
        )

        # Prepare context
        risk_context = {
            "risk_score": risk_score,
            "consecutive_successes": context["consecutive_successes"],
            "consecutive_failures": context["consecutive_failures"]
        }

        policy_context = {
            "policy_decision": policy_decision,
            "policy_rejections": context["policy_rejections"],
            "high_risk_events": context["high_risk_events"]
        }

        # Record transition
        conn.execute("""
            INSERT INTO trust_transitions (
                transition_id, extension_id, action_id,
                old_state, new_state, trigger_event,
                explain, risk_context_json, policy_context_json,
                created_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            transition_id,
            extension_id,
            action_id,
            old_state.value,
            new_state.value,
            trigger_event,
            explain,
            json.dumps(risk_context),
            json.dumps(policy_context),
            now_ms
        ))

        # Update current state
        conn.execute("""
            UPDATE trust_states
            SET current_state = ?,
                consecutive_successes = 0,
                consecutive_failures = 0,
                policy_rejections = 0,
                high_risk_events = 0,
                state_entered_at_ms = ?,
                updated_at_ms = ?
            WHERE extension_id = ? AND action_id = ?
        """, (new_state.value, now_ms, now_ms, extension_id, action_id))

        return TrustTransition(
            transition_id=transition_id,
            extension_id=extension_id,
            action_id=action_id,
            old_state=old_state,
            new_state=new_state,
            trigger_event=trigger_event,
            explain=explain,
            risk_context=risk_context,
            policy_context=policy_context,
            created_at=datetime.fromtimestamp(now_ms / 1000)
        )

    def _generate_explain(
        self,
        old_state: TrustState,
        new_state: TrustState,
        trigger_event: str,
        rule: TrajectoryRule,
        context: Dict
    ) -> str:
        """
        Generate human-readable explanation for transition.

        Args:
            old_state: Previous state
            new_state: New state
            trigger_event: Triggering event
            rule: Rule that triggered transition
            context: Metrics context

        Returns:
            Explanation string
        """
        if old_state == TrustState.EARNING and new_state == TrustState.STABLE:
            return (
                f"Promoted to STABLE after {context['consecutive_successes']} "
                f"consecutive successes with no policy violations. "
                f"Time in EARNING: {context['time_in_state_hours']:.1f}h. "
                f"Trigger: {trigger_event}"
            )

        elif old_state == TrustState.STABLE and new_state == TrustState.DEGRADING:
            return (
                f"Degraded to DEGRADING due to {trigger_event}. "
                f"Failures: {context['consecutive_failures']}, "
                f"Policy rejections: {context['policy_rejections']}, "
                f"High-risk events: {context['high_risk_events']}"
            )

        elif old_state == TrustState.DEGRADING and new_state == TrustState.EARNING:
            return (
                f"Recovered to EARNING after {context['consecutive_successes']} "
                f"successful executions. Time in DEGRADING: {context['time_in_state_hours']:.1f}h. "
                f"Beginning trust re-earning process."
            )

        else:
            return f"Transition from {old_state.value} to {new_state.value} triggered by {trigger_event}"

    def _load_rules(self) -> List[TrajectoryRule]:
        """
        Load trajectory rules from database.

        Returns:
            List of trajectory rules
        """
        if self._rules_cache is not None:
            return self._rules_cache

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT * FROM trust_trajectory_rules
                WHERE active = 1
                ORDER BY priority
            """)

            rules = []
            for row in cursor:
                rule = TrajectoryRule(
                    rule_id=row["rule_id"],
                    from_state=TrustState(row["from_state"]),
                    to_state=TrustState(row["to_state"]),
                    condition=row["condition_description"],
                    threshold_config=json.loads(row["threshold_config_json"]),
                    priority=row["priority"]
                )
                rules.append(rule)

            self._rules_cache = rules
            return rules

    def _get_last_transition(
        self,
        extension_id: str,
        action_id: str
    ) -> Optional[TrustTransition]:
        """
        Get last transition record.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier

        Returns:
            Last transition or None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT * FROM trust_transitions
                WHERE extension_id = ? AND action_id = ?
                ORDER BY created_at_ms DESC
                LIMIT 1
            """, (extension_id, action_id))

            row = cursor.fetchone()
            if row:
                return TrustTransition(
                    transition_id=row["transition_id"],
                    extension_id=row["extension_id"],
                    action_id=row["action_id"],
                    old_state=TrustState(row["old_state"]),
                    new_state=TrustState(row["new_state"]),
                    trigger_event=row["trigger_event"],
                    explain=row["explain"],
                    risk_context=json.loads(row["risk_context_json"]),
                    policy_context=json.loads(row["policy_context_json"]),
                    created_at=datetime.fromtimestamp(row["created_at_ms"] / 1000)
                )

        return None

    def bootstrap_from_marketplace(
        self,
        extension_id: str,
        marketplace_trust: float,
        local_initial_trust: float,
        source: str = "marketplace"
    ) -> Dict:
        """
        Bootstrap trust trajectory from marketplace import.

        This method integrates with F4 Local Trust Bootstrap to initialize
        trust state for marketplace capabilities.

        Trust State: Always EARNING (no direct STABLE)
        Trust Score: Decayed from marketplace
        History: Starts from zero

        Args:
            extension_id: Extension identifier
            marketplace_trust: Original marketplace trust
            local_initial_trust: Trust after decay
            source: Import source

        Returns:
            Bootstrap info dictionary

        Red Lines:
        - ❌ Cannot start in STABLE state
        - ❌ Cannot skip EARNING phase
        - ❌ Must have local evolution history
        """
        with sqlite3.connect(self.db_path) as conn:
            # Ensure trust state exists (will be EARNING)
            self._ensure_state_exists(conn, extension_id, "*")

            # Record bootstrap metadata
            now_ms = utc_now_ms()

            # Check if already exists
            cursor = conn.execute("""
                SELECT 1 FROM trust_states
                WHERE extension_id = ? AND action_id = '*'
            """, (extension_id,))

            if cursor.fetchone():
                # Get current state
                cursor = conn.execute("""
                    SELECT current_state, state_entered_at_ms
                    FROM trust_states
                    WHERE extension_id = ? AND action_id = '*'
                """, (extension_id,))

                row = cursor.fetchone()
                current_state = row[0]
                state_entered_at_ms = row[1]

                return {
                    "extension_id": extension_id,
                    "trust_state": current_state,
                    "marketplace_trust": marketplace_trust,
                    "local_initial_trust": local_initial_trust,
                    "source": source,
                    "state_entered_at_ms": state_entered_at_ms,
                    "message": f"Bootstrapped from {source}. State: {current_state}"
                }

        return {}
