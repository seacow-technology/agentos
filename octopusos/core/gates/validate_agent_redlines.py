"""Agent Red Line Validator - Gate helper for v0.7 Agent constraints.

🎯 PURPOSE: Pre-registration validation, NOT runtime enforcement.

This module is a **gate helper** that validates agent specifications BEFORE
they are registered to ContentRegistry. It is NOT a runtime enforcer.

🚨 RED LINE ENFORCEMENT ENTRY POINTS:
1. ContentRegistry.register() - validates during registration
2. scripts/register_agents.py - validates before batch registration  
3. CI/local gates - validates in development

This validator is called by the above entry points, NOT used directly at runtime.

Usage:
    from agentos.core.gates.validate_agent_redlines import AgentRedlineValidator
    
    validator = AgentRedlineValidator()
    is_valid, errors = validator.validate_all(agent_spec)
    if not is_valid:
        raise ValueError(f"Agent validation failed: {errors}")
"""

from typing import Any


class AgentRedlineViolation(Exception):
    """Raised when an agent violates a red line constraint during validation."""

    pass


class AgentRedlineValidator:
    """Validates v0.7 Agent red lines before registration.
    
    🎯 This is a GATE HELPER, not a runtime enforcer.
    
    Red lines are enforced at registration time, not at runtime.
    This class validates agent specifications against the 5 red lines:
    1. No execution
    2. No command ownership  
    3. Question-only interactions (v0.7 constraint)
    4. Single role (no mixing)
    5. Organizational model (not capability model)
    
    Note: Red lines #1, #2, #3 are v0.7 constraints that may evolve in v0.8+.
    Schema provides structure validation, this validator provides semantic validation.
    """

    # 🚨 RED LINE #5: Forbidden keywords in agent IDs (capability model indicators)
    FORBIDDEN_ID_KEYWORDS = [
        "gpt",
        "llm",
        "model",
        "ai",
        "ml",
        "bot",
        "assistant",
        "chatbot",
    ]

    # 🚨 RED LINE #4: Maximum responsibilities per agent (prevent role mixing)
    MAX_RESPONSIBILITIES = 5

    def __init__(self):
        """Initialize the red line validator (gate helper)."""
        pass

    def validate_all(self, agent_spec: dict) -> tuple[bool, list[str]]:
        """Validate all red lines for an agent spec.
        
        Args:
            agent_spec: Agent specification dict
            
        Returns:
            (is_valid, list_of_error_messages)
        """
        errors = []

        # Red Line #1: No execution
        try:
            self.validate_no_execution(agent_spec)
        except AgentRedlineViolation as e:
            errors.append(str(e))

        # Red Line #2: No commands
        try:
            self.validate_no_commands(agent_spec)
        except AgentRedlineViolation as e:
            errors.append(str(e))

        # Red Line #3: Question only
        try:
            self.validate_question_only(agent_spec)
        except AgentRedlineViolation as e:
            errors.append(str(e))

        # Red Line #4: Single role
        try:
            self.validate_single_role(agent_spec)
        except AgentRedlineViolation as e:
            errors.append(str(e))

        # Red Line #5: Organizational model
        try:
            self.validate_organizational_model(agent_spec)
        except AgentRedlineViolation as e:
            errors.append(str(e))

        return len(errors) == 0, errors

    def validate_no_execution(self, agent_spec: dict) -> bool:
        """🚨 RED LINE #1: Agent does NOT execute Workflow.
        
        Validates that:
        - constraints.execution = "forbidden" (v0.7 requirement)
        - No 'execute', 'run', 'apply' fields exist
        
        Note: This is a v0.7 constraint. Future versions may allow different values,
        but validation logic here can evolve independently of schema.
        
        Args:
            agent_spec: Agent specification dict
            
        Returns:
            True if valid
            
        Raises:
            AgentRedlineViolation: If execution is not properly constrained
        """
        # Check constraints field
        constraints = agent_spec.get("constraints", {})
        execution = constraints.get("execution")

        if execution != "forbidden":
            raise AgentRedlineViolation(
                f"🚨 RED LINE #1 VIOLATION: Agent execution must be 'forbidden', got '{execution}'"
            )

        # Check for execution-related fields (should not exist)
        forbidden_fields = ["execute", "run", "apply", "executor", "execution_logic"]
        for field in forbidden_fields:
            if field in agent_spec:
                raise AgentRedlineViolation(
                    f"🚨 RED LINE #1 VIOLATION: Agent must not have '{field}' field"
                )

        return True

    def validate_no_commands(self, agent_spec: dict) -> bool:
        """🚨 RED LINE #2: Agent does NOT own Commands.
        
        Validates that:
        - constraints.command_ownership = "forbidden" (v0.7 requirement)
        - No 'commands', 'actions', 'tools' fields exist
        
        Note: This validates the absence of command fields, which cannot be
        fully expressed in JSON Schema. This is why we need runtime validation.
        
        Args:
            agent_spec: Agent specification dict
            
        Returns:
            True if valid
            
        Raises:
            AgentRedlineViolation: If command ownership is not properly constrained
        """
        # Check constraints field
        constraints = agent_spec.get("constraints", {})
        command_ownership = constraints.get("command_ownership")

        if command_ownership != "forbidden":
            raise AgentRedlineViolation(
                f"🚨 RED LINE #2 VIOLATION: Agent command_ownership must be 'forbidden', got '{command_ownership}'"
            )

        # Check for command-related fields (should not exist)
        forbidden_fields = ["commands", "actions", "tools", "command_bindings"]
        for field in forbidden_fields:
            if field in agent_spec:
                raise AgentRedlineViolation(
                    f"🚨 RED LINE #2 VIOLATION: Agent must not have '{field}' field"
                )

        return True

    def validate_question_only(self, agent_spec: dict) -> bool:
        """🚨 RED LINE #3: Agent ONLY allows questions (v0.7 constraint).
        
        Validates that:
        - allowed_interactions = ["question"] (v0.7 requirement)
        - No other interaction types exist
        
        Note: This is a v0.7-specific constraint. Future versions may support
        additional interaction types (approve, execute, etc.). This validator
        can be updated independently of schema.
        
        Args:
            agent_spec: Agent specification dict
            
        Returns:
            True if valid
            
        Raises:
            AgentRedlineViolation: If interactions other than 'question' are present
        """
        allowed_interactions = agent_spec.get("allowed_interactions", [])

        # Must have exactly one item: "question"
        if allowed_interactions != ["question"]:
            raise AgentRedlineViolation(
                f"🚨 RED LINE #3 VIOLATION: Agent must only allow 'question' interaction, got {allowed_interactions}"
            )

        # Check for forbidden interaction types
        forbidden_interactions = ["approve", "override", "manual_action", "execute"]
        for interaction in forbidden_interactions:
            if interaction in agent_spec:
                raise AgentRedlineViolation(
                    f"🚨 RED LINE #3 VIOLATION: Agent must not have '{interaction}' interaction"
                )

        return True

    def validate_single_role(self, agent_spec: dict) -> bool:
        """🚨 RED LINE #4: One Agent = One Role (no mixing).
        
        Validates that:
        - Only one category is specified
        - Responsibilities count is reasonable (suggests <= 5 for v0.7)
        - No "full_stack", "universal" naming patterns
        
        Note: The "5 responsibilities" limit is a heuristic for v0.7.
        This is semantic validation that cannot be expressed in schema alone.
        
        Args:
            agent_spec: Agent specification dict
            
        Returns:
            True if valid
            
        Raises:
            AgentRedlineViolation: If role mixing is detected
        """
        # Check category (must be single string, not list)
        category = agent_spec.get("category")
        if isinstance(category, list):
            raise AgentRedlineViolation(
                f"🚨 RED LINE #4 VIOLATION: Agent must have single category, got list: {category}"
            )

        # Check responsibilities count
        responsibilities = agent_spec.get("responsibilities", [])
        if len(responsibilities) > self.MAX_RESPONSIBILITIES:
            raise AgentRedlineViolation(
                f"🚨 RED LINE #4 VIOLATION: Agent has too many responsibilities ({len(responsibilities)} > {self.MAX_RESPONSIBILITIES}). "
                f"This indicates role mixing. Split into multiple agents."
            )

        # Check for forbidden role mixing patterns in agent ID
        agent_id = agent_spec.get("id", "").lower()
        forbidden_patterns = ["full_stack", "fullstack", "universal", "omnipotent", "all_in_one"]
        for pattern in forbidden_patterns:
            if pattern in agent_id:
                raise AgentRedlineViolation(
                    f"🚨 RED LINE #4 VIOLATION: Agent ID '{agent_id}' suggests role mixing (contains '{pattern}')"
                )

        # Check for forbidden role mixing patterns in description
        description = agent_spec.get("description", "").lower()
        forbidden_desc_patterns = ["all roles", "multiple roles", "full-stack", "do everything"]
        for pattern in forbidden_desc_patterns:
            if pattern in description:
                raise AgentRedlineViolation(
                    f"🚨 RED LINE #4 VIOLATION: Agent description suggests role mixing (contains '{pattern}')"
                )

        return True

    def validate_organizational_model(self, agent_spec: dict) -> bool:
        """🚨 RED LINE #5: Agent is organizational model, NOT capability model.
        
        Validates that:
        - Agent ID does not contain capability keywords (gpt, llm, model, ai, etc.)
        - Category is organizational, not technical capability
        - real_world_roles are referenced (semantic requirement)
        
        Note: This is semantic validation. Schema can enforce category enum,
        but cannot validate "agent ID doesn't contain 'gpt'". That's why we need
        this validator as a gate helper.
        
        Args:
            agent_spec: Agent specification dict
            
        Returns:
            True if valid
            
        Raises:
            AgentRedlineViolation: If agent is capability-focused
        """
        agent_id = agent_spec.get("id", "").lower()

        # Check for forbidden capability keywords in agent ID
        for keyword in self.FORBIDDEN_ID_KEYWORDS:
            if keyword in agent_id:
                raise AgentRedlineViolation(
                    f"🚨 RED LINE #5 VIOLATION: Agent ID '{agent_id}' contains capability keyword '{keyword}'. "
                    f"Agent must represent an organizational role, not an AI capability."
                )

        # Check category is organizational (not technical capability)
        category = agent_spec.get("category", "")
        valid_organizational_categories = [
            "product",
            "delivery",
            "design",
            "engineering",
            "data",
            "architecture",
            "quality",
            "security",
            "operations",
            "documentation",
            "leadership",
        ]
        if category not in valid_organizational_categories:
            raise AgentRedlineViolation(
                f"🚨 RED LINE #5 VIOLATION: Agent category '{category}' is not a valid organizational category. "
                f"Must be one of: {valid_organizational_categories}"
            )

        # Check for real-world role references in metadata (if exists)
        metadata = agent_spec.get("metadata", {})
        if "real_world_roles" in metadata:
            real_world_roles = metadata["real_world_roles"]
            if not real_world_roles or not isinstance(real_world_roles, list):
                raise AgentRedlineViolation(
                    f"🚨 RED LINE #5 VIOLATION: Agent must reference real-world job titles in metadata.real_world_roles"
                )

        return True

    def validate(self, agent_spec: dict) -> None:
        """Validate all red lines (raises exception if any violation).
        
        This is the main entry point for gate validation.
        Call this before registering an agent to ContentRegistry.
        
        Args:
            agent_spec: Agent specification dict
            
        Raises:
            AgentRedlineViolation: If any red line is violated
        """
        is_valid, errors = self.validate_all(agent_spec)
        if not is_valid:
            error_msg = "\n".join(errors)
            raise AgentRedlineViolation(
                f"Agent red line violations detected:\n\n{error_msg}\n\n"
                f"Agent ID: {agent_spec.get('id', 'unknown')}\n"
                f"Version: {agent_spec.get('version', 'unknown')}"
            )
