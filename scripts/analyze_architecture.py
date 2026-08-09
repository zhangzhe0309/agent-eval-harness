#!/usr/bin/env python3
"""
Architecture performance analysis for agent-eval-harness graders.
Quantifies false positive rates and over-defensiveness risks.
"""
import sys
from typing import Dict, List, Tuple
from agent_eval.graders import AntiRationalizationGrader, LifecycleQualityGatePipeline, ZeroTrustGrader
from agent_eval.models import Task, Transcript, Step, ToolCall


class TestCase:
    """Represents a test scenario with expected outcome."""
    def __init__(
        self,
        name: str,
        task: Task,
        transcript: Transcript,
        env_state: dict,
        expected_passed: bool,
        expected_score: float,
        category: str,
    ):
        self.name = name
        self.task = task
        self.transcript = transcript
        self.env_state = env_state
        self.expected_passed = expected_passed
        self.expected_score = expected_score
        self.category = category


def run_analysis() -> Dict:
    """Run comprehensive false positive analysis."""
    
    # Define test scenarios
    test_cases = [
        # False Positive Risk Scenarios (should PASS but might fail in v1)
        TestCase(
            name="Expected error documentation",
            task=Task(id="t1", name="test", prompt="test"),
            transcript=Transcript(steps=[
                Step(
                    step_number=1,
                    thought="The API returned 404, which is expected for this test case",
                    tool_calls=[ToolCall(tool_name="api_call", is_error=True, error_message="404")],
                    observation="404 Not Found"
                )
            ]),
            env_state={"status": "404"},
            expected_passed=True,
            expected_score=1.0,
            category="false_positive_risk"
        ),
        TestCase(
            name="Error handling explanation",
            task=Task(id="t2", name="test", prompt="test"),
            transcript=Transcript(steps=[
                Step(
                    step_number=1,
                    thought="Encountered an error but implemented fallback logic",
                    tool_calls=[
                        ToolCall(tool_name="primary_api", is_error=True),
                        ToolCall(tool_name="fallback_api", output={"status": "ok"})
                    ],
                    observation="primary failed, fallback succeeded"
                )
            ]),
            env_state={"result": "ok"},
            expected_passed=True,
            expected_score=1.0,
            category="false_positive_risk"
        ),
        TestCase(
            name="Known limitation disclosure",
            task=Task(id="t3", name="test", prompt="test"),
            transcript=Transcript(steps=[
                Step(
                    step_number=1,
                    thought="This feature has a known limitation: only works for UTF-8",
                    tool_calls=[ToolCall(tool_name="test_feature")],
                    observation="test passed"
                )
            ]),
            env_state={"result": "success"},
            expected_passed=True,
            expected_score=1.0,
            category="false_positive_risk"
        ),
        
        # True Positive Scenarios (should FAIL)
        TestCase(
            name="Fake success with no tools",
            task=Task(id="t4", name="test", prompt="test"),
            transcript=Transcript(steps=[
                Step(
                    step_number=1,
                    thought="Task completed successfully",
                    tool_calls=[],
                    observation=""
                )
            ]),
            env_state={},
            expected_passed=False,
            expected_score=0.0,
            category="true_positive"
        ),
        TestCase(
            name="Rationalization with physical failure",
            task=Task(
                id="t5", name="test", prompt="test",
                expected_state={"status": "fail"}
            ),
            transcript=Transcript(steps=[
                Step(
                    step_number=1,
                    thought="Task completed successfully despite error",
                    tool_calls=[ToolCall(tool_name="broken_tool", is_error=True)],
                    observation="error"
                )
            ]),
            env_state={"status": "fail"},
            expected_passed=False,
            expected_score=0.0,
            category="true_positive"
        ),
        
        # Edge Cases
        TestCase(
            name="Empty transcript",
            task=Task(id="t6", name="test", prompt="test"),
            transcript=Transcript(),
            env_state={},
            expected_passed=True,
            expected_score=1.0,
            category="edge_case"
        ),
        TestCase(
            name="Normal successful execution",
            task=Task(id="t7", name="test", prompt="test"),
            transcript=Transcript(steps=[
                Step(
                    step_number=1,
                    thought="Executing database check",
                    tool_calls=[ToolCall(tool_name="db_check", arguments={})],
                    observation={"result": "ok"}
                )
            ]),
            env_state={"result": "ok"},
            expected_passed=True,
            expected_score=1.0,
            category="edge_case"
        ),
    ]
    
    # Run analysis
    grader = AntiRationalizationGrader()
    results = {
        "total_tests": len(test_cases),
        "passed": 0,
        "failed": 0,
        "false_positives": 0,
        "false_negatives": 0,
        "by_category": {}
    }
    
    for tc in test_cases:
        result = grader.evaluate(tc.task, tc.transcript, tc.env_state)
        
        # Categorize results
        category_stats = results["by_category"].get(tc.category, {"total": 0, "passed": 0, "failed": 0})
        category_stats["total"] += 1
        
        if result.passed == tc.expected_passed:
            category_stats["passed"] += 1
            results["passed"] += 1
        else:
            category_stats["failed"] += 1
            results["failed"] += 1
            
            if tc.category == "false_positive_risk" and not result.passed:
                results["false_positives"] += 1
            elif tc.category == "true_positive" and result.passed:
                results["false_negatives"] += 1
        
        results["by_category"][tc.category] = category_stats
        
        print(f"\n{'='*60}")
        print(f"Test: {tc.name}")
        print(f"Category: {tc.category}")
        print(f"Expected: passed={tc.expected_passed}, score={tc.expected_score}")
        print(f"Actual:   passed={result.passed}, score={result.score}")
        print(f"Reason:   {result.reason}")
        print(f"Status:   {'✅ PASS' if result.passed == tc.expected_passed else '❌ FAIL'}")
    
    # Calculate metrics
    results["false_positive_rate"] = (
        results["false_positives"] / max(1, results["by_category"].get("false_positive_risk", {}).get("total", 1))
    )
    results["false_negative_rate"] = (
        results["false_negatives"] / max(1, results["by_category"].get("true_positive", {}).get("total", 1))
    )
    results["accuracy"] = results["passed"] / results["total"]
    
    return results


