# 从传统测开到 Agent 评测：如何为智能体编写可执行的环境断言与框架上手指南

## 一、 理念解读：从传统测开到 Agent 评测

### 1. 传统测开断言 vs Agent 环境断言的本质差异

- **传统测开断言（文本/接口响应断言）**：
  - **模式**：输入固定 Prompt 或 API 参数 → 期待确定的 Response JSON / 页面 Element 出现。
  - **特点**：单次解码，确定性高，只关注眼前吐出的文本与 HTTP 状态码。
- **Agent ��境断言（Execution-based Assertions）**：
  - **模式**：输入高层目标（如“清理数据库中的无用记录”） → Agent 自主规划并调用 N 次工具 → 校验外部世界的最终物理状态。
  - **特点**：Agent 可以有多种合法实现路径，答案不具备单一标准字符串，必须依赖**环境状态探针**来校验。

---

### 2. 怎么编写“可执行的环境断言”？

在 Agent 自动化测试中，高级断言主要分为三类：

1. **硬断言（State/Code Assertions）**：
   - 直接查询持久化存储。例如：执行 SQL 检查 `SELECT status FROM orders WHERE id=10086` 是否真变成了 `shipped`，或者检查磁盘文件是否存在、权限是否正确。
2. **状态机迁移断言（State Machine Assertions）**：
   - 校验 Agent 的操作是否符合业务状态机路线。例如：订单状态只能从 `pending` → `processing` → `shipped`，如果 Agent 绕过了 `processing` 直接标记为 `shipped`，即使终态正确，断言也要拦截。
3. **副作用无害断言（Side-effect Isolation Assertions）**：
   - 断言不仅要检查“该改的是否改了”，还要检查“不该改的是否被误伤”。例如：检查目标文件被更新的同时，同目录下的其他日志文件未被清理。

---

### 3. 沙箱环境的“干净起跑���与干净终点”

由于 Agent 具有修改外部物理环境的能力，如果前一个测试用例改变了数据库，后一个测试用例就会被污染。

因此，**可执行断言的前提是完善的沙箱机制**：
- **Setup 阶段**：测试前自动恢复基线数据（如通过 Docker 卷快照、内存 DB 重置或数据库事务回滚）。
- **Teardown 阶段**：测试完成后强制清理中间生成的垃圾文件或临时 API 密钥。

---

## 二、 `agent-eval-harness` 框架从零上手指南

本框架将传统 QA 的概念与 Agent 评测进行了映射：

- **Task** ↔ 测开中的 **TestData / TestCase 结构体**
- **SandboxEnvironment** ↔ 测开中的 **Setup / Teardown 钩子**
- **Grader** ↔ 测开中的 **Assert 断言器**
- **AgentEvaluator** ↔ 测开中的 **Runner 执行器与报告生成器**

### 步骤 1：准备环境与安装依赖

```bash
cd /root/agent-eval-harness
source venv/bin/activate
```

---

### 步骤 2：定义测试任务 (Task)

创建一个测试用例，指定 Agent 的输入 Task 以及期望的环境终态：

```python
from agent_eval import Task

my_task = Task(
    id="task_file_cleanup",
    name="临时文件清理任务",
    prompt="请清理 /tmp 目录下所有以 .tmp 结尾的超过 7 天的文件",
    expected_state={
        "tmp_file_count": 0,        # 期望过期文件数量归零
        "config_file_exists": True  # 期望常驻配置文件依然存在
    }
)
```

---

### 步骤 3：配置测试沙箱 (SandboxEnvironment)

定义用例执行前后的环境准备与状态采集函数：

```python
from agent_eval import SandboxEnvironment

def setup_env():
    # 模拟在环境中创建测试数据
    print("沙箱初始化：创建测试文件...")
    return {"tmp_file_count": 5, "config_file_exists": True}

def teardown_env(state):
    # 清理沙箱残余
    print("沙箱重置：清理现场...")

def get_real_state():
    # 从真实物理环境中查询当前状态
    return {
        "tmp_file_count": 0,
        "config_file_exists": True
    }

sandbox = SandboxEnvironment(
    setup_fn=setup_env,
    teardown_fn=teardown_env,
    get_state_fn=get_real_state
)
```

---

### 步骤 4：选择或自定义断言判定器 (Grader)

除了内置的 `StateGrader`，还可以通过 `CodeGrader` 编写灵活的 QA 自定义逻辑：

```python
from agent_eval import CodeGrader

def qa_custom_assert(task, transcript, env_state):
    # 1. 检查物理环境终态
    if env_state.get("tmp_file_count") != 0:
        return False, "环境校验失败：过期临时文件未被彻底清除"
    
    # 2. 检查 Agent 步数效率（过程断言）
    if transcript.total_steps > 3:
        return False, f"性能断言失败：Agent 耗费了 {transcript.total_steps} 步，超过上限 3 步"
        
    # 3. 检查是否有工具报错
    if transcript.error_count > 0:
        return False, f"过程断言失败：执行链路中包含了 {transcript.error_count} 次工具报错"

    return True, "用例测试通过"

grader = CodeGrader(check_fn=qa_custom_assert)
```

---

### 步骤 5：驱动 Agent 运行并计算 Pass^k 可靠性

调用 `evaluate_task(..., k=5)` 连续测试 5 次，验证 Agent 系统的稳定通过率：

```python
from agent_eval import AgentEvaluator

evaluator = AgentEvaluator(grader=grader, env=sandbox)

# 传入被测 Agent 函数，评估 5 轮 (Pass^5)
summary = evaluator.evaluate_task(my_task, my_agent_code, k=5)

print(f"- 任务 ID: {summary.task_id}")
print(f"- k 轮全成功 (Pass^k): {summary.pass_all}")
print(f"- 成功率 (Success Rate): {summary.success_rate * 100}%")
print(f"- 平均执行步数: {summary.avg_steps}")
```

---

### 步骤 6：通过 pytest 集成到 CI/CD 流水线

在 `tests/` 目录下编写测试用例，在命令行中直接运行：

```bash
PYTHONPATH=. venv/bin/pytest tests/test_agent_evaluation.py -v
```
