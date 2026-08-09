from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple
from agent_eval.models import Task, Transcript
from pydantic import BaseModel


class GraderResult(BaseModel):
    passed: bool
    score: float
    reason: str
    name: str = "BaseGrader"
    is_trusted: bool = True
    is_advisory_warning: bool = False


class BaseGrader(ABC):
    @abstractmethod
    def evaluate(self, task: Task, transcript: Transcript, env_state: Any) -> GraderResult:
        pass


class ZeroTrustGrader(BaseGrader):
    def __init__(
        self,
        tdd_assert_fn: Callable[[Task, Transcript, Any], Tuple[bool, str]],
        strict_reject_text_claims: bool = True,
    ):
        self.tdd_assert_fn = tdd_assert_fn
        self.strict_reject_text_claims = strict_reject_text_claims

    def evaluate(self, task: Task, transcript: Transcript, env_state: Any) -> GraderResult:
        try:
            passed, reason = self.tdd_assert_fn(task, transcript, env_state)
        except Exception as e:
            return GraderResult(
                passed=False,
                score=0.0,
                reason=f"[ZeroTrustReject] Probe exception raised: {type(e).__name__}: {e}",
                name="ZeroTrustGrader",
                is_trusted=True,
            )

        if not passed:
            return GraderResult(
                passed=False,
                score=0.0,
                reason=f"[ZeroTrustReject] Independent probe verification failed: {reason}",
                name="ZeroTrustGrader",
                is_trusted=True,
            )

        return GraderResult(
            passed=True,
            score=1.0,
            reason=f"[ZeroTrustVerified] Deliverable passed independent TDD verification: {reason}",
            name="ZeroTrustGrader",
            is_trusted=True,
        )


class CodeGrader(BaseGrader):
    def __init__(self, check_fn: Callable[[Task, Transcript, Any], Tuple[bool, str]]):
        self.check_fn = check_fn

    def evaluate(self, task: Task, transcript: Transcript, env_state: Any) -> GraderResult:
        passed, reason = self.check_fn(task, transcript, env_state)
        return GraderResult(passed=passed, score=1.0 if passed else 0.0, reason=reason, name="CodeGrader")


class StateGrader(BaseGrader):
    def __init__(self, expected_state: Optional[Dict[str, Any]] = None, strict_side_effect: bool = True):
        self.expected_state = expected_state
        self.strict_side_effect = strict_side_effect

    def evaluate(self, task: Task, transcript: Transcript, env_state: Any) -> GraderResult:
        expected = self.expected_state or task.expected_state
        if not expected:
            return GraderResult(passed=True, score=1.0, reason="[StateGrader] No expected state specified", name="StateGrader")

        if not isinstance(env_state, dict):
            return GraderResult(passed=False, score=0.0, reason=f"[StateGrader] Env state is not dict, got {type(env_state)}", name="StateGrader")

        mismatches = []
        for k, expected_v in expected.items():
            if k not in env_state:
                mismatches.append(f"Missing key '{k}'")
            elif env_state[k] != expected_v:
                mismatches.append(f"Key '{k}' expected {expected_v}, got {env_state[k]}")

        if mismatches:
            return GraderResult(passed=False, score=0.0, reason=f"[StateGrader] Failed: {', '.join(mismatches)}", name="StateGrader")

        return GraderResult(passed=True, score=1.0, reason="[StateGrader] State assertion and side-effect check passed", name="StateGrader")


class ToolCorrectnessGrader(BaseGrader):
    def __init__(self, expected_tools: Optional[List[str]] = None, check_args_fn: Optional[Callable[[str, Dict[str, Any]], Tuple[bool, str]]] = None):
        self.expected_tools = expected_tools
        self.check_args_fn = check_args_fn

    def evaluate(self, task: Task, transcript: Transcript, env_state: Any) -> GraderResult:
        expected = self.expected_tools or task.expected_tools
        actual_tool_names = [tc.tool_name for tc in transcript.all_tool_calls]

        if expected:
            missing_tools = [t for t in expected if t not in actual_tool_names]
            if missing_tools:
                return GraderResult(passed=False, score=0.0, reason=f"[ToolGrader] Agent missed expected tools: {missing_tools}", name="ToolCorrectnessGrader")

        if self.check_args_fn:
            for tc in transcript.all_tool_calls:
                ok, reason = self.check_args_fn(tc.tool_name, tc.arguments)
                if not ok:
                    return GraderResult(passed=False, score=0.0, reason=f"[ToolGrader] Argument error on '{tc.tool_name}': {reason}", name="ToolCorrectnessGrader")

        return GraderResult(passed=True, score=1.0, reason=f"[ToolGrader] Called {len(actual_tool_names)} tool(s) correctly", name="ToolCorrectnessGrader")


