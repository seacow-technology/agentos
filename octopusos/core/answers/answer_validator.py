"""
Answer Pack validation against schemas and red lines.

Validates AnswerPacks to ensure they meet all requirements:
- AP1: Only answer questions in the QuestionPack
- AP2: All answers must have evidence_refs
- AP3: Cannot modify command/workflow/agent definitions
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import jsonschema


class AnswerValidator:
    """Validate AnswerPacks against schemas and red lines."""

    def __init__(self, schema_dir: Path = None):
        """
        Initialize validator.

        Args:
            schema_dir: Directory containing JSON schemas.
                       Defaults to agentos/schemas/execution/
        """
        if schema_dir is None:
            # Default to AgentOS schemas directory
            schema_dir = Path(__file__).parent.parent.parent / "schemas" / "execution"
        
        self.schema_dir = schema_dir
        self._answer_pack_schema = None
        self._question_pack_schema = None

    def _load_schema(self, schema_name: str) -> Dict[str, Any]:
        """Load a JSON schema from disk."""
        schema_path = self.schema_dir / schema_name
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema not found: {schema_path}")
        
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @property
    def answer_pack_schema(self) -> Dict[str, Any]:
        """Get AnswerPack schema (lazy load)."""
        if self._answer_pack_schema is None:
            self._answer_pack_schema = self._load_schema("answer_pack.schema.json")
        return self._answer_pack_schema

    def validate_schema(self, answer_pack: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate AnswerPack against JSON schema.

        Args:
            answer_pack: The answer pack to validate

        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        try:
            jsonschema.validate(answer_pack, self.answer_pack_schema)
            return (True, [])
        except jsonschema.ValidationError as e:
            errors.append(f"Schema validation failed: {e.message}")
            if e.path:
                errors.append(f"  Path: {'.'.join(str(p) for p in e.path)}")
            return (False, errors)
        except jsonschema.SchemaError as e:
            errors.append(f"Schema itself is invalid: {e.message}")
            return (False, errors)

    def validate_against_question_pack(
        self,
        answer_pack: Dict[str, Any],
        question_pack: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate AnswerPack against QuestionPack (RED LINE AP1).

        Ensures:
        - question_pack_id matches
        - All answered question_ids exist in QuestionPack
        - No fabricated questions

        Args:
            answer_pack: The answer pack to validate
            question_pack: The question pack it should answer

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # Check question_pack_id match
        ap_qpack_id = answer_pack.get("question_pack_id")
        qp_pack_id = question_pack.get("pack_id")

        if ap_qpack_id != qp_pack_id:
            errors.append(
                f"RED LINE AP1 VIOLATION: question_pack_id mismatch. "
                f"AnswerPack references '{ap_qpack_id}' but QuestionPack is '{qp_pack_id}'"
            )

        # Build set of valid question IDs from QuestionPack
        valid_question_ids = {
            q.get("question_id")
            for q in question_pack.get("questions", [])
            if q.get("question_id")
        }

        # Check all answers reference valid questions
        for i, answer in enumerate(answer_pack.get("answers", [])):
            q_id = answer.get("question_id")
            if q_id not in valid_question_ids:
                errors.append(
                    f"RED LINE AP1 VIOLATION: Answer #{i+1} references unknown question '{q_id}'. "
                    f"Valid question IDs: {sorted(valid_question_ids)}"
                )

        return (len(errors) == 0, errors)

    def validate_evidence_refs(self, answer_pack: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate all answers have evidence_refs (RED LINE AP2).

        Args:
            answer_pack: The answer pack to validate

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        for i, answer in enumerate(answer_pack.get("answers", [])):
            evidence_refs = answer.get("evidence_refs", [])
            
            if not evidence_refs:
                q_id = answer.get("question_id", f"answer #{i+1}")
                errors.append(
                    f"RED LINE AP2 VIOLATION: Answer for '{q_id}' has no evidence_refs. "
                    f"All answers must provide supporting evidence."
                )
            elif not isinstance(evidence_refs, list):
                q_id = answer.get("question_id", f"answer #{i+1}")
                errors.append(
                    f"RED LINE AP2 VIOLATION: Answer for '{q_id}' has invalid evidence_refs "
                    f"(must be array, got {type(evidence_refs).__name__})"
                )

        return (len(errors) == 0, errors)

    def validate_no_definition_override(
        self,
        answer_pack: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate AnswerPack doesn't override definitions (RED LINE AP3).

        Checks that answer_data doesn't contain:
        - command_override
        - workflow_override
        - agent_override

        Args:
            answer_pack: The answer pack to validate

        Returns:
            (is_valid, error_messages)
        """
        errors = []
        forbidden_keys = ["command_override", "workflow_override", "agent_override"]

        for i, answer in enumerate(answer_pack.get("answers", [])):
            answer_data = answer.get("answer_data", {})
            if not isinstance(answer_data, dict):
                continue

            found_overrides = [k for k in forbidden_keys if k in answer_data]
            if found_overrides:
                q_id = answer.get("question_id", f"answer #{i+1}")
                errors.append(
                    f"RED LINE AP3 VIOLATION: Answer for '{q_id}' attempts to override "
                    f"definitions: {found_overrides}. AnswerPacks cannot modify "
                    f"command/workflow/agent definitions."
                )

        return (len(errors) == 0, errors)

    def validate_checksum(self, answer_pack: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate AnswerPack checksum.

        Args:
            answer_pack: The answer pack to validate

        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        stored_checksum = answer_pack.get("checksum")
        if not stored_checksum:
            errors.append("Checksum is missing")
            return (False, errors)

        # Compute checksum (excluding checksum field)
        import hashlib
        data_for_checksum = {k: v for k, v in answer_pack.items() if k != "checksum"}
        json_str = json.dumps(data_for_checksum, sort_keys=True, ensure_ascii=False)
        computed_checksum = hashlib.sha256(json_str.encode("utf-8")).hexdigest()

        if stored_checksum != computed_checksum:
            errors.append(
                f"Checksum mismatch. Expected {computed_checksum}, got {stored_checksum}"
            )
            return (False, errors)

        return (True, [])

    def validate_full(
        self,
        answer_pack: Dict[str, Any],
        question_pack: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Run all validations on an AnswerPack.

        Args:
            answer_pack: The answer pack to validate
            question_pack: Optional question pack to validate against

        Returns:
            (is_valid, error_messages)
        """
        all_errors = []

        # 1. Schema validation
        valid, errors = self.validate_schema(answer_pack)
        if not valid:
            all_errors.extend([f"[SCHEMA] {e}" for e in errors])

        # 2. Evidence refs (RED LINE AP2)
        valid, errors = self.validate_evidence_refs(answer_pack)
        if not valid:
            all_errors.extend([f"[AP2] {e}" for e in errors])

        # 3. No definition override (RED LINE AP3)
        valid, errors = self.validate_no_definition_override(answer_pack)
        if not valid:
            all_errors.extend([f"[AP3] {e}" for e in errors])

        # 4. Checksum
        valid, errors = self.validate_checksum(answer_pack)
        if not valid:
            all_errors.extend([f"[CHECKSUM] {e}" for e in errors])

        # 5. QuestionPack consistency (RED LINE AP1) - if provided
        if question_pack:
            valid, errors = self.validate_against_question_pack(answer_pack, question_pack)
            if not valid:
                all_errors.extend([f"[AP1] {e}" for e in errors])

        return (len(all_errors) == 0, all_errors)


# Convenience function
def validate_answer_pack(
    answer_pack: Dict[str, Any],
    question_pack: Optional[Dict[str, Any]] = None,
    schema_dir: Optional[Path] = None
) -> Tuple[bool, List[str]]:
    """
    Validate an AnswerPack.

    Args:
        answer_pack: The answer pack to validate
        question_pack: Optional question pack to validate against
        schema_dir: Optional custom schema directory

    Returns:
        (is_valid, error_messages)
    """
    validator = AnswerValidator(schema_dir=schema_dir)
    return validator.validate_full(answer_pack, question_pack)
