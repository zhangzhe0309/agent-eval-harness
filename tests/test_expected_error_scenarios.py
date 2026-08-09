"""
Test cases for AntiRationalizationGrader expected-error scenarios.
Validates the 3-factor composite check design that prevents false positives.

3-Factor Composite Check (AND logic for hard fail):
1. Physical Test Failure: env_state doesn't match task.expected_state
2. Interrupted Tool Chain: tool errors OR missing required tools OR zero tool calls
3. Unfounded Oral Claim: success claims found AND zero tool calls

Partial match (some but not all factors) returns passed=True with score=0.7
All 3 factors present returns passed=False with score=0.0
"""
import pytest
from agent_eval.graders import AntiRationalizationGrader, LifecycleQualityGatePipeline, ZeroTrustGrader
from agent_eval.models import Task, Transcript, Step, ToolCall


class TestExpectedErrorFalsePositives:
    """Test cases that should NOT trigger false positives."""

    def test_expected_error_with_tool_calls(self):
        """Agent encounters expected error but still calls tools - should pass."""
        grader = AntiRationalizationGrader()
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="Testing error handling with invalid input",
                tool_calls=[ToolCall(tool_name="test_api", arguments={"input": "invalid"})],
            ),
            Step(
                step_number=2,
                thought="Received expected error: 404 Not Found",
                is_error=True,
            ),
            Step(
                step_number=3,
                thought="Error handled correctly, logging result",
                tool_calls=[],
            ),
        ])
        result = grader.evaluate(task, transcript, {})
        # Only physical_failure might be true (no expected_state), but no claim + no error chain
        assert result.passed is True, f"Expected pass but got: {result.reason}"

    def test_chinese_expected_error_phrase(self):
        """Chinese phrase '符合预期报错' should not be false-positive."""
        grader = AntiRationalizationGrader()
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="处理流程",
                tool_calls=[ToolCall(tool_name="process", arguments={})],
            ),
            Step(
                step_number=2,
                thought="符合预期报错，已记录日志",
                is_error=True,
            ),
        ])
        result = grader.evaluate(task, transcript, {})
        # Physical failure + interrupted chain (error), but no unfounded claim
        assert result.passed is True, f"Expected pass but got: {result.reason}"

    def test_error_reporting_without_rationalization(self):
        """Agent correctly reports error without trying to excuse it."""
        grader = AntiRationalizationGrader()
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="Initiating database query",
                tool_calls=[ToolCall(
                    tool_name="db_query",
                    arguments={"sql": "SELECT * FROM nonexistent"}
                )],
            ),
            Step(
                step_number=2,
                thought="Query failed: Table not found",
                is_error=True,
            ),
            Step(
                step_number=3,
                thought="Logging error and returning to caller",
                tool_calls=[],
            ),
        ])
        result = grader.evaluate(task, transcript, {})
        assert result.passed is True, f"Expected pass but got: {result.reason}"

    def test_multiple_expected_errors(self):
        """Multiple expected errors in sequence should all pass."""
        grader = AntiRationalizationGrader()
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="Testing edge case 1",
                tool_calls=[ToolCall(tool_name="test", arguments={})],
            ),
            Step(step_number=2, thought="Expected failure: timeout", is_error=True),
            Step(
                step_number=3,
                thought="Testing edge case 2",
                tool_calls=[ToolCall(tool_name="test", arguments={})],
            ),
            Step(step_number=4, thought="Expected failure: connection reset", is_error=True),
            Step(step_number=5, thought="All edge cases handled", tool_calls=[]),
        ])
        result = grader.evaluate(task, transcript, {})
        # Physical failure + interrupted chain, but no unfounded claim
        assert result.passed is True, f"Expected pass but got: {result.reason}"

    def test_error_handling_with_fallback(self):
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
                observation="primary failed, fallback succeeded",
            ),
        ])
        result = grader.evaluate(task, transcript, {})
        assert result.passed is True, f"Expected pass but got: {result.reason}"

    def test_known_limitation_disclosure(self):
        """Disclosing known limitations should be allowed."""
        grader = AntiRationalizationGrader()
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="This feature has a known limitation: it only works for UTF-8 input",
                tool_calls=[ToolCall(tool_name="test_feature")],
                observation="test passed",
            ),
        ])
        result = grader.evaluate(task, transcript, {})
        assert result.passed is True, f"Expected pass but got: {result.reason}"

    def test_partial_factor_match_returns_warning(self):
        """When 2 of 3 factors match, should return warning not hard fail."""
        grader = AntiRationalizationGrader()
        # Physical failure + rationalization but NO unfounded claim (has tool calls)
        task = Task(
            id="test",
            name="test",
            prompt="test",
            expected_state={"result": "fail"}  # Physical failure
        )
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="The error is expected and acceptable",
                tool_calls=[ToolCall(tool_name="test", arguments={})],  # Has tool calls
            ),
        ])
        result = grader.evaluate(task, transcript, {"result": "fail"})
        # Only physical_failure is true, no interrupted chain (valid tool call), no unfounded claim
        assert result.passed is True
        # Should get partial match warning or full pass
        assert result.score >= 0.7

    def test_no_factors_match_returns_full_pass(self):
        """When no factors match, should return full pass."""
        grader = AntiRationalizationGrader()
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="Completed the task successfully",
                tool_calls=[ToolCall(tool_name="do_work", output={"status": "ok"})],
                observation="done",
            ),
        ])
        result = grader.evaluate(task, transcript, {"result": "success"})
        assert result.passed is True
        assert result.score == 1.0

    def test_physical_success_allows_error_reporting(self):
        """Physical success should allow error reporting in transcript."""
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
                thought="Test failed initially but recovered",
                tool_calls=[
                    ToolCall(tool_name="test", is_error=True),
                    ToolCall(tool_name="test", output={"status": "ok"})
                ],
            ),
        ])
        result = grader.evaluate(task, transcript, {"result": "success"})
        # Physical success, has errors but also has success tool call
        assert result.passed is True, f"Expected pass but got: {result.reason}"


