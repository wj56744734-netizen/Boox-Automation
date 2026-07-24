"""测试结果共享存储——桥接 excel_runner 和 conftest。

excel_runner 在模块加载时调用 set_cases() 存入 ParsedCase 列表；
用例执行过程中逐步填充 case.skip_reason / step.status 等字段；
conftest 在 pytest_sessionfinish 时调用 get_cases() 读取最终结果。
"""

from __future__ import annotations

_cases: list = []
_device_info: dict = {}


def set_cases(cases: list) -> None:
    """存入用例列表（传引用，运行时状态变更直接可见）。"""
    global _cases
    _cases = cases


def get_cases() -> list:
    """获取用例列表（含运行时填充的 skip_reason / step.status 等）。"""
    return _cases


def set_device_info(info: dict) -> None:
    global _device_info
    _device_info = info


def get_device_info() -> dict:
    return _device_info
