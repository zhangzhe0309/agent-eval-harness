# 项目整体方案与技术演进脉络指南 (Project Architecture & Evolution Lineage)

> 本文档系统归纳了当前 Agent 自动化评测与 UI 测试自愈系统的完整落地方案，并详细梳理其演进来源与开源项目技术脉络。

---

## 一、 当前项目整体架构方案

当前体系由 **`agent-eval-harness`**（ Agent 自动化评测与质量门禁框架）与 **`playwright-ai-healer`**（基于 AI 的 Playwright 测试自愈引擎）两大核心构建：

```
                    ┌─────────────────────────────────────────────────────────┐
                    │               用户需求 / CI/CD 触发                     │
                    └───────────────────────────┬─────────────────────────────┘
                                                │
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                             `playwright-ai-healer` 状态图自愈引擎                         │
│  [执行 Node] ──> [硬断言 Node] ──(失败)──> [AX-Tree DOM 剪枝 Node] ──> [LLM 自愈决策 Node]   │
└───────────────────────────────────────────────┬────────────────────────────────��─────────┘
                                                │ 交互 Trace & Transcript
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                            `agent-eval-harness` 零信任质量门禁                               │
│  1. DEFINE/PLAN : 工具效率与多角色 Agent 审查 (StepEfficiencyGrader)                       │
│  2. BUILD/VERIFY: 物理探针硬断言 (ZeroTrustGrader)                                       │
│  3. REVIEW/SHIP : 反自我合理化与终态校验 (AntiRationalizationGrader + StateGrader)          │
│  4. 节点追踪     : 单步耗时/Token/流失率 (Step-by-Step Node Instrumentation)                 │
└───────────────────────────────────────────────┬──────────────────────────────────────────┘
                                                │
                                                ▼
                                   Pass^k / 评测质量报告导出
```

### 核心功能组件：
1. **零信任物理探针 (`ZeroTrustGrader`)**：绕过 LLM 口头总结，直接执行物理环境断言（检查文件、数据库、进程 exit_code），拦截“嘴上成功但未执行”的欺骗。
2. **反自我合理化判定器 (`AntiRationalizationGrader`)**：基于正则与语义扫描，拦截 Agent 在遇到报错时自圆其说、强行开脱或未调用工具即伪造成功的行为。
3. **全生命周期质量门禁管道 (`LifecycleQualityGatePipeline`)**：将 DEFINE → PLAN → BUILD → VERIFY → REVIEW → SHIP 卡扣化，未通过物理校验禁止进入 SHIP 阶段。
4. **DOM AX-Tree 剪枝器 (Context Engineering)**：从上万 Token 的全量 DOM 树中提炼失败元素周边 3 层 AX-Tree 节点，Token 节省 90%+。
5. **节点级 Trace 监控**：在状态图各节点埋点，计算中间步骤的流失率与超时率。

---

## 二、 演进脉络与来源开源项目清单

本架构不是闭门造车，而是汲取了 2026 年 GitHub 热门 Agent 项目与学术界/工业界顶尖工程实践进化而来：

| 来源项目 / 课程 | 出处 / 开发者 | 关键借鉴与进化点 |
| :--- | :--- | :--- |
| **`prime-agent`** | `PrimeIntellect-ai/prime-agent` | **自改进 RLM 与持久 REPL**：借鉴其心跳检测机制与持久运行时，解决 Agent 长时程任务中断与上下文漂移问题。 |
| **`agent-skills`** | `addyosmani/agent-skills` (Chrome 团队) | **全生命周期质量门禁与反合理化**：吸收其 DEFINE→SHIP 阶段卡扣思想及 Anti-Rationalization 规则，防止 Agent 在测试报错时辩解开脱。 |
| **`superpowers`** | `obra/superpowers` | **Agentic TDD 与子 Agent 驱动开发**：引入物理测试驱动开发（TDD）理念，在代码变更前强制建立红/绿测试探针。 |
| **`cloudflare/computer`** | `cloudflare/computer` | **持久化环境与物理沙箱**：借鉴其 Isolate Shell 与容器隔离思想，让 Agent 在受控沙箱中生成与验证代码。 |
| **`graphify`** | `Graphify-Labs/graphify` | **零 Token 本地知识图谱**：基于 tree-sitter 实现代码库零 API 消耗的结构化索引与检索。 |
| **Google Graph Engineering** | Google 官方实战课程 | **状态图拓扑（Graph Engineering）**：将单线重试升格为有向有环图（DAG），实现条件分支、回滚恢复与“代码做骨架，LLM 做肌肉”。 |
| **SWE-bench & Ragas** | 学术界 / 开源评测标杆 | **Pass^k 可靠性算法与双层评估**：引入基于环境终态校验（Execution-based）的 Pass^k 计算指标，结合 Ragas 软评估维度。 |

---

## 三、 总结与未来路线图

通过吸收上述 7 大优质项目的核心工程纪律，我们成功将传统的“单 Agent 提示词拼接”升级为**“生产级状态图 + 零信任硬门禁 + 节点级 Trace”**的工业级 AI 测试框架。
