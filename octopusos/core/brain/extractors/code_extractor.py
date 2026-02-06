"""
BrainOS Code Extractor (M3-P1 Complete Implementation)

从代码文件提取 File 级依赖关系，构建 DEPENDS_ON 边。

核心功能（v0.1）：
1. 扫描 Python/JS/TS 代码文件
2. 解析 import 语句（文件级）
3. 生成 DEPENDS_ON 边（File → File）
4. 为每个依赖提供证据链

支持范围：
- Python: import, from...import (absolute and relative)
- JavaScript/TypeScript: import, require (relative paths only)

明确排除（避免 AST 地狱）：
- ❌ 动态 import（__import__(), import() expressions）
- ❌ 第三方依赖（只关心 repo 内文件）
- ❌ 函数级调用图
- ❌ 类继承关系

性能目标：
- 单文件解析: < 10ms
- 全量扫描（AgentOS ~2000 files）: < 5s
"""

import os
import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Set, Tuple

from .base import BaseExtractor, ExtractionResult
from agentos.core.brain.models import Entity, EntityType, Edge, EdgeType, Evidence


# 默认配置
DEFAULT_CODE_PATTERNS = [
    "**/*.py",
    "**/*.js",
    "**/*.ts",
    "**/*.tsx"
]

DEFAULT_EXCLUDE_PATTERNS = [
    "**/node_modules/**",
    "**/.git/**",
    "**/build/**",
    "**/dist/**",
    "**/__pycache__/**",
    "**/venv/**",
    "**/.venv/**",
    "**/.venv_packaging/**",  # Exclude packaging venv
    "**/site-packages/**",    # Exclude installed packages
    "**/tests/**",            # 测试代码可选跳过（减少噪音）
    "**/test_*.py",
    "**/*.test.js",
    "**/*.test.ts",
]

# Python import 正则模式
PYTHON_IMPORT_PATTERNS = [
    # import module_name
    (re.compile(r'^\s*import\s+([\w\.]+)(?:\s+as\s+\w+)?', re.MULTILINE), 'full'),
    # from module import name (capture both)
    (re.compile(r'^\s*from\s+([\w\.]+)\s+import\s+([\w,\s]+)', re.MULTILINE), 'from_import'),
    # from . import ... (relative)
    (re.compile(r'^\s*from\s+(\.+)\s+import', re.MULTILINE), 'full'),
    # from .module import ...
    (re.compile(r'^\s*from\s+(\.+[\w\.]*)\s+import', re.MULTILINE), 'full'),
]

# JavaScript/TypeScript import 正则模式
JS_IMPORT_PATTERNS = [
    # import ... from 'module'
    re.compile(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]"),
    # import 'module'
    re.compile(r"import\s+['\"]([^'\"]+)['\"]"),
    # require('module')
    re.compile(r"require\(['\"]([^'\"]+)['\"]\)"),
]


