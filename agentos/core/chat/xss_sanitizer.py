"""XSS Sanitization for Chat Sessions and Messages.

This module provides XSS protection specifically for chat session titles
and message content, preserving legitimate content (emoji, Chinese, markdown)
while blocking malicious scripts.

Security Issue: Task #34 - P0-3: Fix Sessions/Chat API XSS vulnerability
- 4 XSS vectors were unsanitized in session title and message content
- Risk: Session hijacking, cookie theft, account takeover
"""

import html
import re
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# XSS attack patterns to detect and remove
XSS_PATTERNS = [
    # Script tags (various forms)
    (r'<script[^>]*>.*?</script>', 'SCRIPT_TAG'),
    (r'<script[^>]*>', 'SCRIPT_TAG_OPEN'),
    (r'</script>', 'SCRIPT_TAG_CLOSE'),

    # JavaScript protocol
    (r'javascript\s*:', 'JAVASCRIPT_PROTOCOL'),
    (r'jscript\s*:', 'JSCRIPT_PROTOCOL'),
    (r'vbscript\s*:', 'VBSCRIPT_PROTOCOL'),

    # Event handlers (comprehensive list)
    (r'on\w+\s*=', 'EVENT_HANDLER'),
    (r'\bon(abort|blur|change|click|dblclick|error|focus|keydown|keypress|keyup|'
     r'load|mousedown|mousemove|mouseout|mouseover|mouseup|reset|resize|select|'
     r'submit|unload|dragstart|drag|dragenter|dragleave|dragover|drop|dragend|'
     r'scroll|copy|cut|paste|beforecopy|beforecut|beforepaste|contextmenu|'
     r'input|invalid|search|touchstart|touchmove|touchend|touchcancel|'
     r'wheel|animationstart|animationend|animationiteration|transitionend)\s*=', 'SPECIFIC_EVENT'),

    # SVG/XML with script injection
    (r'<svg[^>]*\s+onload\s*=', 'SVG_ONLOAD'),
    (r'<svg[^>]*>', 'SVG_TAG'),  # Will be removed with nested checks

    # IMG with onerror
    (r'<img[^>]*\s+onerror\s*=', 'IMG_ONERROR'),
    (r'<img[^>]*\s+onload\s*=', 'IMG_ONLOAD'),
    (r'<img[^>]*\s+src\s*=\s*["\']?\s*javascript:', 'IMG_JAVASCRIPT_SRC'),

    # Data URLs with script
    (r'data:text/html[^,]*base64', 'DATA_HTML_BASE64'),
    (r'data:[^,]*,.*<script', 'DATA_SCRIPT'),

    # Object/embed/iframe tags
    (r'<(object|embed|iframe|frame|frameset|applet|link|meta|style|base)[^>]*>', 'DANGEROUS_TAG'),

    # Expression() in CSS
    (r'expression\s*\(', 'CSS_EXPRESSION'),
    (r'@import', 'CSS_IMPORT'),
    (r'behavior\s*:', 'CSS_BEHAVIOR'),

    # Document/window access attempts
    (r'\bdocument\s*\.\s*(cookie|domain|write|writeln)', 'DOCUMENT_ACCESS'),
    (r'\bwindow\s*\.\s*(location|open|eval)', 'WINDOW_ACCESS'),

    # Encoded attacks
    (r'&#(\d+);', 'HTML_ENTITY_DECIMAL'),
    (r'&#x([0-9a-fA-F]+);', 'HTML_ENTITY_HEX'),
    (r'\\u[0-9a-fA-F]{4}', 'UNICODE_ESCAPE'),
    (r'%[0-9a-fA-F]{2}', 'URL_ENCODE'),
]


def sanitize_html(text: str, preserve_safe_html: bool = False) -> str:
    """Sanitize HTML content to prevent XSS attacks.

    This function removes or neutralizes malicious HTML/JavaScript while
    preserving legitimate content like emoji, Chinese characters, and
    optionally safe HTML tags.

    Args:
        text: Text to sanitize
        preserve_safe_html: If True, preserve safe HTML tags like <b>, <i>, <code>
                           If False (default), escape all HTML

    Returns:
        Sanitized text
    """
    if not text or not isinstance(text, str):
        return text

    original_text = text
    threats_detected = []

    # Step 1: Detect and remove dangerous patterns
    for pattern, threat_type in XSS_PATTERNS:
        matches = list(re.finditer(pattern, text, re.IGNORECASE | re.DOTALL))
        if matches:
            threats_detected.append(f"{threat_type} ({len(matches)} occurrence(s))")
            # Remove the matched pattern
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)

    # Step 2: Handle encoded content - decode and re-check
    # This prevents bypasses like &#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&#116; (javascript)
    decoded_text = text

    # Decode HTML entities
    decoded_text = html.unescape(decoded_text)

    # Decode URL encoding
    try:
        import urllib.parse
        decoded_text = urllib.parse.unquote(decoded_text)
    except Exception:
        pass

    # Check if decoded content contains threats
    if decoded_text != text:
        for pattern, threat_type in XSS_PATTERNS:
            if re.search(pattern, decoded_text, re.IGNORECASE | re.DOTALL):
                threats_detected.append(f"ENCODED_{threat_type}")
                # Use the original text (before decoding) but remove suspicious patterns
                text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)

    # Step 3: HTML escape if not preserving safe HTML
    # ✅ quote=False: Don't escape quotes (' and ") - they're safe in text content
    # Only escape <, >, & which are dangerous for XSS
    if not preserve_safe_html:
        text = html.escape(text, quote=False)
    else:
        # Preserve only safe tags: <b>, <i>, <em>, <strong>, <code>, <pre>, <br>
        safe_tags = ['b', 'i', 'em', 'strong', 'code', 'pre', 'br', 'p', 'ul', 'ol', 'li']

        # Escape everything first (but not quotes)
        text = html.escape(text, quote=False)

        # Then un-escape safe tags
        for tag in safe_tags:
            text = text.replace(f'&lt;{tag}&gt;', f'<{tag}>')
            text = text.replace(f'&lt;/{tag}&gt;', f'</{tag}>')
            text = text.replace(f'&lt;{tag} /&gt;', f'<{tag} />')

    # Step 4: Log if threats were detected
    if threats_detected:
        logger.warning(
            f"XSS threats detected and removed: {', '.join(threats_detected)}\n"
            f"Original text (truncated): {original_text[:100]}\n"
            f"Sanitized text (truncated): {text[:100]}"
        )

    return text.strip()


