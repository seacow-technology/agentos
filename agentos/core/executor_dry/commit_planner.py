"""
Commit Planner for Dry Executor

Plans how file changes will be grouped into commits.
"""

from datetime import datetime
from typing import Any, Dict, List

from .utils import compute_checksum, generate_id


class CommitPlanner:
    """
    Plans commit grouping from patch plan.
    
    Red Line Enforcement:
    - DE4: All commits must have evidence_refs
    """
    
    def __init__(self, intent: Dict[str, Any], patch_plan: Dict[str, Any]):
        """
        Initialize commit planner.
        
        Args:
            intent: ExecutionIntent (v0.9.1)
            patch_plan: PatchPlan from PatchPlanner
        """
        self.intent = intent
        self.patch_plan = patch_plan
        self.commits: List[Dict[str, Any]] = []
        self.rules_applied: List[Dict[str, Any]] = []
    
    def plan(self) -> Dict[str, Any]:
        """
        Generate commit plan.
        
        Returns:
            CommitPlan dictionary matching commit_plan.schema.json
        """
        # Get max commits budget
        max_commits = self.intent.get("budgets", {}).get("max_commits", 50)
        
        # Group files into commits
        self._group_files_into_commits(max_commits)
        
        # Apply ordering/dependencies
        self._establish_dependencies()
        
        # Build commit plan object
        plan_data = {
            "plan_id": generate_id("commitplan", self.intent["id"]),
            "schema_version": "0.10.0",
            "intent_id": self.intent["id"],
            "created_at": datetime.utcnow().isoformat() + "Z",
            "commits": self.commits,
            "rules_applied": self.rules_applied,
            "metadata": {
                "total_files": len(self.patch_plan.get("files", [])),
                "max_files_per_commit": max([len(c["files"]) for c in self.commits]) if self.commits else 0,
                "respects_max_commits_budget": len(self.commits) <= max_commits,
                "commit_dag_depth": self._calculate_dag_depth()
            }
        }
        
        # Compute freeze checksum
        plan_data["freeze_checksum"] = compute_checksum(plan_data)
        
        return plan_data
    
    def _group_files_into_commits(self, max_commits: int):
        """
        Group files into logical commits.
        
        Strategy:
        1. Group by module/directory
        2. Group by risk level
        3. Respect max_commits budget
        """
        files = self.patch_plan.get("files", [])
        
        if not files:
            # Create empty commit if no files (documentation-only intent)
            self._create_commit(
                title="chore: planning artifact",
                scope="docs",
                files=[],
                risk="low",
                rationale="No file changes planned"
            )
            return
        
        # Group by directory
        by_directory: Dict[str, List[Dict]] = {}
        for file_entry in files:
            path = file_entry["path"]
            # Get directory (first path component) - Windows 兼容
            from pathlib import Path
            parts = Path(path).parts
            directory = parts[0] if parts else "root"

            if directory not in by_directory:
                by_directory[directory] = []
            by_directory[directory].append(file_entry)
        
        # Create commits for each directory group
        for directory, dir_files in by_directory.items():
            # If too many files in one directory, split by risk
            if len(dir_files) > 20:
                self._split_by_risk(directory, dir_files)
            else:
                self._create_commit_from_files(directory, dir_files)
        
        # Ensure we don't exceed max_commits
        if len(self.commits) > max_commits:
            self._merge_commits_to_budget(max_commits)
    
    def _create_commit_from_files(self, scope: str, files: List[Dict]):
        """Create a single commit from a group of files."""
        file_paths = [f["path"] for f in files]
        
        # Determine highest risk
        max_risk = "low"
        for f in files:
            if self._risk_level_value(f["risk"]) > self._risk_level_value(max_risk):
                max_risk = f["risk"]
        
        # Collect evidence
        evidence = []
        for f in files:
            evidence.extend(f.get("evidence_refs", []))
        evidence = list(set(evidence))  # Deduplicate
        
        # Determine commit type and title
        actions = [f["action"] for f in files]
        if all(a == "add" for a in actions):
            commit_type = "feat"
            action_desc = "add"
        elif all(a == "delete" for a in actions):
            commit_type = "chore"
            action_desc = "remove"
        else:
            commit_type = "feat"
            action_desc = "update"
        
        title = f"{commit_type}({scope}): {action_desc} {len(files)} file(s)"
        
        self._create_commit(
            title=title,
            scope=scope,
            files=file_paths,
            risk=max_risk,
            rationale=f"Grouped {len(files)} files from {scope} directory",
            evidence=evidence
        )
    
    def _split_by_risk(self, scope: str, files: List[Dict]):
        """Split files by risk level into separate commits."""
        by_risk: Dict[str, List[Dict]] = {
            "low": [],
            "medium": [],
            "high": [],
            "critical": []
        }
        
        for f in files:
            by_risk[f["risk"]].append(f)
        
        # Create commit for each risk level
        for risk, risk_files in by_risk.items():
            if risk_files:
                self._create_commit_from_files(f"{scope}_{risk}", risk_files)
    
    def _create_commit(self, title: str, scope: str, files: List[str], 
                       risk: str, rationale: str, evidence: List[str] = None):
        """Create a commit entry."""
        if evidence is None:
            evidence = [f"intent://{self.intent['id']}/scope"]
        
        commit = {
            "commit_id": f"commit_{len(self.commits) + 1:04d}",
            "title": title[:160],
            "scope": scope[:100],
            "files": files,
            "rationale": rationale[:2000],
            "depends_on": [],  # Will be filled in _establish_dependencies
            "risk": risk,
            "evidence_refs": evidence,
            "rollback_strategy": self._determine_rollback_strategy(risk),
            "estimated_review_time": self._estimate_review_time(risk, len(files)),
            "tags": self._determine_tags(files, risk)
        }
        
        self.commits.append(commit)
    
    def _establish_dependencies(self):
        """Establish commit dependencies based on risk and file relationships."""
        # Simple strategy: higher risk commits depend on lower risk commits
        if len(self.commits) <= 1:
            return
        
        # Sort commits by risk level
        risk_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        sorted_commits = sorted(self.commits, key=lambda c: risk_order.get(c["risk"], 2))
        
        # Higher risk commits depend on previous commits
        for i in range(1, len(sorted_commits)):
            current = sorted_commits[i]
            # Depend on all previous commits with lower or equal risk
            deps = [sorted_commits[j]["commit_id"] for j in range(i)]
            current["depends_on"] = deps[:3]  # Limit dependencies to avoid complexity
    
    def _merge_commits_to_budget(self, max_commits: int):
        """Merge commits if we exceed budget."""
        while len(self.commits) > max_commits:
            # Find two low-risk commits to merge
            low_risk_commits = [c for c in self.commits if c["risk"] == "low"]
            
            if len(low_risk_commits) >= 2:
                # Merge first two low-risk commits
                c1, c2 = low_risk_commits[0], low_risk_commits[1]
                merged = {
                    "commit_id": c1["commit_id"],
                    "title": f"chore(combined): {c1['scope']} and {c2['scope']}",
                    "scope": f"{c1['scope']}_combined",
                    "files": c1["files"] + c2["files"],
                    "rationale": f"Merged commits to respect budget. {c1['rationale']} + {c2['rationale']}"[:2000],
                    "depends_on": list(set(c1["depends_on"] + c2["depends_on"])),
                    "risk": "low",
                    "evidence_refs": list(set(c1["evidence_refs"] + c2["evidence_refs"])),
                    "rollback_strategy": "revert",
                    "estimated_review_time": "moderate",
                    "tags": list(set(c1.get("tags", []) + c2.get("tags", [])))
                }
                
                # Remove c1 and c2, add merged
                self.commits.remove(c1)
                self.commits.remove(c2)
                self.commits.insert(0, merged)
            else:
                break  # Can't merge further
    
    def _calculate_dag_depth(self) -> int:
        """Calculate longest dependency chain depth."""
        if not self.commits:
            return 0
        
        # Simple heuristic: count max depends_on chain
        max_depth = 1
        for commit in self.commits:
            depth = len(commit.get("depends_on", [])) + 1
            if depth > max_depth:
                max_depth = depth
        
        return max_depth
    
    def _determine_rollback_strategy(self, risk: str) -> str:
        """Determine rollback strategy based on risk."""
        if risk in ["high", "critical"]:
            return "requires_manual"
        elif risk == "medium":
            return "forward_fix"
        else:
            return "revert"
    
    def _estimate_review_time(self, risk: str, file_count: int) -> str:
        """Estimate review time needed."""
        if risk in ["high", "critical"]:
            return "extended"
        elif risk == "medium" or file_count > 10:
            return "thorough"
        elif file_count > 5:
            return "moderate"
        else:
            return "quick"
    
    def _determine_tags(self, files: List[str], risk: str) -> List[str]:
        """Determine tags for commit."""
        tags = []
        
        if risk in ["high", "critical"]:
            tags.append("security")
        
        # Check file patterns
        if any("test" in f for f in files):
            tags.append("tests")
        if any("doc" in f or ".md" in f for f in files):
            tags.append("docs")
        if any("db" in f or "migration" in f for f in files):
            tags.append("data")
        
        return tags or ["refactor"]
    
    def _risk_level_value(self, risk: str) -> int:
        """Convert risk level to numeric value."""
        levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return levels.get(risk, 2)
