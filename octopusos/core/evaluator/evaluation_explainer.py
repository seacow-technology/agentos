"""
Evaluation Explainer — v0.9.3

Generates stable, human-readable explanations of evaluation results.
Used by Gate F for snapshot testing.
"""

from typing import Dict, List, Any
import json


class EvaluationExplainer:
    """Generates explanations of evaluation results."""
    
    def explain(self, evaluation_result: Dict[str, Any]) -> str:
        """
        Generate human-readable explanation of evaluation result.
        
        Output format (stable for Gate F):
        ======================================================================
        INTENT EVALUATION RESULT
        ======================================================================
        
        ID: <result_id>
        Created: <timestamp>
        
        INPUT
        ======================================================================
        Intent Set: <intent_set_id>
        Evaluated Intents: <count>
        - intent_a
        - intent_b
        
        CONFLICTS
        ======================================================================
        Total Conflicts: <count>
        
        [For each conflict]
        Conflict <id>
          Type: <type>
          Severity: <severity>
          Intents: <intent_ids>
          Resource: <resource_ref>
          Description: <description>
        
        RISK COMPARISON
        ======================================================================
        Risk Matrix:
        - intent_a: overall=<risk>, effects=<score>, scope=<score>, blast=<score>, unknowns=<score>
        - intent_b: ...
        
        Dominance:
        - <intent_a> dominates <intent_b>
        
        MERGE PLAN
        ======================================================================
        Strategy: <strategy>
        Operations: <count>
        
        [For each operation]
        Op <id>: <operation> from <source_intent_id>
          Target: <target_field>
          Evidence: <evidence>
        
        Result Intent: <result_intent_id>
        
        QUESTIONS
        ======================================================================
        [If any]
        Question <id>: <reason>
        Options:
        - <option_label>
        
        LINEAGE
        ======================================================================
        Derived from Intent Set: <intent_set_id>
        Evaluator Version: <version>
        Checksum: <checksum>
        
        ======================================================================
        
        Args:
            evaluation_result: Evaluation result dict or EvaluationResult object
            
        Returns:
            Formatted explanation string
        """
        if hasattr(evaluation_result, 'to_dict'):
            data = evaluation_result.to_dict()
        else:
            data = evaluation_result
        
        lines = []
        lines.append("=" * 70)
        lines.append("INTENT EVALUATION RESULT")
        lines.append("=" * 70)
        lines.append("")
        
        lines.append(f"ID: {data.get('id', 'unknown')}")
        lines.append(f"Created: {data.get('created_at', 'unknown')}")
        lines.append("")
        
        # INPUT
        lines.append("INPUT")
        lines.append("=" * 70)
        input_data = data.get("input", {})
        lines.append(f"Intent Set: {input_data.get('intent_set_id', 'unknown')}")
        
        checksums = input_data.get("intent_checksums", {})
        lines.append(f"Evaluated Intents: {len(checksums)}")
        for intent_id in sorted(checksums.keys()):
            lines.append(f"  - {intent_id}")
        lines.append("")
        
        # CONFLICTS
        lines.append("CONFLICTS")
        lines.append("=" * 70)
        conflicts = data.get("evaluation", {}).get("conflicts", [])
        lines.append(f"Total Conflicts: {len(conflicts)}")
        lines.append("")
        
        for conflict in conflicts:
            lines.append(f"Conflict {conflict.get('conflict_id', 'unknown')}")
            lines.append(f"  Type: {conflict.get('type', 'unknown')}")
            lines.append(f"  Severity: {conflict.get('severity', 'unknown')}")
            lines.append(f"  Intents: {', '.join(conflict.get('intent_ids', []))}")
            if conflict.get('resource_ref'):
                lines.append(f"  Resource: {conflict['resource_ref']}")
            lines.append(f"  Description: {conflict.get('description', 'N/A')}")
            lines.append("")
        
        # RISK COMPARISON
        lines.append("RISK COMPARISON")
        lines.append("=" * 70)
        risk_comp = data.get("evaluation", {}).get("risk_comparison", {})
        matrix = risk_comp.get("matrix", [])
        
        lines.append("Risk Matrix:")
        for entry in matrix:
            intent_id = entry.get("intent_id", "unknown")
            overall = entry.get("overall_risk", "unknown")
            dims = entry.get("dimensions", {})
            
            effects = dims.get("effects_risk", 0)
            scope = dims.get("scope_risk", 0)
            blast = dims.get("blast_radius", 0)
            unknowns = dims.get("unknowns", 0)
            
            lines.append(f"  - {intent_id}: overall={overall}, effects={effects:.1f}, scope={scope:.1f}, blast={blast:.1f}, unknowns={unknowns:.1f}")
        lines.append("")
        
        dominance = risk_comp.get("dominance", [])
        if dominance:
            lines.append("Dominance:")
            for rel in dominance:
                lines.append(f"  - {rel.get('intent_a')} {rel.get('relationship')} {rel.get('intent_b')}")
            lines.append("")
        
        # MERGE PLAN
        lines.append("MERGE PLAN")
        lines.append("=" * 70)
        merge_plan = data.get("evaluation", {}).get("merge_plan", {})
        lines.append(f"Strategy: {merge_plan.get('strategy', 'unknown')}")
        
        operations = merge_plan.get("operations", [])
        lines.append(f"Operations: {len(operations)}")
        lines.append("")
        
        for op in operations:
            lines.append(f"Op {op.get('op_id', 'unknown')}: {op.get('operation', 'unknown')} from {op.get('source_intent_id', 'unknown')}")
            if op.get('target_field'):
                lines.append(f"  Target: {op['target_field']}")
            lines.append(f"  Evidence: {op.get('evidence', 'N/A')}")
            lines.append("")
        
        result_intent_id = merge_plan.get("result_intent_id")
        if result_intent_id:
            lines.append(f"Result Intent: {result_intent_id}")
        lines.append("")
        
        # QUESTIONS
        questions = data.get("requires_questions", [])
        if questions:
            lines.append("QUESTIONS")
            lines.append("=" * 70)
            for q in questions:
                lines.append(f"Question {q.get('question_id', 'unknown')}: {q.get('reason', 'N/A')}")
                lines.append("Options:")
                for opt in q.get("options", []):
                    lines.append(f"  - {opt.get('label', 'N/A')}")
                lines.append("")
        
        # LINEAGE
        lines.append("LINEAGE")
        lines.append("=" * 70)
        lineage = data.get("lineage", {})
        lines.append(f"Derived from Intent Set: {lineage.get('derived_from_intent_set', 'unknown')}")
        lines.append(f"Evaluator Version: {lineage.get('evaluator_version', 'unknown')}")
        lines.append(f"Checksum: {data.get('checksum', 'none')}")
        lines.append("")
        
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def explain_compact(self, evaluation_result: Dict[str, Any]) -> str:
        """
        Generate compact explanation (for CLI output).
        
        Args:
            evaluation_result: Evaluation result
            
        Returns:
            Compact explanation
        """
        if hasattr(evaluation_result, 'to_dict'):
            data = evaluation_result.to_dict()
        else:
            data = evaluation_result
        
        lines = []
        lines.append(f"📋 Evaluation Result: {data.get('id', 'unknown')}")
        
        conflicts = data.get("evaluation", {}).get("conflicts", [])
        lines.append(f"   Conflicts: {len(conflicts)}")
        
        strategy = data.get("evaluation", {}).get("merge_plan", {}).get("strategy", "unknown")
        lines.append(f"   Strategy: {strategy}")
        
        questions = data.get("requires_questions", [])
        if questions:
            lines.append(f"   ❓ Requires {len(questions)} question(s)")
        
        return "\n".join(lines)
