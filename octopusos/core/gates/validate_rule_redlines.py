"""Rule Red Line Validator - enforces v0.9 red lines.

🚨 RED LINE RL1: Rule 不包含执行指令
🚨 RED LINE RL2: Rule 必须可审计（evidence_required）
🚨 RED LINE RL3: Rule 必须可机器判定（predicate 结构化）
🚨 RED LINE RL4: Rule 必须声明适用范围（scope）
🚨 RED LINE RL5: Rule 必须有 lineage
"""


class RuleRedlineViolation(Exception):
    """Exception raised when a rule violates a red line."""

    pass


class RuleRedlineValidator:
    """Validator for rule red lines (v0.9).

    Enforces 5 red lines:
    - RL1: No execution payload
    - RL2: Evidence required (non-empty)
    - RL3: Machine-judgable predicate (structured when/then)
    - RL4: Scope declaration
    - RL5: Lineage required
    """

    def __init__(self):
        """Initialize validator."""
        pass

    def validate(self, rule_spec: dict) -> bool:
        """Validate rule against all red lines.

        Args:
            rule_spec: Rule YAML/dict

        Returns:
            True if valid

        Raises:
            RuleRedlineViolation: If any red line is violated
        """
        self.validate_no_execution(rule_spec)
        self.validate_evidence_required(rule_spec)
        self.validate_machine_judgable(rule_spec)
        self.validate_scope_declared(rule_spec)
        self.validate_lineage(rule_spec)
        return True

    def validate_no_execution(self, rule_spec: dict) -> bool:
        """🚨 RED LINE RL1: Rule must not contain execution payload.

        Forbidden fields:
        - execute, run, shell, bash, python, powershell
        - subprocess, command_line, script, exec

        Args:
            rule_spec: Rule dict

        Returns:
            True if valid

        Raises:
            RuleRedlineViolation: If contains forbidden fields
        """
        forbidden_keys = [
            "execute",
            "run",
            "shell",
            "bash",
            "python",
            "powershell",
            "subprocess",
            "command_line",
            "script",
            "exec",
        ]

        for key in forbidden_keys:
            if key in rule_spec:
                raise RuleRedlineViolation(
                    f"RED LINE RL1 VIOLATION: Rule contains forbidden execution field '{key}'. "
                    f"Rules are governance content only, not executable scripts."
                )

        # Check constraints
        constraints = rule_spec.get("constraints", {})
        if constraints.get("execution") != "forbidden":
            raise RuleRedlineViolation(
                "RED LINE RL1 VIOLATION: constraints.execution must be 'forbidden'"
            )

        return True

    def validate_evidence_required(self, rule_spec: dict) -> bool:
        """🚨 RED LINE RL2: Rule must declare evidence_required (non-empty).

        Required:
        - rule.evidence_required (array)
        - Must be non-empty

        Args:
            rule_spec: Rule dict

        Returns:
            True if valid

        Raises:
            RuleRedlineViolation: If evidence_required missing or empty
        """
        if "rule" not in rule_spec:
            raise RuleRedlineViolation(
                "RED LINE RL2 VIOLATION: Rule must have 'rule' field"
            )

        rule_obj = rule_spec["rule"]

        if "evidence_required" not in rule_obj:
            raise RuleRedlineViolation(
                "RED LINE RL2 VIOLATION: rule.evidence_required is required"
            )

        evidence_required = rule_obj["evidence_required"]

        if not isinstance(evidence_required, list):
            raise RuleRedlineViolation(
                f"RED LINE RL2 VIOLATION: rule.evidence_required must be array, got {type(evidence_required)}"
            )

        if len(evidence_required) == 0:
            raise RuleRedlineViolation(
                "RED LINE RL2 VIOLATION: rule.evidence_required must be non-empty (declare at least one evidence type)"
            )

        return True

    def validate_machine_judgable(self, rule_spec: dict) -> bool:
        """🚨 RED LINE RL3: Rule must be machine-judgable (structured predicate).

        Required:
        - rule.when (object, not string)
        - rule.then (object, not string)
        - rule.severity (enum: info|warn|error|block)

        Args:
            rule_spec: Rule dict

        Returns:
            True if valid

        Raises:
            RuleRedlineViolation: If when/then not structured or severity missing
        """
        if "rule" not in rule_spec:
            raise RuleRedlineViolation(
                "RED LINE RL3 VIOLATION: Rule must have 'rule' field"
            )

        rule_obj = rule_spec["rule"]

        # Check severity
        if "severity" not in rule_obj:
            raise RuleRedlineViolation(
                "RED LINE RL3 VIOLATION: rule.severity is required"
            )

        severity = rule_obj["severity"]
        if severity not in ["info", "warn", "error", "block"]:
            raise RuleRedlineViolation(
                f"RED LINE RL3 VIOLATION: rule.severity must be 'info', 'warn', 'error', or 'block', got '{severity}'"
            )

        # Check when (structured condition)
        if "when" not in rule_obj:
            raise RuleRedlineViolation(
                "RED LINE RL3 VIOLATION: rule.when is required (structured condition)"
            )

        when = rule_obj["when"]
        if not isinstance(when, dict):
            raise RuleRedlineViolation(
                f"RED LINE RL3 VIOLATION: rule.when must be a structured object, not {type(when).__name__}"
            )

        if len(when) == 0:
            raise RuleRedlineViolation(
                "RED LINE RL3 VIOLATION: rule.when must not be empty (define at least one condition)"
            )

        # Check then (structured decision)
        if "then" not in rule_obj:
            raise RuleRedlineViolation(
                "RED LINE RL3 VIOLATION: rule.then is required (structured decision)"
            )

        then = rule_obj["then"]
        if not isinstance(then, dict):
            raise RuleRedlineViolation(
                f"RED LINE RL3 VIOLATION: rule.then must be a structured object, not {type(then).__name__}"
            )

        if "decision" not in then:
            raise RuleRedlineViolation(
                "RED LINE RL3 VIOLATION: rule.then.decision is required"
            )

        decision = then["decision"]
        if decision not in ["allow", "deny", "warn", "require_review"]:
            raise RuleRedlineViolation(
                f"RED LINE RL3 VIOLATION: rule.then.decision must be 'allow', 'deny', 'warn', or 'require_review', got '{decision}'"
            )

        return True

    def validate_scope_declared(self, rule_spec: dict) -> bool:
        """🚨 RED LINE RL4: Rule must declare applicability scope.

        Required (at least one non-empty):
        - rule.scope.applies_to_types
        - rule.scope.applies_to_risk
        - rule.scope.applies_to_phases

        Args:
            rule_spec: Rule dict

        Returns:
            True if valid

        Raises:
            RuleRedlineViolation: If scope missing or all fields empty
        """
        if "rule" not in rule_spec:
            raise RuleRedlineViolation(
                "RED LINE RL4 VIOLATION: Rule must have 'rule' field"
            )

        rule_obj = rule_spec["rule"]

        if "scope" not in rule_obj:
            raise RuleRedlineViolation(
                "RED LINE RL4 VIOLATION: rule.scope is required"
            )

        scope = rule_obj["scope"]
        if not isinstance(scope, dict):
            raise RuleRedlineViolation(
                f"RED LINE RL4 VIOLATION: rule.scope must be object, got {type(scope)}"
            )

        # Check at least one field is non-empty
        applies_to_types = scope.get("applies_to_types", [])
        applies_to_risk = scope.get("applies_to_risk", [])
        applies_to_phases = scope.get("applies_to_phases", [])

        if not applies_to_types and not applies_to_risk and not applies_to_phases:
            raise RuleRedlineViolation(
                "RED LINE RL4 VIOLATION: rule.scope must have at least one non-empty field "
                "(applies_to_types, applies_to_risk, or applies_to_phases)"
            )

        return True

    def validate_lineage(self, rule_spec: dict) -> bool:
        """🚨 RED LINE RL5: Rule must have lineage information.

        Required fields:
        - lineage.introduced_in (v0.9 format)
        - lineage.derived_from (null or rule ID)
        - lineage.supersedes (array, can be empty)

        Args:
            rule_spec: Rule dict

        Returns:
            True if valid

        Raises:
            RuleRedlineViolation: If lineage incomplete
        """
        if "lineage" not in rule_spec:
            raise RuleRedlineViolation(
                "RED LINE RL5 VIOLATION: Rule must have 'lineage' field"
            )

        lineage = rule_spec["lineage"]
        if not isinstance(lineage, dict):
            raise RuleRedlineViolation(
                "RED LINE RL5 VIOLATION: 'lineage' must be an object"
            )

        # Check required fields
        required_fields = ["introduced_in", "derived_from", "supersedes"]
        for field in required_fields:
            if field not in lineage:
                raise RuleRedlineViolation(
                    f"RED LINE RL5 VIOLATION: lineage missing required field '{field}'"
                )

        # Validate introduced_in format
        introduced_in = lineage["introduced_in"]
        if not isinstance(introduced_in, str) or not introduced_in.startswith("v"):
            raise RuleRedlineViolation(
                f"RED LINE RL5 VIOLATION: lineage.introduced_in must be in format 'vX.Y', got '{introduced_in}'"
            )

        # Validate derived_from
        derived_from = lineage["derived_from"]
        if derived_from is not None and not isinstance(derived_from, str):
            raise RuleRedlineViolation(
                f"RED LINE RL5 VIOLATION: lineage.derived_from must be null or string, got {type(derived_from)}"
            )

        # Validate supersedes
        supersedes = lineage["supersedes"]
        if not isinstance(supersedes, list):
            raise RuleRedlineViolation(
                f"RED LINE RL5 VIOLATION: lineage.supersedes must be an array, got {type(supersedes)}"
            )

        return True
