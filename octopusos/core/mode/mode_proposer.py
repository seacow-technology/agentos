"""
ModeProposer - LLM-driven mode selection

This module uses LLM structured outputs to propose execution modes
based on natural language understanding, rather than keyword rules.

IMPORTANT: Mode selection is a PROPOSAL, not a DECISION.
- The system may override the proposed mode
- The system may split the pipeline
- The system may abort execution
- Final authority remains with Gate/Verifier, not the proposer

The proposer's job is to understand intent and suggest,
not to make binding decisions.
"""

from __future__ import annotations
import json
import os
from typing import Optional
from dataclasses import dataclass

from openai import OpenAI

from ..schemas import ModeSelection


@dataclass
class ModeProposalContext:
    """Context for mode proposal"""
    nl_input: str
    available_modes: list[str]
    additional_context: Optional[str] = None


class ModeProposer:
    """
    LLM-driven mode proposer
    
    Uses OpenAI structured outputs to understand user intent
    and propose appropriate mode pipeline.
    
    Unlike ModeSelector (rule-based), this uses AI understanding
    for more flexible and nuanced mode selection.
    
    IMPORTANT DISCLAIMER:
    - This is a PROPOSER, not a DECISION-MAKER
    - System retains final authority to override/modify/reject
    - Proposals are subject to Gate/Verifier validation
    - Do not treat confidence as "probability of correctness"
    """
    
    DEFAULT_MODES = [
        "planning",
        "implementation",
        "design",
        "ops",
        "debug",
        "chat",
        "test",
        "release"
    ]
    
    MODE_DESCRIPTIONS = {
        "planning": "生成计划,禁止diff - 用于设计方案和拆解步骤",
        "implementation": "实施代码,允许diff - 用于实际编码和文件修改",
        "design": "设计方案,禁止diff - 用于架构设计和技术选型",
        "ops": "运维操作,禁止diff - 用于部署、监控等运维任务",
        "debug": "调试分析,禁止diff - 用于问题诊断和根因分析",
        "chat": "聊天模式,禁止diff - 用于只读分析和问答",
        "test": "测试模式,允许有限diff - 用于测试相关操作",
        "release": "发布模式,禁止diff - 用于版本发布流程"
    }
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize ModeProposer
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: OpenAI model to use
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
    
    def propose_mode(
        self,
        nl_input: str,
        available_modes: Optional[list[str]] = None,
        additional_context: Optional[str] = None
    ) -> ModeSelection:
        """
        Propose mode selection from natural language input
        
        Args:
            nl_input: User's natural language request
            available_modes: List of available modes (defaults to all modes)
            additional_context: Additional context for better understanding
            
        Returns:
            ModeSelection with proposed pipeline and confidence
            
        Example:
            >>> proposer = ModeProposer()
            >>> selection = proposer.propose_mode("创建一个landing page")
            >>> selection.pipeline
            ['planning', 'implementation']
            >>> selection.confidence
            0.92
        """
        if available_modes is None:
            available_modes = self.DEFAULT_MODES
        
        context = ModeProposalContext(
            nl_input=nl_input,
            available_modes=available_modes,
            additional_context=additional_context
        )
        
        system_prompt = self._build_system_prompt(context)
        user_prompt = self._build_user_prompt(context)
        
        # Define schema for structured output
        schema = {
            "type": "object",
            "properties": {
                "primary_mode": {
                    "type": "string",
                    "description": "Primary mode for this execution",
                    "enum": available_modes
                },
                "pipeline": {
                    "type": "array",
                    "description": "Ordered list of modes to execute",
                    "items": {
                        "type": "string",
                        "enum": available_modes
                    },
                    "minItems": 1
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence in this selection (0.0-1.0)",
                    "minimum": 0.0,
                    "maximum": 1.0
                },
                "reason": {
                    "type": "string",
                    "description": "Human-readable explanation for audit trail"
                }
            },
            "required": ["primary_mode", "pipeline", "confidence", "reason"],
            "additionalProperties": False
        }
        
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
                    "name": "mode_selection",
                    "strict": True,
                    "schema": schema
                }
            },
            temperature=0.3  # Lower temperature for more consistent results
        )
        
        # Parse response
        content = response.choices[0].message.content
        if not content:
            raise ValueError("No content in OpenAI response")
        
        data = json.loads(content)
        
        return ModeSelection(
            primary_mode=data["primary_mode"],
            pipeline=data["pipeline"],
            confidence=data["confidence"],
            reason=data["reason"]
        )
    
    def _build_system_prompt(self, context: ModeProposalContext) -> str:
        """Build system prompt for mode proposal"""
        mode_docs = "\n".join([
            f"- {mode}: {self.MODE_DESCRIPTIONS.get(mode, 'No description')}"
            for mode in context.available_modes
        ])
        
        return f"""You are AgentOS's Mode Proposer.

Your task is to understand the user's request and propose the best execution mode pipeline.

CRITICAL DISCLAIMER:
- You are a PROPOSER, not a DECISION-MAKER
- Your suggestions may be overridden by the system
- The system retains final authority on execution
- Your role is to interpret intent, not to guarantee execution path

AVAILABLE MODES:
{mode_docs}

PIPELINE RULES:
1. planning → implementation: Common pattern for creating new things
2. debug → implementation: Common pattern for fixing bugs
3. chat: For read-only analysis and questions
4. Only implementation mode can produce diffs
5. planning/design/debug modes MUST NOT produce diffs

CONFIDENCE GUIDELINES:
- 0.9-1.0: Very clear intent with exact mode match
- 0.7-0.9: Clear intent with reasonable mode match
- 0.5-0.7: Ambiguous intent but reasonable guess
- 0.3-0.5: Very ambiguous, low confidence
- 0.0-0.3: Cannot determine, recommend fallback

OUTPUT:
- primary_mode: The main mode for this request
- pipeline: Ordered execution sequence (your proposal)
- confidence: Your confidence level (0.0-1.0)
- reason: Clear explanation for audit trail

Be honest about confidence. Low confidence (<0.5) should trigger fallback to rule-based selector.

IMPORTANT: Your mode selection is a PROPOSAL. The system may:
- Override your choice
- Split your pipeline differently
- Abort execution for safety
- Apply additional constraints you're unaware of
"""
    
    def _build_user_prompt(self, context: ModeProposalContext) -> str:
        """Build user prompt"""
        prompt = f"""User request: "{context.nl_input}"

Analyze this request and propose the best mode pipeline.

Consider:
- What is the user trying to achieve?
- Does it require code changes (implementation)?
- Does it need planning first?
- Is it debugging/analysis only?
- Is it a read-only query?
"""
        
        if context.additional_context:
            prompt += f"\nAdditional context: {context.additional_context}"
        
        return prompt


# Convenience function
def propose_mode(
    nl_input: str,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini"
) -> ModeSelection:
    """
    Convenience function to propose mode from natural language
    
    Args:
        nl_input: User's natural language request
        api_key: OpenAI API key
        model: OpenAI model to use
        
    Returns:
        ModeSelection
    """
    proposer = ModeProposer(api_key=api_key, model=model)
    return proposer.propose_mode(nl_input)
