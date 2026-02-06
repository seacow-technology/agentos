"""
Intent Normalizer — v0.9.3

Normalizes intent structures for consistent comparison and conflict detection.
"""

from typing import Dict, Any, List, Set


class CanonicalIntent:
    """Normalized intent representation for evaluation."""
    
    def __init__(self, intent_id: str, intent_data: Dict[str, Any]):
        """
        Initialize canonical intent.
        
        Args:
            intent_id: Intent identifier
            intent_data: Raw intent data
        """
        self.intent_id = intent_id
        self.raw_data = intent_data
        
        # Normalize resources
        self.resources = self._normalize_resources(intent_data)
        
        # Normalize effects
        self.effects = self._normalize_effects(intent_data)
        
        # Normalize scope
        self.scope = self._normalize_scope(intent_data)
        
        # Extract metadata
        self.risk_level = intent_data.get("risk", {}).get("overall", "low")
        self.interaction_mode = intent_data.get("interaction", {}).get("mode", "interactive")
        self.priority = self._extract_priority(intent_data)
    
    def _normalize_resources(self, intent: Dict[str, Any]) -> Set[str]:
        """
        Normalize resource references.
        
        Returns:
            Set of canonical resource identifiers
        """
        resources = set()
        targets = intent.get("scope", {}).get("targets", {})
        
        # Files
        for file_path in targets.get("files", []):
            resources.add(f"file:{file_path}")
        
        # Modules
        for module in targets.get("modules", []):
            resources.add(f"module:{module}")
        
        # Areas
        for area in targets.get("areas", []):
            resources.add(f"area:{area}")
        
        return resources
    
    def _normalize_effects(self, intent: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Normalize effects from commands.
        
        Returns:
            Dict of effect_type -> list of resources affected
        """
        effects_map = {}
        
        for command in intent.get("planned_commands", []):
            command_id = command.get("command_id", "unknown")
            effects = command.get("effects", [])
            
            for effect in effects:
                if effect not in effects_map:
                    effects_map[effect] = []
                effects_map[effect].append(command_id)
        
        return effects_map
    
    def _normalize_scope(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize scope information.
        
        Returns:
            Canonical scope structure
        """
        scope = intent.get("scope", {})
        return {
            "project_id": scope.get("project_id", ""),
            "repo_root": scope.get("repo_root", ""),
            "env": "local",  # Default, can be enriched from context
            "breadth": len(scope.get("targets", {}).get("files", [])) + 
                      len(scope.get("targets", {}).get("modules", [])) +
                      len(scope.get("targets", {}).get("areas", []))
        }
    
    def _extract_priority(self, intent: Dict[str, Any]) -> int:
        """
        Extract or infer priority.
        
        Priority determination (highest to lowest):
        1. Explicit metadata.priority
        2. Status: approved=10, proposed=5, draft=1
        3. Risk: low=10, medium=7, high=4, critical=1 (safer = higher priority)
        
        Returns:
            Priority score (1-10)
        """
        # Check metadata for explicit priority
        metadata = intent.get("metadata", {})
        if "priority" in metadata:
            return int(metadata["priority"])
        
        # Infer from status
        status = intent.get("status", "draft")
        status_priority = {
            "approved": 10,
            "proposed": 5,
            "draft": 1,
            "rejected": 0,
            "superseded": 0
        }
        
        if status in status_priority:
            return status_priority[status]
        
        # Infer from risk (safer = higher priority for conflict resolution)
        risk_priority = {
            "low": 10,
            "medium": 7,
            "high": 4,
            "critical": 1
        }
        
        return risk_priority.get(self.risk_level, 5)
    
    def has_write_effects(self) -> bool:
        """Check if intent has write effects."""
        return any(e in self.effects for e in ["write", "deploy", "delete"])
    
    def overlaps_resources(self, other: "CanonicalIntent") -> Set[str]:
        """
        Find overlapping resources with another intent.
        
        Args:
            other: Another canonical intent
            
        Returns:
            Set of overlapping resources
        """
        return self.resources & other.resources


class IntentNormalizer:
    """Normalizes intents for consistent evaluation."""
    
    def normalize(self, intent: Dict[str, Any]) -> CanonicalIntent:
        """
        Normalize an intent.
        
        Args:
            intent: Raw intent data
            
        Returns:
            Canonical intent
        """
        intent_id = intent.get("id", "unknown")
        return CanonicalIntent(intent_id, intent)
    
    def normalize_batch(self, intents: Dict[str, Dict[str, Any]]) -> Dict[str, CanonicalIntent]:
        """
        Normalize a batch of intents.
        
        Args:
            intents: Dict of intent_id -> intent data
            
        Returns:
            Dict of intent_id -> canonical intent
        """
        return {
            intent_id: self.normalize(intent_data)
            for intent_id, intent_data in intents.items()
        }
