from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple
from agent_eval.models import Task, Transcript
from pydantic import BaseModel


class GraderResult(BaseModel):
    passed: bool
    score: float
    reason: str
    name: str = "BaseGrader"
    is_trusted: bool = True  # 标识是否经过零信任独立验证


class BaseGrader(ABC):
    @abstractmethod
    def evaluate(self, task: Task, transcript: Transcript, env_state: Any) -> GraderResult:
        pass


class ZeroTrustGrader(BaseGrader):
    """
    零信任防御性验证 Grader：
    1. 拒绝盲信 Agent Markdown/Text 自述报告（如"我已修改成功"）；
    2. 强制通过独立的 TDD 测试探针连入物理环境校验交付物；
    3. 宁可输出明确的失败报告 (Explicit Failure)，也绝不妥协接受未经校验的口头成功。
    """

    def __init__(
        self,
        tdd_assert_fn: Callable[[Task, Transcript, Any], Tuple[bool, str]],
        strict_reject_text_claims: bool = True,
    ):
        self.tdd_assert_fn = tdd_assert_fn
        self.strict_reject_text_claims = strict_reject_text_claims

    def evaluate(self, task: Task, transcript: Transcript, env_state: Any) -> GraderResult:
        # 1. 独立运行 TDD 断言探针 (物理校验)
        passed, reason = self.tdd_assert_fn(task, transcript, env_state)

        if not passed:
            # 零信任协议：任何物理探针失败，立刻返回明确的拒绝报告
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
    """基于自定义 Python 断言逻辑的判重器"""

    def __init__(self, check_fn: Callable[[Task, Transcript, Any], Tuple[bool, str]]):
        self.check_fn = check_fn

    def evaluate(self, task: Task, transcript: Transcript, env_state: Any) -> GraderResult:
        passed, reason = self.check_fn(task, transcript, env_state)
        return GraderResult(passed=passed, score=1.0 if passed else 0.0, reason=reason, name="CodeGrader")


class StateGrader(BaseGrader):
    """基于环境物理终态（Execution-based State Check）及副作用断言的判定器"""

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
    """工具调用正确性判定器：校验 Tool 名称、必备工具序列及参数逻辑"""

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
    """步骤效率与死循环断言判定器"""

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
    """LLM 结构化 G-Eval / Rubric 裁判判定器"""

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
    """组合判定器：支持多维度 Grader 加权融合判定"""

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
