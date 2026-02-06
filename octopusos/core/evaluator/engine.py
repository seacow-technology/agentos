"""
Evaluator Engine — v0.9.3

Main engine that orchestrates the evaluation of multiple intents.

Workflow:
1. Load & normalize intents
2. Detect conflicts
3. Compare risks
4. Plan merge
5. Freeze output (checksum + lineage)
"""

import json
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from .intent_set_loader import IntentSetLoader
from .intent_normalizer import IntentNormalizer
from .conflict_detector import ConflictDetector
from .risk_comparator import RiskComparator
from .merge_planner import MergePlanner


class EvaluationResult:
    """Complete evaluation result."""
    
    def __init__(self, result_id: str, intent_set_id: str):
        self.id = result_id
        self.type = "intent_evaluation_result"
        self.schema_version = "0.9.3"
        self.created_at = datetime.now().isoformat()
        
        self.input = {
            "intent_set_id": intent_set_id,
            "intent_checksums": {}
        }
        
        self.evaluation = {
            "conflicts": [],
            "merge_plan": {},
            "risk_comparison": {}
        }
        
        self.requires_questions = []
        
        # RL-E1: Execution forbidden
        self.constraints = {
            "execution": "forbidden"
        }
        
        self.lineage = {
            "derived_from_intent_set": intent_set_id,
            "evaluator_version": "0.9.3"
        }
        
        self.checksum = ""
    
    def set_conflicts(self, conflicts: List[Any]):
        """Set detected conflicts."""
        self.evaluation["conflicts"] = [
            c.to_dict() if hasattr(c, 'to_dict') else c
            for c in conflicts
        ]
    
    def set_merge_plan(self, merge_plan: Any):
        """Set merge plan."""
        if hasattr(merge_plan, 'to_dict'):
            self.evaluation["merge_plan"] = merge_plan.to_dict()
        else:
            self.evaluation["merge_plan"] = merge_plan
    
    def set_risk_comparison(self, risk_comparison: Any):
        """Set risk comparison."""
        if hasattr(risk_comparison, 'to_dict'):
            self.evaluation["risk_comparison"] = risk_comparison.to_dict()
        else:
            self.evaluation["risk_comparison"] = risk_comparison
    
    def add_question(self, question: Dict[str, Any]):
        """Add a question requiring user input."""
        self.requires_questions.append(question)
    
    def freeze(self):
        """
        Freeze the result by computing checksum.
        
        Checksum is SHA-256 of:
        - input
        - evaluation
        - lineage
        """
        checksum_data = {
            "input": self.input,
            "evaluation": self.evaluation,
            "lineage": self.lineage
        }
        
        self.checksum = hashlib.sha256(
            json.dumps(checksum_data, sort_keys=True).encode()
        ).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "type": self.type,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "input": self.input,
            "evaluation": self.evaluation,
            "requires_questions": self.requires_questions,
            "constraints": self.constraints,
            "lineage": self.lineage,
            "checksum": self.checksum
        }


