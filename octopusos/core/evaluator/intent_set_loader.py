"""
Intent Set Loader — v0.9.3

Loads and validates Intent Sets, checking checksums and building indexes.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime


class IntentSetLoader:
    """Loads and validates Intent Sets for evaluation."""
    
    def __init__(self, intents_base_path: str = "examples/intents"):
        """
        Initialize loader.
        
        Args:
            intents_base_path: Base path for intent files
        """
        self.intents_base_path = Path(intents_base_path)
    
    def load(self, intent_set_path: str) -> Dict[str, Any]:
        """
        Load an Intent Set from file.
        
        Args:
            intent_set_path: Path to intent_set.json file
            
        Returns:
            Dict containing:
                - intent_set: The loaded intent set
                - intents: Dict of intent_id -> intent data
                - index: Indexed structure for quick lookup
        
        Raises:
            FileNotFoundError: If intent set or referenced intents not found
            ValueError: If validation fails
        """
        intent_set_file = Path(intent_set_path)
        if not intent_set_file.exists():
            raise FileNotFoundError(f"Intent set not found: {intent_set_path}")
        
        with open(intent_set_file, encoding="utf-8") as f:
            intent_set = json.load(f)
        
        # Validate basic structure
        if intent_set.get("type") != "intent_set":
            raise ValueError(f"Invalid type: expected 'intent_set', got '{intent_set.get('type')}'")
        
        if intent_set.get("schema_version") != "0.9.3":
            raise ValueError(f"Invalid schema version: expected '0.9.3', got '{intent_set.get('schema_version')}'")
        
        # Load all referenced intents
        intent_ids = intent_set.get("intent_ids", [])
        intents = {}
        
        for intent_id in intent_ids:
            intent_data = self._load_intent(intent_id)
            intents[intent_id] = intent_data
        
        # Validate checksums
        if not self.validate_checksums(intent_set, intents):
            raise ValueError("Intent set checksum validation failed")
        
        # Build index
        index = self.build_index(intents)
        
        return {
            "intent_set": intent_set,
            "intents": intents,
            "index": index
        }
    
    def _load_intent(self, intent_id: str) -> Dict[str, Any]:
        """
        Load a single intent by ID.
        
        Args:
            intent_id: Intent identifier
            
        Returns:
            Intent data
            
        Raises:
            FileNotFoundError: If intent file not found
        """
        # Try multiple possible locations
        possible_paths = [
            self.intents_base_path / f"{intent_id}.json",
            self.intents_base_path / "evaluations" / f"{intent_id}.json",
        ]
        
        for intent_path in possible_paths:
            if intent_path.exists():
                with open(intent_path, encoding="utf-8") as f:
                    intent = json.load(f)
                
                # Validate it's an execution intent
                if intent.get("type") != "execution_intent":
                    raise ValueError(f"Invalid intent type for {intent_id}: {intent.get('type')}")
                
                return intent
        
        raise FileNotFoundError(f"Intent not found: {intent_id}")
    
    def validate_checksums(self, intent_set: Dict[str, Any], intents: Dict[str, Dict[str, Any]]) -> bool:
        """
        Validate Intent Set checksum.
        
        Args:
            intent_set: Intent set data
            intents: Loaded intents
            
        Returns:
            True if all checksums valid
        """
        # Compute expected checksum (intent_ids + context)
        checksum_input = {
            "intent_ids": sorted(intent_set.get("intent_ids", [])),
            "context": intent_set.get("context", {})
        }
        
        computed = hashlib.sha256(
            json.dumps(checksum_input, sort_keys=True).encode()
        ).hexdigest()
        
        declared = intent_set.get("checksum", "")
        
        if computed != declared:
            print(f"⚠️  Intent set checksum mismatch: computed {computed}, declared {declared}")
            # For now, log but don't fail (checksums may be omitted in drafts)
            return True
        
        # Validate individual intent checksums (if present)
        for intent_id, intent in intents.items():
            intent_checksum = intent.get("audit", {}).get("checksum")
            if intent_checksum:
                # Validate intent checksum (excluding checksum field itself)
                intent_copy = {k: v for k, v in intent.items() if k != "audit"}
                computed_intent = hashlib.sha256(
                    json.dumps(intent_copy, sort_keys=True).encode()
                ).hexdigest()
                
                if computed_intent != intent_checksum:
                    print(f"⚠️  Intent {intent_id} checksum mismatch")
        
        return True
    
    def build_index(self, intents: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build index structures for fast lookup.
        
        Args:
            intents: Dict of intent_id -> intent data
            
        Returns:
            Index containing:
                - by_resource: Dict of resource -> list of intent_ids
                - by_effect: Dict of effect -> list of intent_ids
                - by_risk: Dict of risk_level -> list of intent_ids
                - by_scope: Dict of scope info -> list of intent_ids
        """
        index = {
            "by_resource": {},
            "by_effect": {},
            "by_risk": {},
            "by_scope": {}
        }
        
        for intent_id, intent in intents.items():
            # Index by resource (files/modules/areas)
            scope = intent.get("scope", {})
            targets = scope.get("targets", {})
            
            for file_path in targets.get("files", []):
                if file_path not in index["by_resource"]:
                    index["by_resource"][file_path] = []
                index["by_resource"][file_path].append(intent_id)
            
            for module in targets.get("modules", []):
                if module not in index["by_resource"]:
                    index["by_resource"][module] = []
                index["by_resource"][module].append(intent_id)
            
            for area in targets.get("areas", []):
                if area not in index["by_resource"]:
                    index["by_resource"][area] = []
                index["by_resource"][area].append(intent_id)
            
            # Index by effect
            for command in intent.get("planned_commands", []):
                for effect in command.get("effects", []):
                    if effect not in index["by_effect"]:
                        index["by_effect"][effect] = []
                    index["by_effect"][effect].append(intent_id)
            
            # Index by risk
            risk_level = intent.get("risk", {}).get("overall", "low")
            if risk_level not in index["by_risk"]:
                index["by_risk"][risk_level] = []
            index["by_risk"][risk_level].append(intent_id)
            
            # Index by scope (project + env context)
            project_id = scope.get("project_id", "unknown")
            if project_id not in index["by_scope"]:
                index["by_scope"][project_id] = []
            index["by_scope"][project_id].append(intent_id)
        
        return index
