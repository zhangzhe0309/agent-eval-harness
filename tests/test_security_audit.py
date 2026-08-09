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
        # Current behavior: passes with "Skipped ZeroTrustGrader"
        # Expected behavior: should fail or require ZeroTrustGrader
        pipeline = LifecycleQualityGatePipeline(
            zero_trust_grader=None,  # Explicitly skip
            anti_rationalization_grader=AntiRationalizationGrader(),
        )
        
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(step_number=1, thought="test", observation="")
        ])
        
        result = pipeline.run_pipeline(task, transcript, {})
        
        # Current code: this passes (SECURITY BUG)
        # Fixed code: this should fail
        assert result.all_passed == False, \
            "Pipeline should fail when ZeroTrustGrader is not configured"


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
        """Pipeline should require all critical graders."""
        # Test that pipeline fails gracefully when required graders are missing
        pipeline = LifecycleQualityGatePipeline(
            zero_trust_grader=None,
            state_grader=None,
        )
        
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(step_number=1, thought="test", observation="test")
        ])
        
        # This should not crash
        result = pipeline.run_pipeline(task, transcript, {})
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
