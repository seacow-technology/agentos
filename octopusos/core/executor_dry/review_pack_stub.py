"""
Review Pack Stub Generator for Dry Executor

Generates a "stub" review pack (summary only, not full review artifacts).
This avoids conflicts with v0.2/v0.3 ReviewPackGenerator.
"""

from typing import Any, Dict, List


class ReviewPackStubGenerator:
    """
    Generates review pack stub (pre-review summary).
    
    Red Line Enforcement:
    - DE5: High/critical risk must have requires_review
    """
    
    def __init__(self, intent: Dict[str, Any], graph: Dict[str, Any], 
                 patch_plan: Dict[str, Any], commit_plan: Dict[str, Any]):
        """
        Initialize review pack stub generator.
        
        Args:
            intent: ExecutionIntent
            graph: ExecutionGraph
            patch_plan: PatchPlan
            commit_plan: CommitPlan
        """
        self.intent = intent
        self.graph = graph
        self.patch_plan = patch_plan
        self.commit_plan = commit_plan
    
    def generate(self) -> Dict[str, Any]:
        """
        Generate review pack stub.
        
        Returns:
            Review pack stub dictionary
        """
        return {
            "risk_summary": self._generate_risk_summary(),
            "requires_review": self._determine_required_reviews(),
            "evidence_coverage": self._calculate_evidence_coverage(),
            "estimated_review_time": self._estimate_review_time()
        }
    
    def _generate_risk_summary(self) -> Dict[str, Any]:
        """Generate risk summary."""
        # Get dominant risk from intent
        overall_risk = self.intent.get("risk", {}).get("overall", "medium")
        
        # Check commit risks
        max_commit_risk = "low"
        for commit in self.commit_plan.get("commits", []):
            commit_risk = commit.get("risk", "low")
            if self._risk_level_value(commit_risk) > self._risk_level_value(max_commit_risk):
                max_commit_risk = commit_risk
        
        # Use higher of the two
        if self._risk_level_value(overall_risk) > self._risk_level_value(max_commit_risk):
            dominant_risk = overall_risk
        else:
            dominant_risk = max_commit_risk
        
        # Get risk drivers from intent
        risk_drivers = self.intent.get("risk", {}).get("drivers", [])
        
        # Generate mitigation notes
        mitigation_notes = self._generate_mitigation_notes(dominant_risk)
        
        return {
            "dominant_risk": dominant_risk,
            "risk_factors": risk_drivers if risk_drivers else ["No specific risk factors identified"],
            "mitigation_notes": mitigation_notes
        }
    
    def _determine_required_reviews(self) -> List[str]:
        """Determine required review types."""
        # Start with intent's requires_review
        required = set(self.intent.get("risk", {}).get("requires_review", []))
        
        # Add inferred reviews based on file types and effects
        for file_entry in self.patch_plan.get("files", []):
            path = file_entry["path"]
            
            # Security review for sensitive files
            if any(term in path.lower() for term in ["auth", "security", "secret", "password"]):
                required.add("security")
            
            # Data review for database/data files
            if any(term in path.lower() for term in ["db", "database", "migration", "schema"]):
                required.add("data")
            
            # Architecture review for core system files
            if any(term in path.lower() for term in ["core", "engine", "orchestrator"]):
                required.add("architecture")
        
        # Add release review for high/critical risk
        dominant_risk = self.intent.get("risk", {}).get("overall", "medium")
        if dominant_risk in ["high", "critical"]:
            required.add("release")
        
        return sorted(list(required))
    
    def _calculate_evidence_coverage(self) -> Dict[str, Any]:
        """Calculate evidence coverage across graph nodes."""
        nodes = self.graph.get("nodes", [])
        
        if not nodes:
            return {
                "total_nodes": 0,
                "nodes_with_evidence": 0,
                "coverage_percentage": 0.0,
                "gaps": []
            }
        
        total_nodes = len(nodes)
        nodes_with_evidence = 0
        gaps = []
        
        for node in nodes:
            evidence_refs = node.get("evidence_refs", [])
            if evidence_refs:
                nodes_with_evidence += 1
            else:
                gaps.append({
                    "node_id": node.get("node_id", "unknown"),
                    "reason": "Missing evidence_refs"
                })
        
        coverage_percentage = (nodes_with_evidence / total_nodes * 100) if total_nodes > 0 else 0.0
        
        return {
            "total_nodes": total_nodes,
            "nodes_with_evidence": nodes_with_evidence,
            "coverage_percentage": round(coverage_percentage, 2),
            "gaps": gaps
        }
    
    def _estimate_review_time(self) -> str:
        """Estimate overall review time needed."""
        # Check commit review times
        review_times = []
        for commit in self.commit_plan.get("commits", []):
            time = commit.get("estimated_review_time", "moderate")
            review_times.append(time)
        
        # Map to numeric values
        time_values = {
            "quick": 1,
            "moderate": 2,
            "thorough": 3,
            "extended": 4
        }
        
        if not review_times:
            return "moderate"
        
        # Take max
        max_time_value = max(time_values.get(t, 2) for t in review_times)
        
        # Reverse map
        for name, value in time_values.items():
            if value == max_time_value:
                return name
        
        return "moderate"
    
    def _generate_mitigation_notes(self, risk: str) -> List[str]:
        """Generate mitigation suggestions based on risk."""
        notes = []
        
        if risk in ["high", "critical"]:
            notes.append("Require multiple reviewers for approval")
            notes.append("Conduct thorough testing in staging environment")
            notes.append("Prepare rollback plan before deployment")
            notes.append("Monitor system closely after deployment")
        elif risk == "medium":
            notes.append("Single reviewer approval required")
            notes.append("Test in staging environment")
            notes.append("Have rollback plan ready")
        else:
            notes.append("Standard review process sufficient")
            notes.append("Basic testing in development environment")
        
        return notes
    
    def _risk_level_value(self, risk: str) -> int:
        """Convert risk level to numeric value."""
        levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return levels.get(risk, 2)
