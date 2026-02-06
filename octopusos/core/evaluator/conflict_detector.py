"""
Conflict Detector — v0.9.3

Detects conflicts between normalized intents across 4 dimensions:
- Resource conflicts
- Effect conflicts  
- Order conflicts
- Constraint conflicts
"""

from typing import Dict, List, Any, Set, Tuple
from .intent_normalizer import CanonicalIntent


class Conflict:
    """Represents a detected conflict between intents."""
    
    def __init__(
        self,
        conflict_id: str,
        conflict_type: str,
        severity: str,
        intent_ids: List[str],
        resource_ref: str = "",
        description: str = "",
        evidence_refs: List[str] = None
    ):
        self.conflict_id = conflict_id
        self.type = conflict_type
        self.severity = severity
        self.intent_ids = intent_ids
        self.resource_ref = resource_ref
        self.description = description
        self.evidence_refs = evidence_refs or []
        self.resolutions = self._suggest_resolutions()
    
    def _suggest_resolutions(self) -> List[str]:
        """Suggest possible resolutions based on conflict type."""
        if self.type == "resource_conflict":
            return ["merge_union", "override_by_priority", "reject"]
        elif self.type == "effect_conflict":
            return ["override_by_priority", "reject"]
        elif self.type == "order_conflict":
            return ["merge_union", "manual_resolution"]
        elif self.type == "constraint_conflict":
            return ["reject", "manual_resolution"]
        return ["manual_resolution"]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "conflict_id": self.conflict_id,
            "type": self.type,
            "severity": self.severity,
            "intent_ids": self.intent_ids,
            "resource_ref": self.resource_ref,
            "description": self.description,
            "evidence_refs": self.evidence_refs,
            "resolutions": self.resolutions
        }


