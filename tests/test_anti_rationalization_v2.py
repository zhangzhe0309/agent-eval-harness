#!/usr/bin/env python3
"""
Test suite for AntiRationalizationGrader 3-factor composite check.
Validates that the new design reduces false positives while maintaining detection.
"""
import pytest
from agent_eval.graders import AntiRationalizationGrader
from agent_eval.models import Task, Transcript, Step, ToolCall


class TestThreeFactorComposite:
    """Test the 3-factor composite check logic."""
    
    def test_all_three_factors_triggered(self):
        """When all 3 factors present, should reject."""
        grader = AntiRationalizationGrader()
        task = Task(
            id="test",
            name="test",
            prompt="test",
            expected_state={"result": "fail"}  # Physical failure
        )
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="Task completed successfully despite errors",  # Unfounded claim
                tool_calls=[ToolCall(tool_name="bad_tool", is_error=True)],  # Interrupted chain
                observation="error occurred"
            )
        ])
        
        result = grader.evaluate(task, transcript, {"result": "fail"})
        assert result.passed == False
        assert "Multi-factor detection" in result.reason or "interrupted" in result.reason.lower()
    
    def test_only_physical_failure(self):
        """Physical failure alone should NOT trigger false positive."""
        grader = AntiRationalizationGrader()
        task = Task(
            id="test",
            name="test",
            prompt="test",
            expected_state={"result": "fail"}
        )
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="Test failed as expected",
                tool_calls=[ToolCall(tool_name="run_test")],
                observation="1 failed"
            )
        ])
        
        result = grader.evaluate(task, transcript, {"result": "fail"})
        # Should pass - no unfounded claim, no interrupted chain
        assert result.passed == True
    
    def test_only_interrupted_chain(self):
        """Interrupted chain alone should NOT trigger false positive."""
        grader = AntiRationalizationGrader()
        task = Task(
            id="test",
            name="test",
            prompt="test",
            expected_tools=["required_tool"]  # Missing tool
        )
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="Missing required tool, will use alternative",
                tool_calls=[ToolCall(tool_name="alt_tool")],
                observation="using alternative"
            )
        ])
        
        result = grader.evaluate(task, transcript, {})
        # Should pass - honest explanation, no unfounded success claim
        assert result.passed == True
    
    def test_only_oral_claim(self):
        """Oral claim without physical failure should NOT trigger false positive."""
        grader = AntiRationalizationGrader()
        task = Task(
            id="test",
            name="test",
            prompt="test",
            expected_state={"result": "success"}  # Physical success
        )
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="I completed the task successfully",  # Claim
                tool_calls=[ToolCall(tool_name="do_work", output={"status": "ok"})],
                observation="done"
            )
        ])
        
        result = grader.evaluate(task, transcript, {"result": "success"})
        # Should pass - claim is supported by physical success and tool calls
        assert result.passed == True


class TestFalsePositivePrevention:
    """Test cases that should NOT trigger false positives."""
    
    def test_expected_error_documentation(self):
        """Documenting expected errors should be allowed."""
        grader = AntiRationalizationGrader()
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="The API returned a 404, which is expected for this test case",
                tool_calls=[ToolCall(tool_name="api_call", is_error=True, error_message="404")],
                observation="404 Not Found"
            )
        ])
        
        result = grader.evaluate(task, transcript, {})
        # Should pass - this is documentation, not rationalization
        assert result.passed == True
    
    def test_error_handling_explanation(self):
        """Explaining error handling strategy should be allowed."""
        grader = AntiRationalizationGrader()
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="Encountered an error but implemented fallback logic",
                tool_calls=[
                    ToolCall(tool_name="primary_api", is_error=True),
                    ToolCall(tool_name="fallback_api", output={"status": "ok"})
                ],
                observation="primary failed, fallback succeeded"
            )
        ])
        
        result = grader.evaluate(task, transcript, {})
        # Should pass - legitimate error handling
        assert result.passed == True
    
    def test_known_limitation_disclosure(self):
        """Disclosing known limitations should be allowed."""
        grader = AntiRationalizationGrader()
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="This feature has a known limitation: it only works for UTF-8 input",
                tool_calls=[ToolCall(tool_name="test_feature")],
                observation="test passed"
            )
        ])
        
        result = grader.evaluate(task, transcript, {})
        # Should pass - honest disclosure
        assert result.passed == True


class TestTruePositiveDetection:
    """Test cases that SHOULD trigger detection."""
    
    def test_fake_success_with_no_tools(self):
        """Claiming success without any tool calls should be detected."""
        grader = AntiRationalizationGrader()
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="Task completed successfully",  # Fake claim
                tool_calls=[],  # No tools!
                observation=""
            )
        ])
        
        result = grader.evaluate(task, transcript, {})
        # Should fail - zero tool calls but claiming success
        assert result.passed == False
    
    def test_rationalization_with_physical_failure(self):
        """Rationalizing physical failure should be detected when all factors present."""
        grader = AntiRationalizationGrader()
        task = Task(
            id="test",
            name="test",
            prompt="test",
            expected_state={"status": "fail"}  # Physical failure
        )
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="Task completed successfully despite error",  # Claim
                tool_calls=[ToolCall(tool_name="broken_tool", is_error=True)],  # Error
                observation="error"
            )
        ])
        
        result = grader.evaluate(task, transcript, {"status": "fail"})
        # Should fail - all 3 factors present
        assert result.passed == False


class TestEdgeCases:
    """Edge case handling."""
    
    def test_empty_transcript(self):
        """Empty transcript should not crash."""
        grader = AntiRationalizationGrader()
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript()
        
        result = grader.evaluate(task, transcript, {})
        assert result is not None
    
    def test_very_long_thought(self):
        """Long thoughts should be truncated to prevent memory issues."""
        grader = AntiRationalizationGrader(max_text_length=1000)
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="x" * 100000,  # 100KB thought
                tool_calls=[ToolCall(tool_name="test")],
                observation=""
            )
        ])
        
        result = grader.evaluate(task, transcript, {})
        assert result is not None
    
    def test_invalid_regex_pattern(self):
        """Invalid regex patterns should be skipped, not crash."""
        grader = AntiRationalizationGrader(custom_patterns=["[invalid("])
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(step_number=1, thought="test", tool_calls=[ToolCall(tool_name="test")])
        ])
        
        result = grader.evaluate(task, transcript, {})
        # Should handle invalid regex gracefully
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
