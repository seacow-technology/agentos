"""Registry Query Service - Query ContentRegistry for matching workflows/agents/commands.

RED LINE: Only query registry, no fabrication.
"""

from typing import List, Dict, Optional
from agentos.core.content.registry import ContentRegistry


class RegistryQueryService:
    """Query ContentRegistry to find matching content.
    
    RED LINE: Never fabricate content IDs. If not found in registry, return empty list.
    """
    
    # Known workflow keywords mapping
    WORKFLOW_KEYWORDS = {
        "feature_implementation": ["feature", "implement", "develop", "build", "new"],
        "bug_fix": ["bug", "fix", "issue", "problem", "error"],
        "refactoring": ["refactor", "cleanup", "reorganize", "restructure"],
        "documentation": ["doc", "documentation", "readme", "guide", "comment"],
        "testing_strategy": ["test", "testing", "qa", "quality"],
        "code_review": ["review", "审查"],
        "api_design": ["api", "endpoint", "interface"],
        "database_migration": ["database", "migration", "schema", "table"],
        "security_review": ["security", "auth", "permission", "encrypt"],
        "performance_optimization": ["performance", "optimize", "speed", "latency"],
        "architectural_evolution": ["architecture", "design", "pattern"],
        "deployment_pipeline": ["deploy", "ci", "cd", "pipeline"],
    }
    
    # Known agent keywords mapping
    AGENT_KEYWORDS = {
        "backend_engineer": ["backend", "api", "server", "database"],
        "frontend_engineer": ["frontend", "ui", "component", "page"],
        "qa_engineer": ["test", "testing", "qa", "quality"],
        "devops_engineer": ["deploy", "ci", "cd", "infra", "ops"],
        "security_engineer": ["security", "auth", "permission"],
        "technical_writer": ["doc", "documentation", "guide", "readme"],
        "architect": ["architecture", "design", "pattern"],
        "product_manager": ["requirement", "feature", "product"],
    }
    
    # Known command keywords mapping (simplified - actual commands are in registry)
    COMMAND_KEYWORDS = {
        "git": ["commit", "branch", "merge", "rebase", "git"],
        "test": ["test", "jest", "pytest", "unit"],
        "lint": ["lint", "eslint", "pylint", "format"],
        "documentation": ["doc", "comment", "jsdoc", "docstring"],
        "api": ["api", "endpoint", "route", "controller"],
        "database": ["database", "migration", "schema", "query"],
    }
    
    def __init__(self, registry: ContentRegistry):
        """Initialize registry query service.
        
        Args:
            registry: ContentRegistry instance
        """
        self.registry = registry
    
    def find_matching_workflows(self, parsed_nl: dict) -> List[dict]:
        """Find matching workflows from registry (v0.6 - 18 workflows).
        
        RED LINE: Only return workflows that exist in registry.
        
        Args:
            parsed_nl: Parsed NL components
        
        Returns:
            List of matching workflow dicts with metadata
        """
        # Get all active workflows from registry
        try:
            all_workflows = self.registry.list(type_="workflow", status="active", limit=100)
        except Exception as e:
            print(f"Warning: Failed to query workflows: {e}")
            return []
        
        if not all_workflows:
            return []
        
        # Score each workflow
        scored_workflows = []
        for workflow in all_workflows:
            score = self._score_workflow(workflow, parsed_nl)
            if score > 0:
                scored_workflows.append({
                    "workflow": workflow,
                    "score": score,
                    "reason": self._generate_workflow_reason(workflow, parsed_nl)
                })
        
        # Sort by score and return top matches
        scored_workflows.sort(key=lambda x: x["score"], reverse=True)
        return scored_workflows[:5]  # Top 5 workflows
    
    def find_matching_agents(self, parsed_nl: dict) -> List[dict]:
        """Find matching agents from registry (v0.7 - 13 agents).
        
        RED LINE: Only return agents that exist in registry.
        
        Args:
            parsed_nl: Parsed NL components
        
        Returns:
            List of matching agent dicts with metadata
        """
        try:
            all_agents = self.registry.list(type_="agent", status="active", limit=100)
        except Exception as e:
            print(f"Warning: Failed to query agents: {e}")
            return []
        
        if not all_agents:
            return []
        
        # Score each agent
        scored_agents = []
        for agent in all_agents:
            score = self._score_agent(agent, parsed_nl)
            if score > 0:
                scored_agents.append({
                    "agent": agent,
                    "score": score,
                    "role": self._infer_agent_role(agent, parsed_nl),
                    "reason": self._generate_agent_reason(agent, parsed_nl)
                })
        
        # Sort by score and return top matches
        scored_agents.sort(key=lambda x: x["score"], reverse=True)
        return scored_agents[:5]  # Top 5 agents
    
    def find_matching_commands(self, parsed_nl: dict, selected_agents: List[dict]) -> List[dict]:
        """Find matching commands from registry (v0.8 - 40 commands).
        
        RED LINE: Only return commands that exist in registry.
        
        Args:
            parsed_nl: Parsed NL components
            selected_agents: List of selected agents (to filter relevant commands)
        
        Returns:
            List of matching command dicts with metadata
        """
        try:
            all_commands = self.registry.list(type_="command", status="active", limit=200)
        except Exception as e:
            print(f"Warning: Failed to query commands: {e}")
            return []
        
        if not all_commands:
            return []
        
        # Score each command
        scored_commands = []
        for command in all_commands:
            score = self._score_command(command, parsed_nl, selected_agents)
            if score > 0:
                scored_commands.append({
                    "command": command,
                    "score": score,
                    "reason": self._generate_command_reason(command, parsed_nl)
                })
        
        # Sort by score and return top matches
        scored_commands.sort(key=lambda x: x["score"], reverse=True)
        return scored_commands[:10]  # Top 10 commands
    
    def _score_workflow(self, workflow: dict, parsed_nl: dict) -> float:
        """Score a workflow based on NL input."""
        score = 0.0
        workflow_id = workflow.get("id", "")
        workflow_spec = workflow.get("spec", {})
        
        goal = parsed_nl.get("goal", "").lower()
        actions = [a.lower() for a in parsed_nl.get("actions", [])]
        
        # Match workflow ID with keywords
        for wf_key, keywords in self.WORKFLOW_KEYWORDS.items():
            if wf_key in workflow_id:
                for keyword in keywords:
                    if keyword in goal or any(keyword in action for action in actions):
                        score += 1.0
        
        # Match workflow description/name
        wf_name = workflow_spec.get("name", "").lower()
        wf_desc = workflow_spec.get("description", "").lower()
        
        for action in actions:
            if action in wf_name or action in wf_desc:
                score += 0.5
        
        return score
    
    def _score_agent(self, agent: dict, parsed_nl: dict) -> float:
        """Score an agent based on NL input."""
        score = 0.0
        agent_id = agent.get("id", "")
        agent_spec = agent.get("spec", {})
        
        areas = parsed_nl.get("areas", [])
        
        # Match agent ID with keywords
        for agent_key, keywords in self.AGENT_KEYWORDS.items():
            if agent_key in agent_id:
                for keyword in keywords:
                    if keyword in " ".join(areas).lower():
                        score += 1.0
        
        # Match agent role/expertise
        agent_role = agent_spec.get("role", "").lower()
        for area in areas:
            if area in agent_role:
                score += 0.5
        
        return score
    
    def _score_command(self, command: dict, parsed_nl: dict, selected_agents: List[dict]) -> float:
        """Score a command based on NL input and selected agents."""
        score = 0.0
        command_id = command.get("id", "")
        command_spec = command.get("spec", {})
        
        actions = [a.lower() for a in parsed_nl.get("actions", [])]
        
        # Match command with actions
        cmd_name = command_spec.get("name", "").lower()
        for action in actions:
            if any(word in cmd_name for word in action.split()):
                score += 1.0
        
        # Boost score if command is relevant to selected agents
        for agent in selected_agents:
            agent_id = agent.get("agent", {}).get("id", "")
            # Simple heuristic: if agent and command share keywords
            if any(keyword in agent_id for keyword in command_id.split("_")):
                score += 0.3
        
        return score
    
    def _generate_workflow_reason(self, workflow: dict, parsed_nl: dict) -> str:
        """Generate reason for workflow selection."""
        workflow_id = workflow.get("id", "")
        goal = parsed_nl.get("goal", "")
        return f"Workflow '{workflow_id}' selected for goal: {goal[:100]}"
    
    def _generate_agent_reason(self, agent: dict, parsed_nl: dict) -> str:
        """Generate reason for agent selection."""
        agent_id = agent.get("id", "")
        areas = ", ".join(parsed_nl.get("areas", []))
        return f"Agent '{agent_id}' selected for areas: {areas}"
    
    def _generate_command_reason(self, command: dict, parsed_nl: dict) -> str:
        """Generate reason for command selection."""
        command_id = command.get("id", "")
        actions = parsed_nl.get("actions", [])
        action_summary = actions[0][:100] if actions else "specified actions"
        return f"Command '{command_id}' selected for: {action_summary}"
    
    def _infer_agent_role(self, agent: dict, parsed_nl: dict) -> str:
        """Infer agent role based on context."""
        agent_spec = agent.get("spec", {})
        return agent_spec.get("role", "contributor")
