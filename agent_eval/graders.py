from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Tuple
from agent_eval.models import Task, Transcript


class BaseGrader(ABC):
    @abstractmethod
    def evaluate(self, task: Task, transcript: Transcript, env_state: Any) -> Tuple[bool, float, str]:
        """
        评估函数
        返回: (passed: bool, score: float, reason: str)
        """
        pass


class CodeGrader(BaseGrader):
    """基于自定义 Python 断言逻辑的判重器"""

    def __init__(self, check_fn: Callable[[Task, Transcript, Any], Tuple[bool, str]]):
        self.check_fn = check_fn

    def evaluate(self, task: Task, transcript: Transcript, env_state: Any) -> Tuple[bool, float, str]:
        passed, reason = self.check_fn(task, transcript, env_state)
        return passed, (1.0 if passed else 0.0), reason


class StateGrader(BaseGrader):
    """基于环境物理终态/键值校验的判定器"""

    def __init__(self, expected_key_values: Optional[Dict[str, Any]] = None):
        self.expected_key_values = expected_key_values or {}

    def evaluate(self, task: Task, transcript: Transcript, env_state: Any) -> Tuple[bool, float, str]:
        expected = task.expected_state or self.expected_key_values
        if not expected:
            return True, 1.0, "No expected state specified, default pass"

        if not isinstance(env_state, dict):
            return False, 0.0, f"Environment state is not dict, got {type(env_state)}"

        for k, v in expected.items():
            if k not in env_state:
                return False, 0.0, f"Missing key '{k}' in env state"
            if env_state[k] != v:
                return False, 0.0, f"State key '{k}' mismatched: expected {v}, got {env_state[k]}"

        return True, 1.0, "State assertion passed successfully"


class LLMJudgeGrader(BaseGrader):
    """LLM 裁判判定器框架（可对接 OpenAI/Gemini/Local LLM）"""

    def __init__(self, rubric: str, judge_fn: Optional[Callable[[str, Transcript], Tuple[bool, float, str]]] = None):
        self.rubric = rubric
        self.judge_fn = judge_fn

    def evaluate(self, task: Task, transcript: Transcript, env_state: Any) -> Tuple[bool, float, str]:
        if self.judge_fn:
            return self.judge_fn(self.rubric, transcript)
        # 默认 Mock 规则判断（若无真实 LLM 句柄）
        if transcript.error_count == 0:
            return True, 1.0, "[LLM Judge] Agent followed rubric and completed task without errors."
        else:
            return False, 0.0, f"[LLM Judge] Agent incurred {transcript.error_count} error(s) during execution."