class ConflictDetector:
    """Detects conflicts between intents."""
    
    def __init__(self):
        self.conflict_counter = 0
    
    def detect_all(self, canonical_intents: Dict[str, CanonicalIntent]) -> List[Conflict]:
        """
        Detect all conflicts across intent set.
        
        Args:
            canonical_intents: Dict of intent_id -> canonical intent
            
        Returns:
            List of detected conflicts
        """
        conflicts = []
        
        # Convert to list for pairwise comparison
        intent_list = list(canonical_intents.values())
        
        # Pairwise conflict detection
        for i, intent_a in enumerate(intent_list):
            for intent_b in intent_list[i+1:]:
                # Resource conflicts
                resource_conflicts = self.detect_resource_conflicts(intent_a, intent_b)
                conflicts.extend(resource_conflicts)
                
                # Effect conflicts
                effect_conflicts = self.detect_effect_conflicts(intent_a, intent_b)
                conflicts.extend(effect_conflicts)
                
                # Order conflicts
                order_conflicts = self.detect_order_conflicts(intent_a, intent_b)
                conflicts.extend(order_conflicts)
                
                # Constraint conflicts
                constraint_conflicts = self.detect_constraint_conflicts(intent_a, intent_b)
                conflicts.extend(constraint_conflicts)
        
        return conflicts
    
    def detect_resource_conflicts(
        self,
        intent_a: CanonicalIntent,
        intent_b: CanonicalIntent
    ) -> List[Conflict]:
        """
        Detect resource conflicts between two intents.
        
        Conflict occurs when:
        - Both intents target the same resource
        - At least one has write effects
        
        Args:
            intent_a: First intent
            intent_b: Second intent
            
        Returns:
            List of resource conflicts
        """
        conflicts = []
        
        # Find overlapping resources
        overlap = intent_a.overlaps_resources(intent_b)
        
        if not overlap:
            return conflicts
        
        # Check if either has write effects
        a_writes = intent_a.has_write_effects()
        b_writes = intent_b.has_write_effects()
        
        if not (a_writes or b_writes):
            # Both read-only, no conflict
            return conflicts
        
        # Determine severity based on overlap size and write type
        severity = "medium"
        if a_writes and b_writes:
            severity = "high"
        if len(overlap) > 10:
            severity = "critical"
        
        for resource in overlap:
            self.conflict_counter += 1
            conflict = Conflict(
                conflict_id=f"conflict_{self.conflict_counter:06d}",
                conflict_type="resource_conflict",
                severity=severity,
                intent_ids=[intent_a.intent_id, intent_b.intent_id],
                resource_ref=resource,
                description=f"Both intents target resource: {resource}",
                evidence_refs=[
                    f"intent:{intent_a.intent_id}:scope",
                    f"intent:{intent_b.intent_id}:scope"
                ]
            )
            conflicts.append(conflict)
        
        return conflicts
    
    def detect_effect_conflicts(
        self,
        intent_a: CanonicalIntent,
        intent_b: CanonicalIntent
    ) -> List[Conflict]:
        """
        Detect effect conflicts (incompatible side effects).
        
        Conflict occurs when effects are semantically incompatible:
        - deploy vs rollback
        - write vs delete
        - create vs remove
        
        Args:
            intent_a: First intent
            intent_b: Second intent
            
        Returns:
            List of effect conflicts
        """
        conflicts = []
        
        # Define incompatible effect pairs
        incompatible = {
            ("deploy", "rollback"),
            ("write", "delete"),
            ("create", "remove"),
            ("enable", "disable")
        }
        
        a_effects = set(intent_a.effects.keys())
        b_effects = set(intent_b.effects.keys())
        
        for effect_a in a_effects:
            for effect_b in b_effects:
                if (effect_a, effect_b) in incompatible or (effect_b, effect_a) in incompatible:
                    self.conflict_counter += 1
                    conflict = Conflict(
                        conflict_id=f"conflict_{self.conflict_counter:06d}",
                        conflict_type="effect_conflict",
                        severity="high",
                        intent_ids=[intent_a.intent_id, intent_b.intent_id],
                        description=f"Incompatible effects: {effect_a} vs {effect_b}",
                        evidence_refs=[
                            f"intent:{intent_a.intent_id}:effects",
                            f"intent:{intent_b.intent_id}:effects"
                        ]
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def detect_order_conflicts(
        self,
        intent_a: CanonicalIntent,
        intent_b: CanonicalIntent
    ) -> List[Conflict]:
        """
        Detect order/dependency conflicts.
        
        Conflict occurs when:
        - Intent B's evidence_refs reference Intent A's outputs
        - No explicit ordering declared
        
        Args:
            intent_a: First intent
            intent_b: Second intent
            
        Returns:
            List of order conflicts
        """
        conflicts = []
        
        # Check if B references A's artifacts
        b_evidence = intent_b.raw_data.get("evidence_refs", [])
        
        # Simple heuristic: if B's evidence mentions A's ID, there may be dependency
        a_id_mentioned = any(intent_a.intent_id in ref for ref in b_evidence)
        
        if a_id_mentioned:
            self.conflict_counter += 1
            conflict = Conflict(
                conflict_id=f"conflict_{self.conflict_counter:06d}",
                conflict_type="order_conflict",
                severity="medium",
                intent_ids=[intent_a.intent_id, intent_b.intent_id],
                description=f"{intent_b.intent_id} may depend on {intent_a.intent_id} outputs",
                evidence_refs=[
                    f"intent:{intent_b.intent_id}:evidence_refs"
                ]
            )
            conflicts.append(conflict)
        
        return conflicts
    
    def detect_constraint_conflicts(
        self,
        intent_a: CanonicalIntent,
        intent_b: CanonicalIntent
    ) -> List[Conflict]:
        """
        Detect constraint conflicts.
        
        Conflict occurs when:
        - Budget sum exceeds limits
        - Lock scopes incompatible
        - Interaction modes incompatible
        
        Args:
            intent_a: First intent
            intent_b: Second intent
            
        Returns:
            List of constraint conflicts
        """
        conflicts = []
        
        # Check interaction mode compatibility
        mode_a = intent_a.interaction_mode
        mode_b = intent_b.interaction_mode
        
        if mode_a == "full_auto" and mode_b != "full_auto":
            self.conflict_counter += 1
            conflict = Conflict(
                conflict_id=f"conflict_{self.conflict_counter:06d}",
                conflict_type="constraint_conflict",
                severity="low",
                intent_ids=[intent_a.intent_id, intent_b.intent_id],
                description="Incompatible interaction modes (full_auto vs interactive)",
                evidence_refs=[
                    f"intent:{intent_a.intent_id}:interaction",
                    f"intent:{intent_b.intent_id}:interaction"
                ]
            )
            conflicts.append(conflict)
        
        # Budget conflict detection
        budget_conflicts = self._detect_budget_conflicts(intent_a, intent_b)
        conflicts.extend(budget_conflicts)

        # Lock scope conflict detection
        lock_conflicts = self._detect_lock_scope_conflicts(intent_a, intent_b)
        conflicts.extend(lock_conflicts)

        return conflicts

    def _detect_budget_conflicts(
        self,
        intent_a: CanonicalIntent,
        intent_b: CanonicalIntent
    ) -> List[Conflict]:
        """
        Detect budget conflicts (cost/tokens exceeding limits).

        Conflict occurs when the sum of budgets exceeds reasonable limits
        or when both intents have high budget requirements.

        Args:
            intent_a: First intent
            intent_b: Second intent

        Returns:
            List of budget conflicts
        """
        conflicts = []

        budgets_a = intent_a.raw_data.get("budgets", {})
        budgets_b = intent_b.raw_data.get("budgets", {})

        # Check cost budget
        max_cost_a = budgets_a.get("max_cost_usd", 0)
        max_cost_b = budgets_b.get("max_cost_usd", 0)
        total_cost = max_cost_a + max_cost_b

        # Define reasonable limits for combined execution
        COST_LIMIT = 100.0  # $100 USD
        TOKEN_LIMIT = 1000000  # 1M tokens

        if total_cost > COST_LIMIT:
            self.conflict_counter += 1
            conflict = Conflict(
                conflict_id=f"conflict_{self.conflict_counter:06d}",
                conflict_type="constraint_conflict",
                severity="high",
                intent_ids=[intent_a.intent_id, intent_b.intent_id],
                description=f"Combined cost budget ${total_cost:.2f} exceeds limit ${COST_LIMIT}",
                evidence_refs=[
                    f"intent:{intent_a.intent_id}:budgets.max_cost_usd",
                    f"intent:{intent_b.intent_id}:budgets.max_cost_usd"
                ]
            )
            conflicts.append(conflict)

        # Check token budget
        max_tokens_a = budgets_a.get("max_tokens", 0)
        max_tokens_b = budgets_b.get("max_tokens", 0)
        total_tokens = max_tokens_a + max_tokens_b

        if total_tokens > TOKEN_LIMIT:
            self.conflict_counter += 1
            conflict = Conflict(
                conflict_id=f"conflict_{self.conflict_counter:06d}",
                conflict_type="constraint_conflict",
                severity="medium",
                intent_ids=[intent_a.intent_id, intent_b.intent_id],
                description=f"Combined token budget {total_tokens:,} exceeds limit {TOKEN_LIMIT:,}",
                evidence_refs=[
                    f"intent:{intent_a.intent_id}:budgets.max_tokens",
                    f"intent:{intent_b.intent_id}:budgets.max_tokens"
                ]
            )
            conflicts.append(conflict)

        return conflicts

    def _detect_lock_scope_conflicts(
        self,
        intent_a: CanonicalIntent,
        intent_b: CanonicalIntent
    ) -> List[Conflict]:
        """
        Detect lock scope conflicts (overlapping file locks).

        Conflict occurs when:
        - Both intents have lock_scope.mode = "files"
        - Lock paths overlap (exact match or glob pattern overlap)

        Args:
            intent_a: First intent
            intent_b: Second intent

        Returns:
            List of lock scope conflicts
        """
        conflicts = []

        constraints_a = intent_a.raw_data.get("constraints", {})
        constraints_b = intent_b.raw_data.get("constraints", {})

        lock_a = constraints_a.get("lock_scope", {})
        lock_b = constraints_b.get("lock_scope", {})

        mode_a = lock_a.get("mode", "none")
        mode_b = lock_b.get("mode", "none")

        # Only check if both have file locks
        if mode_a != "files" or mode_b != "files":
            return conflicts

        paths_a = set(lock_a.get("paths", []))
        paths_b = set(lock_b.get("paths", []))

        # Check for exact path overlap
        exact_overlap = paths_a & paths_b

        if exact_overlap:
            self.conflict_counter += 1
            conflict = Conflict(
                conflict_id=f"conflict_{self.conflict_counter:06d}",
                conflict_type="resource_conflict",
                severity="high",
                intent_ids=[intent_a.intent_id, intent_b.intent_id],
                description=f"Lock scope conflict: {len(exact_overlap)} overlapping paths",
                evidence_refs=[
                    f"intent:{intent_a.intent_id}:constraints.lock_scope",
                    f"intent:{intent_b.intent_id}:constraints.lock_scope"
                ]
            )
            conflicts.append(conflict)

        # Check for glob pattern overlap (e.g., /src/** vs /src/foo.py)
        glob_overlap = self._check_glob_overlap(paths_a, paths_b)

        if glob_overlap:
            self.conflict_counter += 1
            conflict = Conflict(
                conflict_id=f"conflict_{self.conflict_counter:06d}",
                conflict_type="resource_conflict",
                severity="medium",
                intent_ids=[intent_a.intent_id, intent_b.intent_id],
                description=f"Lock scope glob pattern overlap detected",
                evidence_refs=[
                    f"intent:{intent_a.intent_id}:constraints.lock_scope",
                    f"intent:{intent_b.intent_id}:constraints.lock_scope"
                ]
            )
            conflicts.append(conflict)

        return conflicts

    def _check_glob_overlap(self, paths_a: Set[str], paths_b: Set[str]) -> bool:
        """
        Check if glob patterns overlap.

        Simple heuristic:
        - If one path is a prefix of another, they overlap
        - If one path contains "**", check if it covers the other

        Args:
            paths_a: Set of paths from intent A
            paths_b: Set of paths from intent B

        Returns:
            True if overlap detected
        """
        import fnmatch

        for path_a in paths_a:
            for path_b in paths_b:
                # Check if path_a is a glob pattern matching path_b
                if "*" in path_a and fnmatch.fnmatch(path_b, path_a):
                    return True

                # Check if path_b is a glob pattern matching path_a
                if "*" in path_b and fnmatch.fnmatch(path_a, path_b):
                    return True

                # Check prefix overlap (e.g., /src vs /src/foo)
                if path_a.startswith(path_b.rstrip("/*")) or path_b.startswith(path_a.rstrip("/*")):
                    return True

        return False
