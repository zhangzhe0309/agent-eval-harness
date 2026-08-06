# Agent 自动化评测指南（上篇）：从传统测开转型、零信任防御协议与 Pass^k 架构实战

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

## 三、 零信任多 Agent 协作哲学与防御性验证协议 (Zero-Trust Protocol)

针对上述四大失效模式，业界顶尖团队（如 Anthropic、Inspect、Zero-Trust Protocol）总结出核心防御哲学：

```
[拒绝盲信 Agent 自述] ──> [TDD 测试驱动预定义边界] ──> [独立沙箱探针硬校验] ──> [牺牲 3-10x Token 换绝对可靠]
```

### 1. 拒绝盲信 Agent 自述报告 (Refuse Blind Trust in Self-Report)
- **核心准则**：任何被测 Agent 输出的 Markdown 报告、自然语言总结（如“我已经成功修复了该 Bug”）一律视作**未验证凭证（Untrusted Claim）**。绝不能根据 Agent 的口头汇报判定测试通过。

### 2. 测试驱动（TDD）预先定义边界 (TDD Boundary Specification)
- **核心准则**：在被测 Agent 启动前，测试团队或 Orchestrator 必须先编写好独立的可执行单测与边界契约（Input/Output Schemas、SQL/API 状态探针）。要求 Agent 以“使独立单测 PASS”为唯一目标。

### 3. 强制独立测试关卡 (Mandatory Independent Verification Gates)
- **核心准则**：测试探针与沙箱环境必须与被测 Agent 完全解耦。测试关卡独立连入数据库/文件系统进行物理校验，拒绝“Agent 自调工具、自查数据、自评通过”的包饺子假象。

### 4. 3-10 倍 Token 交换法则 (Token Trade-off for Reliability)
- **核心准则**：为了达到生产级高可靠性，主动接受**消耗 3-10 倍 Token** 的代价（用于多轮 Trial 独立抽样、多模型交叉审计、独立探针校验与轨迹比对）。
- **终极目标**：宁可输出明确的失败报告 (Explicit Failure Report)，也绝不容忍模糊带病过关！

---

## 四、 框架解法：多维判定体系 (Grader Matrix) 与沙箱隔离

`agent-eval-harness` 提供了支持零信任协议的四大断言组件：

1. **零信任防御判定器 (ZeroTrustGrader)**：强制执行独立的 TDD 物理探针校验，拦截任何未经过验证的口头自述。
2. **状态断言 (StateGrader)**：测试探针连入物理存储（数据库/文件），校验数据变更与副作用隔离。
3. **工具正确性断言 (ToolCorrectnessGrader)**：校验 Agent 调用的工具序列是否包含必需工具，且参数 JSON 格式与逻辑正确。
4. **步骤效率与死循环断言 (StepEfficiencyGrader)**：校验总步数是否超出上限，自动识别连续重复调用的死循环逻辑。
5. **组合判定器 (CompositeGrader)**：支持多维度 Grader 加权融合打分（如 50% 零信任物理状态 + 30% 工具正确性 + 20% 步骤效率）。

---

## 五、 $Pass^k$ 数学算法与 CI/CD 门禁

为了解决非确定性与概率成功假象，框架引入 $Pass^k$ 统计学模型：

$$Pass^k = \prod_{i=1}^{k} \mathbb{I}(\text{Trial}_i = \text{SUCCESS})$$

- 若单次成功率为 $70\%$，在独立沙箱中进行 $k=5$ 轮评估：
  $$Pass^5 = 0.7^5 \approx 16.8\%$$
  牺牲多轮 Token 开销，将系统潜在不稳定风险暴露无遗。

### CI/CD 四级 Ship Gate 发布门禁

```
[PR 提交] ─> [L1 Syntax Gate] ─> [L2 Sanity Gate] ─> [L3 Reliability Pass^5 Gate] ─> [L4 Efficiency Gate] ─> [发布]
```

---

## 六、 工业级 Python 评测代码实战

```python
from agent_eval import (
    Task, SandboxEnvironment, CompositeGrader, ZeroTrustGrader,
    StateGrader, ToolCorrectnessGrader, StepEfficiencyGrader, AgentEvaluator,
    Step, ToolCall, Transcript
)

# 1. 定义测试 Task (针对零信任发货场景)
task = Task(
    id="task_order_ship",
    name="订单发货处理",
    prompt="请处理订单 10086 的发货并发送通知",
    expected_state={"order_10086_status": "shipped", "email_sent": True},
    expected_tools=["query_order", "update_order", "send_email"],
    max_allowed_steps=5
)

# 2. 配置独立测试沙箱
db_mock = {}
def setup_env():
    db_mock.clear()
    db_mock["order_10086_status"] = "pending"
    db_mock["email_sent"] = False
    return dict(db_mock)

sandbox = SandboxEnvironment(setup_fn=setup_env, get_state_fn=lambda: dict(db_mock))

# 3. 定义 TDD 零信任物理探针
def tdd_probe_assert(task, transcript, env_state):
    if env_state.get("order_10086_status") != "shipped":
        return False, "TDD 探针失败: 数据库订单状态未更改为 shipped"
    if env_state.get("email_sent") is not True:
        return False, "TDD 探针失败: 确认邮件未发出"
    return True, "物理环境探针全量校验通过"

# 4. 构造 CompositeGrader 零信任防御组合断言
composite_grader = CompositeGrader(
    graders=[
        (ZeroTrustGrader(tdd_assert_fn=tdd_probe_assert), 0.5),                        # 50% 零信任探针
        (ToolCorrectnessGrader(expected_tools=["query_order", "update_order"]), 0.3),  # 30% 工具正确性
        (StepEfficiencyGrader(max_steps=5), 0.2)                                      # 20% 步骤效率
    ]
)

# 5. 执行 Pass^5 独立多轮评估
evaluator = AgentEvaluator(grader=composite_grader, env=sandbox)
summary = evaluator.evaluate_task(task, my_agent_runner, k=5)

print(f"Pass^5 全成功率: {summary.pass_all}")
print(f"单次平均成功率: {summary.success_rate * 100}%")
print(f"综合平均得分: {summary.avg_score}")
print(f"平均消耗步数: {summary.avg_steps}")
```
