"""Intent Builder - Convert Natural Language to ExecutionIntent.

RED LINES:
- No execution (no subprocess/shell/exec)
- No fabrication (registry_only=true)
- full_auto => question_budget=0
- Every selection must have evidence_refs
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agentos.core.content.registry import ContentRegistry
from agentos.core.intent_builder.nl_parser import NLParser
from agentos.core.intent_builder.registry_query import RegistryQueryService
from agentos.core.intent_builder.evidence import EvidenceBuilder
from agentos.core.intent_builder.questions import QuestionGenerator
from agentos.core.time import utc_now_iso



# 知识查询关键词
KNOWLEDGE_QUERY_KEYWORDS = [
    "什么是", "如何", "为什么", "在哪里", "说明", "文档", "解释",
    "what is", "how to", "why", "where", "explain", "documentation", "describe",
]


class IntentBuilder:
    """Build ExecutionIntent from Natural Language input.
    
    RED LINES:
    - Does NOT execute any commands
    - Does NOT fabricate registry content
    - full_auto mode enforces question_budget=0
    - All selections must have evidence_refs
    """
    
    def __init__(
        self,
        registry: ContentRegistry,
        model_router=None,  # Reserved for future model integration
        project_kb=None  # ProjectKBService instance (optional)
    ):
        """Initialize Intent Builder.
        
        Args:
            registry: ContentRegistry instance
            model_router: Optional model router (reserved for future use)
            project_kb: Optional ProjectKBService for project knowledge queries
        """
        self.registry = registry
        self.model_router = model_router
        self.project_kb = project_kb
        
        # Initialize components
        self.nl_parser = NLParser()
        self.query_service = RegistryQueryService(registry)
        self.evidence_builder = EvidenceBuilder()
        self.question_generator = QuestionGenerator()
    
    def build_intent(
        self,
        nl_request: dict,
        policy: str = "semi_auto"  # full_auto|semi_auto|interactive
    ) -> dict:
        """Build ExecutionIntent from NL request.
        
        RED LINE: This method does NOT execute anything.
        
        Args:
            nl_request: NL request dict (conforming to nl_request.schema.json)
            policy: Execution policy
        
        Returns:
            Intent Builder Output dict (conforming to intent_builder_output.schema.json)
        """
        # Step 1: Parse NL input
        parsed_nl = self.nl_parser.parse(nl_request)
        
        # Step 2: Check if this is a knowledge query (ProjectKB)
        kb_results = []
        if self.project_kb and self._is_knowledge_query(parsed_nl):
            kb_results = self._query_project_kb(parsed_nl)
        
        # Step 3: Query Registry for matching content
        workflows = self.query_service.find_matching_workflows(parsed_nl)
        agents = self.query_service.find_matching_agents(parsed_nl)
        commands = self.query_service.find_matching_commands(parsed_nl, agents)
        
        # Step 4: Generate Evidence for selections (including KB results)
        selection_evidence = self._build_selection_evidence(
            workflows, agents, commands, kb_results, nl_request, parsed_nl
        )
        
        # Step 5: Build ExecutionIntent (v0.9.1)
        execution_intent = self._build_execution_intent(
            workflows, agents, commands, nl_request, parsed_nl, policy
        )
        
        # Step 6: Generate QuestionPack (if policy allows)
        question_pack = self._build_question_pack(
            parsed_nl, policy, execution_intent, nl_request
        )
        
        # Step 7: Build Builder Audit
        builder_audit = self._build_audit(policy, parsed_nl, workflows, agents, commands, kb_results)
        
        # Step 8: Assemble output
        output = self._assemble_output(
            nl_request, execution_intent, question_pack, selection_evidence, builder_audit
        )
        
        return output
    
    def _is_knowledge_query(self, parsed_nl: dict) -> bool:
        """判断是否为知识查询类请求

        Args:
            parsed_nl: 解析后的 NL 请求

        Returns:
            是否为知识查询
        """
        goal = parsed_nl.get("goal", "").lower()
        
        # 检查是否包含知识查询关键词
        for keyword in KNOWLEDGE_QUERY_KEYWORDS:
            if keyword.lower() in goal:
                return True
        
        return False

    def _query_project_kb(self, parsed_nl: dict) -> list:
        """查询 ProjectKB

        Args:
            parsed_nl: 解析后的 NL 请求

        Returns:
            ChunkResult 列表
        """
        if not self.project_kb:
            return []

        goal = parsed_nl.get("goal", "")
        
        try:
            # 执行检索
            results = self.project_kb.search(
                query=goal,
                top_k=5,
                explain=True,
            )
            return results
        except Exception as e:
            # 静默失败，不阻塞主流程
            print(f"Warning: ProjectKB search failed: {e}")
            return []

    def _build_selection_evidence(
        self,
        workflows: List[dict],
        agents: List[dict],
        commands: List[dict],
        kb_results: List[Any],
        nl_request: dict,
        parsed_nl: dict
    ) -> dict:
        """Build selection evidence for all selections."""
        workflow_selections = []
        for wf in workflows:
            evidence = self.evidence_builder.generate_workflow_evidence(
                wf["workflow"], nl_request, parsed_nl, wf["reason"]
            )
            workflow_selections.append({
                "workflow_id": wf["workflow"]["id"],
                "reason": wf["reason"],
                "evidence_refs": evidence
            })
        
        agent_selections = []
        for ag in agents:
            evidence = self.evidence_builder.generate_agent_evidence(
                ag["agent"], nl_request, parsed_nl, ag["role"], ag["reason"]
            )
            agent_selections.append({
                "agent_id": ag["agent"]["id"],
                "role": ag["role"],
                "reason": ag["reason"],
                "evidence_refs": evidence
            })
        
        command_selections = []
        for cmd in commands:
            evidence = self.evidence_builder.generate_command_evidence(
                cmd["command"], nl_request, parsed_nl, cmd["reason"]
            )
            command_selections.append({
                "command_id": cmd["command"]["id"],
                "reason": cmd["reason"],
                "evidence_refs": evidence
            })
        
        # 添加 KB 结果的 evidence
        kb_selections = []
        for result in kb_results:
            kb_selections.append({
                "chunk_id": result.chunk_id,
                "path": result.path,
                "heading": result.heading,
                "lines": result.lines,
                "score": result.score,
                "evidence_refs": [result.to_evidence_ref()]
            })
        
        return {
            "workflow_selections": workflow_selections,
            "agent_selections": agent_selections,
            "command_selections": command_selections,
            "kb_selections": kb_selections  # 新增
        }
    
    def _build_execution_intent(
        self,
        workflows: List[dict],
        agents: List[dict],
        commands: List[dict],
        nl_request: dict,
        parsed_nl: dict,
        policy: str
    ) -> dict:
        """Build ExecutionIntent (v0.9.1 format)."""
        intent_id = f"intent_{uuid.uuid4().hex[:12]}"
        
        # Build scope
        scope = self._build_scope(nl_request, parsed_nl)
        
        # Build objective
        objective = self._build_objective(parsed_nl)
        
        # Build selected workflows/agents/commands
        selected_workflows = self._build_selected_workflows(workflows)
        selected_agents = self._build_selected_agents(agents)
        planned_commands = self._build_planned_commands(commands, parsed_nl)
        
        # Build interaction
        interaction = self._build_interaction(policy, parsed_nl)
        
        # Build risk
        risk = self._build_risk(parsed_nl, commands)
        
        # Build budgets
        budgets = self._build_budgets(parsed_nl)
        
        # Build evidence_refs (top-level)
        evidence_refs = self.evidence_builder.generate_intent_evidence(nl_request, parsed_nl)
        
        # Build constraints (RED LINE: execution=forbidden)
        constraints = {
            "execution": "forbidden",
            "no_fabrication": True,
            "registry_only": True,
            "lock_scope": {
                "mode": "files",
                "paths": scope["targets"]["files"]
            }
        }
        
        # Build audit
        audit = {
            "created_by": "intent_builder_v0.9.4",
            "source": "agentos",
            "checksum": "placeholder"  # Will be calculated after full intent is built
        }
        
        intent = {
            "id": intent_id,
            "type": "execution_intent",
            "title": parsed_nl["goal"][:160],
            "version": "1.0.0",
            "status": "draft",
            "created_at": utc_now_iso(),
            "lineage": {
                "introduced_in": "0.9.4",
                "derived_from": [],
                "supersedes": []
            },
            "scope": scope,
            "objective": objective,
            "selected_workflows": selected_workflows,
            "selected_agents": selected_agents,
            "planned_commands": planned_commands,
            "interaction": interaction,
            "risk": risk,
            "budgets": budgets,
            "evidence_refs": evidence_refs,
            "constraints": constraints,
            "audit": audit
        }
        
        # Calculate checksum
        intent["audit"]["checksum"] = self._calculate_checksum(intent)
        
        return intent
    
    def _build_scope(self, nl_request: dict, parsed_nl: dict) -> dict:
        """Build scope section."""
        context_hints = nl_request.get("context_hints", {})
        
        files = context_hints.get("files", [])
        modules = context_hints.get("modules", [])
        areas = parsed_nl.get("areas", [])
        
        # Ensure at least one area
        if not areas:
            areas = ["docs"]  # Default to docs for low-risk
        
        return {
            "project_id": nl_request.get("project_id", "unknown"),
            "repo_root": ".",
            "targets": {
                "files": files,
                "modules": modules,
                "areas": areas
            }
        }
    
    def _build_objective(self, parsed_nl: dict) -> dict:
        """Build objective section."""
        goal = parsed_nl.get("goal", "Complete specified tasks")
        actions = parsed_nl.get("actions", [])
        
        # Build success criteria from actions
        success_criteria = [f"Complete: {action[:200]}" for action in actions[:10]]
        if not success_criteria:
            success_criteria = ["Task completed successfully"]
        
        # Build non-goals
        constraints = parsed_nl.get("constraints", [])
        non_goals = [c[:200] for c in constraints[:10]]
        
        return {
            "goal": goal,
            "success_criteria": success_criteria,
            "non_goals": non_goals
        }
    
    def _build_selected_workflows(self, workflows: List[dict]) -> List[dict]:
        """Build selected_workflows section."""
        if not workflows:
            # Default to documentation workflow
            return [{
                "workflow_id": "documentation",
                "phases": ["analysis", "implementation", "review"]
            }]
        
        selected = []
        for wf in workflows[:5]:  # Top 5
            selected.append({
                "workflow_id": wf["workflow"]["id"],
                "phases": ["setup", "analysis", "implementation", "validation", "review"],
                "reason": wf["reason"]
            })
        
        return selected
    
    def _build_selected_agents(self, agents: List[dict]) -> List[dict]:
        """Build selected_agents section."""
        if not agents:
            # Default to technical writer
            return [{
                "agent_id": "technical_writer",
                "role": "documentation",
                "responsibilities": ["Write and update documentation"]
            }]
        
        selected = []
        for ag in agents[:5]:  # Top 5
            agent_spec = ag["agent"].get("spec", {})
            responsibilities = agent_spec.get("responsibilities", ["Contribute to project"])
            
            selected.append({
                "agent_id": ag["agent"]["id"],
                "role": ag["role"],
                "responsibilities": responsibilities[:12]
            })
        
        return selected
    
    def _build_planned_commands(self, commands: List[dict], parsed_nl: dict) -> List[dict]:
        """Build planned_commands section."""
        planned = []
        
        for cmd in commands[:10]:  # Top 10
            command_spec = cmd["command"].get("spec", {})
            
            planned.append({
                "command_id": cmd["command"]["id"],
                "intent": cmd["reason"],
                "effects": command_spec.get("effects", ["read"]),
                "risk_level": command_spec.get("risk_level", "low"),
                "evidence_refs": [f"registry:{cmd['command']['id']}:1.0.0"]
            })
        
        return planned
    
    def _build_interaction(self, policy: str, parsed_nl: dict) -> dict:
        """Build interaction section."""
        # Map policy to mode
        mode = policy
        
        # Determine question budget
        if mode == "full_auto":
            question_budget = 0
            question_policy = "never"
        elif mode == "semi_auto":
            question_budget = 10
            question_policy = "blockers_only"
        else:  # interactive
            question_budget = 20
            question_policy = "conceptual_only"
        
        return {
            "mode": mode,
            "question_budget": question_budget,
            "question_policy": question_policy
        }
    
    def _build_risk(self, parsed_nl: dict, commands: List[dict]) -> dict:
        """Build risk section."""
        risk_level = parsed_nl.get("risk_level", "medium")
        
        # Build drivers
        drivers = [f"Risk level: {risk_level}"]
        ambiguities = parsed_nl.get("ambiguities", [])
        for amb in ambiguities[:5]:
            drivers.append(f"{amb['type']}: {amb['description']}")
        
        # Determine requires_review
        requires_review = []
        if risk_level in ["high", "critical"]:
            requires_review.extend(["security", "architecture"])
        
        areas = parsed_nl.get("areas", [])
        if "data" in areas or "security" in areas:
            requires_review.append("data")
            requires_review.append("security")
        
        # Check command effects
        for cmd in commands:
            effects = cmd["command"].get("spec", {}).get("effects", [])
            if "deploy" in effects:
                requires_review.append("release")
            if "write" in effects or "data" in effects:
                if "architecture" not in requires_review:
                    requires_review.append("architecture")
        
        # Deduplicate
        requires_review = list(set(requires_review))
        
        return {
            "overall": risk_level,
            "drivers": drivers,
            "requires_review": requires_review
        }
    
    def _build_budgets(self, parsed_nl: dict) -> dict:
        """Build budgets section."""
        risk_level = parsed_nl.get("risk_level", "medium")
        
        # Scale budgets by risk
        budget_map = {
            "low": {"files": 10, "commits": 5, "tokens": 100000, "cost": 10.0},
            "medium": {"files": 50, "commits": 10, "tokens": 500000, "cost": 50.0},
            "high": {"files": 100, "commits": 20, "tokens": 1000000, "cost": 100.0}
        }
        
        budgets = budget_map.get(risk_level, budget_map["medium"])
        
        return {
            "max_files": budgets["files"],
            "max_commits": budgets["commits"],
            "max_tokens": budgets["tokens"],
            "max_cost_usd": budgets["cost"]
        }
    
    def _build_question_pack(
        self,
        parsed_nl: dict,
        policy: str,
        execution_intent: dict,
        nl_request: dict
    ) -> Optional[dict]:
        """Build QuestionPack."""
        ambiguities = parsed_nl.get("ambiguities", [])
        max_budget = execution_intent["interaction"]["question_budget"]
        
        return self.question_generator.generate_questions(
            ambiguities, policy, max_budget, nl_request, parsed_nl
        )
    
    def _build_audit(
        self,
        policy: str,
        parsed_nl: dict,
        workflows: List[dict],
        agents: List[dict],
        commands: List[dict]
    ) -> dict:
        """Build builder_audit section."""
        return {
            "builder_version": "0.9.4",
            "model_used": "rule_based",
            "policy_applied": policy,
            "adjudication_summary": {
                "risk_level": parsed_nl.get("risk_level", "medium"),
                "ambiguities_detected": len(parsed_nl.get("ambiguities", [])),
                "registry_queries": len(workflows) + len(agents) + len(commands),
                "decisions_made": len(workflows) + len(agents) + len(commands)
            },
            "created_at": utc_now_iso(),
            "checksum": "placeholder"  # Will be calculated
        }
    
    def _assemble_output(
        self,
        nl_request: dict,
        execution_intent: dict,
        question_pack: Optional[dict],
        selection_evidence: dict,
        builder_audit: dict
    ) -> dict:
        """Assemble final IntentBuilderOutput."""
        output_id = f"builder_out_{uuid.uuid4().hex[:12]}"
        
        output = {
            "id": output_id,
            "schema_version": "0.9.4",
            "nl_request_id": nl_request["id"],
            "execution_intent": execution_intent,
            "question_pack": question_pack,
            "selection_evidence": selection_evidence,
            "builder_audit": builder_audit,
            "lineage": {
                "introduced_in": "0.9.4",
                "derived_from": [nl_request["id"]],
                "supersedes": []
            }
        }
        
        # Calculate checksum
        output["builder_audit"]["checksum"] = self._calculate_checksum(output)
        
        return output
    
    def _calculate_checksum(self, data: dict) -> str:
        """Calculate SHA-256 checksum."""
        # Create a copy without checksum field
        data_copy = json.loads(json.dumps(data))
        
        # Remove checksum fields if present
        if "audit" in data_copy and "checksum" in data_copy["audit"]:
            data_copy["audit"]["checksum"] = ""
        if "builder_audit" in data_copy and "checksum" in data_copy["builder_audit"]:
            data_copy["builder_audit"]["checksum"] = ""
        
        # Serialize deterministically
        data_str = json.dumps(data_copy, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(data_str.encode()).hexdigest()