class EvaluatorEngine:
    """Main evaluator engine."""
    
    def __init__(self, intents_base_path: str = "examples/intents"):
        """
        Initialize evaluator engine.
        
        Args:
            intents_base_path: Base path for intent files
        """
        self.loader = IntentSetLoader(intents_base_path)
        self.normalizer = IntentNormalizer()
        self.conflict_detector = ConflictDetector()
        self.risk_comparator = RiskComparator()
        self.merge_planner = MergePlanner()
    
    def evaluate(
        self,
        intent_set_path: str,
        policy: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """
        Evaluate an intent set.
        
        Args:
            intent_set_path: Path to intent_set.json
            policy: Optional evaluation policy
            
        Returns:
            Complete evaluation result
            
        Raises:
            FileNotFoundError: If intent set not found
            ValueError: If validation fails
        """
        policy = policy or {}
        
        # Step 1: Load & normalize
        print("📂 Loading intent set...")
        loaded = self.loader.load(intent_set_path)
        intent_set = loaded["intent_set"]
        intents = loaded["intents"]
        
        print(f"✅ Loaded {len(intents)} intents")
        
        canonical_intents = self.normalizer.normalize_batch(intents)
        print(f"✅ Normalized {len(canonical_intents)} intents")
        
        # Create result
        result_id = f"eval_result_{intent_set['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result = EvaluationResult(result_id, intent_set["id"])
        
        # Store intent checksums
        for intent_id, intent_data in intents.items():
            checksum = intent_data.get("audit", {}).get("checksum", "")
            result.input["intent_checksums"][intent_id] = checksum
        
        # Step 2: Detect conflicts
        print("🔍 Detecting conflicts...")
        conflicts = self.conflict_detector.detect_all(canonical_intents)
        result.set_conflicts(conflicts)
        print(f"✅ Detected {len(conflicts)} conflicts")
        
        # Step 3: Compare risks
        print("📊 Comparing risks...")
        risk_matrix = self.risk_comparator.build_risk_matrix(canonical_intents)
        result.set_risk_comparison(risk_matrix)
        print(f"✅ Built risk matrix with {len(risk_matrix.entries)} entries")
        
        # Step 4: Plan merge
        print("🔀 Planning merge...")
        merge_plan = self.merge_planner.plan_merge(
            conflicts,
            canonical_intents,
            hints=policy.get("merge_hints", {})
        )
        result.set_merge_plan(merge_plan)
        print(f"✅ Merge strategy: {merge_plan.strategy}")
        
        # Check if questions needed
        if merge_plan.strategy == "reject":
            # Generate question for user
            question = self._generate_conflict_question(conflicts, canonical_intents)
            result.add_question(question)
            print("❓ Requires user input (reject strategy)")
        
        # Step 5: Freeze output
        print("🔒 Freezing result...")
        result.freeze()
        print(f"✅ Checksum: {result.checksum[:16]}...")
        
        return result
    
    def _generate_conflict_question(
        self,
        conflicts: List[Any],
        canonical_intents: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate question for user when merge is rejected.
        
        Args:
            conflicts: Detected conflicts
            canonical_intents: Normalized intents
            
        Returns:
            Question dict
        """
        intent_ids = list(canonical_intents.keys())
        
        return {
            "question_id": "question_001",
            "condition": "merge_rejected_due_to_conflicts",
            "reason": f"Found {len(conflicts)} conflicts with no clear priority. Manual resolution required.",
            "options": [
                {
                    "option_id": f"option_{i+1}",
                    "label": f"Use intent {intent_id}",
                    "implications": f"Will supersede other intents"
                }
                for i, intent_id in enumerate(intent_ids)
            ] + [
                {
                    "option_id": "option_manual",
                    "label": "Manual merge",
                    "implications": "Requires human review and custom merge"
                }
            ]
        }
    
    def evaluate_from_ids(
        self,
        intent_ids: List[str],
        project_id: str,
        env: str = "local"
    ) -> EvaluationResult:
        """
        Evaluate intents directly from IDs (convenience method).
        
        Args:
            intent_ids: List of intent IDs
            project_id: Project identifier
            env: Environment context
            
        Returns:
            Evaluation result
        """
        # Create temporary intent set
        import tempfile
        
        intent_set = {
            "id": f"intent_set_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "type": "intent_set",
            "schema_version": "0.9.3",
            "created_at": datetime.now().isoformat(),
            "intent_ids": intent_ids,
            "context": {
                "project_id": project_id,
                "env": env
            },
            "lineage": {
                "introduced_in": "0.9.3",
                "derived_from": []
            },
            "checksum": hashlib.sha256(
                json.dumps({"intent_ids": intent_ids}, sort_keys=True).encode()
            ).hexdigest()
        }
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(intent_set, f, indent=2)
            temp_path = f.name
        
        try:
            result = self.evaluate(temp_path)
        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)
        
        return result
