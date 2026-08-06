# Agent Evaluation Harness

一个专为 AI Agent 打造的自动化评测框架（Python + pytest）。

## 核心特性

- **基于环境终态校验 (Execution-based)**：支持基于状态、代码断言、数据比对的硬断言 Grader。
- **可靠性评估 (Pass^k & Pass@k)**：针对 Agent 调用的非确定性，支持多轮 Trial 统计评估。
- **执行轨迹分析 (Transcript Analysis)**：记录和分析 Agent Thought-Action-Observation 链路，统计步数、工具报错率及死循环情况。
- **环境隔离与复原 (Sandbox Lifecycle)**：集成测试环境自动初始化与 Setup/Teardown 重置机制。

## 目录结构

- `agent_eval/`: 评测框架核心库
- `tests/`: 自动化评测示例与断言集
- `docs/`: 技术文档与架构指南