class StepEfficiencyGrader(BaseGrader):
    def __init__(self, max_steps: Optional[int] = None, allow_loop: bool = False):
        self.max_steps = max_steps
        self.allow_loop = allow_loop

    def evaluate(self, task: Task, transcript: Transcript, env_state: Any) -> GraderResult:
        max_allowed = self.max_steps or task.max_allowed_steps

        if not self.allow_loop and transcript.has_retry_loop(threshold=3):
            return GraderResult(passed=False, score=0.0, reason="[EfficiencyGrader] Detected infinite retry loop (repeated identical tool call >= 3 times)", name="StepEfficiencyGrader")

        if transcript.total_steps > max_allowed:
            return GraderResult(passed=False, score=0.0, reason=f"[EfficiencyGrader] Step count ({transcript.total_steps}) exceeded max allowed ({max_allowed})", name="StepEfficiencyGrader")

        score = max(0.0, 1.0 - (transcript.total_steps / (max_allowed * 2)))
        return GraderResult(passed=True, score=round(score, 2), reason=f"[EfficiencyGrader] Total steps: {transcript.total_steps} (Within budget)", name="StepEfficiencyGrader")


class LLMJudgeGrader(BaseGrader):
    def __init__(self, rubric: str, judge_fn: Optional[Callable[[Task, Transcript], Tuple[bool, float, str]]] = None):
        self.rubric = rubric
        self.judge_fn = judge_fn

    def evaluate(self, task: Task, transcript: Transcript, env_state: Any) -> GraderResult:
        if self.judge_fn:
            passed, score, reason = self.judge_fn(task, transcript)
            return GraderResult(passed=passed, score=score, reason=f"[LLM Judge] {reason}", name="LLMJudgeGrader")

        if transcript.error_count == 0:
            return GraderResult(passed=True, score=1.0, reason="[LLM Judge] Agent satisfied rubric without step errors", name="LLMJudgeGrader")
        else:
            return GraderResult(passed=False, score=0.0, reason=f"[LLM Judge] Agent incurred {transcript.error_count} step error(s)", name="LLMJudgeGrader")


class CompositeGrader(BaseGrader):
    def __init__(self, graders: List[Tuple[BaseGrader, float]]):
        self.graders = graders

    def evaluate(self, task: Task, transcript: Transcript, env_state: Any) -> GraderResult:
        total_weight = sum(w for _, w in self.graders)
        weighted_score = 0.0
        reasons = []
        all_passed = True

        for grader, weight in self.graders:
            res = grader.evaluate(task, transcript, env_state)
            weighted_score += res.score * (weight / total_weight)
            reasons.append(f"{res.name}: {res.reason}")
            if not res.passed:
                all_passed = False

        final_score = round(weighted_score, 4)
        return GraderResult(passed=all_passed, score=final_score, reason=" | ".join(reasons), name="CompositeGrader")


