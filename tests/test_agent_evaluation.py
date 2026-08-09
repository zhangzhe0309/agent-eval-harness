import random
from agent_eval.dataset import BenchmarkDataset
from agent_eval.evaluator import AgentEvaluator
from agent_eval.graders import (
    AntiRationalizationGrader,
    CodeGrader,
    CompositeGrader,
    LifecycleQualityGatePipeline,
    StateGrader,
    StepEfficiencyGrader,
    ToolCorrectnessGrader,
    ZeroTrustGrader,
)
from agent_eval.models import Step, Task, ToolCall, Transcript


def mock_successful_agent(task: Task, env) -> Transcript:
    """模拟成功、调工具正确、高效的 Agent 行为链条"""
    transcript = Transcript()
    transcript.steps.append(
        Step(
            step_number=1,
            thought="需要先查询订单 10086 的当前状态",
            tool_calls=[ToolCall(tool_name="query_order", arguments={"order_id": "10086"}, output={"status": "pending"})],
            observation={"status": "pending"},
        )
    )
    env._current_state["order_10086_status"] = "shipped"
    transcript.steps.append(
        Step(
            step_number=2,
            thought="修改订单状态为 shipped",
            tool_calls=[ToolCall(tool_name="update_order", arguments={"order_id": "10086", "status": "shipped"}, output={"success": True})],
            observation={"success": True},
        )
    )
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


def test_zero_trust_defense_grader(mock_task, memory_sandbox):
    """测试零信任防御性验证协议 Grader"""
    def tdd_probe_assert(task, transcript, env_state):
        if env_state.get("order_10086_status") != "shipped":
            return False, "TDD 探针防御失败: 数据库物理记录未更新为 shipped"
        return True, "TDD 探针物理验证通过"

    grader = ZeroTrustGrader(tdd_assert_fn=tdd_probe_assert)
    evaluator = AgentEvaluator(grader=grader, env=memory_sandbox)

    # 1. 成功案例
    trial1 = evaluator.run_trial(mock_task, mock_successful_agent)
    assert trial1.passed is True
    assert "[ZeroTrustVerified]" in trial1.reasons[0]

    # 2. 假设 Agent 生成了完美的自述 Markdown 报告，但数据库实际未改
    def agent_claiming_success_without_db_change(task, env):
        t = Transcript()
        t.steps.append(Step(step_number=1, thought="我已经在 Markdown 报告中宣称完成了任务！"))
        return t

    trial2 = evaluator.run_trial(mock_task, agent_claiming_success_without_db_change)
    assert trial2.passed is False
    assert "[ZeroTrustReject]" in trial2.reasons[0]


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
        for i in range(4):
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


def test_anti_rationalization_grader():
    """Test AntiRationalizationGrader with 3-factor composite check."""
    grader = AntiRationalizationGrader()
    task = Task(id="test", name="test", prompt="test")

    # 1. All 3 factors present: physical failure + interrupted chain + unfounded claim
    bad_transcript = Transcript()
    bad_transcript.steps.append(
        Step(
            step_number=1,
            thought="Task completed successfully despite errors",
            tool_calls=[ToolCall(tool_name="test_tool", is_error=True)],
            observation="error occurred"
        )
    )
    res_bad = grader.evaluate(task, bad_transcript, {"result": "fail"})  # physical failure
    assert res_bad.passed is False
    assert "Multi-factor detection" in res_bad.reason or "interrupted" in res_bad.reason.lower()

    # 2. Zero tool calls but claiming success (interrupted chain)
    empty_transcript = Transcript()
    empty_transcript.steps.append(
        Step(
            step_number=1,
            thought="Task completed successfully",
            tool_calls=[],
        )
    )
    res_empty = grader.evaluate(task, empty_transcript, {})
    assert res_empty.passed is False
    assert "zero tool calls" in res_empty.reason.lower() or "interrupted" in res_empty.reason.lower()

    # 3. Normal transcript with successful tool calls
    good_transcript = Transcript()
    good_transcript.steps.append(
        Step(
            step_number=1,
            thought="Executing database check",
            tool_calls=[ToolCall(tool_name="db_check", arguments={})],
            observation={"result": "ok"},
        )
    )
    res_good = grader.evaluate(task, good_transcript, {})
    assert res_good.passed is True


