# 图工程（Graph Engineering）与自主决策 Agent 架构优化方案指��

> 本指南结合 Google 图工程实战课程与最新 Agent 架构演进，总结针对 `agent-eval-harness` 与 `playwright-ai-healer` 的图架构改造、上下文工程及节点级 Trace 评估方案。

---

## 一、 核心理念演进：从单 Agent 到图工程

在复杂 Agent 落地过程中，单 Agent 与线性工作流存在明显的瓶颈：
- **单 Agent 线性执行**：中间任意步骤超时或定位失败将导致全局崩溃，缺乏自我纠错与局部恢复机制。
- **线性 Loop 模式**：缺乏条件路由（Conditional Branching）与状态回滚，容易陷入盲目重试的死循环。
- **图工程（Graph Engineering）**：将复杂任务构建为有向有环状态图（Stateful Graph / DAG），明确定义节点（Node）、边（Edge）、条件路由与全局状态（State），支持并行分支、条件退回与状态共享。

### 1. 架构演进阶段
1. **10% 基础单 Agent**：简单输入 → 工具调用 → 输出。
2. **50% 图工程（Graph Engineering）**：显式 DAG / 状态图拓扑结构，具备多节点协作与状态机逻辑。
3. **75% 循环与自愈工程（Loop & Healing Engineering）**：节点级自我纠错、断言门禁与物理回滚。
4. **100% 自生成图（The Graph That Builds Itself）**：大模型根据复杂任务描述动态生成子节点与拓��图并自主执行。

---

## 二、 核心项目优化方案

### 1. `playwright-ai-healer` 测试自愈系统架构升级

- **状态图重构（State Graph Engineering）**：
  - 将测试执行与自愈过程拆解为标准状态图：
    `定位元素节点` → `硬断言校验节点` → （失败触发）`DOM 剪枝提炼节点` → `LLM 自愈决策节点` → `物理重试与状态更新节点`。
  - 支持多路径降级与最大重试轮次阀门，消除盲目重试死循环。

- **上下文工程（Context Engineering & Observation Masking）**：
  - **痛点**：Playwright 导出完整 DOM 树动辄成千上万 Token，输入 LLM 成本高、响应慢且容易干扰注意力。
  - **优化**：物理层剪枝只提取失败元素周边 3 层父子节点的 Accessibility Tree (AX-Tree) 或关键属性，精简 90% 以上无用 Token，大幅提升自愈决策准确率。

- **确定性与灵活性分离（代码做骨架，LLM 做肌肉）**：
  - **代码做骨架**：页面导航、显式等待、截图保存、报告生成、最终状态物理断言等确定性逻辑由 Python / Node.js 脚本硬编码管控。
  - **LLM 做肌肉**：仅在 `page.locator()` 发生超时或元素改变时，局部触发 LLM 分析剪枝后 DOM 与历史截图，完成选择器自愈修复。

---

## 二、 `agent-eval-harness` 评测框架提升

- **节点级 Step-by-Step 追踪与流失率分析（Node-Level Instrumentation）**：
  - **痛点**：传统的 Pass/Fail 终态评估无法定位 Agent 在第几步开始偏离目标。
  - **优化**：在状态图的每一个 Node 注入 Trace 埋点，记录每个步骤的耗时、Token 消耗、工具调用成功率与流失率（Drop-off Rate），精准找出失败频次最高的瓶颈节点。

- **双层硬软结合评估体系**：
  - **硬断言层（Execution-based Hard Assertions）**：物理检验环境终态（如数据库记录、文件生成、HTTP code、单元测试结果），防范 Markdown 口头欺诈。
  - **软评估层（Ragas / Tool Fidelity Evals）**：评估推理轨迹的“上下文相关度”、“工具使用忠实度”，及时预警 LLM 伪造数据或开脱合理化倾向。

---

## 三、 零信任多 Agent 审查与协作范式

在代码审查与复杂方案校验中，引入多角色 Subagent 并行审查：
1. **边界与异常审查 Agent**：专注空指针、Timeout、网络异常捕获与重试机制。
2. **测试覆盖率 Agent**：校验单元测试与边缘 Case 补充是否完整。
3. **安全与权限 Agent**：审查敏感配置、Token 泄露与硬编码风险。
4. **Master Harness 汇总**：由主控脚本执行物理断言汇总，判定整体方���通过与否。

---

## 四、 实施路径与行动计划

1. **第一阶段**：在 `agent-eval-harness` 中落地节点级 Trace 统计模块与流失率分析指标。
2. **第二阶段**：在 `playwright-ai-healer` 中重构状态图引擎，接入 DOM AX-Tree 剪枝器。
3. **第三阶段**：建立端到端的多 Agent 零信任物理断言集成测试。
