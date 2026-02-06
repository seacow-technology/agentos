"""
InfoNeedClassifier - Question Type Classification System

This module implements a complete classification pipeline to determine:
1. What type of information need the user has
2. What action should be taken to respond

Classification is performed through:
- Rule-based filtering (fast path)
- LLM self-assessment (when needed)
- Decision matrix (final action determination)

Key constraint: This is a JUDGMENT-ONLY module.
- Does NOT perform searches
- Does NOT fetch external data
- Does NOT generate answers
- ONLY classifies and recommends actions
"""

from datetime import datetime, timezone
from typing import Dict, Optional, List, Any
import logging
import json
import re
import time
import uuid

from agentos.core.time import utc_now
from agentos.core.chat.models.info_need import (
    InfoNeedType,
    ConfidenceLevel,
    DecisionAction,
    ClassificationSignal,
    LLMConfidenceResult,
    ClassificationResult,
)

logger = logging.getLogger(__name__)


class RuleBasedFilter:
    """
    Rule-based filter for fast classification signals.

    This component provides the fast path for classification by matching
    keywords and patterns in the user's message. It does NOT make final
    decisions but provides signals to inform the classification.

    Performance target: < 10ms
    """

    # Keyword definitions
    TIME_SENSITIVE_KEYWORDS = [
        "today", "latest", "current", "now", "recently",
        "2025", "2026", "2027", "recent", "this year",
        "新", "最新", "现在", "当前", "今天", "最近"
    ]

    AUTHORITATIVE_KEYWORDS = [
        "policy", "regulation", "law", "official", "standard",
        "government", "announcement", "compliance", "guideline",
        "政策", "法规", "官方", "公告", "规定", "标准"
    ]

    AMBIENT_STATE_KEYWORDS = [
        "time", "phase", "session", "mode", "config", "status",
        "running", "active", "current phase", "what phase",
        "什么时候", "几点", "当前", "状态", "运行", "配置"
    ]

    # Code structure patterns
    CODE_STRUCTURE_PATTERNS = [
        r"\bclass\s+\w+",
        r"\bfunction\s+\w+",
        r"\bmethod\s+\w+",
        r"\.py\b",
        r"\.js\b",
        r"\bAPI\b",
        r"\bexists?\b",
        r"\bwhere\s+is\b",
        r"\bfind\s+.*\bfile",
    ]

    # Opinion indicators
    OPINION_INDICATORS = [
        "recommend", "suggest", "should", "better", "prefer",
        "opinion", "think", "believe", "would you",
        "推荐", "建议", "应该", "最好", "认为", "觉得"
    ]

    def filter(self, message: str) -> ClassificationSignal:
        """
        Fast rule-based filtering to generate classification signals.

        Args:
            message: User's message to analyze

        Returns:
            ClassificationSignal with matched patterns and signal strength
        """
        message_lower = message.lower()
        matched_keywords = []

        # Check time-sensitive keywords
        has_time_sensitive = False
        for keyword in self.TIME_SENSITIVE_KEYWORDS:
            if keyword.lower() in message_lower:
                has_time_sensitive = True
                matched_keywords.append(f"time:{keyword}")

        # Check authoritative keywords
        has_authoritative = False
        for keyword in self.AUTHORITATIVE_KEYWORDS:
            if keyword.lower() in message_lower:
                has_authoritative = True
                matched_keywords.append(f"auth:{keyword}")

        # Check ambient state keywords
        has_ambient_state = False
        for keyword in self.AMBIENT_STATE_KEYWORDS:
            if keyword.lower() in message_lower:
                has_ambient_state = True
                matched_keywords.append(f"state:{keyword}")

        # Check code structure patterns
        has_code_structure = False
        for pattern in self.CODE_STRUCTURE_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                has_code_structure = True
                matched_keywords.append(f"code:{pattern}")

        # Check opinion indicators
        has_opinion = False
        for indicator in self.OPINION_INDICATORS:
            if indicator.lower() in message_lower:
                has_opinion = True
                matched_keywords.append(f"opinion:{indicator}")

        # Calculate signal strength (0.0 - 1.0)
        signal_strength = self._calculate_signal_strength(
            has_time_sensitive=has_time_sensitive,
            has_authoritative=has_authoritative,
            has_ambient_state=has_ambient_state,
            has_code_structure=has_code_structure,
            has_opinion=has_opinion,
            num_matches=len(matched_keywords),
        )

        return ClassificationSignal(
            has_time_sensitive_keywords=has_time_sensitive,
            has_authoritative_keywords=has_authoritative,
            has_ambient_state_keywords=has_ambient_state,
            matched_keywords=matched_keywords,
            signal_strength=signal_strength,
        )

    def _calculate_signal_strength(
        self,
        has_time_sensitive: bool,
        has_authoritative: bool,
        has_ambient_state: bool,
        has_code_structure: bool,
        has_opinion: bool,
        num_matches: int,
    ) -> float:
        """
        Calculate overall signal strength based on matched patterns.

        Signal strength indicates how strongly the rules suggest a specific
        classification. Higher values mean stronger signals.

        Args:
            has_time_sensitive: Whether time-sensitive keywords were found
            has_authoritative: Whether authoritative keywords were found
            has_ambient_state: Whether ambient state keywords were found
            has_code_structure: Whether code structure patterns were found
            has_opinion: Whether opinion indicators were found
            num_matches: Total number of keyword matches

        Returns:
            Signal strength between 0.0 and 1.0
        """
        strength = 0.0

        # Strong signals
        if has_ambient_state:
            strength += 0.4  # Very strong indicator
        if has_code_structure:
            strength += 0.3  # Strong indicator for local deterministic

        # Medium signals
        if has_time_sensitive:
            strength += 0.2
        if has_authoritative:
            strength += 0.2

        # Weak signals
        if has_opinion:
            strength += 0.1

        # Bonus for multiple matches
        if num_matches >= 3:
            strength += 0.1
        elif num_matches >= 5:
            strength += 0.2

        # Clamp to [0.0, 1.0]
        return min(1.0, strength)


