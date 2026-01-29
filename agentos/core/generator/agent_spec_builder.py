"""Agent Spec Builder"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agentos.core.llm import OpenAIClient
from agentos.core.verify import validate_agent_spec


class AgentSpecBuilder:
    """Build AgentSpec from FactPack using OpenAI"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = OpenAIClient(api_key)
    
    def generate(
        self,
        factpack: dict,
        agent_type: str
    ) -> dict:
        """
        Generate AgentSpec from FactPack
        
        Args:
            factpack: Input FactPack
            agent_type: Type of agent (e.g., 'frontend-engineer')
            
        Returns:
            Generated and validated AgentSpec
        """
        # Load schema
        schema = self._load_agent_spec_schema()
        
        # Generate using OpenAI
        agent_spec = self.client.generate_agent_spec(factpack, agent_type, schema)
        
        # Post-process: ensure metadata
        if "metadata" not in agent_spec:
            agent_spec["metadata"] = {}
        
        agent_spec["schema_version"] = "1.0.0"
        agent_spec["metadata"]["generated_at"] = datetime.now(timezone.utc).isoformat()
        agent_spec["metadata"]["agent_type"] = agent_type
        agent_spec["metadata"]["project_id"] = factpack.get("project_id")
        
        # Validate
        is_valid, errors = validate_agent_spec(agent_spec)
        if not is_valid:
            raise ValueError(f"Generated AgentSpec is invalid: {errors}")
        
        # Verify commands exist in FactPack
        self._verify_commands(agent_spec, factpack)
        
        return agent_spec
    
    def _load_agent_spec_schema(self) -> dict[str, Any]:
        """Load AgentSpec JSON schema"""
        schema_path = Path(__file__).parent.parent.parent / "schemas" / "agent_spec.schema.json"
        with open(schema_path, encoding="utf-8") as f:
            return json.load(f)
    
    def _verify_commands(self, agent_spec: dict[str, Any], factpack: dict[str, Any]):
        """Verify all commands exist in FactPack"""
        spec_commands = set(agent_spec.get("commands", {}).keys())
        factpack_commands = set(factpack.get("commands", {}).keys())
        
        fabricated = spec_commands - factpack_commands
        if fabricated:
            raise ValueError(
                f"AgentSpec contains fabricated commands not in FactPack: {fabricated}"
            )
