# Agent 自动化评测指南（上篇）：从传统测开转型、环境硬断言与 Pass^k 架构实战

> **开源项目**：[agent-eval-harness](https://github.com/zhangzhe0309/agent-eval-harness)

---

## 一、 引言：为什么传统自动化测试范式在 Agent 时代彻底失效？

在过去的十余年中，传统软件测试（接口自动化、UI 自动化、E2E 流程测试）建立在**确定性（Determinism）**的基础之上：

$$\text{Input (固定参数 / 步骤)} \longrightarrow \text{System Under Test} \longrightarrow \text{Output (确定的 Response / DOM)} $$

但在 AI Agent 时代，测试对象拥有了自主规划与多步工具调用的能力，带来了三大颠覆性挑战：

1. **过程非确定性（Non-Deterministic Execution）**：给定相同的高层 Prompt，Agent 每次执行选择的工具链、思考路线甚至重试路径都可能完全不同。
2. **文本吐出 ≠ 任务完成（Text Generation ≠ Task Accomplishment）**：大模型生成一段形如“已经成功更新了订单状态”的回复，并不意味着其背后真正发起了 API 调用或数据库 Write 操作（即所谓的“幻觉欺骗”）。
3. **无单一标准答案**：Agent 可以有多种合法的探索路径，任何试图匹配固定文本或硬编码步骤的传统断言都会导致大量误报。

---

## 二、 范式转变：基于环境终态的可执行断言 (Execution-based Assertions)

为了解决上述问题，评测范式必须完成从**“校验输出文本（Text-Matching）”**到**“校验物理环境终态（Execution-based State Check）”**的根本性转变。

```
[Agent 收到 Prompt] ──> [自主规划与工具调用] ──> [修改外部物理环境 (数据库/文件/API)]
                                                          │
                                                          ▼
                                            [测试探针直接检查物理环境终态]
```

### 1. 三大高级环境断言体系

- **物理状态硬断言 (Physical State Assertion)**：
  - 不看 Agent 说了什么，直接由测试探针连入真实的 PostgreSQL、Redis 或 Linux 文件系统，检查目标记录是否发生真实变更。
- **状态机迁移断言 (State Machine Transition Assertion)**：
  - 检查 Agent 的操作是否符合业务合法状态机。例如：订单状态只能由 `PENDING` $\rightarrow$ `PROCESSING` $\rightarrow$ `SHIPPED`，若 Agent 绕过中间态强行修改，断言应立刻拦截。
- **副作用隔离断言 (Side-effect Isolation Assertion)**：
  - 校验“非目标资源是否被误伤”。检查目标订单更新的同时，校验同表其他记录未被误删除。

### 2. 沙箱隔离机制

由于 Agent 具备真实的物理环境破坏力，所有的测试用例必须运行在完全隔离且可自动复原的**沙箱基础设施（Sandbox Infrastructure）**中：
- **Setup 阶段**：测试前自动回滚数据库事务、恢复 Docker 镜像快照或清空 Mock 状态。
- **Teardown 阶段**：测试完成后强制销毁中间生成的临时文件、闭合 HTTP 连接。

---

## 三、 评测框架分层架构设计与 $Pass^k$ 数学模型

`agent-eval-harness` 采用模块化、低耦合的分层架构设计：

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Agent Evaluator (评测引擎)                      │
├────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐     ┌───────────────────┐     ┌──────────────────┐  │
│  │ Task Dataset │ ──> │ Sandbox Lifecycle │ ──> │ Agent Under Test │  │
│  └──────────────┘     └───────────────────┘     └───────────────────┘  │
│                                                          │             │
│                                                          ▼             │
│  ┌──────────────┐     ┌───────────────────┐     ┌──────────────────┐  │
│  │ Pass^k Stats │ <── │  Graders Engine   │ <── │ Transcript Trace │  │
│  └──────────────┘     └───────────────────┘     └──────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### 1. 应对非确定性：$Pass^k$ 与 $Pass@k$ 可靠性模型

由于大模型 Sampling 温度（Temperature > 0）及环境调用的随机性，**Agent 跑通一次测试用例没有任何统计学意义**。框架引入了多轮 Trial 统计模型：

- **$Pass^k$ (All-Pass Reliability Metric)**：
  针对同一个测试任务 $T$，独立重置环境并连续运行 $k$ 次 Trial。只有当 $k$ 次试验**全部通过**时，$Pass^k$ 才判定为 `True`。
  $$Pass^k = \prod_{i=1}^{k} \mathbb{I}(\text{Trial}_i = \text{SUCCESS})$$
  适用于金融、数据库运维、医疗心理辅导等高可靠要求场景。
- **$Pass@k$ (Any-Pass Capability Metric)**：
  在 $k$ 次独立的 Trial 中，只要有**至少 1 次**成功完成任务即判定为 `True`。适用于代码生成与创意设计等探索性场景。

### 2. CI/CD 四级 Ship Gate 发布门禁

```
[PR 提交] ─> [L1 Syntax Gate] ─> [L2 Sanity Gate] ─> [L3 Reliability Gate] ─> [L4 Efficiency Gate] ─> [准予发布]
```

1. **L1 Syntax Gate**：静态校验 Prompt 模板与 Tool JSON Schema 定义。耗时 < 5s。
2. **L2 Sanity Gate**：20 个核心 Task 单次冒烟（$k=1$）。拦截严重接口中断。耗时 < 2min。
3. **L3 Reliability Gate**：100+ Task 集合独立运行 $k=5$ 轮，要求总体 $Pass^5 > 85\%$。
4. **L4 Efficiency Gate**：校验平均调用步数、工具报错率及 Token 消耗，拦截性能死循环退化。

---

## 四、 快速上手代码实战

```python
from agent_eval import Task, SandboxEnvironment, CodeGrader, AgentEvaluator, Step, Transcript

# 1. 定义任务
task = Task(id="task_001", name="废弃记录清理", prompt="清理 EXPIRED 记录", expected_state={"expired_count": 0})

# 2. 配置沙箱
db_mock = {"expired_count": 15, "active_count": 100}
sandbox = SandboxEnvironment(setup_fn=lambda: dict(db_mock), get_state_fn=lambda: dict(db_mock))

# 3. 编写环境硬断言
def assert_db_clean(task, transcript, env_state):
    if env_state.get("expired_count") != 0:
        return False, "物理硬断言失败: 过期记录未清理"
    return True, "断言完全通过"

# 4. 执行 Pass^5 可靠性评估
evaluator = AgentEvaluator(grader=CodeGrader(check_fn=assert_db_clean), env=sandbox)
summary = evaluator.evaluate_task(task, my_mock_agent, k=5)

print(f"Pass^5 全成功: {summary.pass_all}")
print(f"成功率: {summary.success_rate * 100}%")
```