class AntiRationalizationGrader(BaseGrader):
    """
    三因子复合反合理化判定器 (3-Factor Composite Anti-Rationalization Grader)：
    避免单因子过度防御导致的误杀问题 (False Positives)。

    三因子复合规则：
    1. Factor 1 (物理失败/未达成): physical_verified is False 或 env_state 表示失败/未匹配
    2. Factor 2 (工具链中断/异常/未调工具): error tool_calls, zero tool_calls, missing tools
    3. Factor 3 (无凭口头声明): 包含 completed successfully / 任务完成 / 已成功 等无凭据硬吹嘘模式

    判定：
    - 三因子均触发 -> 确认欺骗与开脱，硬阻断 (passed=False, score=0.0)
    - 部分触��� (如仅包含言语说明) -> 降级为 Advisory Warning (passed=True, score=0.85 或 1.0, is_advisory_warning=True)
    - 未触发 -> 校验通过 (passed=True, score=1.0)
    """

    DEFAULT_RATIONALIZATION_PATTERNS = [
        r"(?:this|the) error is (?:expected|acceptable|minor|normal)",
        r"(?:skip|ignoring) (?:this|the) (?:test|failure|error)",
        r"no need to (?:fix|address|worry)",
        r"(?:functioning|working) as intended despite",
        r"视为成功",
        r"忽略此报错",
        r"无需修复",
        r"符合预期报错",
    ]

    UNFOUNDED_CLAIM_PATTERNS = [
        r"completed successfully",
        r"successfully (?:fixed|resolved|updated|completed)",
        r"我已经在.*宣称完成了任务",
        r"已成功",
        r"任务完成",
    ]

    def __init__(
        self,
        custom_patterns: Optional[List[str]] = None,
        require_tool_calls_for_success: bool = True,
        allow_expected_errors: bool = False,
        max_text_length: int = 10000,
    ):
        self.patterns = self.DEFAULT_RATIONALIZATION_PATTERNS + (custom_patterns or [])
        self.require_tool_calls_for_success = require_tool_calls_for_success
        self.allow_expected_errors = allow_expected_errors
        self.max_text_length = max_text_length

    def evaluate(self, task: Task, transcript: Transcript, env_state: Any, physical_verified: Optional[bool] = None) -> GraderResult:
        import re

        is_expected_error_task = self.allow_expected_errors or getattr(task, "allow_expected_errors", False) or (task.metadata and task.metadata.get("allow_expected_errors"))

        # Factor 1: Physical Failure
        f1_physical_failure = False
        if physical_verified is False:
            f1_physical_failure = True
        elif physical_verified is True:
            f1_physical_failure = False
        else:
            if isinstance(env_state, dict):
                if env_state.get("result") in ["fail", "error"] or env_state.get("status") in ["fail", "error"]:
                    f1_physical_failure = True
                elif task.expected_state:
                    for k, expected_v in task.expected_state.items():
                        if k not in env_state or env_state[k] != expected_v:
                            f1_physical_failure = True
                            break

        # Factor 2: Interrupted Chain / Tool Issues
        f2_interrupted_chain = False
        if self.require_tool_calls_for_success and len(transcript.all_tool_calls) == 0 and not is_expected_error_task:
            f2_interrupted_chain = True
        elif any(getattr(tc, "is_error", False) for tc in transcript.all_tool_calls):
            f2_interrupted_chain = True
        elif any(getattr(s, "is_error", False) for s in transcript.steps):
            f2_interrupted_chain = True

        # Factor 3: Unfounded Oral Claim vs Verbal Rationalization Excuse
        f3_oral_claim = False
        f3_verbal_excuse = False
        found_reasons = []

        if not is_expected_error_task:
            if len(transcript.all_tool_calls) == 0 and self.require_tool_calls_for_success:
                f3_oral_claim = True
                found_reasons.append("Zero tool calls produced while claiming task completion")

            all_text = " ".join([f"{step.thought} {step.observation}" for step in transcript.steps])
            if len(all_text) > self.max_text_length:
                all_text = all_text[:self.max_text_length]

            for pattern in self.UNFOUNDED_CLAIM_PATTERNS:
                if "(a+)+b" in pattern:
                    continue
                try:
                    if re.search(pattern, all_text, re.IGNORECASE):
                        f3_oral_claim = True
                        found_reasons.append(f"Matched claim '{pattern}'")
                        break
                except re.error:
                    continue

            for pattern in self.patterns:
                if "(a+)+b" in pattern:
                    continue
                try:
                    if re.search(pattern, all_text, re.IGNORECASE):
                        f3_verbal_excuse = True
                        found_reasons.append(f"Matched excuse '{pattern}'")
                        break
                except re.error:
                    continue

        # Zero tool calls with claim -> Multi-factor detection failure
        if len(transcript.all_tool_calls) == 0 and self.require_tool_calls_for_success and not is_expected_error_task:
            return GraderResult(
                passed=False,
                score=0.0,
                reason="[AntiRationalizationReject] Multi-factor detection triggered (Physical failure + Interrupted chain + Unfounded claim): Agent produced zero tool calls but claimed completion",
                name="AntiRationalizationGrader",
                is_trusted=True,
            )

        # Physical Verified Success (TDD probe passed)
        if physical_verified is True or (isinstance(env_state, dict) and env_state.get("result") == "success"):
            return GraderResult(
                passed=True,
                score=1.0,
                reason="[AntiRationalization] No anti-rationalization patterns detected across all factors",
                name="AntiRationalizationGrader",
                is_trusted=True,
            )

        # Multi-factor decision: Only hard fail if physical failure + interrupted chain + unfounded oral claim
        if f1_physical_failure and f2_interrupted_chain and f3_oral_claim:
            return GraderResult(
                passed=False,
                score=0.0,
                reason=f"[AntiRationalizationReject] Multi-factor detection triggered (Physical failure + Interrupted chain + Unfounded claim): {'; '.join(found_reasons)}",
                name="AntiRationalizationGrader",
                is_trusted=True,
            )

        # Partial match -> Advisory Warning (Prevent False Positives)
        has_any_flag = f1_physical_failure or f2_interrupted_chain or f3_oral_claim or f3_verbal_excuse
        if has_any_flag:
            return GraderResult(
                passed=True,
                score=0.85 if (f3_oral_claim or f1_physical_failure) else 1.0,
                reason=f"[AntiRationalizationAdvisory] Partial factor match (Partial match advisory warning): {'; '.join(found_reasons) if found_reasons else 'Partial match'}",
                name="AntiRationalizationGrader",
                is_trusted=True,
                is_advisory_warning=True if (f3_oral_claim or f1_physical_failure) else False,
            )

        return GraderResult(
            passed=True,
            score=1.0,
            reason="[AntiRationalization] No anti-rationalization patterns detected across all factors",
            name="AntiRationalizationGrader",
            is_trusted=True,
        )


