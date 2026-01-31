"""
Patch Planner for Dry Executor

Plans file changes based on intent without generating actual patches.
Strictly enforces DE3: no path fabrication.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from .utils import compute_checksum, generate_id, validate_path_in_intent
from agentos.core.time import utc_now_iso



class PatchPlanner:
    """
    Plans file changes from an ExecutionIntent.
    
    Red Line Enforcement:
    - DE2: No file system writes
    - DE3: No path fabrication (all paths must come from intent)
    - DE4: All file changes must have evidence_refs
    """
    
    def __init__(self, intent: Dict[str, Any]):
        """
        Initialize patch planner.
        
        Args:
            intent: ExecutionIntent (v0.9.1)
        """
        self.intent = intent
        self.files: List[Dict[str, Any]] = []
        self.estimated_diffs: List[Dict[str, Any]] = []
        self.unknowns: List[Dict[str, Any]] = []
    
    def plan(self) -> Dict[str, Any]:
        """
        Generate patch plan.
        
        Returns:
            PatchPlan dictionary matching patch_plan.schema.json
        """
        # Extract explicit file paths from intent
        target_files = self.intent.get("scope", {}).get("targets", {}).get("files", [])
        
        # Plan changes for each file
        for file_path in target_files:
            self._plan_file_change(file_path)
        
        # Infer additional files from commands (if evidence supports it)
        self._infer_from_commands()
        
        # Build patch plan object
        plan_data = {
            "plan_id": generate_id("patchplan", self.intent["id"]),
            "schema_version": "0.10.0",
            "intent_id": self.intent["id"],
            "created_at": utc_now_iso() + "Z",
            "files": self.files,
            "estimated_diffs": self.estimated_diffs,
            "constraints": {
                "no_exec": True,
                "no_fs_write": True,
                "no_fabrication": True
            },
            "unknowns": self.unknowns
        }
        
        # Compute checksum
        plan_data["checksum"] = compute_checksum(plan_data)
        
        return plan_data
    
    def _plan_file_change(self, file_path: str):
        """
        Plan changes for a specific file.
        
        Args:
            file_path: Path to the file (must be from intent)
        """
        # Validate path is in intent (DE3)
        if not validate_path_in_intent(file_path, self.intent):
            self.unknowns.append({
                "type": "missing_path",
                "description": f"Path '{file_path}' not found in intent",
                "reason": "Path not in scope.targets.files or evidence_refs",
                "needed_evidence": f"Explicit mention of {file_path} in intent or evidence"
            })
            return
        
        # Determine action based on command effects
        action = self._infer_action(file_path)
        
        # Determine risk based on file type and command risks
        risk = self._infer_risk(file_path)
        
        # Collect evidence
        evidence_refs = self._collect_evidence(file_path)
        
        # Create file entry
        file_entry = {
            "path": file_path,
            "action": action,
            "rationale": self._generate_rationale(file_path, action),
            "risk": risk,
            "evidence_refs": evidence_refs,
            "lock_intent": self._infer_lock_intent(file_path, action),
            "estimated_impact": self._estimate_impact(risk)
        }
        
        self.files.append(file_entry)
        
        # Create estimated diff placeholder
        diff_entry = {
            "file_path": file_path,
            "diff_hash_placeholder": self._generate_diff_placeholder(file_path),
            "intent_summary": self._summarize_intent(file_path),
            "estimated_lines_changed": self._estimate_lines(file_path, action)
        }
        
        self.estimated_diffs.append(diff_entry)
    
    def _infer_from_commands(self):
        """
        Infer additional file involvement from planned commands.
        Only if evidence explicitly supports it (DE3).
        """
        for command in self.intent.get("planned_commands", []):
            # Check if command evidence references specific files
            for evidence in command.get("evidence_refs", []):
                # Only accept explicit file references like "scan://file/path.py"
                if evidence.startswith("scan://file/"):
                    file_path = evidence.replace("scan://file/", "")
                    
                    # Validate this path is also in scope.targets.files
                    if validate_path_in_intent(file_path, self.intent):
                        # Check if not already planned
                        if not any(f["path"] == file_path for f in self.files):
                            self._plan_file_change(file_path)
    
    def _infer_action(self, file_path: str) -> str:
        """Infer the action (add/modify/delete) for a file."""
        # Check command effects for write/delete
        for command in self.intent.get("planned_commands", []):
            effects = command.get("effects", [])
            if "delete" in effects:
                return "delete"
            elif "write" in effects:
                # Assume modify if file exists in target (would be add for new files)
                # Default to modify for safety
                return "modify"
        
        return "modify"  # Default
    
    def _infer_risk(self, file_path: str) -> str:
        """Infer risk level for file change."""
        # Check overall intent risk
        overall_risk = self.intent.get("risk", {}).get("overall", "medium")
        
        # Check command risks
        max_cmd_risk = "low"
        for command in self.intent.get("planned_commands", []):
            cmd_risk = command.get("risk_level", "low")
            if self._risk_level_value(cmd_risk) > self._risk_level_value(max_cmd_risk):
                max_cmd_risk = cmd_risk
        
        # Return higher of overall risk and max command risk
        if self._risk_level_value(overall_risk) > self._risk_level_value(max_cmd_risk):
            return overall_risk
        return max_cmd_risk
    
    def _risk_level_value(self, risk: str) -> int:
        """Convert risk level to numeric value."""
        levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return levels.get(risk, 2)
    
    def _collect_evidence(self, file_path: str) -> List[str]:
        """Collect evidence references for file change."""
        evidence = []
        
        # Add intent-level evidence
        evidence.append(f"intent://{self.intent['id']}/scope/targets/files/{file_path}")
        
        # Add command-level evidence
        for command in self.intent.get("planned_commands", []):
            for ref in command.get("evidence_refs", []):
                if file_path in ref:
                    evidence.extend(command["evidence_refs"])
        
        # Deduplicate
        return list(set(evidence))
    
    def _generate_rationale(self, file_path: str, action: str) -> str:
        """Generate rationale for file change."""
        objective = self.intent.get("objective", {}).get("goal", "")
        return f"{action.capitalize()} {file_path} to: {objective}"
    
    def _infer_lock_intent(self, file_path: str, action: str) -> Dict[str, Any]:
        """Infer lock intent for file."""
        if action == "delete":
            return {
                "mode": "exclusive",
                "scope": "file",
                "reason": "Exclusive lock needed for deletion"
            }
        elif action == "modify":
            return {
                "mode": "exclusive",
                "scope": "file",
                "reason": "Exclusive lock needed for modification"
            }
        else:  # add
            return {
                "mode": "exclusive",
                "scope": "file",
                "reason": "Exclusive lock needed for creation"
            }
    
    def _estimate_impact(self, risk: str) -> str:
        """Estimate impact level from risk."""
        impact_map = {
            "low": "minimal",
            "medium": "moderate",
            "high": "significant",
            "critical": "critical"
        }
        return impact_map.get(risk, "moderate")
    
    def _generate_diff_placeholder(self, file_path: str) -> str:
        """Generate a placeholder hash for future diff."""
        import hashlib
        hash_val = hashlib.sha256(f"diff_{file_path}".encode()).hexdigest()[:16]
        return f"placeholder_{hash_val}"
    
    def _summarize_intent(self, file_path: str) -> str:
        """Summarize the intended change for this file."""
        objective = self.intent.get("objective", {}).get("goal", "")
        return f"Changes to {file_path} for: {objective}"[:500]
    
    def _estimate_lines(self, file_path: str, action: str) -> Dict[str, int]:
        """Estimate lines changed (rough heuristic)."""
        if action == "add":
            return {"added": 50, "removed": 0, "modified": 0}
        elif action == "delete":
            return {"added": 0, "removed": 100, "modified": 0}
        else:  # modify
            return {"added": 10, "removed": 5, "modified": 20}
