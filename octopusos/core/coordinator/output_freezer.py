"""Output Freezer - Freeze outputs with checksums and lineage (v0.9.2)"""

import hashlib
import json
from pathlib import Path


class OutputFreezer:
    """Freeze outputs with checksums and lineage tracking"""
    
    def __init__(self):
        self.checksums = {}
    
    def freeze(self, outputs: dict, intent: dict, registry_versions: dict) -> dict:
        """
        Freeze all outputs with checksums and lineage
        
        Returns:
            FrozenOutputs bundle
        """
        frozen = {}
        
        for key, output in outputs.items():
            checksum = self.calculate_checksum(output)
            frozen[key] = {
                "content": output,
                "checksum": checksum,
                "lineage": self.build_lineage(intent, registry_versions)
            }
            self.checksums[key] = checksum
        
        return frozen
    
    def calculate_checksum(self, obj: dict) -> str:
        """Calculate SHA-256 checksum"""
        content = json.dumps(obj, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def build_lineage(self, intent: dict, registry_versions: dict) -> dict:
        """Build complete lineage chain"""
        return {
            "derived_from_intent": intent.get("id"),
            "intent_checksum": intent.get("audit", {}).get("checksum"),
            "registry_versions": registry_versions,
            "coordinator_version": "0.9.2"
        }
    
    def serialize_json(self, obj: dict, output_path: Path) -> str:
        """Serialize object to JSON"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
        
        return self.calculate_checksum(obj)
    
    def validate_frozen(self, frozen: dict) -> tuple[bool, list]:
        """Validate frozen outputs"""
        errors = []
        
        for key, value in frozen.items():
            if "checksum" not in value:
                errors.append(f"{key}: missing checksum")
            if "lineage" not in value:
                errors.append(f"{key}: missing lineage")
        
        return len(errors) == 0, errors
