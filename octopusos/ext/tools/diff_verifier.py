"""
Diff Verifier - Step 3 Runtime Gate 的 Diff 验证器

验证 Tool 产出的 diff：
1. 格式合法性（unified diff）
2. Scope 检查（只改允许的路径）
3. Policy 检查（禁止路径）
"""

import re
from pathlib import Path
from typing import List, Set, Optional

from .types import ToolResult, DiffValidationResult


class DiffVerifier:
    """Diff 验证器"""
    
    @staticmethod
    def verify(result: ToolResult, allowed_paths: List[str], forbidden_paths: List[str]) -> DiffValidationResult:
        """
        验证 Tool 产出的 diff
        
        🔩 H3-2 收口1：自动标准化 diff（支持 format-patch）
        🔩 补强1：记录是否经过 format-patch 标准化（审计证据）
        🔩 补强1改进：记录 diff 起始行号（排查用）
        
        Args:
            result: Tool 执行结果
            allowed_paths: 允许修改的路径（glob 模式）
            forbidden_paths: 禁止修改的路径（glob 模式）
        
        Returns:
            DiffValidationResult（包含 normalized_from_format_patch 标记和起始行号）
        """
        errors = []
        warnings = []
        
        # 1. 检查 diff 是否为空
        if not result.diff or not result.diff.strip():
            errors.append("Diff is empty")
            return DiffValidationResult(is_valid=False, errors=errors)
        
        # 🔩 H3-2 收口1：标准化 diff（strip format-patch mail header）
        # 🔩 补强1：检测是否是 format-patch 格式
        # 🔩 补强1改进：记录起始行号
        normalized_diff, was_format_patch, start_line = DiffVerifier._normalize_diff_with_detection(result.diff)
        
        # 2. 检查是否为 unified diff 格式
        if not DiffVerifier._is_unified_diff(normalized_diff):
            errors.append("Not a valid unified diff format")
        
        # 3. 检查文件路径是否在允许范围内
        touched_files = result.files_touched
        
        for file_path in touched_files:
            # 检查是否在禁止路径中
            if DiffVerifier._matches_any_pattern(file_path, forbidden_paths):
                errors.append(f"File in forbidden path: {file_path}")
            
            # 检查是否在允许路径中
            if allowed_paths and not DiffVerifier._matches_any_pattern(file_path, allowed_paths):
                warnings.append(f"File not in allowed paths: {file_path}")
        
        # 4. 检查 diff 中的文件与 files_touched 是否一致
        diff_files = DiffVerifier._extract_files_from_diff(normalized_diff)
        if set(diff_files) != set(touched_files):
            warnings.append(f"Mismatch: diff has {diff_files}, but files_touched has {touched_files}")
        
        is_valid = len(errors) == 0
        
        return DiffValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            normalized_from_format_patch=was_format_patch,  # 🔩 补强1：审计证据
            normalized_start_line=start_line  # 🔩 补强1改进：排查用
        )
    
    @staticmethod
    def _is_unified_diff(diff: str) -> bool:
        """
        检查是否为 unified diff 格式
        
        🔩 H3-2 收口1：支持 format-patch 输出（自动 strip mail header）
        format-patch 生成的文件包含邮件头（From/Date/Subject），需要跳过
        """
        lines = diff.split('\n')
        
        # unified diff 必须有 'diff --git' 或 '---' 和 '+++'
        has_diff_header = any(line.startswith('diff --git') for line in lines)
        has_file_markers = any(line.startswith('---') for line in lines) and any(line.startswith('+++') for line in lines)
        
        return has_diff_header or has_file_markers
    
    @staticmethod
    def _normalize_diff(diff: str) -> str:
        """
        标准化 diff 内容（向后兼容接口，推荐使用 _normalize_diff_with_detection）
        
        🔩 H3-2 收口1：strip format-patch mail header
        
        用于兼容 git format-patch 邮件头；输出仍必须是 unified diff。
        
        format-patch 文件格式：
            From <sha> Mon Sep 17 00:00:00 2001
            From: author <email>
            Date: ...
            Subject: [PATCH] ...
            ---
            diff --git a/file b/file
            ...
        
        我们只保留 diff 部分（从第一个 'diff --git' 或 '---' 开始）
        
        Args:
            diff: 原始 diff 内容（可能包含 mail header）
        
        Returns:
            标准化后的 unified diff（去除 mail header）
        """
        normalized, _, _ = DiffVerifier._normalize_diff_with_detection(diff)
        return normalized
    
    @staticmethod
    def _normalize_diff_with_detection(diff: str) -> tuple[str, bool, Optional[int]]:
        """
        标准化 diff 内容并检测是否是 format-patch 格式
        
        🔩 补强1：检测并记录 format-patch 标准化（审计证据）
        🔩 补强1改进：加强检测逻辑（不误判普通注释）+ 记录起始行号
        
        Args:
            diff: 原始 diff 内容（可能包含 mail header）
        
        Returns:
            (标准化后的 diff, 是否检测到 format-patch header, 起始行号)
        """
        lines = diff.split('\n')
        
        # 找到第一个 diff 行的索引
        diff_start_idx = None
        for i, line in enumerate(lines):
            if line.startswith('diff --git') or line.startswith('---'):
                diff_start_idx = i
                break
        
        if diff_start_idx is None:
            # 没有找到 diff 标记，返回原内容
            return diff, False, None
        
        # 🔩 补强1：检测是否有 format-patch header（From/Date/Subject）
        # 🔩 补强1改进：加强检测，避免误判"普通 diff 前有注释"
        was_format_patch = False
        if diff_start_idx > 0:
            # 检查前面的行是否包含 format-patch header
            header_lines = lines[:diff_start_idx]
            for line in header_lines:
                # 更强的 format-patch 特征：
                # 1. "From <sha> Mon Sep 17 00:00:00 2001" (format-patch 常见第一行)
                # 2. "Subject: [PATCH" (更强特征)
                # 3. 传统的 From:/Date:/Subject:（次要特征）
                if (line.startswith('From ') and any(mon in line for mon in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])) or \
                   'Subject: [PATCH' in line or \
                   (line.startswith('From:') or line.startswith('Date:') or line.startswith('Subject:')):
                    was_format_patch = True
                    break
        
        # 返回从 diff 开始的内容和起始行号
        return '\n'.join(lines[diff_start_idx:]), was_format_patch, diff_start_idx

    
    @staticmethod
    def _extract_files_from_diff(diff: str) -> List[str]:
        """从 diff 中提取文件路径"""
        files = []
        for line in diff.split('\n'):
            if line.startswith('diff --git'):
                # Extract: diff --git a/file b/file
                parts = line.split()
                if len(parts) >= 3:
                    file_path = parts[2].lstrip('a/')
                    files.append(file_path)
        return files
    
    @staticmethod
    def _matches_any_pattern(path: str, patterns: List[str]) -> bool:
        """检查路径是否匹配任意模式"""
        if not patterns:
            return False
        
        path_obj = Path(path)
        
        for pattern in patterns:
            # 简化版 glob 匹配
            if '**' in pattern:
                # 递归匹配
                pattern_parts = pattern.split('**/')
                if len(pattern_parts) == 2:
                    prefix, suffix = pattern_parts
                    if str(path_obj).startswith(prefix.rstrip('/')):
                        # 匹配成功
                        return True
            elif '*' in pattern:
                # 简单通配符
                import fnmatch
                if fnmatch.fnmatch(str(path_obj), pattern):
                    return True
            else:
                # 精确匹配
                if str(path_obj) == pattern or str(path_obj).startswith(pattern):
                    return True
        
        return False
