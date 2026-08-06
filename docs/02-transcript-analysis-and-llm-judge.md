# Agent 评测深度避坑：执行轨迹（Transcript）分析与 LLM Judge 校准实践

## 一、 为什么单看终态结果（Outcome）会掩盖 90% 的隐蔽风险？

在 Agent 评测实践中，最容易犯的错误是：**“只用黑盒模式校验最终环境结果，通过了就认为大功告成”**。

这种只看 Outcome 的测试方式存在重大盲区：

1. **Reward Hacking 与蒙对现象**：Agent 可能通过错误的机制（例如随机试错、尝试绕过权限限制或硬编码假数据）碰巧达到了终态目标。
2. **死循环与效率陷阱**：Agent 遇到了中间步骤报错，但重复重试了 20 次工具调用才成功。表面上看测试 Pass 了，但线上单次调用的 Token 消耗和延迟将暴涨。
3. **副作用（Side Effects）被遗漏**：Agent 在修改目标订单的同时，不小心误删了关联的日志记录或写入了垃圾数据，而终态校验只关注了订单状态字段。

因此，**阅读与解析 Transcript（执行轨迹日志）是 Agent 评测的核心修养**。没有 Transcript 解析的评测报告是不合格的。

---

## 二、 Transcript 结构化建模与过程指标

在 `agent-eval-harness` 中，我们将 Transcript 抽象为标准的时序动作节点：

```json
{
  "steps": [
    {
      "step_number": 1,
      "thought": "分析用户诉求，需要查询订单数据",
      "action": "query_order_api",
      "action_input": {"order_id": "10086"},
      "observation": {"status": "pending"},
      "is_error": false,
      "duration_sec": 0.45
    }
  ]
}
```

基于轨迹日志，可以提炼出关键的**过程指标（Process Metrics）**：

- **Tool Call Error Rate (工具调用报错率)**：`is_error = True` 的步骤占比。高达 15% 以上通常意味着 Tool Description 或 Prompt 约束不清晰。
- **Trajectory Length Ratio (轨迹冗余度)**：实际步数与标准专家路径步数的比值（Actual Steps / Benchmark Minimal Steps）。
- **Retry Loop Pattern (重试循环模式)**：同一 Action + Action_Input 连续重复执行 > 2 次，标志着系统陷入决策僵局。

---

## 三、 LLM Judge 评分器的最佳实践与防漂移校准

对于无法编写标准断言代码的开放性交互场景（如客服回答质量、心理咨询沟通、复杂报告撰写），我们必须引入 LLM 作为 Judge。但 LLM Judge 存在**随机性高、对 Prompt 敏感、标准易漂移**的问题。

### 1. 评分细则（Rubric）的设计原则
- **拒绝模糊打分**：避免让 LLM 直接给出 1-10 分，而应采用布尔契约（Pass/Fail）或具象的分层断言（Checklist）。
- **输入完整上下文**：评估时必须同时给 LLM Judge 喂入 **Task Prompt + Transcript 完整轨迹 + 初始与终态环境差异**。

### 2. LLM Judge 的校准流程 (Calibration)
1. **构建黄金标注集 (Golden Set)**：挑选 50 个典型 Task 的执行轨迹，由 2 位人类专家进行独立的 Pass/Fail 标注。
2. **运行自动校准脚本**：使用 LLM Judge 对这 50 个 Task 进行评分，计算与人类专家标注的 **Cohen's Kappa 系数** 或 **一致性比例（Consistency Rate）**。
3. **迭代 Prompt 细则**：若一致性 < 85%，��对不一致的 Case 细化 Rubric，直到 LLM Judge 的判定精度稳定符合要求。

---

## 四、 生产环境与离线评测闭环

离线 Benchmark 无论准备得多么全面，都无法穷尽真实用户的奇葩操作。真正的评测体系必须与线上生产闭环联动：

1. **线上异常日志抓取 (Online Exception Capture)**：在生产环境挂载探头，抓取包含工具调用报错、用户中途取消、回答低赞的真实线轨迹。
2. **转回离线 Benchmark Case**：将线上真实失败轨迹抽取关键输入与环境状态，脱敏后脱壳提炼为离线测试套件中的新增 Task。
3. **回归防护网建立**：确保每次针对线上故障的修复，都能在离线评测中被新增的断言规则自动拦截，实现防复发。
