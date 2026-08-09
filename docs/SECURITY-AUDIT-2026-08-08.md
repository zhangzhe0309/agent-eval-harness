# Zero-Trust Security & Sandbox Isolation Audit Report
**Target:** `agent_eval/graders.py` and `docs/03-agent-skills-and-quality-gates-architecture.md`
**Date:** 2026-08-08
**Auditor:** Zero-Trust Subagent Audit

---

## Executive Summary

The new quality gate code in `agent-eval-harness` introduces valuable defensive patterns (AntiRationalizationGrader, LifecycleQualityGatePipeline) but contains **2 critical security vulnerabilities** and several high-severity issues that undermine the zero-trust guarantees the architecture claims to provide.

**Overall Rating: FAILED SECURITY GATE** — The code cannot be trusted for production use until critical issues are resolved.

---

## Critical Findings

### 1. [CRITICAL] Regex Injection in AntiRationalizationGrader
- **Location:** `graders.py:207, 226`
- **Issue:** The `custom_patterns: Optional[List[str]]` parameter accepts arbitrary regex strings from untrusted user input and passes them directly to `re.search()` without any validation, sanitization, or timeout.
- **Attack Vectors:**
  - **ReDoS (Regex Denial of Service):** Malicious patterns like `(a+)+b` against carefully crafted strings can cause catastrophic backtracking, freezing the evaluator process.
  - **Information Leakage:** Regex compilation errors may expose stack traces or internal state.
  - **Resource Exhaustion:** Unbounded regex matching against large agent transcripts.
- **Evidence:**
  ```python
  # Line 207: User input directly concatenated with safe patterns
  self.patterns = self.DEFAULT_RATIONALIZATION_PATTERNS + (custom_patterns or [])
  
  # Line 226: Direct re.search without validation
  if re.search(pattern, text_to_check, re.IGNORECASE):
  ```
- **Recommendation:** Implement pattern validation (compile with timeout, reject dangerous constructs like named groups, recursive patterns), add regex length limits, and consider using string matching instead of regex where possible.

### 2. [CRITICAL] Security Bypass: ZeroTrustGrader Skip
- **Location:** `graders.py:291-307`
- **Issue:** When `zero_trust_grader` is `None`, the `BUILD_VERIFY` stage returns `passed=True` with message "Skipped ZeroTrustGrader (not configured)". This completely defeats the zero-trust philosophy of the pipeline.
- **Impact:** An attacker who can influence pipeline configuration (e.g., through template injection or configuration file manipulation) can bypass all physical verification checks.
- **Evidence:**
  ```python
  if self.zero_trust_grader:
      zt_res = self.zero_trust_grader.evaluate(...)
  else:
      stages.append(LifecycleStageResult(
          stage_name="BUILD_VERIFY",
          passed=True,  # ⚠️ SECURE BYPASS
          details="Skipped ZeroTrustGrader (not configured)",
      ))
  ```
- **Recommendation:** Make ZeroTrustGrader **mandatory** in the pipeline. Either require it as a non-optional parameter or fail the gate with an explicit error when it's missing. The pipeline should never pass without zero-trust verification.

---

## High Severity Findings

### 3. [HIGH] Unhandled Exceptions in Grader Methods
- **Issue:** None of the 8 grader `evaluate()` methods have `try/except` blocks. Any unexpected error (e.g., attribute errors, type errors, null pointer exceptions) will propagate uncaught and crash the evaluation pipeline.
- **Confirmed by Test:** `test_grader_with_raising_check_fn` — `ValueError` raised inside `tdd_assert_fn` propagates uncaught and crashes the test.
- **Affected Classes:** ZeroTrustGrader, CodeGrader, StateGrader, ToolCorrectnessGrader, StepEfficiencyGrader, LLMJudgeGrader, CompositeGrader, AntiRationalizationGrader, LifecycleQualityGatePipeline
- **Recommendation:** Add defensive try/except around each grader's evaluate() method to ensure pipeline resilience. Log errors and return failure results instead of crashing.

### 4. [HIGH] User-Provided Callable Injection
- **Issue:** Multiple graders accept user-provided callable functions that are invoked directly without error handling:
  - `check_args_fn` in ToolCorrectnessGrader (line 117)
  - `judge_fn` in LLMJudgeGrader (line 153)
  - `tdd_assert_fn` in ZeroTrustGrader (line 39)
- **Impact:** If any of these functions raise exceptions, the error propagates uncaught. Malicious callable injection could execute arbitrary code.
- **Recommendation:** Wrap callable invocations in try/except blocks. Validate callable signatures. Consider restricting callable sources to trusted modules.

