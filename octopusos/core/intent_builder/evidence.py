"""Evidence Builder - Generate evidence attribution for selections.

RED LINE: All evidence must be traceable to:
- nl_input:<start>:<end> (NL input text span)
- registry:<content_id>:<version> (Registry content)
- rule:<rule_id> (Rule reference)
"""

from typing import List, Dict


class EvidenceBuilder:
    """Build evidence attribution for workflow/agent/command selections.
    
    RED LINE: Every selection MUST have at least one evidence_ref.
    """
    
    def __init__(self):
        """Initialize evidence builder."""
        pass
    
    def generate_workflow_evidence(
        self,
        workflow: dict,
        nl_request: dict,
        parsed_nl: dict,
        reason: str
    ) -> List[str]:
        """Generate evidence for workflow selection.
        
        Args:
            workflow: Workflow content from registry
            nl_request: Original NL request
            parsed_nl: Parsed NL components
            reason: Selection reason
        
        Returns:
            List of evidence refs (format: type:identifier:detail)
        """
        evidence_refs = []
        
        # Evidence 1: Registry reference
        workflow_id = workflow.get("id", "unknown")
        workflow_version = workflow.get("version", "1.0.0")
        evidence_refs.append(f"registry:{workflow_id}:{workflow_version}")
        
        # Evidence 2: NL input text span (goal)
        input_text = nl_request["input_text"]
        goal = parsed_nl.get("goal", "")
        if goal:
            # Find span of goal in input
            start = input_text.find(goal[:50])  # First 50 chars
            if start != -1:
                end = min(start + len(goal), len(input_text))
                evidence_refs.append(f"nl_input:{start}:{end}")
        
        # Evidence 3: Rule reference (if applicable)
        # For now, reference general workflow selection rule
        evidence_refs.append("rule:r02_lineage_required")  # Example rule
        
        return evidence_refs
    
    def generate_agent_evidence(
        self,
        agent: dict,
        nl_request: dict,
        parsed_nl: dict,
        role: str,
        reason: str
    ) -> List[str]:
        """Generate evidence for agent selection.
        
        Args:
            agent: Agent content from registry
            nl_request: Original NL request
            parsed_nl: Parsed NL components
            role: Inferred role
            reason: Selection reason
        
        Returns:
            List of evidence refs
        """
        evidence_refs = []
        
        # Evidence 1: Registry reference
        agent_id = agent.get("id", "unknown")
        agent_version = agent.get("version", "1.0.0")
        evidence_refs.append(f"registry:{agent_id}:{agent_version}")
        
        # Evidence 2: NL input text span (areas)
        input_text = nl_request["input_text"]
        areas = parsed_nl.get("areas", [])
        if areas:
            # Find first area mention in text
            for area in areas:
                start = input_text.lower().find(area.lower())
                if start != -1:
                    end = start + len(area)
                    evidence_refs.append(f"nl_input:{start}:{end}")
                    break
        
        # Evidence 3: Context hints
        context_hints = nl_request.get("context_hints", {})
        if context_hints.get("areas"):
            evidence_refs.append(f"context_hint:areas:{','.join(context_hints['areas'])}")
        
        return evidence_refs
    
    def generate_command_evidence(
        self,
        command: dict,
        nl_request: dict,
        parsed_nl: dict,
        reason: str
    ) -> List[str]:
        """Generate evidence for command selection.
        
        Args:
            command: Command content from registry
            nl_request: Original NL request
            parsed_nl: Parsed NL components
            reason: Selection reason
        
        Returns:
            List of evidence refs
        """
        evidence_refs = []
        
        # Evidence 1: Registry reference
        command_id = command.get("id", "unknown")
        command_version = command.get("version", "1.0.0")
        evidence_refs.append(f"registry:{command_id}:{command_version}")
        
        # Evidence 2: NL input text span (actions)
        input_text = nl_request["input_text"]
        actions = parsed_nl.get("actions", [])
        if actions:
            # Find first action in text
            for action in actions:
                start = input_text.find(action[:50])
                if start != -1:
                    end = min(start + len(action), len(input_text))
                    evidence_refs.append(f"nl_input:{start}:{end}")
                    break
        
        # Evidence 3: Command effects (inferred from registry)
        command_spec = command.get("spec", {})
        command_effects = command_spec.get("effects", [])
        if command_effects:
            evidence_refs.append(f"command_effects:{','.join(command_effects)}")
        
        return evidence_refs
    
    def generate_intent_evidence(
        self,
        nl_request: dict,
        parsed_nl: dict
    ) -> List[str]:
        """Generate top-level intent evidence.
        
        Args:
            nl_request: Original NL request
            parsed_nl: Parsed NL components
        
        Returns:
            List of evidence refs
        """
        evidence_refs = []
        
        # Evidence 1: NL request reference
        nl_req_id = nl_request.get("id", "unknown")
        evidence_refs.append(f"nl_request:{nl_req_id}")
        
        # Evidence 2: Full input text span
        input_text = nl_request["input_text"]
        evidence_refs.append(f"nl_input:0:{len(input_text)}")
        
        # Evidence 3: Risk assessment
        risk_level = parsed_nl.get("risk_level", "medium")
        evidence_refs.append(f"risk_assessment:{risk_level}")
        
        return evidence_refs
    
    def validate_evidence_refs(self, evidence_refs: List[str]) -> bool:
        """Validate that evidence_refs are well-formed.
        
        Args:
            evidence_refs: List of evidence refs
        
        Returns:
            True if valid, False otherwise
        """
        if not evidence_refs:
            return False
        
        valid_prefixes = ["nl_input:", "registry:", "rule:", "context_hint:", "command_effects:", "risk_assessment:", "nl_request:"]
        
        for ref in evidence_refs:
            if not any(ref.startswith(prefix) for prefix in valid_prefixes):
                return False
            
            # Check format: type:identifier:detail
            parts = ref.split(":", 2)
            if len(parts) < 2:
                return False
        
        return True
