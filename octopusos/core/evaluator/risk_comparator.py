"""
Risk Comparator — v0.9.3

Compares intents across risk dimensions and determines dominance relationships.
"""

from typing import Dict, List, Any, Tuple
from .intent_normalizer import CanonicalIntent


class RiskMatrix:
    """Risk assessment matrix for intents."""
    
    def __init__(self):
        self.entries: List[Dict[str, Any]] = []
        self.dominance: List[Dict[str, str]] = []
        self.incomparable: List[Tuple[str, str]] = []
    
    def add_entry(self, intent_id: str, overall_risk: str, dimensions: Dict[str, float]):
        """Add a risk assessment entry."""
        self.entries.append({
            "intent_id": intent_id,
            "overall_risk": overall_risk,
            "dimensions": dimensions
        })
    
    def add_dominance(self, intent_a: str, intent_b: str, relationship: str):
        """Add a dominance relationship."""
        self.dominance.append({
            "intent_a": intent_a,
            "intent_b": intent_b,
            "relationship": relationship
        })
    
    def add_incomparable(self, intent_a: str, intent_b: str):
        """Mark two intents as incomparable."""
        self.incomparable.append((intent_a, intent_b))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "matrix": self.entries,
            "dominance": self.dominance,
            "incomparable": [[a, b] for a, b in self.incomparable]
        }


class RiskComparator:
    """Compares intents across risk dimensions."""
    
    EFFECT_RISK_SCORES = {
        "read": 0,
        "write": 30,
        "network": 40,
        "deploy": 70,
        "security": 90,
        "data": 80,
        "delete": 85,
        "configure": 50
    }
    
    ENV_RISK_MULTIPLIERS = {
        "local": 0.1,
        "dev": 0.2,
        "staging": 0.5,
        "prod": 1.0
    }
    
    def build_risk_matrix(self, canonical_intents: Dict[str, CanonicalIntent]) -> RiskMatrix:
        """
        Build comprehensive risk matrix for intent set.
        
        Args:
            canonical_intents: Dict of intent_id -> canonical intent
            
        Returns:
            Risk matrix with assessments and dominance relationships
        """
        matrix = RiskMatrix()
        
        # Compute risk dimensions for each intent
        risk_assessments = {}
        
        for intent_id, intent in canonical_intents.items():
            dimensions = {
                "effects_risk": self._compute_effects_risk(intent),
                "scope_risk": self._compute_scope_risk(intent),
                "blast_radius": self._compute_blast_radius(intent),
                "unknowns": self._compute_unknowns(intent)
            }
            
            matrix.add_entry(intent_id, intent.risk_level, dimensions)
            risk_assessments[intent_id] = dimensions
        
        # Compute pairwise dominance
        intent_list = list(canonical_intents.keys())
        for i, intent_a in enumerate(intent_list):
            for intent_b in intent_list[i+1:]:
                relationship = self.compute_dominance(
                    risk_assessments[intent_a],
                    risk_assessments[intent_b]
                )
                
                if relationship == "incomparable":
                    matrix.add_incomparable(intent_a, intent_b)
                else:
                    matrix.add_dominance(intent_a, intent_b, relationship)
        
        return matrix
    
    def _compute_effects_risk(self, intent: CanonicalIntent) -> float:
        """
        Compute risk score based on effects.
        
        Args:
            intent: Canonical intent
            
        Returns:
            Risk score 0-100
        """
        if not intent.effects:
            return 0.0
        
        # Take maximum effect risk
        max_risk = 0.0
        for effect in intent.effects.keys():
            risk = self.EFFECT_RISK_SCORES.get(effect, 20)
            max_risk = max(max_risk, risk)
        
        return min(max_risk, 100.0)
    
    def _compute_scope_risk(self, intent: CanonicalIntent) -> float:
        """
        Compute risk score based on scope.
        
        Args:
            intent: Canonical intent
            
        Returns:
            Risk score 0-100
        """
        scope = intent.scope
        env = scope.get("env", "local")
        breadth = scope.get("breadth", 0)
        
        # Base env risk
        base_risk = self.ENV_RISK_MULTIPLIERS.get(env, 0.2) * 100
        
        # Breadth multiplier (more resources = higher risk)
        if breadth <= 5:
            breadth_factor = 0.5
        elif breadth <= 20:
            breadth_factor = 1.0
        elif breadth <= 50:
            breadth_factor = 1.5
        else:
            breadth_factor = 2.0
        
        return min(base_risk * breadth_factor, 100.0)
    
    def _compute_blast_radius(self, intent: CanonicalIntent) -> float:
        """
        Compute blast radius (affected resources).
        
        Args:
            intent: Canonical intent
            
        Returns:
            Risk score 0-100
        """
        num_resources = len(intent.resources)
        
        if num_resources <= 5:
            return 10.0
        elif num_resources <= 20:
            return 30.0
        elif num_resources <= 50:
            return 60.0
        else:
            return 90.0
    
    def _compute_unknowns(self, intent: CanonicalIntent) -> float:
        """
        Compute unknowns score (inverse of evidence quality).
        
        Args:
            intent: Canonical intent
            
        Returns:
            Risk score 0-100 (higher = more unknowns)
        """
        evidence_count = len(intent.raw_data.get("evidence_refs", []))
        
        if evidence_count <= 5:
            return 90.0
        elif evidence_count <= 10:
            return 60.0
        elif evidence_count <= 20:
            return 30.0
        else:
            return 10.0
    
    def compute_dominance(
        self,
        risk_a: Dict[str, float],
        risk_b: Dict[str, float]
    ) -> str:
        """
        Compute dominance relationship between two risk profiles.
        
        A dominates B if A >= B in all dimensions.
        
        Args:
            risk_a: Risk dimensions for intent A
            risk_b: Risk dimensions for intent B
            
        Returns:
            "A_dominates_B", "B_dominates_A", or "incomparable"
        """
        a_higher = 0
        b_higher = 0
        
        for dimension in risk_a.keys():
            if risk_a[dimension] > risk_b[dimension]:
                a_higher += 1
            elif risk_b[dimension] > risk_a[dimension]:
                b_higher += 1
        
        if a_higher > 0 and b_higher == 0:
            return "A_dominates_B"
        elif b_higher > 0 and a_higher == 0:
            return "B_dominates_A"
        else:
            return "incomparable"
