# Agent 自动化评测指南（下篇）：执行轨迹（Transcript）解析、LLM Judge 数学校准与生产飞轮

> **作者**：张喆 (Zhang Zhe) | 资深 QA 自动化架构师 & AI Agent 评测专家  
> **开源项目**：[agent-eval-harness](https://github.com/zhangzhe0309/agent-eval-harness)

---

## 一、 核心避坑：为什么只看终态结果（Outcome）会掩盖 90% 的隐蔽风险？

在 Agent 测试实践中，初学者最常犯的严重错误是：**“只要最终环境数据库字段对了，或者断言通过了，就认为测试 100% 成功”**。

这种黑盒测试���维会导致严重的隐蔽风险遗漏：

1. **Reward Hacking 与侥幸蒙对**：
   Agent 遇到接口报错后，可能会尝试调用不合规的绕路工具，或者通过硬编码假数据恰好覆盖了校验规则。表面上 Outcome 为 `PASS`，实则是严重的业务漏洞。
2. **死循环与 Token 爆破陷阱**：
   Agent 遇到中间步骤异常时，由于 Prompt 缺乏明确终止条件，连续重复调用同个工具 30 次才偶然成功。虽然结果正确，但线上单次调用的延迟和 API Token 成本暴增了 30 倍。
3. **隐蔽副作用（Side Effects）**：
   Agent 在修改目标订单记录的同时，因 SQL 筛选条件模糊，不小心清空了关联日志表，而终态探针仅仅检查了订单表。

---

## 二、 Transcript（执行轨迹日志）结构化建模与过程指标

为了穿透黑盒，`agent-eval-harness` 对 Agent 的执行全过程进行结构化建模，捕获完整的 **Thought-Action-Observation 链路**：

```json
{
  "task_id": "task_001",
  "steps": [
    {
      "step_number": 1,
      "thought": "分析用户需求，首先调用 query_user 接口",
      "action": "query_user",
      "action_input": {"user_id": "U12345"},
      "observation": {"status": "ACTIVE"},
      "is_error": false,
      "duration_sec": 0.32
    },
    {
      "step_number": 2,
      "thought": "接口报错，尝试重新发送请求",
      "action": "query_user",
      "action_input": {"user_id": "U12345"},
      "observation": "HTTP 500 Server Error",
      "is_error": true,
      "duration_sec": 1.15
    }
  ]
}
```

### 关键过程指标（Process Metrics）：

- **Tool Call Error Rate (工具调用报错率)**：
  $$\text{Error Rate} = \frac{\text{Count}(\text{Is\_Error} == \text{True})}{\text{Total Steps}}$$
  若报错率 $> 15\%$，说明 Tool Description 描述模糊或系统稳定性差。
- **Trajectory Length Ratio (轨迹步数冗余度)**：
  $$\text{Length Ratio} = \frac{\text{Actual Steps}}{\text{Minimal Expert Steps}}$$
  评估 Agent 解决问题是“干练高效”还是“笨拙迂回”。
- **Retry Loop Pattern (死循环阻断率)**：
  检测是否存在连续相同的 `Action + Action_Input` 组合，防止无限重试。

---

## 三、 LLM Judge 评分器的数学校准 (Calibration) 实战

对于无法编写确定性代码断言的开放性场景（如客服回答质量、心理咨询倾听度、复杂报告生成），我们必须引入 LLM 作为 Judge。

但 **未经校准的 LLM Judge 是不可信的**（存在打分漂移、严苛度不一、容易被字数长短误导）。

### 1. 评分细则 (Rubric) 设计原则

- **禁止模糊 1-10 分打分**：要求 LLM Judge 输出布尔契约（Pass/Fail）及具体的 Checklist 原因。
- **上下文完整输入**：评估 Prompt 必须同时包含：`Task 目标 + 完整 Transcript 轨迹 + 最终环境 Diff`。

### 2. 数学校准流程与 Cohen's Kappa 系数

为了证明 LLM Judge 与人类专家打分具备高度一致性，必须执行**校准 (Calibration) 流程**：

```
[准备 50 个黄金样例 (Golden Set)] ──> [人类专家双盲标注] ──> [LLM Judge 跑分] ──> [计算 Cohen's Kappa 系数] ──> [迭代 Rubric]
```

#### 校验一致性指标：Cohen's Kappa 系数

$$K = \frac{p_o - p_e}{1 - p_e}$$

- $p_o$：人类专家与 LLM Judge 的观察一致率。
- $p_e$：偶然一致率。
- **合格标准**：$K \ge 0.75$ 表示强一致，LLM Judge 才可以被批准上线代替人工审核。

---

## 四、 生产环境与离线评测的飞轮闭环

离线评测集（Benchmark）无论准备得多么详尽，都无法覆盖线上用户的全部真实奇葩操作。真正的评测基础设施必须建立**生产闭环飞轮**：

```
[线上生产环境] ──> [挂载异常探针 (探针抓取 Error / 差评轨迹)]
      ▲                                   │
      │                                   ▼
[回归测试防护网] <── [脱敏加工为离线 Task Benchmark]
```

1. **线上异常轨迹抓取**：在生产环境挂载日志探针，自动捕获触发重试 > 3 次、工具调用失败、用户主动中途取消或打差评的真实轨迹。
2. **脱敏与 Task 转化**：将线上真实失败场景脱敏后，提炼为标准 Task JSON 投递至离线评测库。
3. **建立防复发防护网**：针对该故障编写环境硬断言，确保后续的任何代码改动都无法绕过测试防线，实现质量螺旋上升。

---

## 五、 全系列总结

通过上篇与下篇的完整梳理，我们完成了从**基础理念（环境硬断言）** $\rightarrow$ **系统架构（$Pass^k$ 与 Ship Gate）** $\rightarrow$ **高级避坑（轨迹解析与 LLM Judge 校准）** 的完整闭环。

完整的测试框架代码与所有案例文档均已开源，欢迎在 GitHub 上 Star 与贡献代码：
- 官方仓库：[zhangzhe0309/agent-eval-harness](https://github.com/zhangzhe0309/agent-eval-harness)
