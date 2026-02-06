"""Markdown 智能切片器 - 按 heading 切分文档

切片策略:
- 按 # / ## / ### heading 分割
- 保持代码块完整性 (```...```) - 不切断代码块
- 段落窗口: 300-800 tokens
- 记录行号范围便于追溯
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from agentos.core.project_kb.types import Chunk


@dataclass
class MarkdownSection:
    """Markdown 章节 (临时结构)"""

    heading: Optional[str]
    level: int  # 标题级别 (1=# , 2=##, 等)
    start_line: int
    lines: list[str]


class MarkdownChunker:
    """Markdown 智能切片器"""

    # Token 估算: 平均 1 token ≈ 4 chars (中英文混合)
    CHARS_PER_TOKEN = 4

    # Chunk 大小限制
    MIN_TOKENS = 300
    MAX_TOKENS = 800

    def __init__(
        self,
        min_tokens: int = MIN_TOKENS,
        max_tokens: int = MAX_TOKENS,
    ):
        """初始化切片器

        Args:
            min_tokens: 最小 token 数
            max_tokens: 最大 token 数
        """
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens

    def chunk_file(self, source_id: str, file_path: Path) -> Iterator[Chunk]:
        """切片文件生成 chunks

        Args:
            source_id: 文档 source_id
            file_path: 文件路径

        Yields:
            Chunk 对象
        """
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # 按 heading 分割成 sections
        sections = self._split_into_sections(lines)

        # 将 sections 合并成合适大小的 chunks
        for chunk in self._sections_to_chunks(source_id, sections):
            yield chunk

    def _split_into_sections(self, lines: list[str]) -> list[MarkdownSection]:
        """按 heading 分割成 sections
        
        关键：保护代码块不被切断（Gate #4 要求）
        """
        sections = []
        current_section = None
        current_lines = []
        current_start = 1
        in_code_block = False

        for line_num, line in enumerate(lines, start=1):
            # 检测代码块边界
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                current_lines.append(line)
                continue
            
            # 代码块内不切分
            if in_code_block:
                current_lines.append(line)
                continue
            
            # 检测 heading
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)

            if heading_match:
                # 保存前一个 section
                if current_section or current_lines:
                    if current_section:
                        current_section.lines = current_lines
                        sections.append(current_section)
                    elif current_lines:
                        # 文件开头没有 heading 的内容
                        sections.append(
                            MarkdownSection(
                                heading=None,
                                level=0,
                                start_line=current_start,
                                lines=current_lines,
                            )
                        )

                # 开始新 section
                level = len(heading_match.group(1))
                heading = heading_match.group(2).strip()
                current_section = MarkdownSection(
                    heading=heading,
                    level=level,
                    start_line=line_num,
                    lines=[],
                )
                current_lines = [line]
                current_start = line_num
            else:
                current_lines.append(line)

        # 保存最后一个 section
        if current_section or current_lines:
            if current_section:
                current_section.lines = current_lines
                sections.append(current_section)
            elif current_lines:
                sections.append(
                    MarkdownSection(
                        heading=None,
                        level=0,
                        start_line=current_start,
                        lines=current_lines,
                    )
                )

        return sections

    def _sections_to_chunks(self, source_id: str, sections: list[MarkdownSection]) -> Iterator[Chunk]:
        """将 sections 合并成合适大小的 chunks"""
        if not sections:
            return

        buffer = []
        buffer_start = sections[0].start_line
        buffer_heading = sections[0].heading

        for section in sections:
            section_text = "".join(section.lines)
            section_tokens = self._estimate_tokens(section_text)

            # 如果当前 buffer 为空，直接加入
            if not buffer:
                buffer = [section]
                buffer_start = section.start_line
                buffer_heading = section.heading
                continue

            # 计算当前 buffer 大小
            buffer_text = "".join("".join(s.lines) for s in buffer)
            buffer_tokens = self._estimate_tokens(buffer_text)

            # 如果加入新 section 会超过最大限制
            if buffer_tokens + section_tokens > self.max_tokens:
                # 输出当前 buffer
                yield self._create_chunk(source_id, buffer, buffer_start, buffer_heading)

                # 开始新 buffer
                buffer = [section]
                buffer_start = section.start_line
                buffer_heading = section.heading
            else:
                # 加入当前 buffer
                buffer.append(section)

        # 输出最后的 buffer
        if buffer:
            yield self._create_chunk(source_id, buffer, buffer_start, buffer_heading)

    def _create_chunk(
        self,
        source_id: str,
        sections: list[MarkdownSection],
        start_line: int,
        heading: Optional[str],
    ) -> Chunk:
        """从 sections 创建 Chunk"""
        # 合并所有 section 的内容
        content = "".join("".join(s.lines) for s in sections).strip()

        # 计算行号范围
        end_line = sections[-1].start_line + len(sections[-1].lines) - 1

        # 计算 token 数
        token_count = self._estimate_tokens(content)

        # 计算内容哈希
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # 生成 chunk_id
        chunk_id = self._generate_chunk_id(source_id, start_line, end_line)

        return Chunk(
            chunk_id=chunk_id,
            source_id=source_id,
            heading=heading,
            start_line=start_line,
            end_line=end_line,
            content=content,
            content_hash=content_hash,
            token_count=token_count,
        )

    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数 (简单方法: chars / 4)"""
        return max(1, len(text) // self.CHARS_PER_TOKEN)

    def _generate_chunk_id(self, source_id: str, start_line: int, end_line: int) -> str:
        """生成 chunk_id"""
        combined = f"{source_id}:{start_line}-{end_line}"
        return f"chunk_{hashlib.sha256(combined.encode()).hexdigest()[:16]}"
