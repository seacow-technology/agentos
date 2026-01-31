#!/usr/bin/env python3
"""Gate A: Agent 内容存在性检查

验证:
1. docs/content/agents/ 目录存在 13 个 YAML 文件
2. docs/content/agent_workflow_mapping.yaml 存在且可解析
3. 每个 agent YAML 的基本结构正确

用法:
    uv run python scripts/gates/v07_gate_a_agents_exist.py
"""

import sys
from pathlib import Path

import yaml


def check_agents_exist() -> tuple[bool, list[str]]:
    """检查 13 个 agent YAML 文件是否存在"""
    agents_dir = Path("docs/content/agents")
    
    if not agents_dir.exists():
        return False, [f"❌ Directory not found: {agents_dir}"]
    
    yaml_files = list(agents_dir.glob("*.yaml"))
    
    if len(yaml_files) != 13:
        return False, [f"❌ Expected 13 agent YAML files, found {len(yaml_files)}"]
    
    # 验证每个文件可以解析
    errors = []
    expected_agents = {
        "product_manager", "project_manager", "ui_ux_designer", "frontend_engineer",
        "backend_engineer", "database_engineer", "system_architect", "qa_engineer",
        "security_engineer", "devops_engineer", "sre_engineer", "technical_writer",
        "engineering_manager"
    }
    
    found_agents = set()
    
    for yaml_file in yaml_files:
        try:
            with open(yaml_file, encoding="utf-8") as f:
                agent_data = yaml.safe_load(f)
            
            # 验证基本字段
            required_fields = ["id", "type", "version", "category", "description", 
                              "responsibilities", "allowed_interactions", "constraints", "lineage"]
            
            for field in required_fields:
                if field not in agent_data:
                    errors.append(f"❌ {yaml_file.name}: Missing required field '{field}'")
            
            if "id" in agent_data:
                found_agents.add(agent_data["id"])
                
        except Exception as e:
            errors.append(f"❌ Failed to parse {yaml_file.name}: {e}")
    
    # 检查是否所有预期的 agent 都存在
    missing_agents = expected_agents - found_agents
    if missing_agents:
        errors.append(f"❌ Missing agents: {', '.join(sorted(missing_agents))}")
    
    if errors:
        return False, errors
    
    return True, [f"✅ Found all 13 agent YAML files"]


def check_mapping_exists() -> tuple[bool, list[str]]:
    """检查 agent_workflow_mapping.yaml 是否存在且可解析"""
    mapping_file = Path("docs/content/agent_workflow_mapping.yaml")
    
    if not mapping_file.exists():
        return False, [f"❌ File not found: {mapping_file}"]
    
    try:
        with open(mapping_file, encoding="utf-8") as f:
            mapping_data = yaml.safe_load(f)
        
        # 验证基本结构
        if "mappings" not in mapping_data:
            return False, [f"❌ {mapping_file}: Missing 'mappings' field"]
        
        if not isinstance(mapping_data["mappings"], list):
            return False, [f"❌ {mapping_file}: 'mappings' must be a list"]
        
        # 验证每个 mapping 的结构
        for i, mapping in enumerate(mapping_data["mappings"]):
            required_fields = ["agent_id", "workflow_id", "phases"]
            for field in required_fields:
                if field not in mapping:
                    return False, [f"❌ {mapping_file}: Mapping #{i} missing field '{field}'"]
        
        return True, [f"✅ agent_workflow_mapping.yaml exists and is valid ({len(mapping_data['mappings'])} mappings)"]
        
    except Exception as e:
        return False, [f"❌ Failed to parse {mapping_file}: {e}"]


def main():
    """运行 Gate A 检查"""
    print("=" * 60)
    print("Gate A: Agent 内容存在性检查")
    print("=" * 60)
    print()
    
    all_passed = True
    
    # 检查 agents 目录
    passed, messages = check_agents_exist()
    for msg in messages:
        print(msg)
    if not passed:
        all_passed = False
    print()
    
    # 检查 mapping 文件
    passed, messages = check_mapping_exists()
    for msg in messages:
        print(msg)
    if not passed:
        all_passed = False
    print()
    
    if all_passed:
        print("=" * 60)
        print("✅ Gate A: PASS - All checks passed")
        print("=" * 60)
        sys.exit(0)
    else:
        print("=" * 60)
        print("❌ Gate A: FAIL - Some checks failed")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
