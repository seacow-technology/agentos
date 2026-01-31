#!/usr/bin/env python3
"""
Gate G-AP-LLM: LLM Suggestion Requirements

Validates:
1. LLM suggestions must include source (provider/model)
2. LLM suggestions must include prompt_hash for traceability
3. Support both OpenAI and Anthropic
4. Automatic fallback when primary fails
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def check_llm_source_tracking():
    """Check LLM suggestions track source."""
    llm_file = project_root / "agentos" / "core" / "answers" / "llm_suggester.py"
    
    if not llm_file.exists():
        return False, "LLM suggester file not found"
    
    content = llm_file.read_text()
    
    # Check for source field
    if '"source"' not in content or 'sugg["source"]' not in content:
        return False, "Missing source tracking in suggestions"
    
    # Check source includes provider and model
    if 'f"{self.provider}/{self.model}"' not in content:
        return False, "Source doesn't include provider/model"
    
    return True, "Source tracking validated"


def check_llm_prompt_hash():
    """Check LLM suggestions include prompt hash."""
    llm_file = project_root / "agentos" / "core" / "answers" / "llm_suggester.py"
    content = llm_file.read_text()
    
    # Check for prompt_hash field
    if '"prompt_hash"' not in content:
        return False, "Missing prompt_hash field"
    
    # Check hash computation
    if "_hash_prompt" not in content:
        return False, "Missing _hash_prompt method"
    
    # Check SHA-256 usage
    if "hashlib.sha256" not in content or "hexdigest()" not in content:
        return False, "prompt_hash should use SHA-256"
    
    return True, "Prompt hash traceability validated"


def check_llm_dual_providers():
    """Check support for both OpenAI and Anthropic."""
    llm_file = project_root / "agentos" / "core" / "answers" / "llm_suggester.py"
    content = llm_file.read_text()
    
    # Check OpenAI support
    if "openai" not in content.lower():
        return False, "Missing OpenAI support"
    
    if "_suggest_openai" not in content:
        return False, "Missing _suggest_openai method"
    
    # Check Anthropic support  
    if "anthropic" not in content.lower():
        return False, "Missing Anthropic support"
    
    if "_suggest_anthropic" not in content:
        return False, "Missing _suggest_anthropic method"
    
    # Check provider selection
    if 'self.provider == "openai"' not in content:
        return False, "Missing OpenAI provider check"
    
    if 'self.provider == "anthropic"' not in content:
        return False, "Missing Anthropic provider check"
    
    return True, "Dual provider support validated"


def check_llm_fallback():
    """Check automatic fallback mechanism."""
    llm_file = project_root / "agentos" / "core" / "answers" / "llm_suggester.py"
    content = llm_file.read_text()
    
    # Check for fallback function
    if "suggest_all_answers" not in content:
        return False, "Missing suggest_all_answers function"
    
    # Check fallback_provider parameter
    if "fallback_provider" not in content:
        return False, "Missing fallback_provider parameter"
    
    # Check fallback logic
    if "except" not in content or "try:" not in content:
        return False, "Missing error handling for fallback"
    
    # Should try fallback when primary fails
    if "primary_error" not in content and "fallback_error" not in content:
        return False, "Fallback logic not properly implemented"
    
    return True, "Automatic fallback validated"


def check_llm_metadata():
    """Check LLM suggestions include required metadata."""
    llm_file = project_root / "agentos" / "core" / "answers" / "llm_suggester.py"
    content = llm_file.read_text()
    
    required_fields = [
        '"answer_text"',
        '"rationale"',
        '"evidence_refs"',
        '"confidence"',
        '"generated_at"'
    ]
    
    for field in required_fields:
        if field not in content:
            return False, f"Missing required field: {field}"
    
    return True, "Metadata fields validated"


def main():
    """Run G-AP-LLM gate checks."""
    print("🔒 Gate G-AP-LLM: LLM Suggestion Requirements")
    print("=" * 60)
    
    checks = [
        ("Source Tracking", check_llm_source_tracking),
        ("Prompt Hash Traceability", check_llm_prompt_hash),
        ("Dual Provider Support", check_llm_dual_providers),
        ("Automatic Fallback", check_llm_fallback),
        ("Required Metadata", check_llm_metadata)
    ]
    
    all_passed = True
    
    for name, check_func in checks:
        passed, message = check_func()
        status = "✓" if passed else "✗"
        print(f"{status} {name}: {message}")
        
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("✅ Gate G-AP-LLM PASSED")
        return 0
    else:
        print("❌ Gate G-AP-LLM FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
