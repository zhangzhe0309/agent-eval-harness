import random
from agent_eval.evaluator import AgentEvaluator
from agent_eval.graders import CodeGrader, StateGrader
from agent_eval.models import Step, Task, Transcript


def mock_successful_agent(task: Task, env) -> Transcript:
    """模拟成功的 Agent 行为链条"""
    transcript = Transcript()
    # 步骤 1: 思考并调用查询接口
    transcript.steps.append(
        Step(
            step_number=1,
            thought="需要先查询订单 10086 的当前状态",
            action="query_order",
            action_input={"order_id": "10086"},
            observation={"status": "pending"},
        )
    )
    # 步骤 2: 修改订单状态
    env._current_state["order_10086_status"] = "shipped"
    transcript.steps.append(
        Step(
            step_number=2,
            thought="订单状态为 pending，调用 update_order 接口修改为 shipped",
            action="update_order",
            action_input={"order_id": "10086", "status": "shipped"},
            observation={"success": True},
        )
    )
    # 步骤 3: 发送通知邮件
    env._current_state["email_sent"] = True
    transcript.steps.append(
        Step(
            step_number=3,
            thought="订单更新成功，发送确认邮件",
            action="send_email",
            action_input={"to": "user@example.com", "subject": "Shipped"},
            observation={"sent": True},
        )
    )
    return transcript


def mock_flaky_agent(task: Task, env) -> Transcript:
    """模拟概率性失败的 Agent（模拟随机性）"""
    transcript = Transcript()
    if random.random() > 0.3:  # 70% 概率成功
        env._current_state["order_10086_status"] = "shipped"
        env._current_state["email_sent"] = True
        transcript.steps.append(Step(step_number=1, action="update_order"))
    else:  # 30% 概率出错并遗漏步骤
        env._current_state["order_10086_status"] = "pending"
        transcript.steps.append(Step(step_number=1, action="update_order", is_error=True))
    return transcript


def test_state_grader_success(mock_task, memory_sandbox):
    """测试基于环境终态校验的 StateGrader（单次通过）"""
    grader = StateGrader()
    evaluator = AgentEvaluator(grader=grader, env=memory_sandbox)

    trial = evaluator.run_trial(mock_task, mock_successful_agent)
    assert trial.passed is True
    assert trial.score == 1.0
    assert trial.transcript.total_steps == 3
    assert trial.transcript.error_count == 0


def test_pass_k_reliability_evaluation(mock_task, memory_sandbox):
    """测试多轮 Trial (Pass^k vs Pass@k) 可靠性度量"""
    grader = StateGrader()
    evaluator = AgentEvaluator(grader=grader, env=memory_sandbox)

    # 固定随机种子测试概率 agent
    random.seed(42)
    summary = evaluator.evaluate_task(mock_task, mock_flaky_agent, k=5)

    assert summary.k == 5
    assert isinstance(summary.pass_all, bool)
    assert isinstance(summary.pass_any, bool)
    assert 0.0 <= summary.success_rate <= 1.0


def test_code_grader_custom_assertion(mock_task, memory_sandbox):
    """测试基于自定义 Python 逻辑的 CodeGrader"""

    def custom_check(task, transcript, env_state):
        if env_state.get("email_sent") is not True:
            return False, "Email notification was not dispatched"
        if transcript.total_steps > 5:
            return False, "Agent used too many unnecessary steps"
        return True, "All requirements met"

    grader = CodeGrader(check_fn=custom_check)
    evaluator = AgentEvaluator(grader=grader, env=memory_sandbox)

    trial = evaluator.run_trial(mock_task, mock_successful_agent)
    assert trial.passed is True
    assert "All requirements met" in trial.reason