class CodeExtractor(BaseExtractor):
    """
    代码依赖抽取器（文件级）

    从代码文件解析 import 语句，生成 File → File DEPENDS_ON 边。

    Config:
        code_patterns: 文件模式（默认 Python/JS/TS）
        exclude_patterns: 排除模式（默认 tests/node_modules）
        include_tests: 是否包含测试文件（默认 False）

    Example:
        >>> extractor = CodeExtractor()
        >>> result = extractor.extract(Path("/path/to/repo"))
        >>> print(f"Found {len(result.edges)} dependencies")
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="CodeExtractor",
            version="0.1.0",
            config=config
        )

        # Load config
        self.code_patterns = self.config.get("code_patterns", DEFAULT_CODE_PATTERNS)
        self.exclude_patterns = self.config.get("exclude_patterns", DEFAULT_EXCLUDE_PATTERNS)
        self.include_tests = self.config.get("include_tests", False)

        # If include_tests is True, remove test-related exclusions
        if self.include_tests:
            self.exclude_patterns = [
                p for p in self.exclude_patterns
                if "test" not in p.lower()
            ]

    def extract(
        self,
        repo_path: Path,
        incremental: bool = False,
        **kwargs
    ) -> ExtractionResult:
        """
        提取代码依赖关系

        Args:
            repo_path: 仓库根路径
            incremental: 是否增量抽取（暂未实现）
            **kwargs: 保留参数

        Returns:
            ExtractionResult with File entities and DEPENDS_ON edges
        """
        repo_path = Path(repo_path).resolve()

        entities = []
        edges = []
        errors = []

        # Step 1: 扫描所有代码文件
        code_files = self._scan_code_files(repo_path)

        if not code_files:
            return ExtractionResult(
                entities=[],
                edges=[],
                stats={
                    "files_scanned": 0,
                    "dependencies_extracted": 0,
                },
                errors=["No code files found"],
                metadata=self.get_metadata()
            )

        # Step 2: 为每个文件解析 imports
        dependency_count = 0
        seen_files = set()  # Track unique files

        for file_path in code_files:
            try:
                # Get relative path
                rel_path = file_path.relative_to(repo_path)
                rel_path_str = str(rel_path)

                # Create File entity (if not seen before)
                if rel_path_str not in seen_files:
                    file_entity = Entity(
                        id=f"file:{rel_path_str}",  # Use key as temporary id
                        type=EntityType.FILE,
                        key=f"file:{rel_path_str}",
                        name=rel_path_str,
                        attrs={"path": rel_path_str}
                    )
                    entities.append(file_entity)
                    seen_files.add(rel_path_str)

                # Parse imports
                imports = self._parse_imports(file_path, repo_path)

                # Generate DEPENDS_ON edges
                for import_info in imports:
                    target_file = import_info['target_file']

                    # Create target File entity (if not seen before)
                    if target_file not in seen_files:
                        target_entity = Entity(
                            id=f"file:{target_file}",  # Use key as temporary id
                            type=EntityType.FILE,
                            key=f"file:{target_file}",
                            name=target_file,
                            attrs={"path": target_file}
                        )
                        entities.append(target_entity)
                        seen_files.add(target_file)

                    # Create DEPENDS_ON edge
                    edge_key = f"depends_on|src:file:{rel_path_str}|dst:file:{target_file}"

                    evidence = Evidence(
                        source_type="code",
                        source_ref=rel_path_str,
                        span=import_info['statement'],  # span should be string, not dict
                        confidence=1.0,
                        metadata={
                            "line": import_info['line_number'],
                            "import_type": import_info['import_type']
                        }
                    )

                    edge = Edge(
                        id=edge_key,  # Use key as edge id
                        type=EdgeType.DEPENDS_ON,
                        source=f"file:{rel_path_str}",
                        target=f"file:{target_file}",
                        attrs={
                            "import_type": import_info['import_type'],
                            "import_statement": import_info['statement'],
                            "line": import_info['line_number']
                        },
                        evidence=[evidence]
                    )

                    edges.append(edge)
                    dependency_count += 1

            except Exception as e:
                # Fail-soft: log error but continue
                errors.append(f"Failed to parse {file_path}: {str(e)}")
                continue

        # Step 3: Return result
        return ExtractionResult(
            entities=entities,
            edges=edges,
            stats={
                "files_scanned": len(code_files),
                "dependencies_extracted": dependency_count,
            },
            errors=errors,
            metadata=self.get_metadata()
        )

    def _scan_code_files(self, repo_path: Path) -> List[Path]:
        """
        扫描代码文件

        Args:
            repo_path: 仓库根路径

        Returns:
            List of Path objects for code files
        """
        code_files = []

        for pattern in self.code_patterns:
            for file_path in repo_path.glob(pattern):
                # Check if file should be excluded
                if self._should_exclude(file_path, repo_path):
                    continue

                # Check if file exists and is readable
                if file_path.is_file():
                    code_files.append(file_path)

        return code_files

    def _should_exclude(self, file_path: Path, repo_path: Path) -> bool:
        """
        检查文件是否应该被排除

        Args:
            file_path: 文件路径
            repo_path: 仓库根路径

        Returns:
            True if file should be excluded
        """
        rel_path = str(file_path.relative_to(repo_path))

        for exclude_pattern in self.exclude_patterns:
            # Convert glob pattern to simple match
            # (simple implementation, could use pathlib.match in future)
            exclude_pattern = exclude_pattern.replace('**/', '')
            exclude_pattern = exclude_pattern.replace('*', '')

            if exclude_pattern in rel_path:
                return True

        return False

    def _parse_imports(
        self,
        file_path: Path,
        repo_path: Path
    ) -> List[Dict[str, Any]]:
        """
        解析文件中的 import 语句

        Args:
            file_path: 文件路径
            repo_path: 仓库根路径

        Returns:
            List of import info dicts with:
            - target_file: 目标文件相对路径
            - line_number: 行号
            - statement: import 语句原文
            - import_type: "python_import" | "js_import"
        """
        imports = []

        # Determine file type
        if file_path.suffix == '.py':
            imports = self._parse_python_imports(file_path, repo_path)
        elif file_path.suffix in ['.js', '.ts', '.tsx', '.jsx']:
            imports = self._parse_js_imports(file_path, repo_path)

        return imports

    def _parse_python_imports(
        self,
        file_path: Path,
        repo_path: Path
    ) -> List[Dict[str, Any]]:
        """
        解析 Python import 语句

        Args:
            file_path: Python 文件路径
            repo_path: 仓库根路径

        Returns:
            List of import info dicts
        """
        imports = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return []

        lines = content.split('\n')

        for line_number, line in enumerate(lines, start=1):
            # Try each pattern
            for pattern, pattern_type in PYTHON_IMPORT_PATTERNS:
                match = pattern.match(line)
                if match:
                    if pattern_type == 'from_import':
                        # Handle "from module import name1, name2"
                        module_path = match.group(1)
                        import_names = match.group(2).strip()

                        # Split by comma for multiple imports
                        names = [n.strip().split()[0] for n in import_names.split(',')]

                        for name in names:
                            # Try to resolve as module.name
                            combined_path = f"{module_path}.{name}"
                            target_file = self._resolve_python_import(
                                combined_path,
                                file_path,
                                repo_path
                            )

                            if target_file:
                                imports.append({
                                    'target_file': target_file,
                                    'line_number': line_number,
                                    'statement': line.strip(),
                                    'import_type': 'python_import'
                                })
                    else:
                        # Handle simple "import module"
                        import_path = match.group(1)

                        # Resolve to file path
                        target_file = self._resolve_python_import(
                            import_path,
                            file_path,
                            repo_path
                        )

                        if target_file:
                            imports.append({
                                'target_file': target_file,
                                'line_number': line_number,
                                'statement': line.strip(),
                                'import_type': 'python_import'
                            })

                    break  # Only match one pattern per line

        return imports

    def _resolve_python_import(
        self,
        import_path: str,
        source_file: Path,
        repo_path: Path
    ) -> Optional[str]:
        """
        解析 Python import 路径为文件路径

        Args:
            import_path: import 路径（如 "agentos.core.task.manager"）
            source_file: 源文件路径
            repo_path: 仓库根路径

        Returns:
            相对文件路径（如 "agentos/core/task/manager.py"）或 None
        """
        # Handle relative imports
        if import_path.startswith('.'):
            return self._resolve_python_relative_import(
                import_path,
                source_file,
                repo_path
            )

        # Handle absolute imports
        # Convert dot notation to path
        file_path = import_path.replace('.', '/') + '.py'
        abs_path = repo_path / file_path

        if abs_path.exists():
            return file_path

        # Try package __init__.py
        init_path = import_path.replace('.', '/') + '/__init__.py'
        abs_init_path = repo_path / init_path

        if abs_init_path.exists():
            return init_path

        # Not found or third-party
        return None

    def _resolve_python_relative_import(
        self,
        import_path: str,
        source_file: Path,
        repo_path: Path
    ) -> Optional[str]:
        """
        解析 Python 相对导入

        Args:
            import_path: 相对导入路径（如 "." 或 "..module"）
            source_file: 源文件路径
            repo_path: 仓库根路径

        Returns:
            相对文件路径或 None
        """
        # Count leading dots
        level = 0
        for char in import_path:
            if char == '.':
                level += 1
            else:
                break

        # Get module name (after dots)
        module_name = import_path[level:]

        # Get source directory
        source_dir = source_file.parent

        # Go up 'level-1' directories
        target_dir = source_dir
        for _ in range(level - 1):
            target_dir = target_dir.parent

        # If no module name, it's "from . import ..."
        if not module_name:
            # Try __init__.py in current package
            init_path = target_dir / '__init__.py'
            if init_path.exists():
                return str(init_path.relative_to(repo_path))
            return None

        # Construct target path
        target_path = target_dir / (module_name.replace('.', '/') + '.py')

        if target_path.exists():
            return str(target_path.relative_to(repo_path))

        # Try __init__.py
        init_path = target_dir / (module_name.replace('.', '/')) / '__init__.py'
        if init_path.exists():
            return str(init_path.relative_to(repo_path))

        return None

    def _parse_js_imports(
        self,
        file_path: Path,
        repo_path: Path
    ) -> List[Dict[str, Any]]:
        """
        解析 JavaScript/TypeScript import 语句

        Args:
            file_path: JS/TS 文件路径
            repo_path: 仓库根路径

        Returns:
            List of import info dicts
        """
        imports = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return []

        lines = content.split('\n')

        for line_number, line in enumerate(lines, start=1):
            # Try each pattern
            for pattern in JS_IMPORT_PATTERNS:
                matches = pattern.finditer(line)
                for match in matches:
                    import_path = match.group(1)

                    # Only process relative imports (skip third-party)
                    if not import_path.startswith('.'):
                        continue

                    # Resolve to file path
                    target_file = self._resolve_js_import(
                        import_path,
                        file_path,
                        repo_path
                    )

                    if target_file:
                        imports.append({
                            'target_file': target_file,
                            'line_number': line_number,
                            'statement': line.strip(),
                            'import_type': 'js_import'
                        })

        return imports

    def _resolve_js_import(
        self,
        import_path: str,
        source_file: Path,
        repo_path: Path
    ) -> Optional[str]:
        """
        解析 JS/TS import 路径为文件路径

        Args:
            import_path: import 路径（如 "./utils" 或 "../services/api"）
            source_file: 源文件路径
            repo_path: 仓库根路径

        Returns:
            相对文件路径或 None
        """
        # Calculate absolute path
        source_dir = source_file.parent
        target_path = (source_dir / import_path).resolve()

        # Try various extensions
        extensions = ['.ts', '.tsx', '.js', '.jsx']

        for ext in extensions:
            candidate = Path(str(target_path) + ext)
            if candidate.exists() and candidate.is_relative_to(repo_path):
                return str(candidate.relative_to(repo_path))

        # Try index files
        for ext in extensions:
            candidate = target_path / ('index' + ext)
            if candidate.exists() and candidate.is_relative_to(repo_path):
                return str(candidate.relative_to(repo_path))

        return None
