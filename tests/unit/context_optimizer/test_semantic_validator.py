from __future__ import annotations

from octopusos.core.context_optimizer.v2.semantic_validator import validate_context_pack


def test_semantic_validator_catches_verdict_contradiction() -> None:
    pack = {
        "tier_1_facts": [
            {
                "id": "fact1",
                "severity": "info",
                "value_score": 60,
                "signature": "sig",
                "data": {"verdict": "pass", "primary_failures": [{"type": "error", "message": "x"}], "exit_code": 0},
            }
        ]
    }
    errs = validate_context_pack(pack)
    assert any("verdict=pass" in e for e in errs)


def test_semantic_validator_catches_exit_code_contradiction() -> None:
    pack = {
        "tier_1_facts": [
            {
                "id": "fact1",
                "severity": "info",
                "value_score": 60,
                "signature": "sig",
                "data": {"verdict": "pass", "primary_failures": [], "exit_code": 2},
            }
        ]
    }
    errs = validate_context_pack(pack)
    assert any("exit_code!=0" in e for e in errs)

