#!/usr/bin/env python3
"""
v0.9.2 Gate J: Rule Adjudication Completeness

Validates:
- All action_proposal nodes have been adjudicated by rules
- Adjudication records are complete (rule_id, decision, evidence)
- No "skipped rules" scenarios
"""

import json
import sys
from pathlib import Path

EXAMPLES_DIR = Path("examples/coordinator/outputs")

GRAPHS_TO_CHECK = [
    "execution_graph_low_risk.json",
    "execution_graph_high_risk_interactive.json",
    "execution_graph_full_auto_readonly.json"
]

RUN_TAPES_TO_CHECK = [
    "coordinator_run_tape_low_risk.json",
    "coordinator_run_tape_high_risk_interactive.json",
    "coordinator_run_tape_full_auto_readonly.json"
]


def extract_action_proposals(graph):
    """Extract all action_proposal nodes from graph"""
    nodes = graph.get("nodes", [])
    return [node for node in nodes if node.get("node_type") == "action_proposal"]


def check_rule_coverage(graph_file, tape_file):
    """Check if all actions have rule evaluations"""
    graph_path = EXAMPLES_DIR / graph_file
    tape_path = EXAMPLES_DIR / tape_file
    
    if not graph_path.exists() or not tape_path.exists():
        return False, "Files not found"
    
    with open(graph_path, "r", encoding="utf-8") as f:
        graph = json.load(f)
    
    with open(tape_path, "r", encoding="utf-8") as f:
        tape = json.load(f)
    
    # Extract action proposals
    actions = extract_action_proposals(graph)
    action_refs = {action.get("command_ref") for action in actions if action.get("command_ref")}
    
    # Extract rule evaluations
    rule_evals = tape.get("rule_evaluations", [])
    evaluated_targets = {eval.get("target") for eval in rule_evals}
    
    # Check coverage
    unevaluated = []
    for action in actions:
        command_ref = action.get("command_ref", "")
        # Check if this action or its command was evaluated
        if command_ref and "command" in command_ref:
            # Look for partial match in evaluated targets
            found = any(command_ref in target or target in command_ref for target in evaluated_targets)
            if not found:
                unevaluated.append(action.get("node_id"))
    
    if unevaluated and len(actions) > 0:
        return False, f"Unevaluated actions: {unevaluated}"
    
    # Check rule evaluation completeness
    for eval in rule_evals:
        if not eval.get("rule_id"):
            return False, f"Evaluation missing rule_id: {eval}"
        if not eval.get("decision"):
            return False, f"Evaluation missing decision: {eval}"
        if not eval.get("reason"):
            return False, f"Evaluation missing reason: {eval}"
    
    return True, None


def main():
    print("=" * 70)
    print("v0.9.2 Gate J: Rule Adjudication Completeness")
    print("=" * 70)

    all_valid = True

    for graph_file, tape_file in zip(GRAPHS_TO_CHECK, RUN_TAPES_TO_CHECK):
        print(f"\nChecking {graph_file} + {tape_file}...")
        
        success, error = check_rule_coverage(graph_file, tape_file)
        
        if success:
            print(f"  ✅ All actions have rule evaluations")
            print(f"  ✅ Rule evaluation records are complete")
        else:
            print(f"  ❌ {error}")
            all_valid = False

    print("\n" + "=" * 70)
    if all_valid:
        print("✅ Gate J: PASSED")
        print("=" * 70)
        return True
    else:
        print("❌ Gate J: FAILED")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