def sanitize_session_title(title: str) -> str:
    """Sanitize session title to prevent XSS.

    Session titles should never contain HTML, so we escape everything.

    Args:
        title: Session title

    Returns:
        Sanitized title (HTML escaped)
    """
    if not title or not isinstance(title, str):
        return title

    # Remove dangerous patterns first
    sanitized = sanitize_html(title, preserve_safe_html=False)

    # Additional validation: limit length
    max_length = 500
    if len(sanitized) > max_length:
        logger.warning(f"Session title truncated from {len(sanitized)} to {max_length} chars")
        sanitized = sanitized[:max_length]

    return sanitized


def sanitize_message_content(content: str, preserve_markdown: bool = True) -> str:
    """Sanitize message content to prevent XSS.

    Messages may contain markdown, code blocks, emoji, and international
    characters, which should be preserved.

    Args:
        content: Message content
        preserve_markdown: If True, preserve markdown-style formatting and code blocks

    Returns:
        Sanitized content
    """
    if not content or not isinstance(content, str):
        return content

    # ✅ NEW: Extract code blocks before sanitization (they should not be escaped)
    # Code blocks are for display purposes, not execution
    code_blocks = []
    placeholder_template = "___CODE_BLOCK_{}___"

    if preserve_markdown:
        # Match: ```language\ncode\n```
        code_block_pattern = r'(```[\w-]*\n[\s\S]*?```)'

        def replace_code_block(match):
            index = len(code_blocks)
            code_blocks.append(match.group(0))
            return placeholder_template.format(index)

        # Replace code blocks with placeholders
        content = re.sub(code_block_pattern, replace_code_block, content)

    # Remove dangerous patterns first
    # For markdown, we allow some safe HTML tags like <b>, <i>, <code>
    sanitized = sanitize_html(content, preserve_safe_html=preserve_markdown)

    # ✅ NEW: Restore code blocks (without escaping)
    if preserve_markdown and code_blocks:
        for index, code_block in enumerate(code_blocks):
            placeholder = placeholder_template.format(index)
            sanitized = sanitized.replace(placeholder, code_block)

    # Additional validation: limit length
    max_length = 1_000_000  # 1MB of text
    if len(sanitized) > max_length:
        logger.warning(f"Message content truncated from {len(sanitized)} to {max_length} chars")
        sanitized = sanitized[:max_length]

    return sanitized


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize metadata dictionary to prevent XSS.

    Recursively sanitizes all string values in the metadata dict.

    Args:
        metadata: Metadata dictionary

    Returns:
        Sanitized metadata dictionary
    """
    if not metadata or not isinstance(metadata, dict):
        return metadata

    result = {}

    for key, value in metadata.items():
        # Sanitize the key itself
        safe_key = sanitize_html(key, preserve_safe_html=False)

        # Sanitize the value based on type
        if isinstance(value, str):
            result[safe_key] = sanitize_html(value, preserve_safe_html=False)
        elif isinstance(value, dict):
            result[safe_key] = sanitize_metadata(value)
        elif isinstance(value, list):
            result[safe_key] = [
                sanitize_metadata(item) if isinstance(item, dict)
                else sanitize_html(item, preserve_safe_html=False) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            # Preserve non-string primitives (int, float, bool, None)
            result[safe_key] = value

    return result


def validate_xss_safe(text: str) -> tuple[bool, Optional[str]]:
    """Validate that text is free from XSS threats.

    This is a validation-only function (doesn't modify the text).
    Useful for strict validation before accepting input.

    Args:
        text: Text to validate

    Returns:
        (is_safe, threat_description)
    """
    if not text or not isinstance(text, str):
        return True, None

    # Check for dangerous patterns
    for pattern, threat_type in XSS_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return False, f"Potential XSS detected: {threat_type} - '{match.group(0)[:50]}...'"

    # Check decoded content
    decoded_text = html.unescape(text)
    if decoded_text != text:
        for pattern, threat_type in XSS_PATTERNS:
            match = re.search(pattern, decoded_text, re.IGNORECASE | re.DOTALL)
            if match:
                return False, f"Potential encoded XSS detected: {threat_type}"

    return True, None


# Convenience function for backward compatibility
def sanitize_input(data: Any) -> Any:
    """General-purpose input sanitizer with XSS protection.

    This function provides a convenient wrapper for sanitizing various
    types of input data.

    Args:
        data: Data to sanitize (str, dict, list, or primitive)

    Returns:
        Sanitized data
    """
    if isinstance(data, str):
        return sanitize_html(data, preserve_safe_html=False)
    elif isinstance(data, dict):
        return sanitize_metadata(data)
    elif isinstance(data, list):
        return [sanitize_input(item) for item in data]
    else:
        return data
