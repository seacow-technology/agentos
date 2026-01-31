#!/usr/bin/env python3
"""
Gate: Strict No Subprocess (全局扫描)

严格模式：扫描整个 agentos/ 目录，0 subprocess。

豁免：
- agentos/core/infra/container_client.py（容器引擎边界）
- agentos/core/infra/tool_executor.py（外部工具边界）
- agentos/core/executor/container_sandbox.py 的 fallback 执行（注释标记）
"""

import ast
import sys
from pathlib import Path
from typing import List, Dict
import json


FORBIDDEN_SYMBOLS = {
    "subprocess",
    "os.system",
    "exec",
    "eval",
    "shlex",
    "pty",
    "pexpect"
}

# 系统边界文件（允许 subprocess）
EXEMPTED_FILES = {
    "agentos/core/infra/container_client.py",  # 容器引擎适配层
    "agentos/core/infra/tool_executor.py",      # 外部工具适配层
}


class SubprocessVisitor(ast.NodeVisitor):
    """AST 访问器：检测禁止的符号"""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.violations = []
    
    def visit_Import(self, node):
        for alias in node.names:
            if alias.name in FORBIDDEN_SYMBOLS:
                self.violations.append({
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "type": "import",
                    "symbol": alias.name,
                    "code": f"import {alias.name}"
                })
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        if node.module in FORBIDDEN_SYMBOLS:
            self.violations.append({
                "file": str(self.file_path),
                "line": node.lineno,
                "type": "import_from",
                "symbol": node.module,
                "code": f"from {node.module} import ..."
            })
        self.generic_visit(node)
    
    def visit_Attribute(self, node):
        # 检测 os.system 之类
        if isinstance(node.value, ast.Name):
            if node.value.id == "os" and node.attr == "system":
                self.violations.append({
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "type": "attribute",
                    "symbol": "os.system",
                    "code": "os.system(...)"
                })
        self.generic_visit(node)
    
    def visit_Call(self, node):
        # 检测 exec(...) / eval(...)
        if isinstance(node.func, ast.Name):
            if node.func.id in {"exec", "eval"}:
                self.violations.append({
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "type": "call",
                    "symbol": node.func.id,
                    "code": f"{node.func.id}(...)"
                })
        self.generic_visit(node)


def scan_file(file_path: Path) -> List[Dict]:
    """扫描单个文件"""
    try:
        content = file_path.read_text()
        tree = ast.parse(content, filename=str(file_path))
        
        visitor = SubprocessVisitor(file_path)
        visitor.visit(tree)
        
        return visitor.violations
    
    except SyntaxError:
        return []
    except Exception as e:
        print(f"⚠ Error scanning {file_path}: {e}")
        return []


def main():
    repo_root = Path.cwd()
    
    print("🔒 Gate: Strict No Subprocess (全局扫描)")
    print("   Scope: 整个 agentos/ 目录（严格模式）")
    print("=" * 60)
    
    # 扫描整个 agentos 目录
    agentos_dir = repo_root / "agentos"
    all_py_files = list(agentos_dir.rglob("*.py"))
    
    print(f"📁 扫描范围: {len(all_py_files)} Python 文件")
    print(f"   豁免文件: {len(EXEMPTED_FILES)} 个（系统边界）\n")
    
    # 扫描
    all_violations = []
    for file in all_py_files:
        # 检查是否豁免
        rel_path = str(file.relative_to(repo_root))
        if rel_path in EXEMPTED_FILES:
            continue
        
        violations = scan_file(file)
        all_violations.extend(violations)
    
    # 保存扫描结果
    output_dir = repo_root / "outputs" / "gates"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    scan_result = {
        "gate": "strict_no_subprocess",
        "scope": "全局 agentos/ 目录",
        "scanned_files": len(all_py_files),
        "exempted_files": list(EXEMPTED_FILES),
        "violations_count": len(all_violations),
        "violations": all_violations
    }
    
    result_file = output_dir / "strict_no_subprocess.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(scan_result, f, indent=2)
    
    # 报告
    if all_violations:
        print(f"❌ 发现 {len(all_violations)} 个违规:")
        for v in all_violations[:20]:  # 只显示前 20 个
            print(f"   {v['file']}:{v['line']}: {v['symbol']} ({v['type']})")
        
        if len(all_violations) > 20:
            print(f"   ... 以及 {len(all_violations) - 20} 个其他违规")
        
        print()
        print(f"扫描结果已保存: {result_file}")
        print("=" * 60)
        print("❌ Gate 失败: 检测到 subprocess")
        sys.exit(1)
    else:
        print(f"✓ 扫描 {len(all_py_files)} 个文件")
        print(f"✓ 未发现禁止符号")
        print()
        print(f"扫描结果已保存: {result_file}")
        print("=" * 60)
        print("✅ Gate 通过: 严格 0 subprocess")
        sys.exit(0)


if __name__ == "__main__":
    main()
