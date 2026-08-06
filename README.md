# Agent Evaluation Harness

一个专为 AI Agent 打造的自动化评测框架（Python + pytest）。

## 核心特性

- **基于环境终态校验 (Execution-based)**：支持基于状态、代码断言、数据比对的硬断言 Grader。
- **可靠性评估 (Pass^k & Pass@k)**：针对 Agent 调用的非确定性，支持多轮 Trial 统计评估。
- **执行轨迹分析 (Transcript Analysis)**：记录和分析 Agent Thought-Action-Observation 链路，统计步数、工具报错率及死循环情况。
- **环境隔离与复原 (Sandbox Lifecycle)**：集成测试环境自动初始化与 Setup/Teardown 重置机制���

## 目录结构

- `agent_eval/`: 评测框架核心库
- `tests/`: 自动化评测示例与断言集
- `docs/`: 技术文档与架构指南
  - `docs/01-agent-eval-framework-architecture.md`: 《Agent 自动化评测框架设计与落地指南：基于环境状态校验与 Pass^k 可靠性评估》
  - `docs/02-transcript-analysis-and-llm-judge.md`: 《Agent 评测深度避坑：执行轨迹（Transcript）分析与 LLM Judge 校准实践》
  - `docs/03-traditional-qa-to-agent-eval-guide.md`: 《从传统测开到 Agent 评测：如何为智能体编写可执行的环境断言与框架上手指南》
