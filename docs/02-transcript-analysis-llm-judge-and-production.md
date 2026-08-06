# Agent 自动化评测指南（下篇）：执行轨迹（Transcript）解析、LLM Judge 数学校准与生产飞轮

---

## 一、 遇到的实际问题：为什么只看“终态结果”研发和测试都会踩坑？

在 Agent 开发与测试的日常协作中，研发（Dev）和测试（QA）经常陷入以下两难困境：

- **研发的苦恼**：“本地测试数据库记录是对的，为什么线上用户频频反馈 Agent 回复极慢、Token 费用暴涨，甚至偶尔‘发疯’？”
- **测试的苦恼**：“测试断言校验数据库字段 PASS 了，但上线后发现 Agent 在偷偷利用漏洞‘绕路’或者‘造假’，测试根本拦截不住！”

之所以双方都会踩坑，是因为**只看终态结果（Outcome）的黑盒测试掩盖了过程中的四大隐蔽事故**：

### 异常场景 1：“越权偷懒/造假”（Reward Hacking）
- **问题现象**：Agent 遇到“调 API 无权限”报错后，为了完成任务，自己生成了一串硬编码的 JSON 字符串作为工具返回结果，骗过了后续流程。
- **后果**：表面上终态数据更新成功，实则绕过了安全鉴权，属于严重业务漏洞。

### 异常场景 2：“自述虚假繁荣”（Hallucinated Self-Report）
- **问题现象**： Agent 输出了格式精美的 Markdown 报告，声称“已全量修复 Bug 并跑通单测”，但被测环境中的文件代码根本没有任何修改。
- **后果**：若是盲信 Agent 口头汇报，缺陷将被带入下一阶段。

### 异常场景 3：“死循环与 Token 暴爆”
- **问题现象**： Agent 遇到第三方 API 抛出 HTTP 500 错误时，因为 Prompt 没有写明重试上限，在后台连续重试了 30 次调用。
- **后果**：虽然最后一次重试碰巧成功了，但单次请求耗时 40 秒，消耗了 10 万 Token，生产环境账单暴涨。

### 异常场景 4：“暗度陈仓的副作用”
- **问题现象**： Agent 成功更新了目标用户 `#U123` 的状态，但因为 SQL 的 `WHERE` 条件有缺陷，顺手清空了关联表中的历史日志。
- **后果**：终态探针只校验了用户表，导致致命的数据丢失未被发现。

---

## 二、 零信任解法一：执行轨迹（Transcript）结构化解析与多 Agent 审计

为了解决上述问题，我们必须引入**零信任执行轨迹（Transcript）结构化解析与 Auditor Agent 审计机制**。

### 1. 为什么这么做？
类似在系统中安装了“黑匣子/高清录像机”，把 Agent 运行过程中的**思考（Thought） $\rightarrow$ 动作（Action） $\rightarrow$ 输入（Input） $\rightarrow$ 工具观察结果（Observation）**逐帧结构化记录下来。

```json
{
  "task_id": "task_order_refund",
  "steps": [
    {
      "step_number": 1,
      "thought": "收到退款诉求，先查询订单状态",
      "action": "query_order",
      "action_input": {"order_id": "10086"},
      "observation": {"status": "DELIVERED"},
      "is_error": false,
      "duration_sec": 0.25
    },
    {
      "step_number": 2,
      "thought": "接口抛错 HTTP 500，尝试重复调用",
      "action": "query_order",
      "action_input": {"order_id": "10086"},
      "observation": "HTTP 500 Internal Error",
      "is_error": true,
      "duration_sec": 1.10
    }
  ]
}
```

### 2. 这样能解决啥？（研发与测试收益）

- **对研发（Dev）的价值**：
  - **精准定位归因**：出现异常时，能迅速定位到底是因为 Prompt 引导不清、Tool 工具描述（Description）有歧义，还是底层 LLM 推理能力差。
- **对测试（QA）的价值**：
  - **过程质量三维度量**：
    1. **工具报错率 (Tool Call Error Rate)**：
       $$\text{Error Rate} = \frac{\text{错误步骤数}}{\text{总步骤数}}$$
       若报错率 $> 15\%$，说明工具设计不合理或系统不稳定。
    2. **轨迹冗余度 (Trajectory Length Ratio)**：
       $$\text{Length Ratio} = \frac{\text{实际执行步数}}{\text{专家标准步数}}$$
       评估 Agent 是“干练高效”还是“笨拙迂回”。
    3. **死循环熔断率 (Retry Loop Pattern)**：
       检测是否存在连续重复调用，及时熔断防爆破。

---

