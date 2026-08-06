import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Step(BaseModel):
    """Agent 执行链条中的单步记录"""
    step_number: int
    thought: str = ""
    action: str = ""
    action_input: Any = None
    observation: Any = None
    is_error: bool = False
    duration_sec: float = 0.0


class Transcript(BaseModel):
    """Agent 一次任务执行的完整轨迹日志"""
    steps: List[Step] = Field(default_factory=list)

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def error_count(self) -> int:
        return sum(1 for s in self.steps if s.is_error)

    @property
    def tool_usage_summary(self) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for s in self.steps:
            if s.action:
                summary[s.action] = summary.get(s.action, 0) + 1
        return summary


class Task(BaseModel):
    """评测任务定义"""
    id: str
    name: str
    description: str
    prompt: str
    expected_state: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TrialResult(BaseModel):
    """单次试验结果"""
    task_id: str
    trial_index: int
    passed: bool
    score: float = 1.0 if True else 0.0
    reason: str = ""
    transcript: Transcript = Field(default_factory=Transcript)
    execution_time_sec: float = 0.0


class EvaluationSummary(BaseModel):
    """评估任务多轮汇总结果 (Pass^k / Pass@k)"""
    task_id: str
    k: int
    trials: List[TrialResult]
    pass_all: bool  # Pass^k (所有 k 次均成功)
    pass_any: bool  # Pass@k (至少 1 次成功)
    success_rate: float
    avg_steps: float
    avg_duration_sec: float
