import time
from typing import Any, Callable, Dict, List
from agent_eval.environment import SandboxEnvironment
from agent_eval.graders import BaseGrader
from agent_eval.models import EvaluationSummary, Task, Transcript, TrialResult


class AgentEvaluator:
    """Agent 评测执行器，控制沙箱生命周期、多轮 Trial 运行、断言判定与 Pass^k / Pass@k 计算"""

    def __init__(self, grader: BaseGrader, env: SandboxEnvironment):
        self.grader = grader
        self.env = env

    def run_trial(
        self,
        task: Task,
        agent_runner_fn: Callable[[Task, SandboxEnvironment], Transcript],
        trial_index: int = 1,
    ) -> TrialResult:
        """执行单轮 Trial 评测"""
        # 1. 环境 Setup & 状态重置
        self.env.setup()

        start_time = time.time()
        transcript = Transcript()
        reason = ""
        passed = False
        score = 0.0

        try:
            # 2. 运行 Agent 执行链条
            transcript = agent_runner_fn(task, self.env)
            # 3. 收集环境终态
            final_env_state = self.env.get_state()
            # 4. 执行 Grader 评估
            passed, score, reason = self.grader.evaluate(task, transcript, final_env_state)
        except Exception as e:
            passed = False
            score = 0.0
            reason = f"Execution runtime error: {str(e)}"
        finally:
            # 5. 清理与重置沙箱
            self.env.reset()

        duration = round(time.time() - start_time, 3)

        return TrialResult(
            task_id=task.id,
            trial_index=trial_index,
            passed=passed,
            score=score,
            reason=reason,
            transcript=transcript,
            execution_time_sec=duration,
        )

    def evaluate_task(
        self,
        task: Task,
        agent_runner_fn: Callable[[Task, SandboxEnvironment], Transcript],
        k: int = 5,
    ) -> EvaluationSummary:
        """针对 Task 运行 k 轮 Trial 评测，计算 Pass^k 与 Pass@k"""
        trials: List[TrialResult] = []
        for i in range(1, k + 1):
            res = self.run_trial(task, agent_runner_fn, trial_index=i)
            trials.append(res)

        passes = [t.passed for t in trials]
        pass_all = all(passes)
        pass_any = any(passes)
        success_rate = round(sum(passes) / k, 4)
        avg_steps = round(sum(t.transcript.total_steps for t in trials) / k, 2)
        avg_duration = round(sum(t.execution_time_sec for t in trials) / k, 3)

        return EvaluationSummary(
            task_id=task.id,
            k=k,
            trials=trials,
            pass_all=pass_all,
            pass_any=pass_any,
            success_rate=success_rate,
            avg_steps=avg_steps,
            avg_duration_sec=avg_duration,
        )
