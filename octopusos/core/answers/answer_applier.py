"""
Apply AnswerPack to Intent/Pipeline to resolve BLOCKED state.

Merges answers into the intent and prepares the pipeline for resumption.
"""

from __future__ import annotations


import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from agentos.core.time import utc_now_iso



class AnswerApplier:
    """Apply AnswerPack to Intent and Pipeline context."""

    def apply_to_intent(
        self,
        intent: Dict[str, Any],
        answer_pack: Dict[str, Any],
        question_pack: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply AnswerPack to Intent, creating an enriched intent.

        Args:
            intent: The original ExecutionIntent
            answer_pack: The AnswerPack with user responses
            question_pack: The QuestionPack that was answered

        Returns:
            Enriched intent with answers merged

        Note:
            This creates a new intent with answers incorporated into context_hints
            or constraints, without modifying the core intent structure.
        """
        # Create a deep copy of intent
        enriched_intent = json.loads(json.dumps(intent))

        # Add answer metadata to lineage
        if "lineage" not in enriched_intent:
            enriched_intent["lineage"] = {}
        
        enriched_intent["lineage"]["answer_pack_applied"] = {
            "answer_pack_id": answer_pack.get("answer_pack_id"),
            "question_pack_id": answer_pack.get("question_pack_id"),
            "applied_at": utc_now_iso(),
            "answer_count": len(answer_pack.get("answers", []))
        }

        # Map question IDs to questions for easy lookup
        questions_by_id = {
            q.get("question_id"): q
            for q in question_pack.get("questions", [])
        }

        # Map answers by question ID
        answers_by_q_id = {
            a.get("question_id"): a
            for a in answer_pack.get("answers", [])
        }

        # Process each answer and integrate into intent
        resolved_clarifications = []
        for q_id, answer in answers_by_q_id.items():
            question = questions_by_id.get(q_id)
            if not question:
                continue

            resolved_clarifications.append({
                "question": question.get("question_text"),
                "answer": answer.get("answer_text"),
                "question_type": question.get("type"),
                "evidence": answer.get("evidence_refs", [])
            })

        # Add resolved clarifications to constraints
        if "constraints" not in enriched_intent:
            enriched_intent["constraints"] = []

        enriched_intent["constraints"].append({
            "type": "resolved_clarifications",
            "source": "answer_pack",
            "clarifications": resolved_clarifications
        })

        return enriched_intent

    def create_resume_context(
        self,
        pipeline_run_dir: Path,
        answer_pack: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a resume context for pipeline continuation.

        Args:
            pipeline_run_dir: Directory of the blocked pipeline run
            answer_pack: The AnswerPack to apply

        Returns:
            Resume context with metadata

        Raises:
            FileNotFoundError: If pipeline run dir or required files don't exist
        """
        if not pipeline_run_dir.exists():
            raise FileNotFoundError(f"Pipeline run directory not found: {pipeline_run_dir}")

        # Load intent
        intent_path = pipeline_run_dir / "01_intent" / "intent.json"
        if not intent_path.exists():
            raise FileNotFoundError(f"Intent not found: {intent_path}")

        with open(intent_path, "r", encoding="utf-8") as f:
            intent = json.load(f)

        # Load question pack
        qpack_path = pipeline_run_dir / "01_intent" / "question_pack.json"
        if not qpack_path.exists():
            raise FileNotFoundError(f"QuestionPack not found: {qpack_path}")

        with open(qpack_path, "r", encoding="utf-8") as f:
            question_pack = json.load(f)

        # Apply answers to intent
        enriched_intent = self.apply_to_intent(intent, answer_pack, question_pack)

        # Create resume context
        resume_context = {
            "resume_id": f"resume_{answer_pack.get('answer_pack_id', 'unknown')}",
            "original_run_dir": str(pipeline_run_dir),
            "resumed_at": utc_now_iso(),
            "enriched_intent": enriched_intent,
            "answer_pack_id": answer_pack.get("answer_pack_id"),
            "question_pack_id": answer_pack.get("question_pack_id"),
            "resume_from_step": self._determine_resume_step(pipeline_run_dir),
            "previous_status": "BLOCKED"
        }

        return resume_context

    def _determine_resume_step(self, pipeline_run_dir: Path) -> str:
        """
        Determine which step to resume from based on what completed.

        Args:
            pipeline_run_dir: Directory of the blocked pipeline run

        Returns:
            Step name to resume from
        """
        # Check which steps completed
        step1_complete = (pipeline_run_dir / "01_intent" / "intent.json").exists()
        step2_complete = (pipeline_run_dir / "02_coordinator").exists()
        step3_complete = (pipeline_run_dir / "03_dry_executor").exists()
        step4_complete = (pipeline_run_dir / "04_pr_artifacts").exists()

        if step4_complete:
            return "completed"  # Should not be BLOCKED if step4 complete
        elif step3_complete:
            return "step4_pr_artifacts"
        elif step2_complete:
            return "step3_dry_executor"
        elif step1_complete:
            return "step2_coordinator"
        else:
            return "step1_intent"

    def merge_into_pipeline_artifacts(
        self,
        pipeline_run_dir: Path,
        answer_pack: Dict[str, Any]
    ) -> Path:
        """
        Save answer pack into pipeline artifacts for audit trail.

        Args:
            pipeline_run_dir: Directory of the pipeline run
            answer_pack: The AnswerPack to save

        Returns:
            Path where answer pack was saved
        """
        artifacts_dir = pipeline_run_dir / "01_intent"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        output_path = artifacts_dir / "answer_pack_applied.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(answer_pack, f, indent=2, ensure_ascii=False)

        return output_path

    def update_audit_log(
        self,
        pipeline_run_dir: Path,
        answer_pack: Dict[str, Any],
        resume_context: Dict[str, Any]
    ):
        """
        Update pipeline audit log with answer pack application.

        Args:
            pipeline_run_dir: Directory of the pipeline run
            answer_pack: The applied AnswerPack
            resume_context: Resume context created
        """
        audit_log_path = pipeline_run_dir / "audit" / "pipeline_audit_log.jsonl"
        audit_log_path.parent.mkdir(parents=True, exist_ok=True)

        audit_event = {
            "event_type": "answer_pack_applied",
            "timestamp": utc_now_iso(),
            "answer_pack_id": answer_pack.get("answer_pack_id"),
            "question_pack_id": answer_pack.get("question_pack_id"),
            "answer_count": len(answer_pack.get("answers", [])),
            "resume_from_step": resume_context.get("resume_from_step"),
            "status": "ready_to_resume"
        }

        with open(audit_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_event, ensure_ascii=False) + "\n")

    def apply_and_prepare_resume(
        self,
        pipeline_run_dir: Path,
        answer_pack: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Full application: apply answers and prepare pipeline for resume.

        Args:
            pipeline_run_dir: Directory of the blocked pipeline run
            answer_pack: The AnswerPack to apply

        Returns:
            Resume context ready for pipeline continuation

        This is the main entry point that:
        1. Creates resume context
        2. Saves answer pack to artifacts
        3. Updates audit log
        4. Returns resume context for pipeline runner
        """
        # Create resume context
        resume_context = self.create_resume_context(pipeline_run_dir, answer_pack)

        # Save answer pack to pipeline artifacts
        self.merge_into_pipeline_artifacts(pipeline_run_dir, answer_pack)

        # Update audit log
        self.update_audit_log(pipeline_run_dir, answer_pack, resume_context)

        return resume_context


# Convenience function
def apply_answer_pack(
    pipeline_run_dir: Path | str,
    answer_pack: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply AnswerPack to a blocked pipeline run.

    Args:
        pipeline_run_dir: Directory of the blocked pipeline run
        answer_pack: The AnswerPack to apply

    Returns:
        Resume context for pipeline continuation
    """
    applier = AnswerApplier()
    return applier.apply_and_prepare_resume(Path(pipeline_run_dir), answer_pack)