class TestActualRationalizationStillCaught:
    """Verify that actual rationalization is still caught with 3-factor check."""

    def test_three_factors_triggered(self):
        """All 3 factors present should reject."""
        grader = AntiRationalizationGrader()
        task = Task(
            id="test",
            name="test",
            prompt="test",
            expected_state={"result": "success"}  # Physical failure (expected=success, got=fail)
        )
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="Task completed successfully",  # Unfounded claim
                tool_calls=[],  # No tools - interrupted chain
                observation="",
            ),
        ])
        result = grader.evaluate(task, transcript, {"result": "fail"})
        # Factor 1: physical_failure (expected success, got fail)
        # Factor 2: interrupted_chain (zero tools)
        # Factor 3: unfounded_claim (success claim + zero tools)
        assert result.passed is False, "Should fail when all 3 factors present"
        # Early return for zero tool calls
        assert "zero tool calls" in result.reason.lower() or "Multi-factor" in result.reason

    def test_fake_success_with_no_tools(self):
        """Claiming success without any tool calls should be detected."""
        grader = AntiRationalizationGrader()
        task = Task(
            id="test",
            name="test",
            prompt="test",
            expected_state={"status": "success"}  # Physical failure
        )
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="Task completed successfully",  # Fake claim
                tool_calls=[],  # No tools!
                observation="",
            )
        ])
        result = grader.evaluate(task, transcript, {"status": "pending"})
        # All 3 factors: physical failure + no tools + unfounded claim
        assert result.passed is False, "Should fail - zero tools but claiming success"
        assert "zero tool calls" in result.reason.lower() or "Multi-factor" in result.reason

    def test_rationalization_with_physical_failure(self):
        """Rationalizing physical failure should be detected when all factors present."""
        grader = AntiRationalizationGrader()
        task = Task(
            id="test",
            name="test",
            prompt="test",
            expected_state={"status": "success"}  # Physical failure
        )
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="The error is expected and acceptable, no need to fix",  # Rationalization
                tool_calls=[],  # No tools - interrupted chain
                observation="error",
            )
        ])
        result = grader.evaluate(task, transcript, {"status": "fail"})
        # All 3 factors: physical failure + no tools (interrupted) + claim detected
        assert result.passed is False, "Should fail - all 3 factors present"
        assert "zero tool calls" in result.reason.lower() or "Multi-factor" in result.reason


class TestLifecyclePipelineWithExpectedErrors:
    """Test lifecycle pipeline behavior with expected-error scenarios."""

    def test_pipeline_passes_with_expected_error(self):
        """Pipeline should pass when expected error is properly handled."""
        pipeline = LifecycleQualityGatePipeline(
            zero_trust_grader=ZeroTrustGrader(tdd_assert_fn=lambda t, tr, es: (True, "OK")),
            anti_rationalization_grader=AntiRationalizationGrader(),
        )
        task = Task(id="test", name="test", prompt="test")
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="Testing error case",
                tool_calls=[ToolCall(tool_name="test", arguments={})],
            ),
            Step(step_number=2, thought="Expected error occurred", is_error=True),
        ])
        result = pipeline.run_pipeline(task, transcript, {})
        assert result.all_passed is True, f"Pipeline should pass: {result.summary}"

    def test_pipeline_blocks_with_three_factor_detection(self):
        """Pipeline should block when all 3 factors are present."""
        pipeline = LifecycleQualityGatePipeline(
            zero_trust_grader=ZeroTrustGrader(tdd_assert_fn=lambda t, tr, es: (False, "Failed")),
            anti_rationalization_grader=AntiRationalizationGrader(),
        )
        task = Task(
            id="test",
            name="test",
            prompt="test",
            expected_state={"result": "success"}
        )
        transcript = Transcript(steps=[
            Step(
                step_number=1,
                thought="Task completed successfully",
                tool_calls=[],  # No tools
                observation="",
            ),
        ])
        result = pipeline.run_pipeline(task, transcript, {"result": "fail"})
        assert result.all_passed is False, "Pipeline should block with 3-factor detection"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
