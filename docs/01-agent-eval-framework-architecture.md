# Agent 自动化评测框架设计与落地指南：基于环境状态校验与 Pass^k 可靠性评估

## 一、 背景与痛点：为什么 Agent 评测 ≠ 传统 LLM 评测

在传统的 LLM 单轮问答或文本生成评测中，评测范式是静态且简单的：**“给定 Prompt → 模型单次输出 → 与参考答案匹配（如 EM、F1、BLEU 或 Rouge）”**。

然而，当大模型进化为 **AI Agent（智能体）** 时，这种评测范式彻底失效了。Agent 具备了自主规划、多次工具调用、接收环境反馈以及根据报错进行自修复的能力。

Agent 评测面临三大根本差异：

1. **执行性与终态校验（Execution-based）**：Agent 的目标通常是修改外部世界（数据库、文件系统、API 状态）。同一个任务可能存在多种合法的操作路径，无法通过简单的字符串匹配衡量正确性，必须检查“环境终态是否满足预期”。
2. **非确定性与随机性**：大模型生成与工具调用的链路组合带来了极高的随机性。单次运行成功不代表系统可靠，必须进行多轮试验（Trials）评估统计分布。
3. **过程与��迹质量（Transcript Quality）**：Agent 可能会通过“蒙对”、“死循环重试”或“Reward Hacking（滥用工具）”来达到目的。评测不仅要关注“做成了没有”，还要关注“过程合不合理”。

---

## 二、 Agent 评测框架核心架构设计

为了解决上述问题，本项目（`agent-eval-harness`）设计了四大核心模块：

### 1. 沙箱环境模块 (Sandbox Environment)
- **职责**：负责测试环境的生命周期管理（Setup -> Execution -> State Collection -> Teardown/Reset）。
- **设计原则**：确保每次 Trial 均在干净、隔离的环境中运行，避免跨任务或跨试验之间的状态污染。

### 2. 判定器体系 (Graders)
- **代码级判定器 (CodeGrader)**：基于 Python 函数或断言进行硬校验，如数据库记录查询、单元测试运行。具有客观、快速、可重复的特点。
- **状态判定器 (StateGrader)**：检查环境终态键值对（Key-Value State）是否与预期目标严格对齐。
- **模型判定器 (LLMJudgeGrader)**：针对无标准答案或开放式交互任务，由预先校准过的 LLM 按照判定细则（Rubric）评分。

### 3. 轨迹记录器 (Transcript Tracker)
- 完整记录 Agent 执行链路中的 `Step`（思考 Thought、动作 Action、输入 Input、观察 Observation��报错 Is_Error）。
- 提供指标提取能力：统计总步数、错误数、工具使用频率及重试分布。

### 4. 评估控制器 (Agent Evaluator)
- 驱动试验循环，自动计算可靠性指标：
  - **Pass^k**：k 次 Trial 中**全部成功**才计为通过（用于高可靠性要求的生产系统）。
  - **Pass@k**：k 次 Trial 中**至少一次成功**即通过（用于探索性或代码生成类场景）。

---

## 三、 四级 Ship Gate 发布门禁设计

为了保证 Agent 在迭代升级（Prompt 修改、模型切换、工具更新）时不发生能力退化，建议在 CI/CD 中建立四级发布门禁：

1. **L1 语法与结构门 (L1 Syntax & Schema Gate)**：
   - 校验 Prompt 模板合法性、工具 Schema JSON 定义是否标准。
2. **L2 单元功能回归门 (L2 Sanity Regression Gate)**：
   - 选取 20 个具备确定性预期的小 Task，进行单次快速断言回归。
3. **L3 可靠性评估门 (L3 Reliability Gate)**：
   - 选取 100+ 覆盖核心业务的 Task，设置 k=5 进行 Pass^k / Pass@k 统计评估，要求 Pass^5 达到预设阈值（如 > 85%）。
4. **L4 轨迹与性能门 (L4 Transcript & Efficiency Gate)**：
   - 检查平均执行步数、平均耗时与工具报错率，拦截“通过率合格但效率严重下降/死循环增多”的版本。

---

## 四、 快速开始与示例代码

在项目中使用 `agent-eval-harness` 快速构建评测用例：

```python
from agent_eval import AgentEvaluator, SandboxEnvironment, StateGrader, Task

# 1. 定义评测任务
task = Task(
    id="task_order_update",
    name="订单状态更新",
    prompt="请将订单 10086 标记为 shipped",
    expected_state={"order_10086_status": "shipped", "email_sent": True}
)

# 2. 准备沙箱与 Grader
env = SandboxEnvironment(setup_fn=my_setup_db, teardown_fn=my_reset_db)
grader = StateGrader()
evaluator = AgentEvaluator(grader=grader, env=env)

# 3. 运行 5 轮 Reliability 评估 (Pass^5)
summary = evaluator.evaluate_task(task, my_agent_runner, k=5)

print(f"Task Pass^5 All: {summary.pass_all}")
print(f"Success Rate: {summary.success_rate * 100}%")
print(f"Average Steps: {summary.avg_steps}")
```
