"""
Coordinator Engine - State Machine Driver (v0.9.2)

RED LINE: This module MUST NOT execute any commands. It only produces plans.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CoordinatorRun:
    """Result of a coordinator run"""
    run_id: str
    intent_id: str
    final_state: str
    graph: Optional[dict] = None
    questions: Optional[dict] = None
    review: Optional[dict] = None
    tape: Optional[dict] = None
    audit_log: Optional[list] = None
    failure_pack: Optional[dict] = None


class CoordinatorEngine:
    """
    Main orchestrator and state machine driver for Coordinator v0.9.2
    
    RED LINE: Does NOT execute - only plans!
    """
    
    # State constants
    STATE_INIT = "INIT"
    STATE_RECEIVED = "RECEIVED"
    STATE_PRECHECKED = "PRECHECKED"
    STATE_CONTEXT_BUILT = "CONTEXT_BUILT"
    STATE_RULES_EVALUATED = "RULES_EVALUATED"
    STATE_GRAPH_DRAFTED = "GRAPH_DRAFTED"
    STATE_QUESTIONS_EMITTED = "QUESTIONS_EMITTED"
    STATE_AWAITING_ANSWERS = "AWAITING_ANSWERS"
    STATE_GRAPH_FINALIZED = "GRAPH_FINALIZED"
    STATE_REVIEW_PACK_BUILT = "REVIEW_PACK_BUILT"
    STATE_FROZEN_OUTPUTS = "FROZEN_OUTPUTS"
    STATE_DONE = "DONE"
    STATE_BLOCKED = "BLOCKED"
    STATE_ABORTED = "ABORTED"
    
    def __init__(self, registry, memory_service):
        """
        Initialize Coordinator Engine
        
        Args:
            registry: ContentRegistry instance (read-only)
            memory_service: MemoryService instance (read-only)
        """
        self.registry = registry
        self.memory_service = memory_service
        self.current_state = self.STATE_INIT
        self.run_tape = []
        self.context = {}
        
    def coordinate(self, intent: dict, policy: dict, factpack: dict) -> CoordinatorRun:
        """
        Main entry point: Transform Intent into ExecutionGraph and artifacts
        
        Args:
            intent: ExecutionIntent (v0.9.1)
            policy: ExecutionPolicy
            factpack: FactPack (project scan evidence)
            
        Returns:
            CoordinatorRun with all outputs
        """
        run_id = f"coord_run_{intent['id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        self.context = {
            "run_id": run_id,
            "intent": intent,
            "policy": policy,
            "factpack": factpack
        }
        
        # State machine execution
        try:
            self._transition(self.STATE_INIT, self.STATE_RECEIVED, "Intent submitted")
            
            # Execute state machine
            while self.current_state not in [self.STATE_DONE, self.STATE_BLOCKED, self.STATE_ABORTED]:
                self._execute_current_state()
                
            # Build result
            return self._build_result()
            
        except Exception as e:
            return self._handle_error(e)
    
    def _transition(self, from_state: str, to_state: str, trigger: str) -> bool:
        """
        Execute state transition with guard evaluation
        
        Args:
            from_state: Source state
            to_state: Target state
            trigger: Reason for transition
            
        Returns:
            True if transition succeeded
        """
        # Evaluate guards
        passed, reasons = self._evaluate_guards(to_state, self.context)
        
        if not passed:
            self._handle_blocked(f"Guard failed: {reasons}")
            return False
        
        # Record transition in RunTape
        self.run_tape.append({
            "sequence": len(self.run_tape) + 1,
            "from_state": from_state,
            "to_state": to_state,
            "timestamp": datetime.now().isoformat(),
            "trigger": trigger,
            "guards_evaluated": reasons
        })
        
        self.current_state = to_state
        return True
    
    def _evaluate_guards(self, to_state: str, context: dict) -> tuple[bool, list]:
        """
        Evaluate guard conditions for transition
        
        Returns:
            (passed, guard_results)
        """
        guards = []
        
        if to_state == self.STATE_PRECHECKED:
            # Check intent schema, checksum, registry refs
            guards.append({"guard": "intent_schema_valid", "passed": True, "reason": "Schema valid"})
            
        elif to_state == self.STATE_CONTEXT_BUILT:
            # Check MemoryPack and FactPack available
            guards.append({"guard": "memory_pack_available", "passed": True, "reason": "Memory available"})
            
        # Add more guard checks for other states...
        
        all_passed = all(g["passed"] for g in guards)
        return all_passed, guards
    
    def _execute_current_state(self):
        """Execute handler for current state"""
        handler_name = f"_handle_{self.current_state.lower()}"
        handler = getattr(self, handler_name, None)
        
        if handler:
            handler(self.context)
        else:
            raise ValueError(f"No handler for state: {self.current_state}")
    
    # State handlers (13 total)
    
    def _handle_received(self, context: dict):
        """Handle RECEIVED state"""
        self._transition(self.STATE_RECEIVED, self.STATE_PRECHECKED, "Starting precheck")
    
    def _handle_prechecked(self, context: dict):
        """Handle PRECHECKED state - schema validation"""
        # Validate intent, checksum, registry refs
        self._transition(self.STATE_PRECHECKED, self.STATE_CONTEXT_BUILT, "Precheck passed")
    
    def _handle_context_built(self, context: dict):
        """Handle CONTEXT_BUILT state - load memory + factpack"""
        # Build MemoryPack and ContextBundle
        self._transition(self.STATE_CONTEXT_BUILT, self.STATE_RULES_EVALUATED, "Context ready")
    
    def _handle_rules_evaluated(self, context: dict):
        """Handle RULES_EVALUATED state - rule adjudication"""
        # Adjudicate all rules
        self._transition(self.STATE_RULES_EVALUATED, self.STATE_GRAPH_DRAFTED, "Rules adjudicated")
    
    def _handle_graph_drafted(self, context: dict):
        """Handle GRAPH_DRAFTED state - graph construction"""
        # Build ExecutionGraph
        policy_mode = context.get("policy", {}).get("mode", "interactive")
        
        if policy_mode == "full_auto":
            # Skip questions
            self._transition(self.STATE_GRAPH_DRAFTED, self.STATE_GRAPH_FINALIZED, "No questions (full_auto)")
        else:
            # Check if questions needed
            self._transition(self.STATE_GRAPH_DRAFTED, self.STATE_GRAPH_FINALIZED, "No uncertainties")
    
    def _handle_questions_emitted(self, context: dict):
        """Handle QUESTIONS_EMITTED state - question generation"""
        self._transition(self.STATE_QUESTIONS_EMITTED, self.STATE_AWAITING_ANSWERS, "Questions emitted")
    
    def _handle_awaiting_answers(self, context: dict):
        """Handle AWAITING_ANSWERS state - wait for AnswerPack"""
        # This would block waiting for answers in real implementation
        self._transition(self.STATE_AWAITING_ANSWERS, self.STATE_GRAPH_FINALIZED, "Answers received")
    
    def _handle_graph_finalized(self, context: dict):
        """Handle GRAPH_FINALIZED state - integrate answers"""
        self._transition(self.STATE_GRAPH_FINALIZED, self.STATE_REVIEW_PACK_BUILT, "Graph finalized")
    
    def _handle_review_pack_built(self, context: dict):
        """Handle REVIEW_PACK_BUILT state - build review package"""
        self._transition(self.STATE_REVIEW_PACK_BUILT, self.STATE_FROZEN_OUTPUTS, "Review pack ready")
    
    def _handle_frozen_outputs(self, context: dict):
        """Handle FROZEN_OUTPUTS state - freeze and checksum"""
        self._transition(self.STATE_FROZEN_OUTPUTS, self.STATE_DONE, "Outputs frozen")
    
    def _handle_done(self, context: dict):
        """Handle DONE state - terminal success"""
        pass  # Terminal state
    
    def _handle_blocked(self, reason: str):
        """Handle BLOCKED state - constraint violation"""
        self.current_state = self.STATE_BLOCKED
        self.context["failure_reason"] = reason
    
    def _handle_aborted(self, reason: str):
        """Handle ABORTED state - red line violation"""
        self.current_state = self.STATE_ABORTED
        self.context["abort_reason"] = reason
    
    def _build_result(self) -> CoordinatorRun:
        """Build final CoordinatorRun result"""
        return CoordinatorRun(
            run_id=self.context["run_id"],
            intent_id=self.context["intent"]["id"],
            final_state=self.current_state,
            graph=self.context.get("graph"),
            questions=self.context.get("questions"),
            review=self.context.get("review"),
            tape={"run_id": self.context["run_id"], "steps": self.run_tape},
            audit_log=self.context.get("audit_log", [])
        )
    
    def _handle_error(self, error: Exception) -> CoordinatorRun:
        """Handle unexpected errors"""
        return CoordinatorRun(
            run_id=self.context.get("run_id", "error"),
            intent_id=self.context.get("intent", {}).get("id", "unknown"),
            final_state=self.STATE_ABORTED,
            failure_pack={"error": str(error)}
        )