class LLMConfidenceEvaluator:
    """
    LLM self-assessment module (controlled).

    This component asks the LLM to evaluate its own confidence in answering
    a question WITHOUT actually answering it. The prompt is carefully designed
    to prevent the LLM from generating answer content.

    Key constraint: The LLM evaluates stability, not correctness.
    Question: "If I answer this without internet, will the answer be wrong in 24h?"
    """

    PROMPT_TEMPLATE = '''Please evaluate the answer stability for the following question.

Question: {question}

If you answer this question WITHOUT accessing the internet, is your answer likely to be judged as incorrect or outdated 24 hours later?

Return ONLY valid JSON in this exact format:
{{
  "confidence": "high | medium | low",
  "reason": "time-sensitive | authoritative | stable | uncertain | outdated"
}}

Constraints:
- Do NOT provide the actual answer to the question
- Only evaluate whether your answer would remain stable
- "high": Answer is based on stable, well-established knowledge
- "medium": Answer may change but is not urgent
- "low": Answer has time-sensitivity or requires authoritative sources

Your response (JSON only):'''

    def __init__(self, llm_callable: Optional[Any] = None):
        """
        Initialize LLM confidence evaluator.

        Args:
            llm_callable: Optional callable for LLM invocation.
                         If None, will be set to a default implementation
                         or can be mocked for testing.
        """
        self.llm_callable = llm_callable or self._default_llm_callable

    async def evaluate(self, message: str) -> LLMConfidenceResult:
        """
        Evaluate LLM confidence using self-assessment.

        This method invokes the LLM with a controlled prompt that asks it
        to evaluate answer stability rather than provide an answer.

        Args:
            message: User's question to evaluate

        Returns:
            LLMConfidenceResult with confidence level and reasoning

        Raises:
            ValueError: If LLM response cannot be parsed
            RuntimeError: If LLM call fails
        """
        try:
            # Generate prompt
            prompt = self.PROMPT_TEMPLATE.format(question=message)

            # Call LLM
            logger.debug(f"Calling LLM for confidence evaluation: {message[:50]}...")
            response = await self.llm_callable(prompt)

            # Parse response
            result = self._parse_llm_response(response)

            logger.debug(
                f"LLM confidence evaluation: {result.confidence.value} "
                f"({result.reason})"
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            # Fallback to medium confidence
            return LLMConfidenceResult(
                confidence=ConfidenceLevel.MEDIUM,
                reason="uncertain",
                reasoning=f"Failed to parse LLM response: {str(e)}"
            )
        except Exception as e:
            logger.error(f"LLM confidence evaluation failed: {e}")
            raise RuntimeError(f"LLM evaluation failed: {str(e)}") from e

    def _parse_llm_response(self, response: str) -> LLMConfidenceResult:
        """
        Parse LLM JSON response into LLMConfidenceResult.

        Args:
            response: Raw LLM response (should be JSON)

        Returns:
            Parsed LLMConfidenceResult

        Raises:
            ValueError: If response format is invalid
        """
        # Try to extract JSON from response (in case there's extra text)
        json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = response.strip()

        # Parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in LLM response: {response}")

        # Validate required fields
        if "confidence" not in data or "reason" not in data:
            raise ValueError(
                f"Missing required fields in LLM response: {data}"
            )

        # Map confidence string to enum
        confidence_str = data["confidence"].lower()
        if confidence_str == "high":
            confidence = ConfidenceLevel.HIGH
        elif confidence_str == "medium":
            confidence = ConfidenceLevel.MEDIUM
        elif confidence_str == "low":
            confidence = ConfidenceLevel.LOW
        else:
            raise ValueError(
                f"Invalid confidence level: {data['confidence']}"
            )

        return LLMConfidenceResult(
            confidence=confidence,
            reason=data["reason"],
            reasoning=data.get("reasoning", None)
        )

    async def _default_llm_callable(self, prompt: str) -> str:
        """
        Default LLM callable (placeholder for testing).

        In production, this should be replaced with actual LLM invocation
        or provided via constructor.

        Args:
            prompt: Prompt to send to LLM

        Returns:
            LLM response
        """
        logger.warning(
            "Using default LLM callable (placeholder). "
            "Provide llm_callable in constructor for production use."
        )
        # Return a default medium confidence response
        return json.dumps({
            "confidence": "medium",
            "reason": "uncertain"
        })


class DecisionMatrix:
    """
    Decision matrix for final action determination.

    This component implements the decision logic based on:
    - Classified information need type
    - Confidence level

    The matrix is designed to be conservative: when in doubt, suggest or
    require communication rather than risk incorrect answers.
    """

    # Decision matrix: (InfoNeedType, ConfidenceLevel) -> DecisionAction
    MATRIX = {
        # LOCAL_DETERMINISTIC: Always use local capabilities (file system, grep, etc.)
        (InfoNeedType.LOCAL_DETERMINISTIC, ConfidenceLevel.HIGH): DecisionAction.LOCAL_CAPABILITY,
        (InfoNeedType.LOCAL_DETERMINISTIC, ConfidenceLevel.MEDIUM): DecisionAction.LOCAL_CAPABILITY,
        (InfoNeedType.LOCAL_DETERMINISTIC, ConfidenceLevel.LOW): DecisionAction.LOCAL_CAPABILITY,

        # LOCAL_KNOWLEDGE: Confidence-dependent
        (InfoNeedType.LOCAL_KNOWLEDGE, ConfidenceLevel.HIGH): DecisionAction.DIRECT_ANSWER,
        (InfoNeedType.LOCAL_KNOWLEDGE, ConfidenceLevel.MEDIUM): DecisionAction.DIRECT_ANSWER,
        (InfoNeedType.LOCAL_KNOWLEDGE, ConfidenceLevel.LOW): DecisionAction.SUGGEST_COMM,

        # AMBIENT_STATE: Always use local capabilities (status checks, config reads)
        (InfoNeedType.AMBIENT_STATE, ConfidenceLevel.HIGH): DecisionAction.LOCAL_CAPABILITY,
        (InfoNeedType.AMBIENT_STATE, ConfidenceLevel.MEDIUM): DecisionAction.LOCAL_CAPABILITY,
        (InfoNeedType.AMBIENT_STATE, ConfidenceLevel.LOW): DecisionAction.LOCAL_CAPABILITY,

        # EXTERNAL_FACT_UNCERTAIN: Always require communication for accuracy
        (InfoNeedType.EXTERNAL_FACT_UNCERTAIN, ConfidenceLevel.HIGH): DecisionAction.REQUIRE_COMM,
        (InfoNeedType.EXTERNAL_FACT_UNCERTAIN, ConfidenceLevel.MEDIUM): DecisionAction.REQUIRE_COMM,
        (InfoNeedType.EXTERNAL_FACT_UNCERTAIN, ConfidenceLevel.LOW): DecisionAction.REQUIRE_COMM,

        # OPINION: Confidence-dependent, but suggest comm for external perspectives
        (InfoNeedType.OPINION, ConfidenceLevel.HIGH): DecisionAction.DIRECT_ANSWER,
        (InfoNeedType.OPINION, ConfidenceLevel.MEDIUM): DecisionAction.SUGGEST_COMM,
        (InfoNeedType.OPINION, ConfidenceLevel.LOW): DecisionAction.REQUIRE_COMM,
    }

    def decide(
        self,
        info_type: InfoNeedType,
        confidence: ConfidenceLevel
    ) -> DecisionAction:
        """
        Determine decision action based on info type and confidence.

        Args:
            info_type: Classified information need type
            confidence: LLM confidence level

        Returns:
            Recommended decision action
        """
        # Look up in matrix
        action = self.MATRIX.get(
            (info_type, confidence),
            DecisionAction.SUGGEST_COMM  # Safe default
        )

        logger.debug(
            f"Decision matrix: {info_type.value} + {confidence.value} "
            f"-> {action.value}"
        )

        return action


class InfoNeedClassifier:
    """
    Main classifier for information need classification.

    This is the primary entry point for classification. It orchestrates:
    1. Rule-based filtering (fast path)
    2. LLM self-assessment (when needed)
    3. Decision matrix lookup

    Usage:
        classifier = InfoNeedClassifier()
        result = await classifier.classify("What is the latest Python version?")

        if result.decision_action == DecisionAction.REQUIRE_COMM:
            # Use communication capability
            pass
        elif result.decision_action == DecisionAction.LOCAL_CAPABILITY:
            # Use local tools
            pass
        else:
            # Direct answer or suggest comm
            pass
    """

    def __init__(
        self,
        config: Optional[Dict] = None,
        llm_callable: Optional[Any] = None
    ):
        """
        Initialize InfoNeedClassifier.

        Args:
            config: Optional configuration dictionary
            llm_callable: Optional callable for LLM invocation (for testing/mocking)
        """
        self.config = config or {}
        self.rule_filter = RuleBasedFilter()
        self.llm_evaluator = LLMConfidenceEvaluator(llm_callable=llm_callable)
        self.decision_matrix = DecisionMatrix()

        # Configuration options
        self.enable_llm_evaluation = self.config.get("enable_llm_evaluation", True)
        self.llm_threshold = self.config.get("llm_threshold", 0.5)

    async def classify(
        self,
        message: str,
        session_id: Optional[str] = None
    ) -> ClassificationResult:
        """
        Complete classification pipeline for user message.

        This is the main entry point for classification. It performs:
        1. Rule-based filtering for fast signals
        2. Preliminary type determination
        3. LLM self-assessment (if needed)
        4. Final type and confidence determination
        5. Decision matrix lookup
        6. Audit logging (non-blocking)

        Args:
            message: User's message to classify
            session_id: Optional session ID for audit trail

        Returns:
            Complete ClassificationResult with decision action and reasoning
        """
        logger.info(f"Classifying message: {message[:100]}...")

        # Track start time for latency measurement
        start_time = time.time()

        # Generate unique message ID for this classification
        message_id = str(uuid.uuid4())

        # Step 1: Rule-based filtering
        signals = self.rule_filter.filter(message)
        logger.debug(
            f"Rule signals: strength={signals.signal_strength:.2f}, "
            f"matches={len(signals.matched_keywords)}"
        )

        # Step 2: Determine preliminary type based on rules
        preliminary_type = self._determine_type(signals)
        logger.debug(f"Preliminary type: {preliminary_type.value}")

        # Step 3: LLM self-assessment (if needed)
        llm_result = None
        if self._needs_llm_evaluation(preliminary_type, signals):
            logger.debug("LLM evaluation needed")
            if self.enable_llm_evaluation:
                try:
                    llm_result = await self.llm_evaluator.evaluate(message)
                except Exception as e:
                    logger.warning(f"LLM evaluation failed, continuing without it: {e}")
            else:
                logger.debug("LLM evaluation disabled by config")

        # Step 4: Finalize type and confidence
        final_type = self._finalize_type(preliminary_type, signals, llm_result)
        confidence = self._determine_confidence(signals, llm_result)

        logger.debug(
            f"Final classification: type={final_type.value}, "
            f"confidence={confidence.value}"
        )

        # Step 5: Decision matrix lookup
        action = self.decision_matrix.decide(final_type, confidence)
        logger.info(f"Decision action: {action.value}")

        # Step 6: Generate reasoning
        reasoning = self._generate_reasoning(final_type, signals, llm_result, action)

        # Step 7: Create result
        result = ClassificationResult(
            info_need_type=final_type,
            decision_action=action,
            confidence_level=confidence,
            rule_signals=signals,
            llm_confidence=llm_result,
            reasoning=reasoning,
            timestamp=utc_now(),
        )

        logger.info(f"Classification complete: {result.info_need_type.value} -> {result.decision_action.value}")

        # Step 8: Log to audit trail (non-blocking, fire-and-forget)
        latency_ms = (time.time() - start_time) * 1000
        try:
            await self._log_classification_audit(
                message_id=message_id,
                message=message,
                result=result,
                session_id=session_id,
                latency_ms=latency_ms,
            )
        except Exception as e:
            # Audit logging failure should never break classification
            logger.warning(f"Failed to log classification to audit trail: {e}")

        # Store message_id in result metadata for correlation with outcomes
        result.message_id = message_id  # type: ignore

        return result

    def _determine_type(self, signals: ClassificationSignal) -> InfoNeedType:
        """
        Determine preliminary information need type based on rule signals.

        This uses a rule-based heuristic to make an initial classification.
        The classification may be refined later with LLM input.

        Args:
            signals: Rule-based classification signals

        Returns:
            Preliminary InfoNeedType
        """
        # Strong signal: Ambient state
        if signals.has_ambient_state_keywords:
            return InfoNeedType.AMBIENT_STATE

        # Strong signal: Code structure (check for code patterns in matched keywords)
        code_matches = [k for k in signals.matched_keywords if k.startswith("code:")]
        if code_matches:
            return InfoNeedType.LOCAL_DETERMINISTIC

        # Medium signal: Time-sensitive + Authoritative
        if signals.has_time_sensitive_keywords and signals.has_authoritative_keywords:
            return InfoNeedType.EXTERNAL_FACT_UNCERTAIN

        # Medium signal: Only time-sensitive
        if signals.has_time_sensitive_keywords:
            return InfoNeedType.EXTERNAL_FACT_UNCERTAIN

        # Medium signal: Only authoritative
        if signals.has_authoritative_keywords:
            return InfoNeedType.EXTERNAL_FACT_UNCERTAIN

        # Weak signal: Opinion indicators
        opinion_matches = [k for k in signals.matched_keywords if k.startswith("opinion:")]
        if opinion_matches:
            return InfoNeedType.OPINION

        # Default: Treat as local knowledge (can be refined by LLM)
        return InfoNeedType.LOCAL_KNOWLEDGE

    def _needs_llm_evaluation(
        self,
        preliminary_type: InfoNeedType,
        signals: ClassificationSignal
    ) -> bool:
        """
        Determine if LLM self-assessment is needed.

        LLM evaluation is expensive, so we only use it when:
        1. Rule signals are weak (ambiguous case)
        2. Type is LOCAL_KNOWLEDGE or OPINION (confidence matters)

        We skip LLM for:
        - LOCAL_DETERMINISTIC (always use local tools)
        - AMBIENT_STATE (always use local tools)
        - EXTERNAL_FACT_UNCERTAIN with strong signals (clearly needs comm)

        Args:
            preliminary_type: Preliminary classification
            signals: Rule signals

        Returns:
            True if LLM evaluation should be performed
        """
        # Skip for types that don't benefit from LLM input
        if preliminary_type in [
            InfoNeedType.LOCAL_DETERMINISTIC,
            InfoNeedType.AMBIENT_STATE
        ]:
            return False

        # For EXTERNAL_FACT_UNCERTAIN with strong signals, skip LLM
        if (preliminary_type == InfoNeedType.EXTERNAL_FACT_UNCERTAIN and
                signals.signal_strength >= 0.7):
            return False

        # For LOCAL_KNOWLEDGE and OPINION, use LLM to assess confidence
        if preliminary_type in [InfoNeedType.LOCAL_KNOWLEDGE, InfoNeedType.OPINION]:
            return True

        # For weak signals, use LLM to help classify
        if signals.signal_strength < self.llm_threshold:
            return True

        return False

    def _finalize_type(
        self,
        preliminary_type: InfoNeedType,
        signals: ClassificationSignal,
        llm_result: Optional[LLMConfidenceResult]
    ) -> InfoNeedType:
        """
        Finalize information need type using LLM input.

        This combines rule-based signals with LLM assessment to make
        the final type determination.

        Args:
            preliminary_type: Type from rule-based classification
            signals: Rule signals
            llm_result: Optional LLM confidence result

        Returns:
            Final InfoNeedType
        """
        # If no LLM result, use preliminary type
        if llm_result is None:
            return preliminary_type

        # Strong rule signals override LLM
        if signals.signal_strength >= 0.7:
            return preliminary_type

        # Use LLM reason to refine classification
        reason = llm_result.reason.lower()

        if "time-sensitive" in reason:
            return InfoNeedType.EXTERNAL_FACT_UNCERTAIN
        elif "authoritative" in reason:
            return InfoNeedType.EXTERNAL_FACT_UNCERTAIN
        elif "stable" in reason:
            return InfoNeedType.LOCAL_KNOWLEDGE
        elif "uncertain" in reason or "outdated" in reason:
            # Keep preliminary type but flag as uncertain
            if preliminary_type == InfoNeedType.LOCAL_KNOWLEDGE:
                return InfoNeedType.LOCAL_KNOWLEDGE
            else:
                return InfoNeedType.EXTERNAL_FACT_UNCERTAIN

        # Default: use preliminary type
        return preliminary_type

    def _determine_confidence(
        self,
        signals: ClassificationSignal,
        llm_result: Optional[LLMConfidenceResult]
    ) -> ConfidenceLevel:
        """
        Determine overall confidence level.

        This combines rule signal strength with LLM confidence assessment.

        Args:
            signals: Rule signals
            llm_result: Optional LLM confidence result

        Returns:
            Overall ConfidenceLevel
        """
        # If LLM result available, use it directly
        if llm_result is not None:
            return llm_result.confidence

        # Otherwise, infer from signal strength
        if signals.signal_strength >= 0.8:
            return ConfidenceLevel.HIGH
        elif signals.signal_strength >= 0.5:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def _generate_reasoning(
        self,
        info_type: InfoNeedType,
        signals: ClassificationSignal,
        llm_result: Optional[LLMConfidenceResult],
        action: DecisionAction
    ) -> str:
        """
        Generate human-readable reasoning for the classification.

        This explains WHY the classification was made, which is useful for:
        - Debugging
        - User transparency
        - Audit trails

        Args:
            info_type: Final information need type
            signals: Rule signals
            llm_result: Optional LLM confidence result
            action: Decision action

        Returns:
            Human-readable reasoning string
        """
        parts = []

        # Type reasoning
        parts.append(f"Classified as {info_type.value}.")

        # Rule signals
        if signals.matched_keywords:
            parts.append(
                f"Rule-based signals (strength={signals.signal_strength:.2f}): "
                f"{', '.join(signals.matched_keywords[:5])}"
            )

        # LLM reasoning
        if llm_result:
            parts.append(
                f"LLM self-assessment: {llm_result.confidence.value} confidence "
                f"({llm_result.reason})"
            )
            if llm_result.reasoning:
                parts.append(f"LLM reasoning: {llm_result.reasoning}")

        # Decision action
        action_explanation = {
            DecisionAction.DIRECT_ANSWER: "Can answer directly from LLM knowledge",
            DecisionAction.LOCAL_CAPABILITY: "Requires local tools (file system, status checks, etc.)",
            DecisionAction.REQUIRE_COMM: "Requires communication capability for up-to-date information",
            DecisionAction.SUGGEST_COMM: "Can answer but communication may improve accuracy",
        }
        parts.append(f"Decision: {action_explanation.get(action, action.value)}")

        return ". ".join(parts) + "."

    async def _log_classification_audit(
        self,
        message_id: str,
        message: str,
        result: ClassificationResult,
        session_id: Optional[str],
        latency_ms: float,
    ) -> None:
        """
        Log classification event to audit trail and MemoryOS.

        This is a non-blocking operation that records the classification decision
        for later analysis and validation.

        Args:
            message_id: Unique message identifier
            message: User's original question
            result: Classification result
            session_id: Session ID (if available)
            latency_ms: Classification latency in milliseconds
        """
        from agentos.core.audit import log_info_need_classification
        from agentos.core.memory.info_need_writer import InfoNeedMemoryWriter

        # Extract signal data
        signals = {
            "time_sensitive": result.rule_signals.has_time_sensitive_keywords,
            "authoritative": result.rule_signals.has_authoritative_keywords,
            "ambient": result.rule_signals.has_ambient_state_keywords,
            "signal_strength": result.rule_signals.signal_strength,
        }

        # Extract LLM confidence data (if available)
        llm_confidence = None
        if result.llm_confidence:
            llm_confidence = result.llm_confidence.to_dict()

        # Log to audit trail
        await log_info_need_classification(
            message_id=message_id,
            session_id=session_id or "unknown",
            question=message,
            classified_type=result.info_need_type.value,
            confidence=result.confidence_level.value,
            decision=result.decision_action.value,
            signals=signals,
            rule_matches=result.rule_signals.matched_keywords,
            llm_confidence=llm_confidence,
            latency_ms=latency_ms,
        )

        # Write to MemoryOS (non-blocking, fire-and-forget)
        try:
            writer = InfoNeedMemoryWriter()
            await writer.write_judgment(
                classification_result=result,
                session_id=session_id or "unknown",
                message_id=message_id,
                question_text=message,
                phase="planning",  # Default to planning phase
                mode=None,  # Will be set by ChatEngine if available
                trust_tier=None,
                latency_ms=latency_ms,
            )
        except Exception as e:
            # MemoryOS write failure should never break classification
            logger.warning(f"Failed to write judgment to MemoryOS: {e}")


# Convenience function for quick classification
async def classify_info_need(
    message: str,
    config: Optional[Dict] = None,
    llm_callable: Optional[Any] = None
) -> ClassificationResult:
    """
    Convenience function for one-off classification.

    For repeated classifications, create a classifier instance and reuse it.

    Args:
        message: User's message to classify
        config: Optional configuration
        llm_callable: Optional LLM callable (for testing/mocking)

    Returns:
        ClassificationResult
    """
    classifier = InfoNeedClassifier(config=config, llm_callable=llm_callable)
    return await classifier.classify(message)
