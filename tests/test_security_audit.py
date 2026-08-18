#!/usr/bin/env python3
"""
Security test cases for agent-eval-harness quality gates.
These tests verify zero-trust security properties.
"""
import pytest
import re
from agent_eval.graders import (
    AntiRationalizationGrader,
    LifecycleQualityGatePipeline,
    ZeroTrustGrader,
    StepEfficiencyGrader,
    CodeGrader,
    LLMJudgeGrader,
    ToolCorrectnessGrader,
    CompositeGrader,
)
from agent_eval.models import Task, Transcript, Step


class TestRegexInjection:
    """Test regex injection safety in AntiRationalizationGrader."""
    
    def test_malicious_redos_pattern_rejected(self):
        """ReDoS patterns should not cause catastrophic backtracking."""
        grader = AntiRationalizationGrader(
            custom_patterns=[r"(a+)+b"]  # Classic ReDoS pattern
        )
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(step_number=1, thought="a" * 100, observation="")
        ])
        
        # This should complete quickly, not hang
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Regex matching took too long - ReDoS detected!")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(2)  # 2 second timeout
        
        try:
            result = grader.evaluate(task, transcript, {})
            signal.alarm(0)  # Cancel alarm
        except TimeoutError:
            pytest.fail("ReDoS vulnerability detected: regex matching timed out")
        finally:
            signal.alarm(0)
    
    def test_named_group_injection(self):
        """Named group injection should be handled safely."""
        # This pattern contains a named group - potential info leakage
        malicious_pattern = r"(?P<secret>test)"
        
        grader = AntiRationalizationGrader(custom_patterns=[malicious_pattern])
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(step_number=1, thought="test", observation="")
        ])
        
        # Should not raise an exception
        result = grader.evaluate(task, transcript, {})
        assert result is not None


class TestZeroTrustBypass:
    """Test ZeroTrustGrader cannot be silently skipped."""
    
    def test_pipeline_without_zero_trust_should_fail(self):
        """Pipeline should not pass when ZeroTrustGrader is missing."""
        # Current behavior: raises ValueError
        # Expected behavior: should fail or require ZeroTrustGrader
        with pytest.raises(ValueError, match="ZeroTrustGrader is mandatory"):
            pipeline = LifecycleQualityGatePipeline(
                zero_trust_grader=None,  # Explicitly skip
                anti_rationalization_grader=AntiRationalizationGrader(),
            )


class TestExceptionHandler:
    """Test exception handling in grader methods."""
    
    def test_grader_with_raising_check_fn(self):
        """Graders should handle exceptions in user-provided callables."""
        def bad_check_fn(task, transcript, env_state):
            raise ValueError("Intentional error")
        
        grader = ZeroTrustGrader(tdd_assert_fn=bad_check_fn)
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript()
        
        # Should not raise, should return failed result
        result = grader.evaluate(task, transcript, {})
        assert result.passed == False
        assert "Error" in result.reason or "Exception" in result.reason

    def test_code_grader_with_raising_check_fn(self):
        """CodeGrader should handle exceptions in user-provided callables."""
        def bad_check_fn(task, transcript, env_state):
            raise ValueError("Intentional error")
        
        grader = CodeGrader(check_fn=bad_check_fn)
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript()
        
        # Should not raise, should return failed result
        result = grader.evaluate(task, transcript, {})
        assert result.passed == False
        assert "CodeGrader" in result.name
        assert "Check function error" in result.reason

    def test_llm_judge_grader_with_raising_judge_fn(self):
        """LLMJudgeGrader should handle exceptions in user-provided callables."""
        def bad_judge_fn(task, transcript):
            raise TypeError("Intentional error")
        
        grader = LLMJudgeGrader(rubric="test rubric", judge_fn=bad_judge_fn)
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript()
        
        # Should not raise, should return failed result
        result = grader.evaluate(task, transcript, {})
        assert result.passed == False
        assert "LLMJudgeGrader" in result.name
        assert "Judge function error" in result.reason

    def test_tool_correctness_grader_with_raising_check_fn(self):
        """ToolCorrectnessGrader should handle exceptions in user-provided callables."""
        def bad_check_fn(tool_name, args):
            raise RuntimeError("Intentional error")
        
        grader = ToolCorrectnessGrader(check_args_fn=bad_check_fn)
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(step_number=1, tool_calls=[{"tool_name": "test", "arguments": {}}])
        ])
        
        # Should not raise, should return failed result
        result = grader.evaluate(task, transcript, {})
        assert result.passed == False
        assert "ToolCorrectnessGrader" in result.name
        assert "Args check error" in result.reason

    def test_composite_grader_with_raising_subgrader(self):
        """CompositeGrader should handle exceptions in sub-graders."""
        class BadGrader:
            name = "BadGrader"
            def evaluate(self, task, transcript, env_state):
                raise ValueError("Intentional error")
        
        grader = CompositeGrader(graders=[(BadGrader(), 1.0)])
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript()
        
        # Should not raise, should return failed result
        result = grader.evaluate(task, transcript, {})
        assert result.passed == False
        assert "Error during evaluation" in result.reason

    def test_composite_grader_with_empty_list(self):
        """CompositeGrader should handle empty graders list gracefully."""
        grader = CompositeGrader(graders=[])
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript()
        
        # Should not raise, should return result
        result = grader.evaluate(task, transcript, {})
        assert result is not None
        assert "No graders configured" in result.reason

    def test_composite_grader_with_zero_total_weight(self):
        """CompositeGrader should handle zero total weight gracefully."""
        grader = CompositeGrader(graders=[
            (CodeGrader(check_fn=lambda t, tr, es: (True, "ok")), 0.0),
            (CodeGrader(check_fn=lambda t, tr, es: (True, "ok")), 0.0),
        ])
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript()
        
        # Should not raise, should return result
        result = grader.evaluate(task, transcript, {})
        assert result is not None
        assert "Total weight is zero" in result.reason


