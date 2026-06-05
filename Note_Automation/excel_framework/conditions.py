"""前置条件检查器：根据 device_info 判断条件是否满足。"""
from __future__ import annotations

import re

# 条件关键字 → (设备字段, 操作符, 期望值)
_COND_SPEC: dict[str, tuple[str, str, str]] = {
    "国内设备执行": ("device_region", "eq", "国内"),
    "海外设备执行": ("device_region", "in", "海外,全球"),
    "平板设备执行": ("devices_reader", "eq", "平板"),
    "阅读器设备执行": ("devices_reader", "eq", "阅读器"),
    "黑白设备执行": ("driver_colour", "eq", "黑白"),
    "彩色设备执行": ("driver_colour", "eq", "彩色"),
}

# 条件关键字 → 人类可读的字段中文名（用于 skip 原因展示）
_FIELD_LABEL: dict[str, str] = {
    "device_region": "设备区域",
    "devices_reader": "设备类型",
    "driver_colour": "设备颜色",
}


def check_conditions(preconditions: list, device_info: dict) -> str | None:
    """检查所有条件型前置条件，全部通过返回 None，第一个不通过返回 skip_reason。"""
    for pc in preconditions:
        if pc.type != "condition":
            continue

        ok = _check_one(pc, device_info)
        if not ok:
            return _build_skip_reason(pc, device_info)

    return None


def _check_one(pc, device_info: dict) -> bool:
    """检查单条条件。"""
    # 版本检查（非关键字条件）
    if pc.kind == "version":
        return _check_version(pc, device_info)

    # 关键字条件
    spec = _COND_SPEC.get(pc.kind)
    if not spec:
        return False

    field, op, expected = spec
    actual = str(device_info.get(field, ""))

    if op == "eq":
        return actual == expected
    if op == "in":
        allowed = set(expected.split(","))
        return actual in allowed

    return False


def _check_version(pc, device_info: dict) -> bool:
    """检查固件版本 >= 期望版本。"""
    actual_str = str(device_info.get("version_info", ""))
    match = re.search(r"(\d+\.\d+\.\d+)", actual_str)
    if not match:
        return False

    actual_ver = _parse_version(match.group(1))
    expected_ver = _parse_version(pc.expected)
    return actual_ver >= expected_ver


def _parse_version(v: str) -> tuple[int, ...]:
    """解析版本号为可比较的元组。"""
    try:
        return tuple(int(x) for x in v.split("."))
    except (ValueError, AttributeError):
        return (0,)


def _build_skip_reason(pc, device_info: dict) -> str:
    """构造人类可读的跳过原因。"""
    if pc.kind == "version":
        actual_str = str(device_info.get("version_info", ""))
        match = re.search(r"(\d+\.\d+\.\d+)", actual_str)
        actual = match.group(1) if match else "未知"
        return f"前置条件不满足: 固件版本 {actual} < {pc.expected}"

    spec = _COND_SPEC.get(pc.kind)
    if not spec:
        return pc.skip_reason

    field, op, expected = spec
    actual = device_info.get(field, "未知")
    label = _FIELD_LABEL.get(field, field)

    if op == "eq":
        return f"前置条件不满足: {label}为{actual}，要求{expected}"
    if op == "in":
        allowed_list = expected.replace(",", " / ")
        return f"前置条件不满足: {label}为{actual}，要求{allowed_list}"

    return pc.skip_reason
