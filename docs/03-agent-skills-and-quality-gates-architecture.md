# Agent 技能库、质量门禁与生产级工程架构指南

> 本指南基于 2026 年 GitHub 热门 Agent 项目（包括 `prime-agent`, `agent-skills`, `superpowers`, `cloudflare/computer` 等）的硬核工程实践，总结并演进 Agent 自动化评测与生产落地架构。

---

## 一、 核心痛点与行业趋势

在 2026 年的 Agent 工程实践中，简单提示词拼接的玩具 Agent 已全面淘汰，业界核心风口已升级为：
**「可组合 Skills + 持久运行时 + 生产级工程纪律（Quality Gates）」**。

### 1. 四大工程失效模式
- **自理合理化 (Anti-Rationalization Failure)**：Agent 在遇到测试报错或断言失败时，容易在 `Thought` 中自圆其说（如“此报错符合预期”、“测试环境缺少依赖，跳过该项仍算成功”），向用户提供虚假的口头成功。
- **长时程崩溃 (Long-Horizon Drift)**：执行 10 步以上复杂任务时，没有持续 REPL 和心跳维持，导致上下文漂移或重复陷入死循环。
- **无门禁直投 (Ungated Shipping)**：Agent 缺乏定义良好的 DEFINE → PLAN → BUILD → VERIFY → REVIEW → SHIP 生命周期阶段校验，直接交付未经探针检验的代码。
- **Token 暴耗**：代码库分析时盲目全量读取，缺乏零 Token 损耗的本地图谱（如 tree-sitter 索引）。

---

## 二、 生产级质量门禁架构 (Quality Gate Architecture)

为了彻底解决上述失效模式，我们在 `agent-eval-harness` 中引入两大核心级门禁组件：

### 1. 反合理化判定器 (`AntiRationalizationGrader`)
- **防御目标**：拦截 Agent 在 Transcript 中的自我辩解、强行合理化报错或伪造成功的行为。
- **机制**：内置硬逻辑与正则模式扫描（如 `expected error`, `minor issue`, `skip test`, `no need to fix` 等自我开脱特征词），结合物理断言比对，一旦发现 Agent 在未修复问题的情况下擅自下结论，判定为失败。

### 2. 全生命周期质量门禁 (`LifecycleQualityGatePipeline`)
将规范化开发流程抽象为阶段式硬性拦截：
- **DEFINE / PLAN**：校验 Agent 是否建立清晰的任务拆解与工具使用策略（Tool Efficiency Check）。
- **BUILD / VERIFY**：强制引入独立物理探针（ZeroTrustGrader），拒绝盲信 Text 报告。
- **REVIEW / SHIP**：进行反合理化扫描（AntiRationalizationGrader）与物理终态比对（StateGrader），满足全套硬断言后才允许标记为 SHIP 状态。

---

## 三、 零信任多视角审查机制 (Multi-Perspective Zero-Trust Audit)

在代码交付阶段，建立零信任多视角 Subagent 审查矩阵：
1. **安全与边界审查**：校验物理隔离、沙箱权限与输入转义。
2. **反合理化与边缘逻辑审查**：防止 Agent 误判、漏判及正则逃逸。
3. **架构与可靠性审查**：确保 Pass^k 计算、Pydantic 数据模型兼容性与接口简洁度。

---

## 四、 最佳实践总结

- **拒绝口头成功**：所有交付物必须附带独立运行的通过日志或物理终态哈希。
- **零信任探针优先**：测试探针与 Agent 运行逻辑彻底解耦，由第三方 Harness 执行。
- **阶段流转硬限制**：前一阶段 Gate 未 Pass 时，严禁流转至下一个 Stage。
