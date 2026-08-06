import json
import time
from typing import Any, Callable, Dict, List, Optional
from agent_eval.environment import SandboxEnvironment
from agent_eval.graders import BaseGrader, GraderResult
from agent_eval.models import EvaluationSummary, Task, Transcript, TrialResult


class AgentEvaluator:
    """工业级 Agent 自动化评测执行引擎"""

    def __init__(self, grader: BaseGrader, env: SandboxEnvironment):
        self.grader = grader
        self.env = env

    def run_trial(
        self,
        task: Task,
        agent_runner_fn: Callable[[Task, SandboxEnvironment], Transcript],
        trial_index: int = 1,
    ) -> TrialResult:
        """运行单次 Trial 试验"""
        # 1. 环境 Setup & 状态重置
        self.env.setup()

        start_time = time.time()
        transcript = Transcript()
        grader_res = GraderResult(passed=False, score=0.0, reason="Execution failed", name="Init")

        try:
            # 2. 运行 Agent 执行链条
            transcript = agent_runner_fn(task, self.env)
            # 3. 收集物理环境终态
            final_env_state = self.env.get_state()
            # 4. 执行 Grader 评估
            grader_res = self.grader.evaluate(task, transcript, final_env_state)
        except Exception as e:
            grader_res = GraderResult(passed=False, score=0.0, reason=f"Runtime Exception: {str(e)}", name="RuntimeError")
        finally:
            # 5. 重置与清理沙箱
            self.env.reset()

        duration = round(time.time() - start_time, 3)

        # 收集过程指标
        metrics = {
            "total_steps": float(transcript.total_steps),
            "error_count": float(transcript.error_count),
            "tool_call_count": float(len(transcript.all_tool_calls)),
            "has_retry_loop": 1.0 if transcript.has_retry_loop() else 0.0,
        }

        return TrialResult(
            task_id=task.id,
            trial_index=trial_index,
            passed=grader_res.passed,
            score=grader_res.score,
            reasons=[grader_res.reason],
            transcript=transcript,
            execution_time_sec=duration,
            metrics=metrics,
        )

    def evaluate_task(
        self,
        task: Task,
        agent_runner_fn: Callable[[Task, SandboxEnvironment], Transcript],
        k: int = 5,
    ) -> EvaluationSummary:
        """评估单个 Task 连续 k 轮 Trial (Pass^k & Pass@k)"""
        trials: List[TrialResult] = []
        for i in range(1, k + 1):
            res = self.run_trial(task, agent_runner_fn, trial_index=i)
            trials.append(res)

        passes = [t.passed for t in trials]
        scores = [t.score for t in trials]
        steps = [t.transcript.total_steps for t in trials]
        durations = [t.execution_time_sec for t in trials]
        errors = [t.transcript.error_count for t in trials]

        pass_all = all(passes)
        pass_any = any(passes)
        success_rate = round(sum(passes) / k, 4)
        avg_score = round(sum(scores) / k, 4)
        avg_steps = round(sum(steps) / k, 2)
        avg_duration = round(sum(durations) / k, 3)
        avg_errors = round(sum(errors) / k, 2)

        metrics_summary = {
            "pass_all": 1.0 if pass_all else 0.0,
            "pass_any": 1.0 if pass_any else 0.0,
            "success_rate": success_rate,
            "avg_score": avg_score,
            "avg_steps": avg_steps,
            "avg_duration_sec": avg_duration,
        }

        return EvaluationSummary(
            task_id=task.id,
            k=k,
            trials=trials,
            pass_all=pass_all,
            pass_any=pass_any,
            success_rate=success_rate,
            avg_score=avg_score,
            avg_steps=avg_steps,
            avg_error_count=avg_errors,
            avg_duration_sec=avg_duration,
            metrics_summary=metrics_summary,
        )
