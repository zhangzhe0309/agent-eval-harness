# 第01篇：从传统测开到 Agent 评测 —— 理念转变、环境硬断言与快速上手

> **作者**：张喆 (Zhang Zhe) | 资深 QA 自动化架构师 & AI Agent 评测专家  
> **开源项目**：[agent-eval-harness](https://github.com/zhangzhe0309/agent-eval-harness)

---

## 一、 引言：为什么传统自动化测试范式在 Agent 时代彻底失效？

在过去的十余年中，传统软件测试（接口测试、UI 自动化测试、E2E 流程测试）建立在**确定性（Determinism）**的基础之上：

$$\text{Input (固定参数 / 步骤)} \longrightarrow \text{System Under Test} \longrightarrow \text{Output (确定的 Response / DOM)} $$

在此范式下，QA 工程师编写的断言极其直接：
```python
# 传统 API 测试断言
assert response.status_code == 200
assert response.json()["data"]["order_status"] == "SHIPPED"
```

然而，当测试对象转换为 **AI Agent（智能体）** 时，这套逻辑遭遇���颠覆性的挑战：

1. **过程非确定性（Non-Deterministic Execution）**：给定相同的高层 Prompt（如“帮我清理 7 天前废弃的临时数据库记录”），Agent 每次执行选择的工具链、思考路线（Thought Chain）甚至重试路径都可能完全不同。
2. **文本吐出 ≠ 任务完成（Text Generation ≠ Task Accomplishment）**：大模型生成一段形如“我已经成功更新了订单状态”的回复，并不意味着其背后真正发起了 API 调用或执行了数据库 Write 操作（即所谓的“幻觉欺骗”）。
3. **路径多样性与无单一标准答案**：Agent 可以先查数据库再调用 API，也可以先调 API 校验再发 MQ 消息。任何试图匹配固定文本或硬编码步骤的传统断言都会导致大量误报（False Positives）。

---

## 二、 范式转变：基于环境终态的可执行断言 (Execution-based Assertions)

为了解决 Agent 测试难题，评测范式必须完成从**“校验输出文本（Text-Matching）”**到**“校验物理环境终态（Execution-based State Check）”**的根本性转变。

```
[Agent 收到 Prompt] ──> [自主规划与工具调用] ──> [修改外部物理环境 (数据库/文件/API)]
                                                          │
                                                          ▼
                                            [测试探针直接检查物理环境终态]
```

### 1. 三大高级环境断言体系

在 Agent 自动化测试中，QA 应建立以下三层硬断言能力：

- **物理状态硬断言 (Physical State Assertion)**：
  - 不看 Agent 说了什么，直接由测试探针连入真实的 PostgreSQL、Redis 或 Linux 文件系统，检查目标记录是否发生真实变更。
- **状态机迁移断言 (State Machine Transition Assertion)**：
  - 检查 Agent 的操作是否符合业务合法状态机。例如：订单状态只能由 `PENDING` $\rightarrow$ `PROCESSING` $\rightarrow$ `SHIPPED`，若 Agent 绕过中间态强行修改为 `SHIPPED`，断言应立刻拦截。
- **副作用隔离断言 (Side-effect Isolation Assertion)**：
  - 传统测试只看“目标改没改”，Agent 测试还必须校验“非目标资源是否被误伤”。检查目标订单更新的同时，校验同表其他 10000 条记录未被误删除。

---

## 三、 沙箱机制：构建隔离与可复原的测试环境

由于 Agent 具备真实的物理环境破坏力，所有的测试用例必须运行在完全隔离且可自动复原的**沙箱基础设施（Sandbox Infrastructure）**中：

- **Setup 阶段（环境恢复）**：每次测试前自动回滚数据库事务、���复 Docker 镜像快照或清空 Mock 容器状态，确保跑在干净的“起点”。
- **Teardown 阶段（环境清理）**：测试完成后强制销毁中间生成的临时文件、闭合 HTTP 连接、释放锁资源。

---

## 四、 `agent-eval-harness` 快速上手指南

`agent-eval-harness` 是一个开源的轻量级 Python + pytest 评测框架。下面展示如何从零编写一个包含沙箱与环境硬断言的完整测试用例。

### 1. 安装与环境准备

```bash
git clone https://github.com/zhangzhe0309/agent-eval-harness.git
cd agent-eval-harness
source venv/bin/activate
```

### 2. 编写测试用例实战

创建测试脚本 `demo_test.py`：

```python
from agent_eval import Task, SandboxEnvironment, CodeGrader, AgentEvaluator, Step, Transcript

# 1. 定义评测任务 (Task)
task = Task(
    id="task_db_clean",
    name="废弃记录清理",
    prompt="请清理数据库中 status 为 EXPIRED 的过期日志",
    expected_state={"expired_count": 0, "active_count": 100}
)

# 2. 配置沙箱环境钩子 (SandboxEnvironment)
db_mock = {}

def setup_db():
    db_mock["expired_count"] = 15
    db_mock["active_count"] = 100
    return dict(db_mock)

def get_db_state():
    return dict(db_mock)

def teardown_db(state):
    db_mock.clear()

sandbox = SandboxEnvironment(
    setup_fn=setup_db,
    teardown_fn=teardown_db,
    get_state_fn=get_db_state
)

# 3. 自定义 QA 环境硬断言 (CodeGrader)
def assert_db_clean(task, transcript, env_state):
    # 物理断言 1: 过期记录必须为 0
    if env_state.get("expired_count") != 0:
        return False, f"物理硬断言失败: 过期记录剩余 {env_state.get('expired_count')} 条"
    
    # 物理断言 2: 活跃记录不能被误删 (副作用隔离)
    if env_state.get("active_count") != 100:
        return False, f"副作用断言失败: 正常记录被误删，剩余 {env_state.get('active_count')} 条"
        
    return True, "环境硬断言与副作用断言完全通过"

grader = CodeGrader(check_fn=assert_db_clean)

# 4. 模拟 Agent 行为并运行测试
def my_mock_agent(task, env):
    transcript = Transcript()
    # Agent 步骤 1: 思考并执行清理工具
    env._current_state["expired_count"] = 0 # 改变沙箱物理状态
    transcript.steps.append(
        Step(
            step_number=1,
            thought="查询到 15 条 EXPIRED 记录，发起 delete 操作",
            action="delete_expired_logs",
            observation="Deleted 15 rows"
        )
    )
    return transcript

# 5. 执行评测并校验结果
evaluator = AgentEvaluator(grader=grader, env=sandbox)
trial = evaluator.run_trial(task, my_mock_agent)

print(f"测试通过: {trial.passed}")
print(f"断言结果: {trial.reason}")
```

### 3. CI/CD 流水线中运行

直接通过 pytest 命令行驱动批量测试：

```bash
PYTHONPATH=. venv/bin/pytest tests/test_agent_evaluation.py -v
```

下一篇中，我们将深入讲解框架的核心架构设计，以及如何针对 Agent 的随机性引入 **$Pass^k$ 可靠性计算模型**与 **CI/CD 四级 Ship Gate 发布门禁**。
