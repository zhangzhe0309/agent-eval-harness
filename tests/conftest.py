import pytest
from agent_eval.environment import SandboxEnvironment
from agent_eval.models import Task


@pytest.fixture
def mock_task():
    return Task(
        id="task_001",
        name="修改数据库订单状态",
        description="将订单 10086 的状态更改为 shipped",
        prompt="请将订单号为 10086 的状态更新为 shipped",
        expected_state={"order_10086_status": "shipped", "email_sent": True},
    )


@pytest.fixture
def memory_sandbox():
    db = {}

    def setup():
        db.clear()
        db["order_10086_status"] = "pending"
        db["email_sent"] = False
        return db

    def teardown(state):
        db.clear()

    def get_state():
        return dict(db)

    return SandboxEnvironment(setup_fn=setup, teardown_fn=teardown, get_state_fn=get_state)
