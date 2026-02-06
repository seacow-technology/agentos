"""OpenAI client for structured outputs"""

import json
import os
from pathlib import Path
from typing import Any, Optional

from openai import OpenAI


class OpenAIClient:
    """OpenAI client wrapper with structured outputs support"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        
        self.client = OpenAI(api_key=self.api_key)
    
    def generate_agent_spec(
        self,
        factpack: dict,
        agent_type: str,
        schema: dict
    ) -> dict:
        """
        Generate AgentSpec using OpenAI Structured Outputs
        
        Args:
            factpack: Input FactPack
            agent_type: Type of agent to generate (e.g., 'frontend-engineer')
            schema: JSON schema for AgentSpec
            
        Returns:
            Generated AgentSpec as dictionary
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(factpack, agent_type)
        
        # Call OpenAI with structured outputs
        response = self.client.chat.completions.create(
            model="gpt-4o-2024-08-06",  # Supports Structured Outputs
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "agent_spec",
                    "strict": True,
                    "schema": schema
                }
            }
        )
        
        # Parse response
        content = response.choices[0].message.content
        if content:
            return json.loads(content)
        else:
            raise ValueError("No content in OpenAI response")
    
    def _build_system_prompt(self) -> str:
        """Build system prompt"""
        return """You are AgentOS's AgentSpec generator.

Your task is to generate a precise, validated AgentSpec from a FactPack.

CRITICAL RULES:
1. All commands MUST come from FactPack.commands or evidence
2. All allowed_paths MUST reference real paths from the project
3. NEVER fabricate commands, paths, or capabilities
4. verification.schema_check MUST be true
5. verification.command_existence_check MUST be true
6. provenance MUST reference real evidence IDs from the FactPack

OUTPUT:
- Strict JSON conforming to AgentSpec schema
- Evidence-based: every claim traceable to FactPack
- Actionable: agent can immediately execute the spec
"""
    
    def _build_user_prompt(self, factpack: dict[str, Any], agent_type: str) -> str:
        """Build user prompt with FactPack"""
        # Simplify FactPack for token efficiency
        simplified_fp = {
            "project_id": factpack.get("project_id"),
            "detected_projects": factpack.get("detected_projects", []),
            "commands": factpack.get("commands", {}),
            "constraints": factpack.get("constraints", {}),
            "governance": factpack.get("governance", {}),
            "evidence": [
                {
                    "id": ev["id"],
                    "source": ev.get("source_file"),
                    "category": ev.get("category"),
                    "desc": ev.get("description", "")
                }
                for ev in factpack.get("evidence", [])
            ]
        }
        
        return f"""Generate an AgentSpec for agent_type: {agent_type}

FactPack:
{json.dumps(simplified_fp, indent=2)}

Requirements:
- name: Use lowercase-with-dashes format (e.g., "frontend-engineer")
- role: Descriptive role title
- mission: Clear, actionable mission statement
- allowed_paths: Paths relevant to the detected project type (e.g., src/, package.json for frontend)
- forbidden_paths: Sensitive paths (e.g., .env, .git/, node_modules/)
- workflows: At least 1 workflow with clear steps and verification
- commands: Copy from FactPack.commands (use actual command names)
- verification: Set both checks to true
- escalation_rules: Define at least 1 rule
- provenance: Reference evidence IDs from FactPack
- metadata: Include project_id and agent_type

Generate the AgentSpec now."""