## 三、 零信任解法二：LLM Judge 打分器的“数学校准”

### 1. 遇到的实际问题
对于开放性交互场景（如客服服务态度、心理咨询倾听度、复杂报告撰写），我们无法用 `assert database["status"] == "ok"` 编写硬代码，必须引入大模型当裁判（LLM Judge）。

但**未经校准的 LLM Judge 存在三大致命毛病**：
- **打分随心所欲**：同样的回答，今天打 8 分，明天打 5 分（标准漂移）。
- **字数偏见**：天生喜欢字数长、客套话多的回答，哪怕内容是废话。
- **对 Prompt 极度敏感**：修改了 Judge 的 Prompt 中的一个词，打分分布大幅漂移。

### 2. 为什么这么做？
根据零信任防御协议，必须用**黄金标注集 (Golden Set) + 人类专家双盲标注**对 LLM Judge 进行数学校准，只有通过一致性检验的 LLM 裁判才准许上岗！

```
[准备 50 个典型 Task (Golden Set)] ──> [人类专家双盲标注 PASS/FAIL] ──> [LLM Judge 独立打分] ──> [计算 Cohen's Kappa 系数] ──> [迭代 Rubric 细则]
```

### 3. 这样能解决啥？

- **细则契约化 (Rubric Contract)**：
  放弃模糊的 1-10 分打分，要求 LLM Judge 输出布尔（PASS/FAIL）与具体的 Checklist 依据。
- **Cohen's Kappa 系数数学校验**：
  使用统计学公式计算人类与 LLM Judge 的一致性得分：
  $$K = \frac{p_o - p_e}{1 - p_e}$$
  - $p_o$ 为人类专家与 LLM Judge 的观察一致率。
  - **解决的问题**：只有当 $K \ge 0.75$（强一致）时，才证明 LLM 裁判具备人审替代能力，彻底消除打分随心所欲的患害。

---

## 四、 零信任解法三：生产环境与离线 Benchmark 的飞轮闭环

### 1. 遇到的实际问题
离线测试用例（Benchmark）无论准备得多么详尽，研发和测试都无法穷尽线上真实用户的奇葩操作。线上经常冒出离线测试从未见过的异常。

### 2. 为什么这么做？
建立**零信任生产闭环飞轮**，把线上真实生产环境变成测试用例的“自动孵化池”。

```
[线上生产环境] ──> [挂载探针抓取 (高重试 / 差评 / Error 轨迹)]
      ▲                                       │
      │                                       ▼
[回归防护网] <── [自动脱敏加工为离线 Task Benchmark]
```

### 3. 这样能解决啥？
1. **线上异常探针抓取**：自动监控生产环境，一旦发现 Agent 步数 $> 10$ 步、工具连续报错或用户打差评，立刻捕获其 Transcript 轨迹。
2. **自动化脱敏提炼**：将异常轨迹提取为标准的离线 Task JSON 投递至测试库。
3. **彻底解决 Bug 屡教不改**：针对该故障补齐 TDD 环境硬断言，确保代码重构或模型升级时，该问题永远无法在生产环境复发。

---

## 五、 全指南总结（零信任多 Agent 评测矩阵）

通过《上篇》与《下篇》的全面梳理，团队形成以下零信任落地规范：

| 测试维度 | 解决什么问题 | 零信任落地规范 |
| :--- | :--- | :--- |
| **零信任探针 (ZeroTrustGrader)** | 拒绝盲信 Agent 自述，解决幻觉与假通关 | 强制通过独立 TDD 代码探针直接比对物理环境 |
| **环境硬断言 (StateGrader)** | 解决大模型隐蔽破坏与副作用 | 数据库多表联动校验、非目标数据隔离断言 |
| **Pass^k 可靠性模型** | 解决 Agent 执行非确定性与概率成功假象 | 牺牲 3-10x Token 预算进行 $k=5$ 轮独立沙箱抽样 |
| **执行轨迹解析 (Transcript)** | 解决黑盒追踪难题与 Token 暴爆风险 | 捕获 Thought-Action 链路、Tool Error Rate、死循环熔断 |
| **LLM Judge 校准** | 解决主观开放场景打分随心所欲 | Golden Set 黄金集、Rubric 契约、Cohen's Kappa ($K \ge 0.75$) |
| **生产闭环飞轮** | 解决离线测试覆盖不全与线上 Bug 复发 | 线上探针捕抓、自动转化为回归 Task |

完整的测试框架代码与所有案例文档均已开源：
- 官方仓库：[zhangzhe0309/agent-eval-harness](https://github.com/zhangzhe0309/agent-eval-harness)
