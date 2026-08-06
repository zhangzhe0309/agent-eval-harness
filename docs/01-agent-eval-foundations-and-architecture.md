# Agent 自动化评测指南（上篇）：从传统测开转型、环境硬断言与 Pass^k 架构实战

---

## 一、 Agent 使用方案与业务落地场景：Agent 到底在干什么？

在讨论如何评测 Agent 之前，必须首先厘清：**现在的 AI Agent 在企业业务中究竟是如何落地的？它和传统 LLM 聊天工具有何本质不同？**

在企业真实场景中，Agent 已经从单纯的“自然语言对话”演变为**具备自主规划与外部世界修改能力的自动化智能体**：

```
[用户 Prompt/业务事件] ──> [LLM 思考规划 Thought] ──> [选择并调用工具 Action] ──> [环境返回结果 Observation]
        ▲                                                                           │
        └──────────────────────────── (循环直至目标完成) ────────────────────────────┘
```

### 常见的 4 类 Agent 落地方案与能力边界：

1. **SQL 与数据库变更 Agent**：
   - **能做的事**：接收用户自然语言需求（如“帮助整理上周逾期 7 天的用户并冻结账号”），生成 SQL、校验权限、直接连入数据库执行 Write/Update 操作。
2. **自动化运维与 DevOps Agent**：
   - **能做的事**：监听到线上 CPU 告警，自动登录 Linux VPS、读取日志、定位异常进程并执行重启或 Pod 扩容。
3. **电商与客服退换货 Agent**：
   - **能做的事**：自动查询订单 API、比对物流状态、调用支付接口发起退款并向用户发送通知邮件。
4. **代码修复与工程 Agent**：
   - **能做的事**：读取 Git Issue，在本地沙箱中克隆代码、定位 Bug、修改文件、运行单测并提交 PR。

---

## 二、 Agent 系统落地的“四大固有失效模式（Failure Modes）”

在实际落地上述 Agent 方案时，系统架构师与测试工程师会发现，Agent 系统本身存在以下**四大固有失效模式（Failure Modes）**：

### 失效模式一：“嘴上说成功，暗地里没动”（幻觉欺骗与未执行）
- **产生原因**：大模型的文本生成与真实工具执行是解耦的。Agent 遇到了 API 调用抛错或无权限，但 LLM 产生了幻觉，生成了一段完美文本：“已成功更新了订单状态”，欺骗了上层系统或用户。
- **质量挑战**：仅仅检查 Agent 吐出的文本或 HTTP 状态码无法判断实际业务是否真的执行成功。

### 失效模式二：“过程弯弯绕，每次都不一样”（非确定性执行）
- **产生原因**：LLM 采样随机性（Temperature > 0）与 Agent 的 Reasoning 规划属性。处理同一个需求，第一次可能调 2 个工具完成，第二次可能绕了弯路调用 5 个工具并在中间重试 2 次。
- **质量挑战**：传统自动化测试中硬编码固定操作步骤（`Step 1 -> Step 2 -> Step 3`）的断言模式全盘失效。

### 失效模式三：“目标达到了，副作用毁所有”（隐蔽破坏力）
- **产生原因**：Agent 具备对数据库、文件系统、集群的物理修改权限，但生成的操作指令（如 SQL/Shell）作用域缺乏精确约束。例如成功修改了订单 `#10086`，但 SQL 少写了 `WHERE` 前缀，顺手抹掉了同表其他 500 条记录。
- **质量挑战**：如果测试探针仅仅检查目标数据字段，将完全无法察觉非目标资源被破坏的隐蔽事故。

### 失效模式四：“单次跑通不代表上线安全”（概率成功假象）
- **产生原因**：LLM 决策路径的概率分布特性。在开发或单次测试时偶然“打中了成功路径”，并不代表系统稳定。在生产环境面对多样化输入时，系统可能暴露出 30% 以上的失败率。
- **质量挑战**：传统测试“跑通一次用例即可判定 Pass”的准则在 Agent 场景下失去有效性。

---

## 三、 为什么传统测试方法失效？对应代码与算法解法

正因为 Agent 系统存在上述四大固有失效模式，传统接口测试（Postman/pytest 接口断言）与 UI 测试（Playwright DOM 校验）才会在 Agent 测试中全面失效。

针对 Agent 的固有缺陷，`agent-eval-harness` 引入了**多维组合判定器 (CompositeGrader) 与 $Pass^k$ 统计算法**：

```
【失效模式一 & 失效模式三】 ──────> 【解法一：物理环境终态校验 (StateGrader) + 工具链参数断言 (ToolCorrectnessGrader)】
【失效模式二 & 失效模式四】 ──────> 【解法二：步骤效率/死循环阻断 (StepEfficiencyGrader) + Pass^k 可靠性模型】
```

