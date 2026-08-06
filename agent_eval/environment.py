from typing import Any, Callable, Dict, Optional


class SandboxEnvironment:
    """Agent 测试沙箱基础设施：负责环境 setup, state 收集与 teardown/reset"""

    def __init__(
        self,
        setup_fn: Optional[Callable[[], Any]] = None,
        teardown_fn: Optional[Callable[[Any], None]] = None,
        get_state_fn: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        self.setup_fn = setup_fn
        self.teardown_fn = teardown_fn
        self.get_state_fn = get_state_fn
        self._current_state: Dict[str, Any] = {}

    def setup(self) -> None:
        """初始化沙箱环境状态"""
        self._current_state = {}
        if self.setup_fn:
            res = self.setup_fn()
            if isinstance(res, dict):
                self._current_state = res

    def get_state(self) -> Dict[str, Any]:
        """获取物理环境终态"""
        if self.get_state_fn:
            return self.get_state_fn()
        return self._current_state

    def reset(self) -> None:
        """复原/清理沙箱环境"""
        if self.teardown_fn:
            self.teardown_fn(self._current_state)
        self._current_state = {}
