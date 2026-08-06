import json
import os
from typing import Any, List
from agent_eval.models import Task


class BenchmarkDataset:
    """Benchmark 测试数据集加载与管理模块"""

    def __init__(self, tasks: List[Task]):
        self.tasks = tasks

    @classmethod
    def from_json_file(cls, json_path: str) -> "BenchmarkDataset":
        """从 JSON 文件加载 Task 测试集"""
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Dataset file not found: {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        tasks = []
        if isinstance(data, list):
            for item in data:
                tasks.append(Task(**item))
        elif isinstance(data, dict) and "tasks" in data:
            for item in data["tasks"]:
                tasks.append(Task(**item))

        return cls(tasks=tasks)

    def filter_by_metadata(self, key: str, value: Any) -> "BenchmarkDataset":
        """根据元数据标签筛选任务集"""
        filtered = [t for t in self.tasks if t.metadata.get(key) == value]
        return BenchmarkDataset(tasks=filtered)

    def __len__(self) -> int:
        return len(self.tasks)

    def __getitem__(self, index: int) -> Task:
        return self.tasks[index]
