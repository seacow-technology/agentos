"""
Merge Planner — v0.9.3

Plans intent merges based on conflict analysis and risk comparison.
Produces merge operations and resulting merged intent.

RED LINE RL-E2: All merged intents must have complete lineage.
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from .intent_normalizer import CanonicalIntent
from .conflict_detector import Conflict


class MergeOperation:
    """Represents a single merge operation."""
    
    def __init__(
        self,
        op_id: str,
        operation: str,
        source_intent_id: str,
        target_field: str = "",
        value: Any = None,
        evidence: str = ""
    ):
        self.op_id = op_id
        self.operation = operation
        self.source_intent_id = source_intent_id
        self.target_field = target_field
        self.value = value
        self.evidence = evidence
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "op_id": self.op_id,
            "operation": self.operation,
            "source_intent_id": self.source_intent_id,
            "evidence": self.evidence
        }
        if self.target_field:
            result["target_field"] = self.target_field
        if self.value is not None:
            result["value"] = self.value
        return result


class MergePlan:
    """Complete plan for merging intents."""
    
    def __init__(self, strategy: str, source_intent_ids: List[str]):
        self.strategy = strategy
        self.source_intent_ids = source_intent_ids
        self.operations: List[MergeOperation] = []
        self.result_intent_id: Optional[str] = None
        self.result_intent: Optional[Dict[str, Any]] = None
    
    def add_operation(self, operation: MergeOperation):
        """Add an operation to the plan."""
        self.operations.append(operation)
    
    def set_result(self, intent_id: str, intent_data: Dict[str, Any]):
        """Set the resulting intent."""
        self.result_intent_id = intent_id
        self.result_intent = intent_data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "strategy": self.strategy,
            "operations": [op.to_dict() for op in self.operations],
            "result_intent_id": self.result_intent_id
        }


class MergePlanner:
    """Plans intent merges based on conflicts and priorities."""
    
    def __init__(self):
        self.op_counter = 0
    
    def plan_merge(
        self,
        conflicts: List[Conflict],
        canonical_intents: Dict[str, CanonicalIntent],
        hints: Dict[str, Any] = None
    ) -> MergePlan:
        """
        Plan merge strategy and operations.
        
        Args:
            conflicts: Detected conflicts
            canonical_intents: Normalized intents
            hints: Optional hints (e.g., explicit priorities)
            
        Returns:
            Merge plan with strategy and operations
        """
        hints = hints or {}
        
        # Determine strategy
        strategy = self._determine_strategy(conflicts, canonical_intents, hints)
        
        source_ids = list(canonical_intents.keys())
        plan = MergePlan(strategy, source_ids)
        
        if strategy == "merge_union":
            self._plan_union_merge(plan, canonical_intents)
        elif strategy == "override_by_priority":
            self._plan_override_merge(plan, conflicts, canonical_intents)
        elif strategy == "reject":
            # No operations, just return reject plan
            pass
        
        return plan
    
    def _determine_strategy(
        self,
        conflicts: List[Conflict],
        canonical_intents: Dict[str, CanonicalIntent],
        hints: Dict[str, Any]
    ) -> str:
        """
        Determine merge strategy based on conflicts and priorities.
        
        Logic:
        - No conflicts or only low-severity → merge_union
        - Conflicts + clear priority → override_by_priority
        - Conflicts + no clear priority → reject
        """
        if not conflicts:
            return "merge_union"
        
        # Check for high-severity conflicts
        high_severity = any(c.severity in ["high", "critical"] for c in conflicts)
        
        if not high_severity:
            # Low/medium conflicts, try merge
            return "merge_union"
        
        # High severity, check priority clarity
        priorities = {
            intent_id: intent.priority
            for intent_id, intent in canonical_intents.items()
        }
        
        # If all priorities are distinct, we can override
        unique_priorities = len(set(priorities.values()))
        if unique_priorities == len(priorities):
            return "override_by_priority"
        
        # Priorities not clear, reject
        return "reject"
    
    def _plan_union_merge(
        self,
        plan: MergePlan,
        canonical_intents: Dict[str, CanonicalIntent]
    ):
        """
        Plan union merge operations.
        
        Operations:
        - Union all planned_commands
        - Union all selected_workflows
        - Union all selected_agents
        - Union all evidence_refs
        - Aggregate budgets
        - Aggregate risk
        """
        intent_list = list(canonical_intents.values())
        
        # Union commands
        for intent in intent_list:
            self.op_counter += 1
            op = MergeOperation(
                op_id=f"op_{self.op_counter:03d}",
                operation="union_commands",
                source_intent_id=intent.intent_id,
                target_field="planned_commands",
                evidence=f"Merging commands from {intent.intent_id}"
            )
            plan.add_operation(op)
        
        # Union workflows
        for intent in intent_list:
            self.op_counter += 1
            op = MergeOperation(
                op_id=f"op_{self.op_counter:03d}",
                operation="union_workflows",
                source_intent_id=intent.intent_id,
                target_field="selected_workflows",
                evidence=f"Merging workflows from {intent.intent_id}"
            )
            plan.add_operation(op)
        
        # Union agents
        for intent in intent_list:
            self.op_counter += 1
            op = MergeOperation(
                op_id=f"op_{self.op_counter:03d}",
                operation="union_agents",
                source_intent_id=intent.intent_id,
                target_field="selected_agents",
                evidence=f"Merging agents from {intent.intent_id}"
            )
            plan.add_operation(op)
        
        # Build result intent
        result = self.build_result_intent(plan, canonical_intents)
        plan.set_result(result["id"], result)
    
    def _plan_override_merge(
        self,
        plan: MergePlan,
        conflicts: List[Conflict],
        canonical_intents: Dict[str, CanonicalIntent]
    ):
        """
        Plan override merge (highest priority wins).
        
        Operations:
        - Keep all fields from highest priority intent
        - Mark lower priority intents as superseded
        """
        # Find highest priority intent
        priorities = {
            intent_id: intent.priority
            for intent_id, intent in canonical_intents.items()
        }
        
        winner_id = max(priorities, key=priorities.get)
        losers = [iid for iid in priorities if iid != winner_id]
        
        # Keep winner's fields
        self.op_counter += 1
        op = MergeOperation(
            op_id=f"op_{self.op_counter:03d}",
            operation="keep_field",
            source_intent_id=winner_id,
            target_field="*",
            evidence=f"Keeping all fields from highest priority intent {winner_id}"
        )
        plan.add_operation(op)
        
        # Build result (same as winner, but with lineage)
        winner_intent = canonical_intents[winner_id]
        result = winner_intent.raw_data.copy()
        
        # RL-E2: Update lineage
        result["lineage"]["derived_from"] = [winner_id]
        result["lineage"]["supersedes"] = losers
        
        plan.set_result(winner_id, result)
    
    def build_result_intent(
        self,
        plan: MergePlan,
        canonical_intents: Dict[str, CanonicalIntent]
    ) -> Dict[str, Any]:
        """
        Build resulting merged intent.
        
        RL-E2: Must have complete lineage (derived_from, supersedes).
        
        Args:
            plan: Merge plan
            canonical_intents: Source intents
            
        Returns:
            Merged intent conforming to intent.schema.json
        """
        intent_list = list(canonical_intents.values())
        
        if not intent_list:
            raise ValueError("Cannot build result intent from empty intent list")
        
        # Use first intent as base
        base = intent_list[0].raw_data.copy()
        
        # Generate new ID for merged intent
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        merged_id = f"intent_merged_{timestamp}"
        
        base["id"] = merged_id
        base["title"] = f"Merged: {base.get('title', 'Untitled')}"
        base["status"] = "draft"
        base["version"] = "0.9.3"
        base["created_at"] = datetime.now().isoformat()
        
        # RL-E2: Update lineage (REQUIRED)
        base["lineage"] = {
            "introduced_in": "0.9.3",
            "derived_from": plan.source_intent_ids,  # MUST be populated
            "supersedes": []  # Empty for merge_union, populated for override
        }
        
        # Merge commands
        all_commands = []
        for intent in intent_list:
            all_commands.extend(intent.raw_data.get("planned_commands", []))
        base["planned_commands"] = all_commands
        
        # Merge workflows (deduplicate)
        all_workflows = []
        seen_workflows = set()
        for intent in intent_list:
            for wf in intent.raw_data.get("selected_workflows", []):
                wf_id = wf.get("workflow_id")
                if wf_id not in seen_workflows:
                    all_workflows.append(wf)
                    seen_workflows.add(wf_id)
        base["selected_workflows"] = all_workflows
        
        # Merge agents (deduplicate)
        all_agents = []
        seen_agents = set()
        for intent in intent_list:
            for agent in intent.raw_data.get("selected_agents", []):
                agent_id = agent.get("agent_id")
                if agent_id not in seen_agents:
                    all_agents.append(agent)
                    seen_agents.add(agent_id)
        base["selected_agents"] = all_agents
        
        # Union evidence_refs
        all_evidence = []
        for intent in intent_list:
            all_evidence.extend(intent.raw_data.get("evidence_refs", []))
        base["evidence_refs"] = list(set(all_evidence))  # Deduplicate
        
        # Aggregate risk (take highest)
        risk_levels = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        max_risk = "low"
        for intent in intent_list:
            risk = intent.raw_data.get("risk", {}).get("overall", "low")
            if risk_levels.get(risk, 0) > risk_levels.get(max_risk, 0):
                max_risk = risk
        base["risk"]["overall"] = max_risk
        
        return base
    
    def generate_operations(
        self,
        strategy: str,
        intents: Dict[str, Dict[str, Any]]
    ) -> List[MergeOperation]:
        """
        Generate ordered operations for a given strategy.
        
        Args:
            strategy: Merge strategy
            intents: Raw intent data
            
        Returns:
            List of operations
        """
        # Convert to canonical
        from .intent_normalizer import IntentNormalizer
        normalizer = IntentNormalizer()
        canonical = normalizer.normalize_batch(intents)
        
        # Create plan
        plan = MergePlan(strategy, list(intents.keys()))
        
        if strategy == "merge_union":
            self._plan_union_merge(plan, canonical)
        elif strategy == "override_by_priority":
            conflicts = []  # Simplified, no conflicts passed
            self._plan_override_merge(plan, conflicts, canonical)
        
        return plan.operations
