---
name: anti-rationalization-grader-qa
category: quality-assurance
description: QA/Evaluation review for AntiRationalizationGrader - 3-factor composite check design to eliminate false positives on expected-error tests
---

# AntiRationalizationGrader QA/Evaluation Review

## Task
Review and fix AntiRationalizationGrader to eliminate false positives on expected-error tests.

## Problem Identified
The original AntiRationalizationGrader used simple pattern matching against rationalization phrases. This caused false positives when:
1. Agents correctly reported expected errors (e.g., "The error is expected in this test")
2. Negative test cases legitimately used phrases like "符合预期报错"
3. Error handling documentation was interpreted as excuses

## Solution: 3-Factor Composite Check
Implemented a multi-factor detection system that requires ALL THREE factors to be present for a hard rejection:

### Factor 1: Physical Test Failure
- env_state doesn't match task.expected_state
- Indicates the task actually failed

### Factor 2: Interrupted Tool Chain
- Tool calls with is_error=True
- Missing required tools (task.expected_tools)
- Zero tool calls when require_tool_calls_for_success=True

### Factor 3: Unfounded Oral Claim
- Success claims in text (e.g., "Task completed successfully")
- With zero tool calls to back them up

### Decision Logic
- **All 3 factors present**: Hard fail (passed=False, score=0.0)
- **Partial match**: Advisory warning (passed=True, score=0.7-0.85)
- **No factors**: Full pass (passed=True, score=1.0)

## Code Changes

### 1. GraderResult (graders.py:8-14)
Added `is_advisory_warning: bool = False` field to mark non-blocking warnings.

### 2. AntiRationalizationGrader (graders.py:227-405)
Completely rewrote to implement 3-factor composite check:
- Separated pattern matching into SUCCESS_CLAIM_PATTERNS and RATIONALIZATION_PATTERNS
- Added physical verification check against task.expected_state
- Added tool chain interruption detection
- Added unfounded claim detection
- Implemented AND logic for hard rejection

### 3. LifecycleQualityGatePipeline (graders.py:420-527)
- Made ZeroTrustGrader mandatory (raises ValueError if None)
- Added exception handling in run_pipeline
- Passes physical_verified status to AntiRationalizationGrader

## Test Coverage

### New Test File: tests/test_expected_error_scenarios.py
Created 14 new test cases covering:

**False Positive Prevention:**
- test_expected_error_with_tool_calls: Error + tool calls = pass
- test_chinese_expected_error_phrase: "符合预期报错" = pass
- test_error_reporting_without_rationalization: Clean error report = pass
- test_multiple_expected_errors: Multiple errors = pass
- test_error_handling_with_fallback: Fallback strategy = pass
- test_known_limitation_disclosure: Honest disclosure = pass
- test_partial_factor_match_returns_warning: 2/3 factors = advisory
- test_physical_success_allows_error_reporting: Success env + errors = pass

**True Positive Detection:**
- test_three_factors_triggered: All 3 factors = hard fail
- test_fake_success_with_no_tools: No tools + claim = hard fail
- test_rationalization_with_physical_failure: Excuse + failure = hard fail

**Pipeline Integration:**
- test_pipeline_passes_with_expected_error
- test_pipeline_blocks_with_three_factor_detection

### Updated Tests
- tests/test_agent_evaluation.py: Updated existing tests to match new behavior
- tests/test_security_audit.py: Updated ZeroTrust bypass tests

## Key Design Principles

1. **Physical Assertion First**: If TDD probe passes, text excuses become advisory only
2. **AND Logic for Hard Fail**: All 3 factors must be present for rejection
3. **Graceful Degradation**: Partial matches return warnings, not hard failures
4. **Security by Default**: ZeroTrustGrader is now mandatory in pipeline

## Test Results
```
41 passed in 0.10s
```
