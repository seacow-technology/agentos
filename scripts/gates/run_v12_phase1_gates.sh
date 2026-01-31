#!/usr/bin/env bash
# Run all Phase 1 AnswerPack Gates (v0.12)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔒 Running Phase 1 AnswerPack Gates (v0.12)"
echo "=========================================="

# G-AP-TUI: TUI Interface Requirements
echo ""
python3 "$SCRIPT_DIR/v12_ap_gate_tui.py"

# G-AP-LLM: LLM Suggestion Requirements
echo ""
python3 "$SCRIPT_DIR/v12_ap_gate_llm.py"

# G-AP-MULTI: Multi-Round Requirements
echo ""
python3 "$SCRIPT_DIR/v12_ap_gate_multi.py"

echo ""
echo "=========================================="
echo "✅ All Phase 1 Gates PASSED"