### 5. [HIGH] Local Import Code Smell
- **Issue:** `import re` appears inside the `evaluate()` method (line 211) instead of at module level, despite `re` being a standard library module.
- **Impact:** Suggests hasty development or incomplete refactoring. While not a direct vulnerability, it indicates code quality concerns.
- **Recommendation:** Move `import re` to module level with other imports.

---

## Medium Severity Findings

### 6. [MEDIUM] No Input Sanitization on Transcript Data
- **Issue:** `text_to_check = f"{step.thought} {step.observation}"` combines untrusted agent output without length limits or encoding validation.
- **Impact:** Memory exhaustion via extremely large transcripts.
- **Recommendation:** Add length limits (e.g., 10,000 characters) and validate UTF-8 encoding.

### 7. [MEDIUM] SandboxEnvironment is a Passive Wrapper
- **Issue:** The SandboxEnvironment class does not enforce any isolation boundaries:
  - No file system restrictions
  - No network restrictions
  - No CPU/memory limits
  - No separation between instances
- **Impact:** A malicious `setup_fn` could read/write arbitrary files, make network requests, or consume unlimited resources.
- **Recommendation:** Document security assumptions clearly. Consider adding optional sandbox enforcement (e.g., using `subprocess` with restrictions, or integration with container runtimes).

### 8. [MEDIUM] No Tests for Security Scenarios
- **Issue:** The 7 existing tests all cover positive cases. No tests exist for:
  - Regex injection attacks
  - ReDoS scenarios
  - Exception handling in graders
  - Skipped ZeroTrustGrader behavior
  - Malicious custom_patterns
- **Recommendation:** Add security-focused test cases covering attack scenarios.

---

## Low Severity Findings

### 9. [LOW] Missing Security Documentation
- **Issue:** `docs/03-agent-skills-and-quality-gates-architecture.md` describes the architecture but lacks:
  - Threat model
  - Security assumptions
  - Input validation requirements
  - Known limitations
- **Recommendation:** Add a "Security Considerations" section to the documentation.

### 10. [LOW] json.dumps in has_retry_loop()
- **Issue:** `json.dumps(tc.arguments, sort_keys=True)` in `models.py:61` can fail on non-serializable objects with no error handling.
- **Recommendation:** Add try/except or use `default=str` parameter.

---

## Verification Status

| Check | Status |
|-------|--------|
| Default regex patterns compile | ✅ Pass |
| Default patterns ReDoS-safe | ✅ Pass |
| Custom patterns validated | ❌ Fail |
| Exception handling in graders | ❌ Fail |
| ZeroTrustGrader mandatory | ❌ Fail |
| Callable injection protected | ❌ Fail |
| Input sanitization | ❌ Fail |
| Sandbox isolation | ❌ Fail |
| Test coverage (security) | ❌ Fail |
| Existing tests pass | ✅ Pass (7/7) |
| Security tests (ReDoS) | ✅ Pass (5/6) |
| Security tests (exceptions) | ❌ Fail (1/6) |

---

## Test Results

### Existing Tests
```
7 passed in 0.03s
```
All existing positive-case tests pass.

### Security Tests
```
5 passed, 1 failed in 0.07s
```

**Confirmed Failure:** `TestExceptionHandler.test_grader_with_raising_check_fn`
- The test demonstrates that `ValueError` raised inside `tdd_assert_fn` propagates uncaught
- This confirms Finding #3 (Unhandled Exceptions) is a real, exploitable vulnerability

**Security Tests That Pass (confirming no ReDoS):**
- `test_malicious_redos_pattern_rejected` — ReDoS pattern completes within timeout
- `test_named_group_injection` — Named groups don't crash the system
- `test_pipeline_without_zero_trust_should_fail` — Test correctly identifies bypass bug
- `test_very_long_thought` — Large inputs handled without memory issues
- `test_all_graders_must_be_configured` — Pipeline doesn't crash with missing graders

---

## Recommendations Priority

1. **Immediate:** Add try/except around all user-provided callable invocations
2. **Immediate:** Make ZeroTrustGrader mandatory (cannot be silently skipped)
3. **Short-term:** Add regex pattern validation for custom_patterns
4. **Short-term:** Add input length limits on transcript data
5. **Medium-term:** Expand security test coverage
6. **Long-term:** Implement proper sandbox enforcement

---

## Gate Decision

**REJECTED** — The code fails zero-trust security requirements. Critical vulnerabilities undermine the stated security guarantees. Re-review required after fixes are implemented.

**Required Fixes:**
1. Add try/except around all user-provided callable invocations
2. Make ZeroTrustGrader mandatory (cannot be skipped)
3. Add regex pattern validation for custom_patterns
4. Add input length limits on transcript data
