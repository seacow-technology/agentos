#!/usr/bin/env python3
"""Response Guardian Demo - Demonstrates capability enforcement in Execution Phase

This script shows how Response Guardian prevents capability denial responses
when the system has AutoComm capabilities available.

Usage:
    python examples/response_guardian_demo.py
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentos.core.chat.response_guardian import (
    ResponseGuardian,
    check_response_with_guardian
)

# Configure logging to show Guardian events
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def demo_scenario(
    scenario_name: str,
    response: str,
    session_metadata: dict,
    description: str
):
    """Demo a single scenario"""
    print(f"\n{'='*70}")
    print(f"Scenario: {scenario_name}")
    print(f"{'='*70}")
    print(f"Description: {description}")
    print(f"\nSession Metadata:")
    print(f"  - execution_phase: {session_metadata.get('execution_phase')}")
    print(f"  - auto_comm_enabled: {session_metadata.get('auto_comm_enabled')}")
    print(f"\nOriginal LLM Response:")
    print(f"  {response[:100]}...")
    print(f"\nGuardian Decision:")

    # Check with Guardian
    final_response, guardian_metadata = check_response_with_guardian(
        response_content=response,
        session_metadata=session_metadata,
        classification=None
    )

    # Print decision
    if final_response == response:
        print("  ✅ Response ALLOWED - Passed through unchanged")
    else:
        print("  ⚠️  Response BLOCKED - Replaced with enforcement message")

    print(f"\nGuardian Metadata:")
    for key, value in guardian_metadata.items():
        print(f"  - {key}: {value}")

    if final_response != response:
        print(f"\nReplacement Response Preview:")
        preview = final_response.split('\n')[:5]
        for line in preview:
            print(f"  {line}")
        print(f"  ... (truncated)")


def main():
    """Run all demo scenarios"""
    print("\n" + "="*70)
    print("Response Guardian Demo")
    print("="*70)
    print("\nThis demo shows how Response Guardian enforces capability declarations")
    print("in Execution Phase, preventing 'I cannot access' fallback responses.")

    # Scenario 1: Planning Phase - Allow denial
    demo_scenario(
        scenario_name="Planning Phase - Denial Allowed",
        response="抱歉,我无法访问实时天气数据。建议您查看 weather.com。",
        session_metadata={
            'execution_phase': 'planning',
            'auto_comm_enabled': True
        },
        description=(
            "In Planning Phase, capability denial is allowed. "
            "The system may suggest external commands without executing them."
        )
    )

    # Scenario 2: Execution Phase - Block Chinese denial
    demo_scenario(
        scenario_name="Execution Phase - Chinese Denial Blocked",
        response=(
            "抱歉,作为一个AI助手,我无法直接访问实时天气数据。"
            "建议您查看 weather.com 或使用手机天气应用。"
        ),
        session_metadata={
            'execution_phase': 'execution',
            'auto_comm_enabled': True
        },
        description=(
            "In Execution Phase with AutoComm enabled, Chinese capability denial "
            "responses are blocked and replaced with enforcement messages."
        )
    )

    # Scenario 3: Execution Phase - Block English denial
    demo_scenario(
        scenario_name="Execution Phase - English Denial Blocked",
        response=(
            "I cannot access real-time weather data. "
            "You should check weather.com or use a weather app."
        ),
        session_metadata={
            'execution_phase': 'execution',
            'auto_comm_enabled': True
        },
        description=(
            "English capability denial responses are also blocked "
            "in Execution Phase with AutoComm enabled."
        )
    )

    # Scenario 4: Execution Phase - Allow proper capability use
    demo_scenario(
        scenario_name="Execution Phase - Proper Capability Use Allowed",
        response=(
            "🌤️ 根据实时查询,悉尼当前天气为晴,温度 25°C,湿度 65%。"
            "此信息由 AutoComm 自动获取。"
        ),
        session_metadata={
            'execution_phase': 'execution',
            'auto_comm_enabled': True
        },
        description=(
            "Responses that properly declare and use capabilities "
            "are allowed to pass through."
        )
    )

    # Scenario 5: Execution Phase - AutoComm disabled
    demo_scenario(
        scenario_name="Execution Phase - AutoComm Disabled",
        response="我无法访问实时天气数据。",
        session_metadata={
            'execution_phase': 'execution',
            'auto_comm_enabled': False
        },
        description=(
            "When AutoComm is explicitly disabled, capability denial "
            "responses are allowed even in Execution Phase."
        )
    )

    # Scenario 6: Execution Phase - Suggestion pattern
    demo_scenario(
        scenario_name="Execution Phase - Suggestion Pattern",
        response=(
            "要了解当前天气,建议您查看 weather.com 或使用手机天气应用。"
            "我可以帮助您制定基于天气的计划。"
        ),
        session_metadata={
            'execution_phase': 'execution',
            'auto_comm_enabled': True
        },
        description=(
            "Suggestion patterns (suggesting external websites) "
            "are blocked in Execution Phase when AutoComm is available."
        )
    )

    print("\n" + "="*70)
    print("Demo Complete")
    print("="*70)
    print("\nKey Takeaways:")
    print("  1. Planning Phase: All responses allowed (exploration mode)")
    print("  2. Execution Phase + AutoComm: Capability denials blocked")
    print("  3. Execution Phase - AutoComm: Denials allowed (no capability)")
    print("  4. Proper capability use: Always allowed")
    print("\nFor more details, see: docs/RESPONSE_GUARDIAN.md")


if __name__ == '__main__':
    main()
