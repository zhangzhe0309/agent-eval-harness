# Agent 自动化评测指南（上篇）：从传统测开转型、环境硬断言与 Pass^k 架构实战

---

## 一、 Agent 使用方案与业务落地场景：Agent 到底在干什么？

在讨论如何评测 Agent 之前，QA 必须首先厘清：**现在的 AI Agent 在企业业务中究竟是如何落地的？它和传统 LLM 聊天工具有何本质不同？**

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

## 二、 传统 QA 进场后的“四大噩梦”：为什么传统测试直接翻车？

当传统测开工程师拿接口测试（pytest/Postman）或 UI 自动化（Playwright/Selenium）的经验去测 Agent 时，会立刻陷入以下四大噩梦：

### 噩梦一：“嘴上说成功，暗地里没动”（幻觉与欺骗）
- **现象**：Agent 输出了完美自然语言：“我已经成功帮您清空了过期用户的数据”。但 QA 连入数据库一查，数据原封不动，后台日志显示 Agent 在第二步调用 Tool API 时就已经抛出了 HTTP 500 错误。
- **痛点**：传统测试断言 `assert "成功" in response.text` 彻底失效。

### 噩梦二：“过程弯弯绕，每次都不一样”（非确定性执行）
- **现象**：测试同一个“修改订单”功能，第一次跑 Agent 调了 2 个 Tool 直接完成；第二次跑 Agent 在工具选择上绕了弯路，调用了 5 次 Tool 并在中间重试了 2 次；第三次跑 Agent 甚至选了完全不同的 API 组合。
- **痛点**：传统测试固定的 `Step 1 -> Step 2 -> Step 3` 硬编码断言路线完全崩溃。

### 噩梦三：“目标达到了，副作用毁所有”（隐蔽破坏力）
- **现象**：Agent 成功将订单 `#10086` 的状态修改为了 `SHIPPED`，但因为生成的 SQL 语句少写了一个 `WHERE` 条件前缀，导致同表前 500 条记录的状态都被误刷成了 `SHIPPED`。
- **痛点**：传统测试只校验目标字段，忽略了对外部环境整体“副作用”的防护。

### 噩梦四：“单次跑通不代表上线安全”（概率成功假象）
- **现象**：QA 在本地手动运行了一次测试，Agent 顺利完成了任务，于是批准上线。上线后在生产环境面对真实流量，失败率高达 30%。
- **痛点**：LLM 采样温度（Temperature > 0）导致单次测试成功仅仅是偶然“打中了成功概率分支”。

---

## 三、 代码与算法为了解决什么问题？

正是为了解决上述四大噩梦，我们才必须设计**针对 Agent 特性的测试代码框架与 $Pass^k$ 数学算法**。

```
【噩梦一 & 噩梦三】 ──────> 【解法一：基于物理环境的硬断言与沙箱机制 (Execution-based & Sandbox)】
【噩梦二 & 噩梦四】 ──────> 【解法二：解决非确定性的 Pass^k 数学模型 (Reliability Evaluation)】
```

---

## 四、 解法一：编写可执行的环境硬断言与沙箱机制

为了解决**噩梦一（幻觉欺骗）**与**噩梦三（副作用破坏）**，测试框架摒弃了文本比对，引入了三类硬断言：

1. **物理状态硬断言 (Physical State Assertion)**：
   - 不看 Agent 说了什么，由测试探针直接连入真实数据库或文件系统，校验数据记录。
2. **状态机迁移断言 (State Machine Transition Assertion)**：
   - 校验 Agent 的操作是否符合业务合法状态机（如 `PENDING` $\rightarrow$ `PROCESSING` $\rightarrow$ `SHIPPED`），防止越级非法修改。
3. **副作用隔离断言 (Side-effect Isolation Assertion)**：
   - 检查目标记录变更的同时，校验同表非目标记录未被误删除或误修改。

### 沙箱隔离机制 (Sandbox Lifecycle)
每次测试运行在独立的沙箱中：
- **Setup 阶段**：测试前回滚 DB 事务、重置 Mock 状态，确保干净起跑线。
- **Teardown 阶段**：测试后强制销毁垃圾数据与连接，防止用例污染。

---

## 五、 解法二：代码框架设计与 $Pass^k$ 数学算法

为了解决**噩梦二（过程弯弯绕）**与**噩梦四（概率成功假象）**，我们必须引入 $Pass^k$ 统计学模型。

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

## 六、 评测框架 Python 实战

`agent-eval-harness` 框架如何通过代码落地上述解法：

```python
from agent_eval import Task, SandboxEnvironment, CodeGrader, AgentEvaluator, Step, Transcript

# 1. 定义测试 Task (针对 SQL 变更场景)
task = Task(
    id="task_sql_clean",
    name="过期用户冻结任务",
    prompt="请冻结 status 为 EXPIRED 的用户账号",
    expected_state={"expired_active_count": 0, "normal_active_count": 100}
)

# 2. 配置沙箱钩子 (防止用例污染)
db_mock = {}

def setup_db():
    db_mock["expired_active_count"] = 15  # 待清理记录
    db_mock["normal_active_count"] = 100   # 正常记录 (保护对象)
    return dict(db_mock)

sandbox = SandboxEnvironment(
    setup_fn=setup_db,
    teardown_fn=lambda state: db_mock.clear(),
    get_state_fn=lambda: dict(db_mock)
)

# 3. 编写 QA 硬断言 (解决噩梦一与噩梦三)
def qa_hard_assert(task, transcript, env_state):
    # 硬断言 1: 目标数据必须变更
    if env_state.get("expired_active_count") != 0:
        return False, "物理断言失败: 过期账号未被冻结"
    
    # 硬断言 2: 副作用隔离 (正常数据不能被误修改)
    if env_state.get("normal_active_count") != 100:
        return False, "副作用断言失败: 正常用户账号被误修改"
        
    return True, "物理硬断言与副作用校验完全通过"

# 4. 执行 Pass^5 可靠性统计评估 (解决噩梦二与噩梦四)
evaluator = AgentEvaluator(grader=CodeGrader(check_fn=qa_hard_assert), env=sandbox)
summary = evaluator.evaluate_task(task, my_agent_runner, k=5)

print(f"Task ID: {summary.task_id}")
print(f"Pass^5 全成功率: {summary.pass_all}")
print(f"单次平均成功率: {summary.success_rate * 100}%")
print(f"平均消耗步数: {summary.avg_steps}")
```