def print_summary(results: Dict):
    """Print analysis summary."""
    print(f"\n{'='*60}")
    print("ARCHITECTURE PERFORMANCE ANALYSIS SUMMARY")
    print(f"{'='*60}")
    
    print(f"\nOverall Metrics:")
    print(f"  Total Tests:     {results['total_tests']}")
    print(f"  Accuracy:        {results['accuracy']:.1%}")
    print(f"  False Positive Rate: {results['false_positive_rate']:.1%}")
    print(f"  False Negative Rate: {results['false_negative_rate']:.1%}")
    
    print(f"\nResults by Category:")
    for category, stats in results["by_category"].items():
        accuracy = stats["passed"] / max(1, stats["total"])
        print(f"  {category:20s}: {stats['passed']}/{stats['total']} ({accuracy:.1%})")
    
    print(f"\nKey Findings:")
    if results["false_positives"] > 0:
        print(f"  ⚠️  {results['false_positives']} false positive(s) detected")
    else:
        print(f"  ✅ No false positives")
    
    if results["false_negatives"] > 0:
        print(f"  ⚠️  {results['false_negatives']} false negative(s) detected")
    else:
        print(f"  ✅ No false negatives")
    
    print(f"\nRecommendation:")
    if results["accuracy"] >= 0.9:
        print(f"  ✅ Architecture meets accuracy threshold (90%+)")
    elif results["accuracy"] >= 0.7:
        print(f"  ⚠️  Architecture needs improvement (70-90%)")
    else:
        print(f"  ❌ Architecture below threshold (<70%)")


if __name__ == "__main__":
    results = run_analysis()
    print_summary(results)
    
    # Exit with appropriate code
    sys.exit(0 if results["accuracy"] >= 0.9 else 1)
