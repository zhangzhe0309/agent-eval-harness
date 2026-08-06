# 第02篇：Agent 自动化评测框架设计与落地 —— 架构解析、$Pass^k$ 可靠性度量与 Ship Gate 门禁

> **作者**：张喆 (Zhang Zhe) | 资深 QA 自动化架构师 & AI Agent 评测专家  
> **开源项目**：[agent-eval-harness](https://github.com/zhangzhe0309/agent-eval-harness)

---

## 一、 框架整体架构设计 (System Architecture)

`agent-eval-harness` 采用模块化、低耦合的分层架构设计，确保评测引擎能够灵活适配不同的 Agent 架构（如 ReAct、Plan-and-Solve、Multi-Agent 协作体系）及复杂的测试物理环境。

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Agent Evaluator (评测引擎)                      │
├────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐     ┌───────────────────┐     ┌──────────────────┐  │
│  │ Task Dataset │ ──> │ Sandbox Lifecycle │ ──> │ Agent Under Test │  │
│  └──────────────┘     └───────────────────┘     └──────────────────┘  │
│                                                          │             │
│                                                          ▼             │
│  ┌──────────────┐     ┌───────────────────┐     ┌──────────────────┐  │
│  │ Pass^k Stats │ <── │  Graders Engine   │ <── │ Transcript Trace │  │
│  └──────────────┘     └───────────────────┘     └──────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### 核心解耦模块划分：

1. **Task Model (测试用例数据模型)**：定义测试 Prompt、预期物理环境终态（Expected State）、元数据分类。
2. **Sandbox Lifecycle (沙箱生命周期控制器)**：托管 Setup、State Snapshot、Teardown/Reset 回滚逻辑。
3. **Transcript Trace Collector (执行轨迹收集器)**：实时捕获 Agent 执行过程中的 Thought、Action、Input、Observation 及 Error 状态。
4. **Graders Engine (断言判定引擎)**：支持 CodeGrader（代码硬断言）、StateGrader（状态键值断言）与 LLMJudgeGrader（大模型规则判定）。
5. **Evaluator & Reliability Statistics (可靠性统计引擎)**：驱动多轮 Trial 独立循环，计算 $Pass^k$ / $Pass@k$ 统计学分布。

---

## 二、 应对非确定性：$Pass^k$ 与 $Pass@k$ 可靠性度量模型

由于大模型 Sampling 温度（Temperature > 0）及环境调用的随机性，**Agent 跑通一次测试用例几乎没有任何统计学意义**（可能仅仅是运气好蒙对了路径）。

为了准确度量 Agent 系统在生产环境中的真正可靠性，评测框架引入了多轮 Trial 统计模型：

### 1. $Pass^k$ (All-Pass Reliability Metric)
- **定义**：针对同一个测试任务 $T$，独立重置环境并连续运行 $k$ 次 Trial。只有当 $k$ 次试验**全部通过**时，$Pass^k$ 才判定为 `True`。
- **数学公式**：
  $$Pass^k = \prod_{i=1}^{k} \mathbb{I}(\text{Trial}_i = \text{SUCCESS})$$
- **适用场景**：面向客户的严肃业务系统（如金融转账 Agent、数据库运维 Agent、医疗心理辅导 Agent）。要求系统具备高重复稳定性。

### 2. $Pass@k$ (Any-Pass Capability Metric)
- **定义**：在 $k$ 次独立的 Trial 中，只要有**至少 1 次**成功完成任务，$Pass@k$ 即判定为 `True`。
- **适用场景**：探索性生成场景（如代码生成、创意设计）。允许通过生成 $k$ 个 Candidate 供用户选择。

---

## 三、 判定器（Grader）选型矩阵与组合策略

在工程落地中，不能单一依赖某种断言方式，应根据任务特性组合使用不同类型的 Grader：

| Grader 类型 | 判定原理 | 优点 | 缺点 | 推荐应用场景 |
| :--- | :--- | :--- | :--- | :--- |
| **CodeGrader** | 执行 Python 代码/单元测试/SQL | 速度快、100% 确定性、零 Token 成本 | 编写成本高，缺乏对自然语言的弹性 | 数据库修改、文件处理、API 状态更新 |
| **StateGrader** | 校验环境物理 State 键值对 | 声明式配置，简单易用 | 仅限于结构化状态比较 | 容器配置、字段状态迁移��验 |
| **LLMJudgeGrader** | 依据预设 Rubric Prompt 由 LLM 评分 | 灵活性高，擅长开放式文本评估 | 存在判定漂移、成本高、需提前校准 | 客服服务态度、报告撰写质量 |

---

## 四、 工业级 CI/CD 四级 Ship Gate 发布门禁设计

为了防止 Agent 在 Prompt 微调、模型版本升级或工具更新时发生静默能力退化，建议在 CI/CD 流水线中构建**四级 Ship Gate 门禁体系**：

```
[PR 提交] ─> [L1 Syntax Gate] ─> [L2 Sanity Gate] ─> [L3 Reliability Gate] ─> [L4 Efficiency Gate] ─> [准予发布]
```

1. **L1 语法与契约门 (L1 Syntax & Schema Gate)**：
   - 静态校验 Prompt 模板参数匹配度、Tool JSON Schema 定义合法性。耗时 < 5s。
2. **L2 基础功能冒烟门 (L2 Sanity Regression Gate)**：
   - 选取 20 个确定性极高的核心 Task，单次跑通（$k=1$）。拦截严重的语法与接口中断问题。耗时 < 2min。
3. **L3 可靠性统计门 (L3 Reliability $Pass^k$ Gate)**：
   - 运行 100+ 标准 Task 集合，每个 Task 独立运行 $k=5$ 轮。要求总体 $Pass^5$ 达到目标阈值（如 $>85\%$），且无严重退化。
4. **L4 轨迹效率门 (L4 Trajectory & Efficiency Gate)**：
   - 解析 Transcript 轨迹，校验 Agent 平均调用步数（Average Steps）���工具报错率（Tool Error Rate）及 Token 消耗。拦截“通过率合格但步数死循环暴涨”的非健康代码。

---

## 五、 代码实战：运行 $Pass^k$ 可靠性评估

下面的代码展示了如何在 `agent-eval-harness` 中评估一个概率性失败 Agent 的 $Pass^k$ 表现：

```python
import random
from agent_eval import Task, SandboxEnvironment, StateGrader, AgentEvaluator, Transcript, Step

# 1. 定义任务与沙箱
task = Task(id="order_ship", name="订单发货", prompt="将订单 10086 发货", expected_state={"status": "shipped"})
sandbox = SandboxEnvironment(setup_fn=lambda: {"status": "pending"}, get_state_fn=None)

# 2. 模拟一个非稳定 Agent (70% 成功率)
def flaky_agent(task, env):
    transcript = Transcript()
    if random.random() < 0.7:
        env._current_state["status"] = "shipped" # 成功
        transcript.steps.append(Step(step_number=1, action="ship_order"))
    else:
        transcript.steps.append(Step(step_number=1, action="ship_order", is_error=True)) # 失败
    return transcript

# 3. 执行 Pass^5 可靠性评估
evaluator = AgentEvaluator(grader=StateGrader(), env=sandbox)
summary = evaluator.evaluate_task(task, flaky_agent, k=5)

print(f"Task ID: {summary.task_id}")
print(f"Pass^5 (连续5次全成功): {summary.pass_all}")
print(f"Pass@5 (5次中至少1次成功): {summary.pass_any}")
print(f"单次成功率: {summary.success_rate * 100}%")
```

下一篇中，我们将进入终极避坑实战：详细讲解如何解析 **Transcript 过程轨迹** 以及如何为 **LLM Judge 机制进行数学校准（Calibration）**。
