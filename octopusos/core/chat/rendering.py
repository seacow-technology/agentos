"""Enhanced message rendering with code block support"""

import re
from typing import List, Tuple
from rich.syntax import Syntax
from rich.markdown import Markdown


def parse_message_content(content: str) -> List[Tuple[str, str]]:
    """Parse message content into text and code blocks
    
    Args:
        content: Message content
    
    Returns:
        List of (type, content) tuples where type is "text" or "code"
    """
    parts = []
    
    # Pattern for code blocks: ```language\ncode\n```
    pattern = r'```(\w+)?\n(.*?)```'
    
    last_end = 0
    for match in re.finditer(pattern, content, re.DOTALL):
        # Add text before code block
        text_before = content[last_end:match.start()].strip()
        if text_before:
            parts.append(("text", text_before))
        
        # Add code block
        language = match.group(1) or "text"
        code = match.group(2).strip()
        parts.append(("code", f"{language}:{code}"))
        
        last_end = match.end()
    
    # Add remaining text
    text_after = content[last_end:].strip()
    if text_after:
        parts.append(("text", text_after))
    
    # If no code blocks found, return as single text
    if not parts:
        parts.append(("text", content))
    
    return parts


def render_code_block(language: str, code: str, max_lines: int = 30) -> str:
    """Render code block with syntax highlighting
    
    Args:
        language: Programming language
        code: Code content
        max_lines: Maximum lines to show (truncate if longer)
    
    Returns:
        Rendered code string
    """
    lines = code.split('\n')
    
    if len(lines) > max_lines:
        code = '\n'.join(lines[:max_lines])
        truncated = True
    else:
        truncated = False
    
    # Simple syntax highlighting for common languages
    # In production, use Rich's Syntax for better highlighting
    header = f"┌─ {language} {'─' * (40 - len(language))}"
    footer = "└" + "─" * 40
    
    result = [header]
    for line in code.split('\n'):
        result.append(f"│ {line}")
    
    if truncated:
        result.append(f"│ ... ({len(lines) - max_lines} more lines)")
    
    result.append(footer)
    
    return '\n'.join(result)


def format_message_with_code(content: str, max_code_lines: int = 30) -> str:
    """Format message content with code block rendering
    
    Args:
        content: Message content
        max_code_lines: Maximum lines per code block
    
    Returns:
        Formatted content string
    """
    parts = parse_message_content(content)
    
    formatted_parts = []
    for part_type, part_content in parts:
        if part_type == "text":
            formatted_parts.append(part_content)
        else:  # code
            language, code = part_content.split(':', 1)
            formatted_parts.append("\n" + render_code_block(language, code, max_code_lines) + "\n")
    
    return '\n\n'.join(formatted_parts)


def detect_content_type(content: str) -> str:
    """Detect message content type
    
    Args:
        content: Message content
    
    Returns:
        Content type: "plain", "code", "mixed"
    """
    if '```' in content:
        # Check if there's text outside code blocks
        parts = parse_message_content(content)
        has_text = any(t == "text" for t, _ in parts)
        has_code = any(t == "code" for t, _ in parts)
        
        if has_text and has_code:
            return "mixed"
        elif has_code:
            return "code"
    
    return "plain"
