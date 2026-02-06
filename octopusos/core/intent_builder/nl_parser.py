"""NL Parser - Parse natural language input to extract intent components."""

import re
from typing import Dict, List, Tuple


class NLParser:
    """Parse natural language input to extract goals, constraints, and risks.
    
    RED LINE: This is a rule-based parser, no execution.
    """
    
    # Keywords for risk detection
    RISK_KEYWORDS = {
        "high": ["database", "migration", "production", "deploy", "security", "auth", "permission", "delete", "drop"],
        "medium": ["api", "endpoint", "authentication", "integration", "external"],
        "low": ["documentation", "comment", "readme", "test", "spec", "guide"]
    }
    
    # Keywords for area detection
    AREA_KEYWORDS = {
        "frontend": ["ui", "component", "react", "vue", "angular", "page", "layout", "css"],
        "backend": ["api", "endpoint", "server", "service", "database", "query"],
        "data": ["database", "migration", "schema", "table", "query", "data"],
        "security": ["auth", "authentication", "authorization", "permission", "security", "encrypt"],
        "tests": ["test", "testing", "unit test", "integration test", "e2e"],
        "docs": ["documentation", "readme", "doc", "comment", "jsdoc", "guide"],
        "infra": ["deploy", "ci", "cd", "pipeline", "docker", "kubernetes"],
        "ops": ["monitoring", "logging", "metrics", "alert", "performance"]
    }
    
    def __init__(self):
        """Initialize NL parser."""
        pass
    
    def parse(self, nl_request: dict) -> dict:
        """Parse NL request to extract structured components.
        
        Args:
            nl_request: NL request dict (conforming to nl_request.schema.json)
        
        Returns:
            Parsed components:
                - goal: Main objective
                - actions: List of actions to perform
                - constraints: List of constraints
                - risk_level: Detected risk level
                - areas: Detected technical areas
                - ambiguities: List of ambiguities requiring questions
        """
        input_text = nl_request["input_text"]
        context_hints = nl_request.get("context_hints", {})
        
        # Extract actions (imperative verbs)
        actions = self._extract_actions(input_text)
        
        # Detect risk level
        risk_level = self._detect_risk_level(input_text, context_hints)
        
        # Detect areas
        areas = self._detect_areas(input_text, context_hints)
        
        # Detect ambiguities
        ambiguities = self._detect_ambiguities(input_text, actions)
        
        # Extract goal (first sentence or first action)
        goal = self._extract_goal(input_text)
        
        # Extract constraints (negative statements)
        constraints = self._extract_constraints(input_text)
        
        return {
            "goal": goal,
            "actions": actions,
            "constraints": constraints,
            "risk_level": risk_level,
            "areas": areas,
            "ambiguities": ambiguities,
            "context_hints": context_hints
        }
    
    def _extract_actions(self, text: str) -> List[str]:
        """Extract action items from text."""
        actions = []
        
        # Split by bullet points or line breaks
        lines = re.split(r'[\n•\-]\s*', text)
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for imperative verbs
            action_patterns = [
                r'^(add|create|implement|build|develop|write|update|modify|refactor|fix|remove|delete|migrate)\s+(.+)',
                r'^(新增|添加|创建|实现|开发|编写|更新|修改|重构|修复|删除|迁移)\s+(.+)',
            ]
            
            for pattern in action_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    actions.append(line)
                    break
        
        return actions
    
    def _detect_risk_level(self, text: str, context_hints: dict) -> str:
        """Detect risk level based on keywords."""
        text_lower = text.lower()
        
        # Check high risk keywords
        for keyword in self.RISK_KEYWORDS["high"]:
            if keyword in text_lower:
                return "high"
        
        # Check context hints areas
        hint_areas = context_hints.get("areas", [])
        if "data" in hint_areas or "security" in hint_areas:
            return "high"
        
        # Check medium risk keywords
        for keyword in self.RISK_KEYWORDS["medium"]:
            if keyword in text_lower:
                return "medium"
        
        # Check low risk keywords
        for keyword in self.RISK_KEYWORDS["low"]:
            if keyword in text_lower:
                return "low"
        
        # Default to medium
        return "medium"
    
    def _detect_areas(self, text: str, context_hints: dict) -> List[str]:
        """Detect technical areas."""
        text_lower = text.lower()
        detected_areas = set()
        
        # Add from context hints
        hint_areas = context_hints.get("areas", [])
        detected_areas.update(hint_areas)
        
        # Detect from keywords
        for area, keywords in self.AREA_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    detected_areas.add(area)
                    break
        
        return list(detected_areas)
    
    def _detect_ambiguities(self, text: str, actions: List[str]) -> List[dict]:
        """Detect ambiguities that may require questions."""
        ambiguities = []
        
        # Ambiguity 1: No actions detected
        if not actions:
            ambiguities.append({
                "type": "missing_actions",
                "description": "No clear actions detected in the input",
                "severity": "high"
            })
        
        # Ambiguity 2: Vague specifications
        vague_terms = ["somehow", "maybe", "possibly", "optionally", "考虑", "可能"]
        for term in vague_terms:
            if term.lower() in text.lower():
                ambiguities.append({
                    "type": "vague_specification",
                    "description": f"Vague term detected: {term}",
                    "severity": "medium"
                })
                break
        
        # Ambiguity 3: Multiple conflicting requirements
        if len(actions) > 10:
            ambiguities.append({
                "type": "too_many_actions",
                "description": f"Too many actions ({len(actions)}) - may need prioritization",
                "severity": "medium"
            })
        
        return ambiguities
    
    def _extract_goal(self, text: str) -> str:
        """Extract main goal (first meaningful sentence)."""
        # Split by periods or newlines
        sentences = re.split(r'[。\.\n]+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 10:  # Meaningful sentence
                return sentence[:200]  # Truncate to 200 chars
        
        # Fallback: first 200 chars
        return text[:200].strip()
    
    def _extract_constraints(self, text: str) -> List[str]:
        """Extract constraints (negative requirements)."""
        constraints = []
        
        # Patterns for constraints
        constraint_patterns = [
            r'(do not|don\'t|must not|cannot|禁止|不能|不要)\s+(.+)',
            r'(without|excluding|except|除了|排除)\s+(.+)',
            r'(requirement|constraint|限制|要求):\s*(.+)',
        ]
        
        lines = re.split(r'[\n•\-]\s*', text)
        
        for line in lines:
            for pattern in constraint_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    constraints.append(line.strip())
                    break
        
        return constraints[:10]  # Max 10 constraints
    
    def extract_text_span(self, text: str, keyword: str) -> Tuple[int, int]:
        """Extract character span for a keyword in text.
        
        Returns:
            (start_char, end_char) tuple
        """
        text_lower = text.lower()
        keyword_lower = keyword.lower()
        
        start = text_lower.find(keyword_lower)
        if start == -1:
            return (0, 0)
        
        end = start + len(keyword)
        return (start, end)