class TestInputSanitization:
    """Test input sanitization."""
    
    def test_very_long_thought(self):
        """Very long agent thoughts should not cause memory issues."""
        grader = AntiRationalizationGrader()
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(step_number=1, thought="x" * 100000, observation="")  # 100KB thought
        ])
        
        # Should complete without memory issues
        result = grader.evaluate(task, transcript, {})
        assert result is not None


class TestLifecyclePipeline:
    """Test lifecycle pipeline security."""
    
    def test_all_graders_must_be_configured(self):
        """Pipeline should require ZeroTrustGrader."""
        # Test that pipeline raises when ZeroTrustGrader is missing
        with pytest.raises(ValueError, match="ZeroTrustGrader is mandatory"):
            pipeline = LifecycleQualityGatePipeline(
                zero_trust_grader=None,
                state_grader=None,
            )

    def test_pipeline_with_all_required_graders(self):
        """Pipeline should work when ZeroTrustGrader is provided."""
        pipeline = LifecycleQualityGatePipeline(
            zero_trust_grader=ZeroTrustGrader(
                tdd_assert_fn=lambda t, tr, es: (True, "verified")
            ),
            state_grader=None,
        )
        
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(step_number=1, thought="test", observation="test")
        ])
        
        # This should not crash
        result = pipeline.run_pipeline(task, transcript, {})
        assert result is not None


class TestStepEfficiencyGrader:
    """Test StepEfficiencyGrader edge cases."""
    
    def test_max_steps_zero_with_no_steps(self):
        """max_steps=0 with no steps should pass."""
        grader = StepEfficiencyGrader(max_steps=0)
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript()
        
        result = grader.evaluate(task, transcript, {})
        assert result.passed == True
        assert result.score == 1.0

    def test_max_steps_zero_with_steps(self):
        """max_steps=0 with steps should fail."""
        grader = StepEfficiencyGrader(max_steps=0)
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(step_number=1, thought="test")
        ])
        
        result = grader.evaluate(task, transcript, {})
        assert result.passed == False
        assert result.score == 0.0


class TestAntiRationalizationGrader:
    """Test AntiRationalizationGrader edge cases."""
    
    def test_physical_verified_override_true(self):
        """physical_verified=True should disable physical failure detection."""
        grader = AntiRationalizationGrader()
        task = Task(id="test", name="test", prompt="test", expected_state={"status": "fail"})
        transcript = Transcript(steps=[
            Step(step_number=1, thought="Task completed successfully", tool_calls=[])
        ])
        
        # Even though env_state doesn't match expected, physical_verified=True
        # should prevent physical failure detection
        result = grader.evaluate(task, transcript, {"status": "fail"}, physical_verified=True)
        # Should still detect zero tool calls + unfounded claim
        assert result is not None

    def test_physical_verified_override_false(self):
        """physical_verified=False should force physical failure."""
        grader = AntiRationalizationGrader()
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(step_number=1, thought="Task completed successfully", tool_calls=[])
        ])
        
        result = grader.evaluate(task, transcript, {}, physical_verified=False)
        # Should detect physical failure + zero tools + unfounded claim
        assert result is not None

    def test_allow_expected_errors_prevents_false_positive(self):
        """allow_expected_errors=True should prevent false positives."""
        grader = AntiRationalizationGrader(allow_expected_errors=True)
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(step_number=1, thought="The error is expected for this test", tool_calls=[
                {"tool_name": "test", "arguments": {}, "is_error": True}
            ])
        ])
        
        result = grader.evaluate(task, transcript, {})
        assert result.passed == True

    def test_invalid_regex_pattern_skipped(self):
        """Invalid regex patterns should be skipped, not crash."""
        grader = AntiRationalizationGrader(custom_patterns=["[invalid("])
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(step_number=1, thought="test", tool_calls=[{"tool_name": "test"}])
        ])
        
        result = grader.evaluate(task, transcript, {})
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
