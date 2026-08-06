# Agent Evaluation Harness

一个专为 AI Agent 打造的零信任自动化评测框架（Python + pytest）。

## 核心特性

- **零信任防御协议 (Zero-Trust Protocol)**：拒绝盲信 Agent 自述 Markdown/Text 报告，强制通过物理探针硬校验交付物。
- **基于环境终态校验 (Execution-based)**：支持基于状态、代码断言、数据比对与副作用隔离的硬断言 Grader。
- **可靠性评估 (Pass^k & Pass@k)**：针对 Agent 调用的非确定性，支持多轮 Trial 统计评估，牺牲 3-10x Token 换取 100% 可靠性。
- **执行轨迹分析 (Transcript Analysis)**：记录和分析 Agent Thought-Action-Observation 链路，统计步数、工具报错率及死循环情况。
- **环境隔离与复原 (Sandbox Lifecycle)**：集成测试环境自动初始化与 Setup/Teardown 重置机制。

## 📚 深度技术文档与指南 (docs/)

1. 📖 **[Agent 自动化评测指南（上篇）：从传统测开转型、零信任防御协议与 Pass^k 架构实战](docs/01-agent-eval-foundations-and-architecture.md)**
   - 分析 Agent 业务落地方案与能力边界，剖析 Agent 系统落地的“四大固有失效模式”（幻觉欺骗、非确定性、副作用破坏与概率成功假象），详解从“零信任 TDD 探针/沙箱隔离”到“Pass^k 数学模型/CI 四级 Ship Gate”的完整解法与 Python 代码实战。
2. 📖 **[Agent 自动化评测指南（下篇）：执行轨迹（Transcript）解析、LLM Judge 数学校准与生产飞轮](docs/02-transcript-analysis-llm-judge-and-production.md)**
   - 结合研发与测试视角剖析黑盒测试的四大异常事故（Reward Hacking、自述虚假繁荣、死循环 Token 暴爆、暗度陈仓副作用），详解 Transcript 结构化解析与三大过程指标、LLM Judge Cohen's Kappa 数学校准（K ≥ 0.75）与生产飞轮闭环。

## 目录结构

- `agent_eval/`: 评测框架核心库（包含 ZeroTrustGrader, StateGrader, ToolCorrectnessGrader, StepEfficiencyGrader 等）
- `tests/`: 自动化评测示例与断言集
- `docs/`: 技术文档与架构指南