---

## 四、 解法一：多维判定体系 (Grader Matrix) 与沙箱隔离

为了解决**失效模式一（幻觉欺骗）**与**失效模式三（副作用破坏）**，评测框架提供了四大断言组件：

1. **状态断言 (StateGrader)**：测试探针连入物理存储（数据库/文件），校验数据变更与副作用隔离。
2. **工具正确性断言 (ToolCorrectnessGrader)**：校验 Agent 调用的工具序列是否包含必需工具，且参数 JSON 格式与逻辑正确。
3. **效率与死循环断言 (StepEfficiencyGrader)**：校验总步数是否超出上限，自动识别连续重复调用的死循环逻辑。
4. **组合判定器 (CompositeGrader)**：支持多维度 Grader 加权融合打分（如 50% 物理状态 + 30% 工具正确性 + 20% 步骤效率）。

### 沙箱隔离机制 (Sandbox Lifecycle)
每次测试运行在独立的沙箱中：
- **Setup 阶段**：测试前回滚 DB 事务、重置 Mock 状态，确保干净起跑线。
- **Teardown 阶段**：测试后强制销毁垃圾数据与连接，防止用例污染。

---

## 五、 解法二：$Pass^k$ 数学算法与 CI/CD 门禁

为了解决**失效模式二（过程弯弯绕）**与**失效模式四（概率成功假象）**，我们必须引入 $Pass^k$ 统计学模型。

### 1. $Pass^k$ 算法数学原理

单次测试通过没有意义。在独立沙箱中将同一个任务连续运行 $k$ 次 Trial，只有当 $k$ 次试验**全部成功**时，$Pass^k$ 才判定为 `True`：

$$Pass^k = \prod_{i=1}^{k} \mathbb{I}(\text{Trial}_i = \text{SUCCESS})$$

- 若单次成功率为 $70\%$，在 $k=5$ 时：
  $$Pass^5 = 0.7^5 \approx 16.8\%$$
  真实的系统不稳定风险会被指数级放大并暴露出来！

### 2. CI/CD 四级 Ship Gate 发布门禁

```
[PR 提交] ─> [L1 Syntax Gate] ─> [L2 Sanity Gate] ─> [L3 Reliability Pass^5 Gate] ─> [L4 Efficiency Gate] ─> [发布]
```

1. **L1 Syntax Gate**：静态校验 Prompt 模板与 Tool JSON Schema 定义。
2. **L2 Sanity Gate**：20 个核心 Task 单次冒烟（$k=1$）。
3. **L3 Reliability Gate**：100+ Task 集合独立运行 $k=5$ 轮，要求总体 $Pass^5 > 85\%$。
4. **L4 Efficiency Gate**：校验平均步数与工具报错率，拦截耗时死循环退化。

---

## 六、 工业级 Python 评测代码实战

`agent-eval-harness` 框架如何通过组合判定器与沙箱进行测试：

```python
from agent_eval import (
    Task, SandboxEnvironment, CompositeGrader, StateGrader,
    ToolCorrectnessGrader, StepEfficiencyGrader, AgentEvaluator,
    Step, ToolCall, Transcript
)

# 1. 定义测试 Task
task = Task(
    id="task_order_ship",
    name="订单发货处理",
    prompt="请处理订单 10086 的发货并发送通知",
    expected_state={"order_10086_status": "shipped", "email_sent": True},
    expected_tools=["query_order", "update_order", "send_email"],
    max_allowed_steps=5
)

# 2. 配置测试沙箱
db_mock = {}
def setup_env():
    db_mock.clear()
    db_mock["order_10086_status"] = "pending"
    db_mock["email_sent"] = False
    return dict(db_mock)

sandbox = SandboxEnvironment(setup_fn=setup_env, get_state_fn=lambda: dict(db_mock))

# 3. 构造 CompositeGrader 加权组合断言
composite_grader = CompositeGrader(
    graders=[
        (StateGrader(), 0.5),                                                         # 50% 权重：物理状态断言
        (ToolCorrectnessGrader(expected_tools=["query_order", "update_order"]), 0.3),  # 30% 权重：工具序列与参数断言
        (StepEfficiencyGrader(max_steps=5), 0.2)                                      # 20% 权重：步骤效率与死循环熔断
    ]
)

# 4. 执行 Pass^5 可靠性统计评估
evaluator = AgentEvaluator(grader=composite_grader, env=sandbox)
summary = evaluator.evaluate_task(task, my_agent_runner, k=5)

print(f"Task ID: {summary.task_id}")
print(f"Pass^5 全成功率: {summary.pass_all}")
print(f"单次平均成功率: {summary.success_rate * 100}%")
print(f"综合平均得分: {summary.avg_score}")
print(f"平均消耗步数: {summary.avg_steps}")
```
