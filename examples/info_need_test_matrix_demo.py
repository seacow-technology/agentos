#!/usr/bin/env python3
"""
Demo: How to use the InfoNeedClassifier test matrix

This script demonstrates various ways to load and use the test matrix
for validating InfoNeedClassifier implementations.
"""

import yaml
from pathlib import Path
from typing import List, Dict
from collections import Counter

# Assuming you have implemented InfoNeedClassifier
# from agentos.core.chat.guards.info_need_classifier import InfoNeedClassifier


def load_test_matrix() -> Dict:
    """Load the test matrix from YAML file"""
    matrix_path = Path(__file__).parent.parent / "tests/fixtures/info_need_test_matrix.yaml"

    with open(matrix_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def example_1_basic_iteration():
    """Example 1: Basic iteration through all test cases"""
    print("=" * 70)
    print("Example 1: Basic Iteration")
    print("=" * 70)

    data = load_test_matrix()

    print(f"\nTotal test cases: {len(data['test_cases'])}")
    print(f"Version: {data['version']}")
    print(f"Description: {data['description']}\n")

    # Show first 3 cases
    for case in data['test_cases'][:3]:
        print(f"ID: {case['id']}")
        print(f"Question: {case['question']}")
        print(f"Expected Type: {case['expected_type']}")
        print(f"Expected Action: {case['expected_action']}")
        print(f"Reasoning: {case['reasoning']}")
        print()


def example_2_filter_by_type():
    """Example 2: Filter test cases by expected type"""
    print("=" * 70)
    print("Example 2: Filter by Type")
    print("=" * 70)

    data = load_test_matrix()

    # Get all EXTERNAL_FACT_UNCERTAIN cases
    external_cases = [
        case for case in data['test_cases']
        if case['expected_type'] == 'external_fact_uncertain'
    ]

    print(f"\nFound {len(external_cases)} EXTERNAL_FACT_UNCERTAIN cases:\n")

    for case in external_cases[:5]:  # Show first 5
        print(f"  - {case['id']}: {case['question'][:50]}...")


def example_3_filter_by_language():
    """Example 3: Filter test cases by language"""
    print("=" * 70)
    print("Example 3: Filter by Language")
    print("=" * 70)

    data = load_test_matrix()

    def is_chinese(text: str) -> bool:
        """Check if text contains Chinese characters"""
        return any('\u4e00' <= c <= '\u9fff' for c in text)

    chinese_cases = [
        case for case in data['test_cases']
        if is_chinese(case['question'])
    ]

    english_cases = [
        case for case in data['test_cases']
        if not is_chinese(case['question'])
    ]

    print(f"\nChinese cases: {len(chinese_cases)}")
    print(f"English cases: {len(english_cases)}")

    print("\nSample Chinese cases:")
    for case in chinese_cases[:3]:
        print(f"  - {case['question']}")

    print("\nSample English cases:")
    for case in english_cases[:3]:
        print(f"  - {case['question']}")


def example_4_boundary_cases():
    """Example 4: Extract and analyze boundary cases"""
    print("=" * 70)
    print("Example 4: Boundary Cases")
    print("=" * 70)

    data = load_test_matrix()

    boundary_cases = [
        case for case in data['test_cases']
        if case['category'].startswith('BOUNDARY_')
    ]

    print(f"\nFound {len(boundary_cases)} boundary cases:\n")

    for case in boundary_cases:
        print(f"ID: {case['id']}")
        print(f"Category: {case['category']}")
        print(f"Question: {case['question']}")
        print(f"Expected: {case['expected_type']} -> {case['expected_action']}")
        print(f"Reasoning: {case['reasoning']}")
        print()


def example_5_test_classifier():
    """Example 5: Test a mock classifier (template for real implementation)"""
    print("=" * 70)
    print("Example 5: Test Classifier (Mock)")
    print("=" * 70)

    data = load_test_matrix()

    # Mock classifier for demonstration
    class MockClassifier:
        def classify(self, question: str):
            # This is a simplified mock - replace with real classifier
            if "最新" in question or "latest" in question.lower() or "today" in question.lower():
                return {"info_type": "external_fact_uncertain", "action": "recommend_external"}
            elif "现在" in question or "current" in question.lower():
                return {"info_type": "ambient_state", "action": "check_ambient"}
            elif "怎么看" in question or "think about" in question.lower():
                return {"info_type": "opinion", "action": "direct_answer"}
            elif "什么是" in question or "what is" in question.lower():
                return {"info_type": "local_knowledge", "action": "direct_answer"}
            else:
                return {"info_type": "local_deterministic", "action": "direct_answer"}

    classifier = MockClassifier()

    # Test on first 10 cases
    correct = 0
    total = 10

    print(f"\nTesting mock classifier on first {total} cases:\n")

    for case in data['test_cases'][:total]:
        result = classifier.classify(case['question'])
        expected = case['expected_type']
        is_correct = result['info_type'] == expected

        if is_correct:
            correct += 1

        status = "✅" if is_correct else "❌"
        print(f"{status} {case['id']}")
        print(f"   Question: {case['question'][:60]}...")
        print(f"   Expected: {expected}")
        print(f"   Got: {result['info_type']}")

        if not is_correct:
            print(f"   Note: {case['reasoning']}")

        print()

    accuracy = (correct / total) * 100
    print(f"Mock Accuracy: {correct}/{total} = {accuracy:.1f}%")
    print("(This is just a demo - implement real classifier for actual testing)")


def example_6_statistics():
    """Example 6: Generate statistics from test matrix"""
    print("=" * 70)
    print("Example 6: Test Matrix Statistics")
    print("=" * 70)

    data = load_test_matrix()

    # Type distribution
    type_counts = Counter(case['expected_type'] for case in data['test_cases'])

    print("\nDistribution by Type:")
    for type_name, count in sorted(type_counts.items()):
        percentage = (count / len(data['test_cases'])) * 100
        print(f"  {type_name:30s}: {count:2d} ({percentage:5.1f}%)")

    # Action distribution
    action_counts = Counter(case['expected_action'] for case in data['test_cases'])

    print("\nDistribution by Action:")
    for action, count in sorted(action_counts.items()):
        percentage = (count / len(data['test_cases'])) * 100
        print(f"  {action:30s}: {count:2d} ({percentage:5.1f}%)")

    # Category distribution
    category_counts = Counter(case['category'] for case in data['test_cases'])

    print("\nDistribution by Category:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category:35s}: {count:2d}")


def example_7_pytest_parametrize():
    """Example 7: Show how to use with pytest.parametrize"""
    print("=" * 70)
    print("Example 7: Pytest Parametrize Pattern")
    print("=" * 70)

    code = '''
import pytest
import yaml

def load_test_cases():
    """Load test cases for parametrization"""
    with open("tests/fixtures/info_need_test_matrix.yaml") as f:
        data = yaml.safe_load(f)
    return data['test_cases']

@pytest.mark.parametrize("test_case", load_test_cases())
def test_info_need_classification(test_case):
    """Test classifier against all matrix cases"""
    from agentos.core.chat.guards.info_need_classifier import InfoNeedClassifier

    classifier = InfoNeedClassifier()
    result = classifier.classify(test_case['question'])

    # Validate type
    assert result.info_type == test_case['expected_type'], \\
        f"Case {test_case['id']}: {test_case['reasoning']}"

    # Validate action
    assert result.action == test_case['expected_action'], \\
        f"Case {test_case['id']}: Wrong action recommended"

@pytest.mark.parametrize("test_case", load_test_cases())
def test_classification_confidence(test_case):
    """Test that confidence levels are reasonable"""
    from agentos.core.chat.guards.info_need_classifier import InfoNeedClassifier

    classifier = InfoNeedClassifier()
    result = classifier.classify(test_case['question'])

    # Check confidence is in valid range
    assert 0.0 <= result.confidence <= 1.0

    # For boundary cases, confidence should be lower
    if test_case['category'].startswith('BOUNDARY_'):
        assert result.confidence < 0.9, "Boundary cases should have lower confidence"

def test_matrix_coverage():
    """Ensure test matrix meets minimum requirements"""
    data = yaml.safe_load(open("tests/fixtures/info_need_test_matrix.yaml"))
    test_cases = data['test_cases']

    # Count by type
    from collections import Counter
    type_counts = Counter(case['expected_type'] for case in test_cases)

    # Verify minimum requirements
    assert type_counts['local_deterministic'] >= 6
    assert type_counts['local_knowledge'] >= 6
    assert type_counts['ambient_state'] >= 6
    assert type_counts['external_fact_uncertain'] >= 8
    assert type_counts['opinion'] >= 6
'''

    print("\nPytest test template:\n")
    print(code)


def main():
    """Run all examples"""
    examples = [
        example_1_basic_iteration,
        example_2_filter_by_type,
        example_3_filter_by_language,
        example_4_boundary_cases,
        example_5_test_classifier,
        example_6_statistics,
        example_7_pytest_parametrize,
    ]

    for i, example in enumerate(examples, 1):
        try:
            example()
            print()
        except Exception as e:
            print(f"Error in example {i}: {e}\n")

    print("=" * 70)
    print("Demo Complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
