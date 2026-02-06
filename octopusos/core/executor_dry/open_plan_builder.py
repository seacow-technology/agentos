"""
OpenPlanBuilder - LLM-driven execution plan generator

Generates OpenPlan from user intent using LLM structured outputs.
This allows AI to freely propose execution steps while the system
validates structural boundaries.
"""

from __future__ import annotations
import json
import os
from typing import Optional, Dict, Any
from datetime import datetime

from openai import OpenAI

from ..schemas import (
    OpenPlan,
    ModeSelection,
    PlanStep,
    ProposedAction,
    Artifact,
    get_available_kinds
)


class OpenPlanBuilder:
    """
    LLM-driven Open Plan builder
    
    Generates execution plans from user intent and mode selection,
    allowing AI to freely decompose tasks into steps and actions.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize OpenPlanBuilder
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: OpenAI model to use
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
    
    def build(
        self,
        goal: str,
        mode_selection: ModeSelection,
        context: Optional[Dict[str, Any]] = None
    ) -> OpenPlan:
        """
        Build OpenPlan from goal and mode selection
        
        Args:
            goal: User's goal/request
            mode_selection: Selected mode pipeline
            context: Additional context (project info, constraints, etc.)
            
        Returns:
            OpenPlan with generated steps and actions
            
        Example:
            >>> builder = OpenPlanBuilder()
            >>> selection = ModeSelection(
            ...     primary_mode="planning",
            ...     pipeline=["planning", "implementation"],
            ...     confidence=0.9,
            ...     reason="Creating new feature"
            ... )
            >>> plan = builder.build("创建一个landing page", selection)
            >>> len(plan.steps)
            5
        """
        system_prompt = self._build_system_prompt(mode_selection, context)
        user_prompt = self._build_user_prompt(goal, mode_selection, context)
        
        # Define schema for structured output
        schema = self._build_plan_schema()
        
        # Call OpenAI with structured outputs
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "open_plan",
                    "strict": True,
                    "schema": schema
                }
            },
            temperature=0.4  # Balanced creativity and consistency
        )
        
        # Parse response
        content = response.choices[0].message.content
        if not content:
            raise ValueError("No content in OpenAI response")
        
        plan_data = json.loads(content)
        
        # Add metadata
        plan_data["metadata"] = {
            "plan_id": f"openplan_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "generated_at": datetime.now().isoformat(),
            "model": self.model,
            "builder_version": "1.0.0"
        }
        
        # Inject mode_selection (LLM doesn't need to regenerate it)
        plan_data["mode_selection"] = mode_selection.to_dict()
        
        return OpenPlan.from_dict(plan_data)
    
    def _build_system_prompt(
        self,
        mode_selection: ModeSelection,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build system prompt"""
        available_kinds = get_available_kinds()
        kinds_doc = ", ".join(available_kinds)
        
        # Mode-specific rules
        mode_rules = []
        if "planning" in mode_selection.pipeline:
            mode_rules.append("- Planning phase: NO file create/update/delete operations")
            mode_rules.append("- Planning phase: Only declare files with operation='declare'")
        
        if "implementation" in mode_selection.pipeline:
            mode_rules.append("- Implementation phase: MUST include file operations")
            mode_rules.append("- Implementation phase: Can use operation='create' or 'update'")
        
        mode_rules_str = "\n".join(mode_rules) if mode_rules else "- No specific mode restrictions"
        
        project_context = ""
        if context:
            if "project_type" in context:
                project_context += f"\nProject type: {context['project_type']}"
            if "tech_stack" in context:
                project_context += f"\nTech stack: {', '.join(context['tech_stack'])}"
            if "constraints" in context:
                project_context += f"\nConstraints: {context['constraints']}"
        
        return f"""You are AgentOS's Open Plan Builder.

Your task is to decompose a user's goal into executable steps with concrete actions.

MODE PIPELINE: {' → '.join(mode_selection.pipeline)}
PRIMARY MODE: {mode_selection.primary_mode}

MODE-SPECIFIC RULES:
{mode_rules_str}

AVAILABLE ACTION KINDS:
{kinds_doc}

ACTION KIND DETAILS:
- command: {{cmd, args?, working_dir?, timeout?}}
- file: {{path, operation, intent?, content_hint?}}
  - operation must be: create, update, delete, or declare
  - Use 'declare' in planning phase (no actual content)
  - Use 'create'/'update' in implementation phase
- agent: {{agent_type, task, context?, inputs?}}
- check: {{check_type, target, expected?, threshold?}}
- rule: {{constraint, scope?, enforcement?}}
- note: {{message, level?}}
{project_context}

DECOMPOSITION PRINCIPLES:
1. Break goal into logical steps (3-10 steps ideal)
2. Each step should have clear intent and success criteria
3. Propose concrete actions (not vague descriptions)
4. Consider risks and dependencies
5. Declare artifacts that will be produced

OUTPUT REQUIREMENTS:
- steps: Array of steps with id, intent, proposed_actions
- Each action MUST have valid 'kind' and complete 'payload'
- success_criteria: How to verify each step
- risks: What could go wrong
- artifacts: Files/outputs that will be created

Be specific and actionable. This plan will be executed by the system.
"""
    
    def _build_user_prompt(
        self,
        goal: str,
        mode_selection: ModeSelection,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build user prompt"""
        prompt = f"""Goal: {goal}

Mode selection reason: {mode_selection.reason}
Confidence: {mode_selection.confidence}

Generate a detailed execution plan that:
1. Decomposes this goal into logical steps
2. Proposes concrete actions for each step
3. Respects the mode pipeline constraints
4. Is immediately executable

Remember:
- Planning mode: declare intent, don't modify files
- Implementation mode: make actual changes
- Each action must have a valid 'kind' and complete 'payload'
"""
        
        if context:
            prompt += f"\n\nAdditional context:\n{json.dumps(context, indent=2)}"
        
        return prompt
    
    def _build_plan_schema(self) -> Dict[str, Any]:
        """Build JSON schema for OpenPlan (without mode_selection)"""
        return {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "User's original goal restated"
                },
                "steps": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Step ID (e.g., S1, S2)"
                            },
                            "intent": {
                                "type": "string",
                                "description": "What this step aims to achieve"
                            },
                            "proposed_actions": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "kind": {
                                            "type": "string",
                                            "enum": get_available_kinds(),
                                            "description": "Action type"
                                        },
                                        "payload": {
                                            "type": "object",
                                            "description": "Action-specific parameters"
                                        }
                                    },
                                    "required": ["kind", "payload"],
                                    "additionalProperties": False
                                }
                            },
                            "success_criteria": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "How to verify this step succeeded"
                            },
                            "risks": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "What could go wrong"
                            }
                        },
                        "required": ["id", "intent", "proposed_actions"],
                        "additionalProperties": False
                    }
                },
                "artifacts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "role": {"type": "string"},
                            "notes": {"type": "string"}
                        },
                        "required": ["path", "role"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["goal", "steps"],
            "additionalProperties": False
        }


# Convenience function
def build_open_plan(
    goal: str,
    mode_selection: ModeSelection,
    context: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini"
) -> OpenPlan:
    """
    Convenience function to build OpenPlan
    
    Args:
        goal: User's goal/request
        mode_selection: Selected mode pipeline
        context: Additional context
        api_key: OpenAI API key
        model: OpenAI model to use
        
    Returns:
        OpenPlan
    """
    builder = OpenPlanBuilder(api_key=api_key, model=model)
    return builder.build(goal, mode_selection, context)
