# Agent Evaluation Harness

一个专为 AI Agent 打造的自动化评测框架（Python + pytest）。

## 核心特性

- **基于环境终态校验 (Execution-based)**：支持基于状态、代码断言、数据比对的硬断言 Grader。
- **可靠性评估 (Pass^k & Pass@k)**：针对 Agent 调用的非确定性，支持多轮 Trial 统计评估。
- **执行轨迹分析 (Transcript Analysis)**：记录和分析 Agent Thought-Action-Observation 链路，统计步数、工具报错率及死循环情况。
- **环境隔离与复原 (Sandbox Lifecycle)**：集成测试环境自动初始化与 Setup/Teardown 重置机制。

## 📚 深度技术文档与设计指南 (docs/)

1. 📖 **[第01篇：从传统测开到 Agent 评测 —— 理念转变、环境硬断言与快速上手](docs/01-traditional-qa-to-agent-eval-guide.md)**
   - 传统 QA 与 Agent 评测范式对比、三大高级环境断言体系、沙箱隔离机制与从零上手 Python 指南。
2. 📖 **[第02篇：Agent 自动化评测框架设计与落地 —— 架构解析、Pass^k 可靠性度量与 Ship Gate 门禁](docs/02-agent-eval-framework-architecture.md)**
   - 框架分层架构解析、Pass^k / Pass@k 数学模型、Grader 选型矩阵与 CI/CD 四级 Ship Gate 发布门禁。
3. 📖 **[第03篇：Agent 评测深度避坑 —— 轨迹（Transcript）解析、LLM Judge 校准与生产闭环](docs/03-transcript-analysis-and-llm-judge.md)**
   - Outcome 盲区与轨迹过程指标、LLM Judge Cohen's Kappa 数学校准与线上生产闭环飞轮。

## 目录结构

- `agent_eval/`: 评测框架核心库
- `tests/`: 自动化评测示例与断言集
- `docs/`: 技术文档与架构指南
