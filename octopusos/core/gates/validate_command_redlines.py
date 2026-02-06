"""Command Red Line Validator - enforces v0.8 red lines.

🚨 RED LINE C1: Command ≠ 可执行脚本
🚨 RED LINE C2: Command 不能绑定 Agent 执行
🚨 RED LINE C3: Command 必须声明副作用与风险
🚨 RED LINE C4: Command 必须可追溯 lineage
"""


class CommandRedlineViolation(Exception):
    """Exception raised when a command violates a red line."""

    pass


class CommandRedlineValidator:
    """Validator for command red lines (v0.8).

    Enforces 4 red lines:
    - C1: No executable payload
    - C2: No agent binding
    - C3: Must declare effects + risk
    - C4: Must have lineage
    """

    def __init__(self):
        """Initialize validator."""
        pass

    def validate(self, command_spec: dict) -> bool:
        """Validate command against all red lines.

        Args:
            command_spec: Command YAML/dict

        Returns:
            True if valid

        Raises:
            CommandRedlineViolation: If any red line is violated
        """
        self.validate_no_executable_payload(command_spec)
        self.validate_no_agent_binding(command_spec)
        self.validate_effects_and_risk(command_spec)
        self.validate_lineage(command_spec)
        return True

    def validate_no_executable_payload(self, command_spec: dict) -> bool:
        """🚨 RED LINE C1: Command must not contain executable payload.

        Forbidden fields:
        - shell, bash, powershell, python, code
        - run, execute, invoke, payload
        - script, command_line, exec

        Args:
            command_spec: Command dict

        Returns:
            True if valid

        Raises:
            CommandRedlineViolation: If contains forbidden fields
        """
        forbidden_keys = [
            "shell",
            "bash",
            "powershell",
            "python",
            "code",
            "run",
            "execute",
            "invoke",
            "payload",
            "script",
            "command_line",
            "exec",
            "executable",
        ]

        for key in forbidden_keys:
            if key in command_spec:
                raise CommandRedlineViolation(
                    f"RED LINE C1 VIOLATION: Command contains forbidden executable field '{key}'. "
                    f"Commands are definitions only, not executable scripts."
                )

        # Check constraints
        constraints = command_spec.get("constraints", {})
        if constraints.get("executable_payload") != "forbidden":
            raise CommandRedlineViolation(
                "RED LINE C1 VIOLATION: constraints.executable_payload must be 'forbidden'"
            )

        return True

    def validate_no_agent_binding(self, command_spec: dict) -> bool:
        """🚨 RED LINE C2: Command must not bind to specific agent for execution.

        Allowed:
        - recommended_roles (recommendation only)

        Forbidden:
        - assigned_agent_id, executor, tool_binding, agent_binding
        - bind_to_agent, execute_by, assigned_to

        Args:
            command_spec: Command dict

        Returns:
            True if valid

        Raises:
            CommandRedlineViolation: If contains agent binding
        """
        forbidden_keys = [
            "assigned_agent_id",
            "executor",
            "tool_binding",
            "agent_binding",
            "bind_to_agent",
            "execute_by",
            "assigned_to",
            "agent_executor",
        ]

        for key in forbidden_keys:
            if key in command_spec:
                raise CommandRedlineViolation(
                    f"RED LINE C2 VIOLATION: Command contains forbidden agent binding field '{key}'. "
                    f"Use 'recommended_roles' for recommendations only."
                )

        # Check constraints
        constraints = command_spec.get("constraints", {})
        if constraints.get("agent_binding") != "forbidden":
            raise CommandRedlineViolation(
                "RED LINE C2 VIOLATION: constraints.agent_binding must be 'forbidden'"
            )

        return True

    def validate_effects_and_risk(self, command_spec: dict) -> bool:
        """🚨 RED LINE C3: Command must declare side effects and risk.

        Required fields:
        - effects (array with scope/kind/description)
        - risk_level (low/medium/high)
        - evidence_required (boolean)

        Args:
            command_spec: Command dict

        Returns:
            True if valid

        Raises:
            CommandRedlineViolation: If missing required fields
        """
        # Check effects
        if "effects" not in command_spec:
            raise CommandRedlineViolation(
                "RED LINE C3 VIOLATION: Command must have 'effects' field"
            )

        effects = command_spec["effects"]
        if not isinstance(effects, list) or len(effects) == 0:
            raise CommandRedlineViolation(
                "RED LINE C3 VIOLATION: 'effects' must be a non-empty array"
            )

        # Validate each effect
        for i, effect in enumerate(effects):
            if not isinstance(effect, dict):
                raise CommandRedlineViolation(
                    f"RED LINE C3 VIOLATION: effects[{i}] must be an object"
                )

            required_effect_fields = ["scope", "kind", "description"]
            for field in required_effect_fields:
                if field not in effect:
                    raise CommandRedlineViolation(
                        f"RED LINE C3 VIOLATION: effects[{i}] missing required field '{field}'"
                    )

        # Check risk_level
        if "risk_level" not in command_spec:
            raise CommandRedlineViolation(
                "RED LINE C3 VIOLATION: Command must have 'risk_level' field"
            )

        risk_level = command_spec["risk_level"]
        if risk_level not in ["low", "medium", "high"]:
            raise CommandRedlineViolation(
                f"RED LINE C3 VIOLATION: risk_level must be 'low', 'medium', or 'high', got '{risk_level}'"
            )

        # Check evidence_required
        if "evidence_required" not in command_spec:
            raise CommandRedlineViolation(
                "RED LINE C3 VIOLATION: Command must have 'evidence_required' field"
            )

        evidence_required = command_spec["evidence_required"]
        if not isinstance(evidence_required, bool):
            raise CommandRedlineViolation(
                f"RED LINE C3 VIOLATION: evidence_required must be boolean, got {type(evidence_required)}"
            )

        return True

    def validate_lineage(self, command_spec: dict) -> bool:
        """🚨 RED LINE C4: Command must have lineage information.

        Required fields:
        - lineage.introduced_in (v0.8 format)
        - lineage.derived_from (null or command ID)
        - lineage.supersedes (array, can be empty)

        Args:
            command_spec: Command dict

        Returns:
            True if valid

        Raises:
            CommandRedlineViolation: If lineage incomplete
        """
        if "lineage" not in command_spec:
            raise CommandRedlineViolation(
                "RED LINE C4 VIOLATION: Command must have 'lineage' field"
            )

        lineage = command_spec["lineage"]
        if not isinstance(lineage, dict):
            raise CommandRedlineViolation(
                "RED LINE C4 VIOLATION: 'lineage' must be an object"
            )

        # Check required fields
        required_fields = ["introduced_in", "derived_from", "supersedes"]
        for field in required_fields:
            if field not in lineage:
                raise CommandRedlineViolation(
                    f"RED LINE C4 VIOLATION: lineage missing required field '{field}'"
                )

        # Validate introduced_in format
        introduced_in = lineage["introduced_in"]
        if not isinstance(introduced_in, str) or not introduced_in.startswith("v"):
            raise CommandRedlineViolation(
                f"RED LINE C4 VIOLATION: lineage.introduced_in must be in format 'vX.Y', got '{introduced_in}'"
            )

        # Validate derived_from
        derived_from = lineage["derived_from"]
        if derived_from is not None and not isinstance(derived_from, str):
            raise CommandRedlineViolation(
                f"RED LINE C4 VIOLATION: lineage.derived_from must be null or string, got {type(derived_from)}"
            )

        # Validate supersedes
        supersedes = lineage["supersedes"]
        if not isinstance(supersedes, list):
            raise CommandRedlineViolation(
                f"RED LINE C4 VIOLATION: lineage.supersedes must be an array, got {type(supersedes)}"
            )

        return True