class LifecycleStageResult(BaseModel):
    stage_name: str
    passed: bool
    details: str
    is_advisory: bool = False


class LifecycleGateResult(BaseModel):
    all_passed: bool
    stages: List[LifecycleStageResult]
    summary: str


class LifecycleQualityGatePipeline:
    def __init__(
        self,
        zero_trust_grader: Optional[ZeroTrustGrader] = None,
        state_grader: Optional[StateGrader] = None,
        efficiency_grader: Optional[StepEfficiencyGrader] = None,
        anti_rationalization_grader: Optional[AntiRationalizationGrader] = None,
    ):
        if zero_trust_grader is None:
            raise ValueError(
                "[LifecyclePipeline] ZeroTrustGrader is mandatory. "
                "Cannot bypass physical verification in zero-trust architecture."
            )
        self.zero_trust_grader = zero_trust_grader
        self.state_grader = state_grader
        self.efficiency_grader = efficiency_grader or StepEfficiencyGrader(max_steps=10)
        self.anti_rationalization_grader = anti_rationalization_grader or AntiRationalizationGrader()

    def run_pipeline(self, task: Task, transcript: Transcript, env_state: Any) -> LifecycleGateResult:
        stages: List[LifecycleStageResult] = []

        # Stage 1: DEFINE & PLAN (Tool / Step Efficiency Check)
        eff_res = self.efficiency_grader.evaluate(task, transcript, env_state)
        stages.append(
            LifecycleStageResult(
                stage_name="DEFINE_PLAN",
                passed=eff_res.passed,
                details=eff_res.reason,
            )
        )

        # Stage 2: BUILD & VERIFY (Zero-Trust Physical Probe)
        zt_res = self.zero_trust_grader.evaluate(task, transcript, env_state)
        physical_passed = zt_res.passed
        stages.append(
            LifecycleStageResult(
                stage_name="BUILD_VERIFY",
                passed=zt_res.passed,
                details=zt_res.reason,
            )
        )

        # Stage 3: REVIEW & SHIP (Anti-Rationalization + Final State Check)
        ar_res = self.anti_rationalization_grader.evaluate(
            task, transcript, env_state, physical_verified=physical_passed
        )
        state_pass = True
        state_details = "State check skipped"
        if self.state_grader:
            st_res = self.state_grader.evaluate(task, transcript, env_state)
            state_pass = st_res.passed
            state_details = st_res.reason

        review_passed = ar_res.passed and state_pass
        stages.append(
            LifecycleStageResult(
                stage_name="REVIEW_SHIP",
                passed=review_passed,
                details=f"AntiRationalization: {ar_res.reason} | State: {state_details}",
                is_advisory=ar_res.is_advisory_warning,
            )
        )

        all_passed = all(s.passed for s in stages)
        summary = "All lifecycle quality gates PASSED [READY TO SHIP]" if all_passed else "Lifecycle quality gates FAILED [BLOCKED]"

        return LifecycleGateResult(all_passed=all_passed, stages=stages, summary=summary)
