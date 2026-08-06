# Agent Evaluation Harness

一个专为 AI Agent 打造的自动化评测框架（Python + pytest）。

## 核心特性

- **基于环境终态校验 (Execution-based)**：支持基于状态、代码断言、数据比对的硬断言 Grader。
- **可靠性评估 (Pass^k & Pass@k)**：针对 Agent 调用的非确定性，支持多轮 Trial 统计评估。
- **执行轨迹分析 (Transcript Analysis)**：记录和分析 Agent Thought-Action-Observation 链路，统计步数、工具报错率及死循环情况。
- **环境隔离与复原 (Sandbox Lifecycle)**：集成测试环境自动初始化与 Setup/Teardown 重置机制。

## 📚 深度技术文档与指南 (docs/)

1. 📖 **[Agent 自动化评测指南（上篇）：从传统测开转型、环境硬断言与 Pass^k 架构实战](docs/01-agent-eval-foundations-and-architecture.md)**
   - 分析 Agent 业务落地方案与能力边界，剖析 QA 进场后的“四大噩梦”（幻觉欺骗、非确定性、副作用破坏与概率成功假象），详解从“物理硬断言/沙箱隔离”到“Pass^k 数学模型/CI 四级 Ship Gate”的完整解法与 Python 代码实战。
2. 📖 **[Agent 自动化评测��南（下篇）：执行轨迹（Transcript）解析、LLM Judge 数学校准与生产飞轮](docs/02-transcript-analysis-llm-judge-and-production.md)**
   - Outcome 盲区与风险揭秘、Thought-Action-Observation 轨迹解析、LLM Judge Cohen's Kappa 数学打分校准（$K \ge 0.75$）与线上生产闭环飞轮。

## 目录结构

- `agent_eval/`: 评测框架核心库
- `tests/`: 自动化评测示例与断言集
- `docs/`: 技术文档与架构指南
