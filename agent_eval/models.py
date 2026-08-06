import json
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """单次工具调用结构体"""
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[Any] = None
    is_error: bool = False
    error_message: Optional[str] = None
    duration_sec: float = 0.0


class Step(BaseModel):
    """Agent 执行链条中的单步 (Thought -> Action -> Observation)"""
    step_number: int
    thought: str = ""
    tool_calls: List[ToolCall] = Field(default_factory=list)
    observation: Optional[Any] = None
    is_error: bool = False
    duration_sec: float = 0.0


class Transcript(BaseModel):
    """Agent 完整执行轨迹日志与过程度量"""
    steps: List[Step] = Field(default_factory=list)

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def error_count(self) -> int:
        count = sum(1 for s in self.steps if s.is_error)
        for s in self.steps:
            count += sum(1 for tc in s.tool_calls if tc.is_error)
        return count

    @property
    def all_tool_calls(self) -> List[ToolCall]:
        calls = []
        for s in self.steps:
            calls.extend(s.tool_calls)
        return calls

    @property
    def tool_usage_summary(self) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for tc in self.all_tool_calls:
            summary[tc.tool_name] = summary.get(tc.tool_name, 0) + 1
        return summary

    def has_retry_loop(self, threshold: int = 3) -> bool:
        """检测是否存在连续重复调用相同的 工具名+参数 (死循环)"""
        last_signature = None
        repeat_count = 0
        for tc in self.all_tool_calls:
            sig = f"{tc.tool_name}:{json.dumps(tc.arguments, sort_keys=True)}"
            if sig == last_signature:
                repeat_count += 1
                if repeat_count >= threshold:
                    return True
            else:
                last_signature = sig
                repeat_count = 1
        return False


class Task(BaseModel):
    """工业级测试 Task 数据结构"""
    id: str
    name: str
    description: str = ""
    prompt: str
    expected_state: Optional[Dict[str, Any]] = None
    expected_tools: Optional[List[str]] = None
    max_allowed_steps: int = 10
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TrialResult(BaseModel):
    """单次 Trial 执行评估结果"""
    task_id: str
    trial_index: int
    passed: bool
    score: float = 0.0  # 0.0 - 1.0
    metrics: Dict[str, float] = Field(default_factory=dict)
    reasons: List[str] = Field(default_factory=list)
    transcript: Transcript = Field(default_factory=Transcript)
    execution_time_sec: float = 0.0


class EvaluationSummary(BaseModel):
    """任务多轮 Trial 可靠性与性能统计 (Pass^k / Pass@k)"""
    task_id: str
    k: int
    trials: List[TrialResult]
    pass_all: bool  # Pass^k (k 次全通过)
    pass_any: bool  # Pass@k (至少 1 次通过)
    success_rate: float
    avg_score: float
    avg_steps: float
    avg_error_count: float
    avg_duration_sec: float
    metrics_summary: Dict[str, float] = Field(default_factory=dict)
