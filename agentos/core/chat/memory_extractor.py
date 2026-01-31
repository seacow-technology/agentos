"""
Rule-based Memory Extractor for Chat Messages

This module extracts memory items from user/assistant messages using pattern matching.
It identifies personal information, preferences, and technical details that should be
remembered across sessions.

Design Principle:
- Use explicit rule patterns (Chinese + English)
- High confidence (0.9) for rule-based extraction
- Async integration to avoid blocking chat flow
- Detailed logging for observability
"""

from __future__ import annotations

import re
import uuid
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from agentos.core.chat.models_base import ChatMessage
from agentos.core.time import utc_now_iso

logger = logging.getLogger(__name__)


@dataclass
class ExtractionRule:
    """Represents a memory extraction rule"""
    pattern: str  # Regex pattern
    memory_type: str  # preference, fact, contact
    key: str  # Memory key (e.g., "preferred_name", "email")
    tags: List[str]  # Tags for categorization
    scope: str = "global"  # Default scope
    confidence: float = 0.9  # High confidence for rule-based


class MemoryExtractor:
    """
    Rule-based memory extractor for chat messages.

    Extracts structured memory items from conversational text using
    pattern matching rules. Supports both Chinese and English.
    """

    def __init__(self):
        """Initialize with extraction rules"""
        self.rules = self._build_rules()
        logger.info(f"MemoryExtractor initialized with {len(self.rules)} rules")

    def _build_rules(self) -> List[ExtractionRule]:
        """
        Build extraction rules for different memory types.

        Returns:
            List of extraction rules
        """
        rules = []

        # ========================================
        # 1. PREFERRED NAME RULES
        # ========================================

        # Chinese patterns
        rules.append(ExtractionRule(
            pattern=r'(?:以后|今后)?(?:请|可以)?(?:叫我|称呼我|喊我)\s*["""\']*([^，。！？\s]{1,20})["""\']*',
            memory_type="preference",
            key="preferred_name",
            tags=["user_preference", "name"],
            scope="global"
        ))

        rules.append(ExtractionRule(
            pattern=r'(?:我叫|我是|本人)\s*["""\']*([^，。！？\s]{1,20})["""\']*',
            memory_type="preference",
            key="preferred_name",
            tags=["user_preference", "name"],
            scope="global"
        ))

        # English patterns
        rules.append(ExtractionRule(
            pattern=r'(?:call me|you can call me|please call me)\s+["""\']*([A-Za-z\u4e00-\u9fa5\s]{1,20})["""\']*',
            memory_type="preference",
            key="preferred_name",
            tags=["user_preference", "name"],
            scope="global"
        ))

        rules.append(ExtractionRule(
            pattern=r'(?:my name is|i am|i\'m)\s+["""\']*([A-Za-z\u4e00-\u9fa5\s]{1,20})["""\']*',
            memory_type="preference",
            key="preferred_name",
            tags=["user_preference", "name"],
            scope="global"
        ))

        # ========================================
        # 2. EMAIL RULES
        # ========================================

        # Chinese patterns
        rules.append(ExtractionRule(
            pattern=r'(?:我的)?邮箱(?:地址)?(?:是|为|:|：)\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            memory_type="contact",
            key="email",
            tags=["contact_info", "email"],
            scope="global"
        ))

        # Mixed Chinese-English pattern for email
        rules.append(ExtractionRule(
            pattern=r'(?:我的)?email(?:是|:|：)\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            memory_type="contact",
            key="email",
            tags=["contact_info", "email"],
            scope="global"
        ))

        # English patterns (more flexible)
        rules.append(ExtractionRule(
            pattern=r'(?:my )?email(?:\s+(?:address|is))?\s*(?::|is)?\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            memory_type="contact",
            key="email",
            tags=["contact_info", "email"],
            scope="global"
        ))

        # ========================================
        # 3. PHONE NUMBER RULES
        # ========================================

        # Chinese patterns (support multiple formats)
        rules.append(ExtractionRule(
            pattern=r'(?:我的)?(?:手机号|电话|联系方式)(?:是|为|:|：)\s*(1[3-9]\d{9})',
            memory_type="contact",
            key="phone",
            tags=["contact_info", "phone"],
            scope="global"
        ))

        # English patterns
        rules.append(ExtractionRule(
            pattern=r'(?:my )?(?:phone|mobile|cell)(?:\s+(?:number|is))?(?:\s*:|:\s*)\s*([+]?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9})',
            memory_type="contact",
            key="phone",
            tags=["contact_info", "phone"],
            scope="global"
        ))

        # ========================================
        # 4. COMPANY/ORGANIZATION RULES
        # ========================================

        # Chinese patterns
        rules.append(ExtractionRule(
            pattern=r'(?:我在|我是)\s*([^，。！？\s]{2,30})(?:公司|企业|组织)(?:工作|任职|上班)',
            memory_type="fact",
            key="company",
            tags=["personal_info", "company"],
            scope="global"
        ))

        # English patterns
        rules.append(ExtractionRule(
            pattern=r'(?:i work at|i\'m at|i work for)\s+([A-Za-z0-9\s&.]+?)(?:\s+(?:as|company|corp|inc|ltd)|\.|,|$)',
            memory_type="fact",
            key="company",
            tags=["personal_info", "company"],
            scope="global"
        ))

        # ========================================
        # 5. TECHNICAL PREFERENCE RULES
        # ========================================

        # Framework/language preferences (Chinese)
        rules.append(ExtractionRule(
            pattern=r'我(?:喜欢|偏好|倾向于|习惯)(?:使用|用)\s*([A-Za-z0-9\u4e00-\u9fa5.+#\s]{2,30})(?:框架|语言|工具|技术)',
            memory_type="preference",
            key="tech_preference",
            tags=["technical_preference", "framework"],
            scope="global"
        ))

        # Framework/language preferences (English)
        rules.append(ExtractionRule(
            pattern=r'(?:i prefer|i like to use|i use)\s+([A-Za-z0-9.+#\s]{2,30})(?:\s+(?:framework|language|tool|for))',
            memory_type="preference",
            key="tech_preference",
            tags=["technical_preference", "framework"],
            scope="global"
        ))

        # Dislike patterns (Chinese) - more explicit
        rules.append(ExtractionRule(
            pattern=r'(?:但)?(?:我)?(?:不喜欢|讨厌|不想用)\s*([A-Za-z0-9\u4e00-\u9fa5.+#]{2,20})(?:框架|语言|工具|技术)?',
            memory_type="preference",
            key="tech_dislike",
            tags=["technical_preference", "dislike"],
            scope="global"
        ))

        # Dislike patterns (English)
        rules.append(ExtractionRule(
            pattern=r'(?:i don\'t like|i dislike|i hate)\s+([A-Za-z0-9.+#\s]{2,30})(?:\s+(?:framework|language|tool))?',
            memory_type="preference",
            key="tech_dislike",
            tags=["technical_preference", "dislike"],
            scope="global"
        ))

        # ========================================
        # 6. PROJECT/DOMAIN RULES
        # ========================================

        # Project context (Chinese)
        rules.append(ExtractionRule(
            pattern=r'(?:我的项目|项目名称|这个项目)(?:是|叫|为|:|：)\s*([^，。！？\s]{2,30})',
            memory_type="fact",
            key="project_name",
            tags=["project_info", "context"],
            scope="project"
        ))

        # Project context (English)
        rules.append(ExtractionRule(
            pattern=r'(?:my project|project name|this project)(?:\s+is)?\s*(?::|called)?\s*([A-Za-z0-9\-_\s]{2,30})',
            memory_type="fact",
            key="project_name",
            tags=["project_info", "context"],
            scope="project"
        ))

        return rules

    def extract_memories(
        self,
        message: ChatMessage,
        session_id: str,
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract memory items from a chat message.

        Args:
            message: Chat message to extract from
            session_id: Current session ID
            project_id: Optional project ID (for project-scoped memories)

        Returns:
            List of extracted memory items (MemoryItem dicts)
        """
        # Only extract from user messages
        if message.role != "user":
            return []

        content = message.content.strip()
        if not content:
            return []

        extracted_memories = []

        # Apply each rule
        for rule in self.rules:
            matches = self._apply_rule(rule, content)

            for match_value in matches:
                memory_item = self._create_memory_item(
                    rule=rule,
                    value=match_value,
                    raw_text=content,
                    message_id=message.message_id,
                    session_id=session_id,
                    project_id=project_id
                )
                extracted_memories.append(memory_item)

                logger.info(
                    f"Extracted memory: type={rule.memory_type}, "
                    f"key={rule.key}, value={match_value[:50]}"
                )

        return extracted_memories

    def _apply_rule(self, rule: ExtractionRule, content: str) -> List[str]:
        """
        Apply a single extraction rule to content.

        Args:
            rule: Extraction rule to apply
            content: Message content

        Returns:
            List of extracted values
        """
        try:
            pattern = re.compile(rule.pattern, re.IGNORECASE | re.UNICODE)
            matches = pattern.findall(content)

            # Clean and validate matches
            cleaned_matches = []
            for match in matches:
                # Handle tuple results from groups
                if isinstance(match, tuple):
                    match = match[0] if match else ""

                match = str(match).strip()

                # Skip invalid matches
                if not match or len(match) < 1:
                    continue

                # Remove quotes
                match = match.strip('"\'""''')

                # Skip if still too short or just punctuation
                if len(match) < 1 or match in ['。', '，', '！', '？', '.', ',', '!', '?']:
                    continue

                cleaned_matches.append(match)

            return cleaned_matches

        except re.error as e:
            logger.error(f"Regex error in rule {rule.key}: {e}")
            return []

    def _create_memory_item(
        self,
        rule: ExtractionRule,
        value: str,
        raw_text: str,
        message_id: str,
        session_id: str,
        project_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Create a structured memory item from extraction.

        Args:
            rule: Extraction rule that matched
            value: Extracted value
            raw_text: Original message text
            message_id: Source message ID
            session_id: Current session ID
            project_id: Optional project ID

        Returns:
            MemoryItem dictionary conforming to schema
        """
        memory_id = f"mem-{uuid.uuid4().hex[:12]}"

        memory_item = {
            "id": memory_id,
            "scope": rule.scope,
            "type": rule.memory_type,
            "content": {
                "key": rule.key,
                "value": value,
                "raw_text": raw_text[:500]  # Truncate long texts
            },
            "tags": rule.tags,
            "confidence": rule.confidence,
            "sources": [
                {
                    "message_id": message_id,
                    "session_id": session_id
                }
            ]
        }

        # Add project_id for project-scoped memories
        if rule.scope == "project" and project_id:
            memory_item["project_id"] = project_id

        return memory_item

    def extract_and_log(
        self,
        message: ChatMessage,
        session_id: str,
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract memories and log statistics.

        This is a convenience method that wraps extract_memories
        with additional logging for observability.

        Args:
            message: Chat message to extract from
            session_id: Current session ID
            project_id: Optional project ID

        Returns:
            List of extracted memory items
        """
        memories = self.extract_memories(message, session_id, project_id)

        if memories:
            memory_types = {}
            for mem in memories:
                mem_type = mem["type"]
                memory_types[mem_type] = memory_types.get(mem_type, 0) + 1

            logger.info(
                f"Memory extraction completed: "
                f"session={session_id}, "
                f"extracted={len(memories)}, "
                f"types={memory_types}"
            )

        return memories

    def is_negative_case(self, message: ChatMessage) -> bool:
        """
        Check if message is a negative case (should not extract).

        Negative cases include:
        - Questions about names (not declarations)
        - General inquiries
        - System messages

        Args:
            message: Chat message to check

        Returns:
            True if this is a negative case, False otherwise
        """
        if message.role != "user":
            return True

        content = message.content.lower()

        # Question patterns that should not trigger extraction
        negative_patterns = [
            r'(?:你|您)叫什么',  # "你叫什么名字"
            r'what(?:\'s| is) your name',  # "what's your name"
            r'请问',  # Polite questions
            r'can you tell me',
            r'do you know',
            r'what is',
            r'who is',
        ]

        for pattern in negative_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False


# Global instance for easy access
_extractor_instance: Optional[MemoryExtractor] = None


def get_extractor() -> MemoryExtractor:
    """
    Get or create global memory extractor instance.

    Returns:
        Global MemoryExtractor instance
    """
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = MemoryExtractor()
    return _extractor_instance


async def extract_and_store_async(
    message: ChatMessage,
    session_id: str,
    memory_service,
    project_id: Optional[str] = None
) -> int:
    """
    Async wrapper for extracting and storing memories.

    This function extracts memories from a message and stores them
    in the memory service asynchronously to avoid blocking the chat flow.

    Args:
        message: Chat message to extract from
        session_id: Current session ID
        memory_service: MemoryService instance
        project_id: Optional project ID

    Returns:
        Number of memories extracted and stored
    """
    extractor = get_extractor()

    # Check negative cases first
    if extractor.is_negative_case(message):
        return 0

    # Extract memories
    memories = extractor.extract_and_log(message, session_id, project_id)

    # Store each memory
    stored_count = 0
    for memory in memories:
        try:
            memory_id = memory_service.upsert(memory)
            logger.debug(f"Stored memory: {memory_id}")
            stored_count += 1
        except Exception as e:
            logger.error(f"Failed to store memory: {e}", exc_info=True)

    return stored_count
