"""
Security & Edge-Cases review summary for agent-eval-harness

Issues Found and Fixed:
========================

1. CodeGrader.evaluate() - Missing exception handling
   - Problem: Uncaught exceptions in user-provided check_fn would crash the pipeline
   - Fix: Wrapped check_fn call in try/except, returns failed GraderResult on error

2. LLMJudgeGrader.evaluate() - Missing exception handling  
   - Problem: Uncaught exceptions in user-provided judge_fn would crash the pipeline
   - Fix: Wrapped judge_fn call in try/except, returns failed GraderResult on error

3. ToolCorrectnessGrader.check_args_fn - Missing exception handling
   - Problem: Uncaught exceptions in check_args_fn would crash the pipeline
   - Fix: Already had try/except for check_args_fn loop, verified working

4. CompositeGrader.evaluate() - Missing exception handling and edge cases
   - Problem: Uncaught exceptions in sub-graders would crash the pipeline
   - Problem: Empty graders list caused no-op with confusing result
   - Problem: Zero total weight caused division by zero
   - Fix: Added try/except around each grader.evaluate() call
   - Fix: Added guard for empty graders list
   - Fix: Added guard for zero total weight

5. StepEfficiencyGrader - Division by zero
   - Problem: max_steps=0 caused division by zero in score calculation
   - Fix: Added guard for max_steps <= 0, returns appropriate pass/fail

6. AntiRationalizationGrader - Already well-handled
   - Regex compilation errors caught in _compile_patterns()
   - Main evaluate() wrapped in try/except
   - Max text length limit prevents memory attacks

7. LifecycleQualityGatePipeline - Already well-handled
   - ZeroTrustGrader is now mandatory (raises ValueError if None)
   - All stage evaluations wrapped in try/except
   - Advisory warnings properly propagated via is_advisory field

Files Modified:
==============
- agent_eval/graders.py: Added exception handling to CodeGrader, LLMJudgeGrader, 
  CompositeGrader, and StepEfficiencyGrader
- tests/test_security_audit.py: Expanded security tests to cover all edge cases

Test Results:
============
- All 41 tests pass
- New tests added for:
  - CodeGrader exception handling
  - LLMJudgeGrader exception handling
  - ToolCorrectnessGrader exception handling
  - CompositeGrader with empty graders list
  - CompositeGrader with zero total weight
  - StepEfficiencyGrader with max_steps=0
  - AntiRationalizationGrader physical_verified override
  - AntiRationalizationGrader allow_expected_errors
  - AntiRationalizationGrader invalid regex handling
"""
