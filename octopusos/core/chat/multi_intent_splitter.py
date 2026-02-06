"""
Multi-Intent Question Splitter

This module implements rule-based question splitting to handle composite questions
like "What time is it? And what's the latest AI policy?"

Key principles:
- Rule-based (no LLM) for low latency and cost
- Conservative: When uncertain, don't split (preserve original question)
- Context preservation: Split sub-questions retain necessary context

Performance target: < 5ms (p95)
"""

import re
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class SubQuestion:
    """Represents a split sub-question from a composite question."""

    text: str
    """The text content of the sub-question"""

    index: int
    """Zero-based index of this sub-question in the split sequence"""

    original_start: int
    """Character position where this sub-question starts in original text"""

    original_end: int
    """Character position where this sub-question ends in original text"""

    needs_context: bool = False
    """Whether this sub-question requires context from previous questions"""

    context_hint: Optional[str] = None
    """Hint about what context is needed (e.g., 'pronoun_reference')"""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "text": self.text,
            "index": self.index,
            "original_start": self.original_start,
            "original_end": self.original_end,
            "needs_context": self.needs_context,
            "context_hint": self.context_hint,
        }


class MultiIntentSplitter:
    """
    Rule-based multi-intent question splitter.

    This splitter identifies composite questions containing multiple intents
    and splits them into individual sub-questions. It uses pattern matching
    on connectors, punctuation, and enumeration markers.

    The splitter is conservative: when uncertain, it preserves the original
    question rather than risk incorrect splitting.

    Usage:
        splitter = MultiIntentSplitter()
        if splitter.should_split(question):
            sub_questions = splitter.split(question)
            for sub_q in sub_questions:
                process(sub_q.text)
    """

    # Chinese connectors that suggest separate intents
    CHINESE_CONNECTORS = [
        "以及",
        "还有",
        "另外",
        "同时",
        "顺便",
        "而且",
        "并且",
        "再者",
        "此外",
    ]

    # English connectors that suggest separate intents
    ENGLISH_CONNECTORS = [
        "and also",
        "also",
        "additionally",
        "as well as",
        "by the way",
        "furthermore",
        "moreover",
        "besides",
    ]

    # Punctuation patterns that indicate question boundaries
    QUESTION_BOUNDARY_PUNCTUATION = [
        (r'[。.][？?]', 'period_question'),  # Period followed by question mark
        (r'[；;]', 'semicolon'),  # Semicolon
    ]

    # Enumeration patterns
    ENUMERATION_PATTERNS = [
        (r'^\s*(\d+)[.、）\)]\s*', 'numeric'),  # 1. 2. or 1、2、 or 1) 2)
        (r'^\s*[（(](\d+)[）)]\s*', 'numeric_paren'),  # (1) (2)
        (r'^\s*(first|second|third|fourth|fifth|then|next)[,，]\s*', 'ordinal_en'),
        (r'^\s*(第[一二三四五六七八九十]+[条款项点]?)[,，、]\s*', 'ordinal_zh'),
    ]

    # Context indicators (pronouns, demonstratives)
    CONTEXT_INDICATORS = {
        'en': [
            r'\b(he|she|it|they|them|his|her|its|their|this|that|these|those)\b',
            r'\b(the former|the latter)\b',
        ],
        'zh': [
            r'[他她它们]的?',
            r'这[个些]?',
            r'那[个些]?',
            r'前者|后者',
        ],
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the multi-intent splitter.

        Args:
            config: Configuration dictionary with options:
                - min_length: Minimum sub-question length (default: 3)
                - max_splits: Maximum number of splits allowed (default: 3)
                - enable_context: Whether to detect and mark context needs (default: True)
        """
        self.config = config or {}
        self.min_length = self.config.get('min_length', 3)  # Lower for Chinese text
        self.max_splits = self.config.get('max_splits', 3)
        self.enable_context = self.config.get('enable_context', True)

    def should_split(self, question: str) -> bool:
        """
        Determine if a question should be split into multiple intents.

        This is a fast pre-check to avoid unnecessary processing.

        Args:
            question: The question to evaluate

        Returns:
            True if the question likely contains multiple intents
        """
        if not question or len(question.strip()) < self.min_length:
            return False

        # Check for connector patterns
        for connector in self.CHINESE_CONNECTORS + self.ENGLISH_CONNECTORS:
            if connector.lower() in question.lower():
                return True

        # Check for punctuation patterns
        for pattern, _ in self.QUESTION_BOUNDARY_PUNCTUATION:
            if re.search(pattern, question):
                return True

        # Check for enumeration patterns (both newline and space-separated)
        lines = question.split('\n')
        if len(lines) > 1:
            enum_count = 0
            for line in lines:
                for pattern, _ in self.ENUMERATION_PATTERNS:
                    if re.match(pattern, line.strip(), re.IGNORECASE):
                        enum_count += 1
                        break
            if enum_count >= 2:
                return True

        # Check for space-separated enumeration
        space_enum_pattern = r'(\d+)[.、）\)]\s+'
        enum_matches = re.findall(space_enum_pattern, question)
        if len(enum_matches) >= 2:
            return True

        # Check for ordinal enumeration
        ordinal_pattern = r'\b(first|second|third|fourth|fifth|then|next)[,،]\s+'
        ordinal_matches = re.findall(ordinal_pattern, question, re.IGNORECASE)
        if len(ordinal_matches) >= 2:
            return True

        # Check for multiple question marks
        question_marks = question.count('?') + question.count('？')
        if question_marks >= 2:
            return True

        return False

    def split(self, question: str) -> List[SubQuestion]:
        """
        Split a question into sub-questions based on detected patterns.

        Args:
            question: The composite question to split

        Returns:
            List of SubQuestion objects. Returns empty list if no split needed.
        """
        if not self.should_split(question):
            return []

        # Try different splitting strategies in order of confidence
        candidates = []

        # Strategy 1: Enumeration-based splitting (highest confidence)
        enum_splits = self._split_by_enumeration(question)
        if enum_splits:
            candidates.append(('enumeration', enum_splits))

        # Strategy 2: Multiple question marks splitting
        qmark_splits = self._split_by_question_marks(question)
        if qmark_splits:
            candidates.append(('question_marks', qmark_splits))

        # Strategy 3: Punctuation-based splitting
        punct_splits = self._split_by_punctuation(question)
        if punct_splits:
            candidates.append(('punctuation', punct_splits))

        # Strategy 4: Connector-based splitting
        connector_splits = self._split_by_connector(question)
        if connector_splits:
            candidates.append(('connector', connector_splits))

        # Select best split strategy
        if not candidates:
            logger.debug("No valid split candidates found")
            return []

        # Use the first valid strategy (ordered by confidence)
        strategy, splits = candidates[0]

        # Validate all splits
        valid_splits = self._validate_splits(splits, question)

        if not valid_splits or len(valid_splits) <= 1:
            logger.debug(f"Splits did not pass validation: {len(valid_splits)} valid")
            return []

        # Check max_splits limit
        if len(valid_splits) > self.max_splits:
            logger.debug(f"Too many splits ({len(valid_splits)} > {self.max_splits}), not splitting")
            return []

        # Add context hints if enabled
        if self.enable_context:
            self._add_context_hints(valid_splits)

        logger.info(f"Split question into {len(valid_splits)} sub-questions using {strategy} strategy")
        return valid_splits

    def _split_by_enumeration(self, text: str) -> List[SubQuestion]:
        """
        Split by enumeration patterns (1. 2. or 1) 2) etc.).

        Args:
            text: Text to split

        Returns:
            List of SubQuestion objects
        """
        lines = text.split('\n')
        splits = []
        current_pos = 0

        for line_idx, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                current_pos += len(line) + 1  # +1 for newline
                continue

            # Check if line starts with enumeration
            matched = False
            for pattern, pattern_type in self.ENUMERATION_PATTERNS:
                match = re.match(pattern, line_stripped, re.IGNORECASE)
                if match:
                    # Extract the question part (after the enumeration marker)
                    question_text = line_stripped[match.end():].strip()
                    if question_text:
                        splits.append(SubQuestion(
                            text=question_text,
                            index=len(splits),
                            original_start=current_pos + match.end(),
                            original_end=current_pos + len(line),
                        ))
                    matched = True
                    break

            current_pos += len(line) + 1  # +1 for newline

        # If newline-based didn't work, try space-separated enumeration
        if len(splits) < 2:
            splits = self._split_by_space_enumeration(text)

        return splits if len(splits) >= 2 else []

    def _split_by_space_enumeration(self, text: str) -> List[SubQuestion]:
        """
        Split by space-separated enumeration (e.g., "1. A 2. B 3. C").

        Args:
            text: Text to split

        Returns:
            List of SubQuestion objects
        """
        splits = []

        # Find all enumeration markers in the text
        # Remove ^ anchor for non-newline-based matching
        enum_matches = []
        space_enum_patterns = [
            (r'(\d+)[.、）\)]\s+', 'numeric'),  # Remove ^ and require space after
            (r'[（(](\d+)[）)]\s+', 'numeric_paren'),
            (r'(first|second|third|fourth|fifth|then|next)[,，]\s+', 'ordinal_en'),
            (r'(第[一二三四五六七八九十]+[条款项点]?)[,،、]\s+', 'ordinal_zh'),
        ]

        for pattern, pattern_type in space_enum_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                enum_matches.append((match.start(), match.end(), pattern_type))

        if len(enum_matches) < 2:
            return []

        # Sort by position
        enum_matches.sort(key=lambda x: x[0])

        # Extract text between enumeration markers
        for i, (start, end, pattern_type) in enumerate(enum_matches):
            # Determine where this enumerated item ends
            if i + 1 < len(enum_matches):
                # Ends where next enumeration starts
                item_end = enum_matches[i + 1][0]
            else:
                # Last item, ends at text end
                item_end = len(text)

            # Extract the text for this item (after the marker)
            item_text = text[end:item_end].strip()

            if item_text:
                splits.append(SubQuestion(
                    text=item_text,
                    index=len(splits),
                    original_start=end,
                    original_end=item_end,
                ))

        return splits

    def _split_by_question_marks(self, text: str) -> List[SubQuestion]:
        """
        Split by multiple question marks (? or ？).

        This handles cases like "现在几点？今天天气如何？" where questions
        are back-to-back without explicit separators.

        Args:
            text: Text to split

        Returns:
            List of SubQuestion objects
        """
        # Find all question mark positions
        qmark_positions = []
        for i, char in enumerate(text):
            if char in '?？':
                qmark_positions.append(i)

        if len(qmark_positions) < 2:
            return []

        # Split at question mark positions
        splits = []
        last_end = 0

        for pos in qmark_positions:
            # Extract text from last_end to just after this question mark
            segment = text[last_end:pos + 1].strip()

            if segment:
                splits.append(SubQuestion(
                    text=segment,
                    index=len(splits),
                    original_start=last_end,
                    original_end=pos + 1,
                ))

            last_end = pos + 1

        # Add remaining text if any (no question mark at end)
        if last_end < len(text):
            remaining = text[last_end:].strip()
            if remaining:
                splits.append(SubQuestion(
                    text=remaining,
                    index=len(splits),
                    original_start=last_end,
                    original_end=len(text),
                ))

        return splits if len(splits) >= 2 else []

    def _split_by_punctuation(self, text: str) -> List[SubQuestion]:
        """
        Split by punctuation patterns (.? or ;).

        Args:
            text: Text to split

        Returns:
            List of SubQuestion objects
        """
        splits = []
        last_end = 0

        for pattern, pattern_type in self.QUESTION_BOUNDARY_PUNCTUATION:
            for match in re.finditer(pattern, text):
                # Extract text from last_end to current match
                segment = text[last_end:match.end()].strip()

                if segment:
                    # Remove the boundary punctuation for cleaner sub-questions
                    if pattern_type == 'semicolon':
                        segment = segment.rstrip('；;').strip()

                    splits.append(SubQuestion(
                        text=segment,
                        index=len(splits),
                        original_start=last_end,
                        original_end=match.end(),
                    ))

                last_end = match.end()

        # Add remaining text if any
        if last_end < len(text):
            remaining = text[last_end:].strip()
            if remaining:
                splits.append(SubQuestion(
                    text=remaining,
                    index=len(splits),
                    original_start=last_end,
                    original_end=len(text),
                ))

        return splits if len(splits) >= 2 else []

    def _split_by_connector(self, text: str) -> List[SubQuestion]:
        """
        Split by connector words (and also, 以及, etc.).

        This is the most conservative strategy as connectors can
        sometimes link parallel components rather than separate questions.

        Args:
            text: Text to split

        Returns:
            List of SubQuestion objects
        """
        # Find all connector positions
        connectors_found = []

        for connector in self.CHINESE_CONNECTORS + self.ENGLISH_CONNECTORS:
            # Case-insensitive search
            pattern = re.escape(connector)
            for match in re.finditer(pattern, text, re.IGNORECASE):
                connectors_found.append((match.start(), match.end(), connector))

        if not connectors_found:
            return []

        # Sort by position
        connectors_found.sort(key=lambda x: x[0])

        # Split at connector positions
        splits = []
        last_end = 0

        for start, end, connector in connectors_found:
            # Extract text before connector and strip trailing punctuation
            before = text[last_end:start].strip().rstrip(',，、')
            if before:
                splits.append(SubQuestion(
                    text=before,
                    index=len(splits),
                    original_start=last_end,
                    original_end=start,
                ))

            last_end = end

        # Add remaining text after last connector
        if last_end < len(text):
            after = text[last_end:].strip().lstrip(',，、 ')
            # Strip leading connectors that may have been left
            for conn in ['and ', 'or ', 'but ', 'also ']:
                if after.lower().startswith(conn):
                    after = after[len(conn):].lstrip()
                    break
            if after:
                splits.append(SubQuestion(
                    text=after,
                    index=len(splits),
                    original_start=last_end,
                    original_end=len(text),
                ))

        return splits if len(splits) >= 2 else []

    def _validate_splits(self, splits: List[SubQuestion], original: str) -> List[SubQuestion]:
        """
        Validate that all splits meet quality criteria.

        Args:
            splits: Candidate sub-questions
            original: Original question text

        Returns:
            List of valid SubQuestion objects
        """
        valid = []

        for sub_q in splits:
            # Check minimum length
            if len(sub_q.text.strip()) < self.min_length:
                logger.debug(f"Sub-question too short: '{sub_q.text[:20]}...'")
                continue

            # Check if it looks like a question or statement
            # Valid sub-questions should have some content substance
            if not self._has_question_substance(sub_q.text):
                logger.debug(f"Sub-question lacks substance: '{sub_q.text[:20]}...'")
                continue

            valid.append(sub_q)

        return valid

    def _has_question_substance(self, text: str) -> bool:
        """
        Check if text has substance of a question or statement.

        Valid sub-questions should contain:
        - Question words (what, how, 什么, 如何, etc.) OR
        - Question marks (?, ？) OR
        - Content words (nouns, verbs) suggesting a question or command
        - At least 2 characters of actual content

        This is intentionally lenient to avoid over-filtering.
        Conservative strategy: accept unless clearly invalid.

        Args:
            text: Text to check

        Returns:
            True if text has question substance
        """
        # Check for question markers
        question_markers = [
            'what', 'how', 'when', 'where', 'why', 'who', 'which',
            '什么', '如何', '怎么', '怎样', '为什么', '哪里', '谁', '哪个',
            '?', '？', 'is', 'are', 'do', 'does', 'can', 'could', 'should',
            '是', '吗', '呢', 'show', 'tell', 'explain', 'describe',
            '显示', '告诉', '解释', '说明', '描述', '查看', '检查',
        ]

        text_lower = text.lower()
        for marker in question_markers:
            if marker.lower() in text_lower:
                return True

        # Check for content words (at least 2 non-whitespace characters)
        content_chars = re.findall(r'\w', text)
        if len(content_chars) >= 2:
            # Has enough content, likely valid
            return True

        return False

    def _add_context_hints(self, splits: List[SubQuestion]) -> None:
        """
        Add context hints to sub-questions that need context.

        This detects pronouns and demonstratives that refer to
        previous content and marks them as needing context.

        Args:
            splits: List of SubQuestion objects to annotate (modified in-place)
        """
        for i, sub_q in enumerate(splits):
            if i == 0:
                # First question doesn't need context from previous
                continue

            # Check for context indicators
            needs_context = False
            hint = None

            # Check English patterns
            for pattern in self.CONTEXT_INDICATORS['en']:
                if re.search(pattern, sub_q.text, re.IGNORECASE):
                    needs_context = True
                    hint = 'pronoun_reference'
                    break

            # Check Chinese patterns
            if not needs_context:
                for pattern in self.CONTEXT_INDICATORS['zh']:
                    if re.search(pattern, sub_q.text):
                        needs_context = True
                        hint = 'pronoun_reference'
                        break

            # Check for incomplete questions (starts with "and", "or", etc.)
            incomplete_starters = ['and', 'or', 'but', '和', '或', '但']
            for starter in incomplete_starters:
                if sub_q.text.lower().startswith(starter):
                    needs_context = True
                    hint = 'incomplete_sentence'
                    break

            if needs_context:
                sub_q.needs_context = True
                sub_q.context_hint = hint
                logger.debug(f"Sub-question {i} needs context: {hint}")


def split_question(
    question: str,
    config: Optional[Dict[str, Any]] = None
) -> List[SubQuestion]:
    """
    Convenience function for one-off question splitting.

    For repeated splitting, create a MultiIntentSplitter instance and reuse it.

    Args:
        question: Question to split
        config: Optional configuration dictionary

    Returns:
        List of SubQuestion objects (empty if no split needed)
    """
    splitter = MultiIntentSplitter(config=config)
    return splitter.split(question)
