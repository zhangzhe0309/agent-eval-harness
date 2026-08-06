import random
from agent_eval.dataset import BenchmarkDataset
from agent_eval.evaluator import AgentEvaluator
from agent_eval.graders import (
    CodeGrader,
    CompositeGrader,
    StateGrader,
    StepEfficiencyGrader,
    ToolCorrectnessGrader,
)
from agent_eval.models import Step, Task, ToolCall, Transcript


def mock_successful_agent(task: Task, env) -> Transcript:
    """模拟成功、调工具正确、高效的 Agent 行为链条"""
    transcript = Transcript()
    # Step 1: 查询
    transcript.steps.append(
        Step(
            step_number=1,
            thought="需要先查询订单 10086 的当前状态",
            tool_calls=[ToolCall(tool_name="query_order", arguments={"order_id": "10086"}, output={"status": "pending"})],
            observation={"status": "pending"},
        )
    )
    # Step 2: 改变物理状态
    env._current_state["order_10086_status"] = "shipped"
    transcript.steps.append(
        Step(
            step_number=2,
            thought="修改订单状态为 shipped",
            tool_calls=[ToolCall(tool_name="update_order", arguments={"order_id": "10086", "status": "shipped"}, output={"success": True})],
            observation={"success": True},
        )
    )
    # Step 3: 发送邮件
    env._current_state["email_sent"] = True
    transcript.steps.append(
        Step(
            step_number=3,
            thought="发送发货确认邮件",
            tool_calls=[ToolCall(tool_name="send_email", arguments={"to": "user@example.com", "subject": "Shipped"}, output={"sent": True})],
            observation={"sent": True},
        )
    )
    return transcript


def mock_flaky_agent(task: Task, env) -> Transcript:
    """模拟概率性失败的 Agent"""
    transcript = Transcript()
    if random.random() > 0.3:  # 70% 成功率
        env._current_state["order_10086_status"] = "shipped"
        env._current_state["email_sent"] = True
        transcript.steps.append(
            Step(step_number=1, tool_calls=[ToolCall(tool_name="update_order", arguments={"order_id": "10086"})])
        )
    else:  # 30% 失败率
        env._current_state["order_10086_status"] = "pending"
        transcript.steps.append(
            Step(step_number=1, is_error=True, tool_calls=[ToolCall(tool_name="update_order", is_error=True)])
        )
    return transcript


def test_composite_grader_and_evaluator(mock_task, memory_sandbox):
    """测试加权组合判定器与评测引擎"""
    composite = CompositeGrader(
        graders=[
            (StateGrader(), 0.5),
            (ToolCorrectnessGrader(expected_tools=["query_order", "update_order"]), 0.3),
            (StepEfficiencyGrader(max_steps=5), 0.2),
        ]
    )

    evaluator = AgentEvaluator(grader=composite, env=memory_sandbox)
    trial = evaluator.run_trial(mock_task, mock_successful_agent)

    assert trial.passed is True
    assert trial.score > 0.8
    assert trial.transcript.total_steps == 3
    assert trial.transcript.error_count == 0


def test_pass_k_statistical_evaluation(mock_task, memory_sandbox):
    """测试多轮 Pass^k 与 Pass@k 可靠性计算模型"""
    grader = StateGrader()
    evaluator = AgentEvaluator(grader=grader, env=memory_sandbox)

    random.seed(42)
    summary = evaluator.evaluate_task(mock_task, mock_flaky_agent, k=5)

    assert summary.k == 5
    assert isinstance(summary.pass_all, bool)
    assert isinstance(summary.pass_any, bool)
    assert 0.0 <= summary.success_rate <= 1.0
    assert summary.avg_steps > 0


def test_step_efficiency_loop_detection(mock_task, memory_sandbox):
    """测试死循环（重复调用相同工具参数）检测能力"""
    def looping_agent(task, env):
        transcript = Transcript()
        for i in range(4):  # 连续重复调用 4 次
            transcript.steps.append(
                Step(step_number=i+1, tool_calls=[ToolCall(tool_name="retry_api", arguments={"param": "1"})])
            )
        return transcript

    grader = StepEfficiencyGrader()
    evaluator = AgentEvaluator(grader=grader, env=memory_sandbox)

    trial = evaluator.run_trial(mock_task, looping_agent)
    assert trial.passed is False
    assert "infinite retry loop" in trial.reasons[0]


def test_benchmark_dataset_loader(tmp_path):
    """测试 Task 测试集 JSON 加载"""
    dataset_file = tmp_path / "test_benchmark.json"
    dataset_file.write_text(
        '[{"id": "t1", "name": "Task 1", "prompt": "Prompt 1", "metadata": {"category": "devops"}}]'
    )

    dataset = BenchmarkDataset.from_json_file(str(dataset_file))
    assert len(dataset) == 1
    assert dataset[0].id == "t1"
    assert len(dataset.filter_by_metadata("category", "devops")) == 1