def test_anti_rationalization_decoupling_with_physical_verification():
    """测试物理断言优先与解耦机制（防止过度防御误杀正当用例）"""
    grader = AntiRationalizationGrader()
    task = Task(id="test", name="test", prompt="test")

    # 物理验证通过 + 有工具调用 + 无成功声明 → 应该通过
    excuse_transcript = Transcript()
    excuse_transcript.steps.append(
        Step(
            step_number=1,
            thought="The error is expected in this dry run.",
            tool_calls=[ToolCall(tool_name="dry_run", arguments={})],
        )
    )

    # 物理断言通过（env_state matches expected_state）
    res_decoupled = grader.evaluate(task, excuse_transcript, {"result": "success"})
    assert res_decoupled.passed is True
    # 应该返回全分，因为没有物理失败
    assert res_decoupled.score == 1.0
    assert "No anti-rationalization" in res_decoupled.reason


def test_anti_rationalization_allow_expected_errors():
    """测试负向/异常测试用例不触发误杀拦截"""
    grader = AntiRationalizationGrader()
    # 预期错误场景：物理失败 + 工具错误 + 无成功声明
    task = Task(id="test", name="test", prompt="test")

    negative_test_transcript = Transcript()
    negative_test_transcript.steps.append(
        Step(
            step_number=1,
            thought="The error is expected when testing 404 response.",
            tool_calls=[ToolCall(tool_name="test_api", is_error=True, arguments={})],
        )
    )

    # 物理失败 + 工具错误，但没有成功声明 → 只匹配2个因子，返回警告
    res = grader.evaluate(task, negative_test_transcript, {"result": "fail"})
    # 只匹配2个因子（physical_failure + interrupted_chain），应该返回警告而非硬失败
    assert res.passed is True
    assert res.score < 1.0, "Should have reduced score for partial match"
    assert "Partial match" in res.reason


def test_lifecycle_quality_gate_pipeline(mock_task, memory_sandbox):
    def tdd_probe_assert(task, transcript, env_state):
        if env_state.get("order_10086_status") != "shipped":
            return False, "Database state not updated"
        return True, "Verified"

    pipeline = LifecycleQualityGatePipeline(
        zero_trust_grader=ZeroTrustGrader(tdd_assert_fn=tdd_probe_assert),
        state_grader=StateGrader(expected_state={"order_10086_status": "shipped"}),
        anti_rationalization_grader=AntiRationalizationGrader(),
    )

    # 1. 成功全流程
    memory_sandbox.setup()
    state = memory_sandbox.get_state()
    state["order_10086_status"] = "shipped"
    state["email_sent"] = True
    memory_sandbox.get_state_fn = lambda: state

    good_transcript = Transcript()
    good_transcript.steps.append(
        Step(
            step_number=1,
            thought="Updating order status and sending email",
            tool_calls=[ToolCall(tool_name="update_order", arguments={"id": "10086"})],
        )
    )
    gate_res = pipeline.run_pipeline(mock_task, good_transcript, memory_sandbox.get_state())
    assert gate_res.all_passed is True
    assert "READY TO SHIP" in gate_res.summary

    # 2. 在 BUILD_VERIFY 阶段卡住的失败案例
    state_pending = dict(state)
    state_pending["order_10086_status"] = "pending"
    memory_sandbox.get_state_fn = lambda: state_pending
    failed_gate_res = pipeline.run_pipeline(mock_task, good_transcript, memory_sandbox.get_state())
    assert failed_gate_res.all_passed is False
    assert "BLOCKED" in failed_gate_res.summary
