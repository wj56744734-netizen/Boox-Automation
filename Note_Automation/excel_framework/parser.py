"""步骤解析器：从 Excel 操作步骤文本中提取【】标记和动作类型。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# 动作词 → 操作类型映射
_ACTION_MAP = {
    "点击": "click",
    "打开": "click",
    "进入": "click",
    "选择": "click",
    "双击": "click",
    "检查": "assert_visible",
    "查看": "assert_visible",
    "校验": "assert_visible",
    "输入": "input",
    "长按": "long_press",
    "退出": "click",
    "返回": "click",
    "滑动": "swipe",
    "清空": "click",
    "确认": "click",
}

_TAG_RE = re.compile(r"【(.+?)】")
_STEP_RE = re.compile(r"(\d+)[\.\、](.*)")
_VERSION_COND_RE = re.compile(r"^\d+\.\d+\.\d+-版本执行$")

# ---- 条件型前置：关键字 → 设备字段 + 期望值 ----
_CONDITION_KEYWORDS: dict[str, tuple[str, str]] = {
    "国内设备执行": ("device_region", "国内"),
    "海外设备执行": ("device_region__in", "海外,全球"),
    "平板设备执行": ("devices_reader", "平板"),
    "阅读器设备执行": ("devices_reader", "阅读器"),
    "黑白设备执行": ("driver_colour", "黑白"),
    "彩色设备执行": ("driver_colour", "彩色"),
}


@dataclass
class ParsedStep:
    seq: int
    raw: str
    action: str  # click / assert / assert_not / assert_text / assert_toast / input / long_press / skip
    tag: str = ""  # 第一个【】= 元素标记
    element_key: str = ""  # 由 matcher 填入
    input_ref: str = ""  # 输入动作的第二个【】= 变量引用（无则为空）
    status: str = ""  # pass / fail / skip


@dataclass
class Precondition:
    """前置条件 — 条件型/变量型/描述型。"""
    raw: str  # 原始文本内容（不含"前置条件【】"外壳）
    type: str  # "condition" | "variable" | "descriptive"
    kind: str = ""  # 条件型: 条件名  变量型: 变量键
    value: str = ""  # 变量型: 变量值
    operator: str = ""  # "eq" | "ge" | "in"
    expected: str = ""  # 期望值（条件型用）
    skip_reason: str = ""  # 不满足时的原因


@dataclass
class ParsedCase:
    title: str
    priority: str
    module: str
    steps: list[ParsedStep] = field(default_factory=list)
    preconditions: list[Precondition] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)
    row_number: int = 0
    skip_reason: str = ""  # 前置条件不满足时的跳过原因


def parse_steps(raw_text: str) -> list[ParsedStep]:
    """解析一个用例的操作步骤文本，返回结构化步骤列表。"""
    if not raw_text:
        return []

    lines = [l.strip() for l in str(raw_text).split("\n") if l.strip()]
    steps = []

    for line in lines:
        seq_match = _STEP_RE.match(line)
        seq = int(seq_match.group(1)) if seq_match else len(steps) + 1
        content = seq_match.group(2) if seq_match else line

        tags = _TAG_RE.findall(content)
        tag = tags[0] if tags else ""

        action = _detect_action(content, tag)

        # 输入动作提取第二个【】作为变量引用
        input_ref = ""
        if action == "input" and len(tags) >= 2:
            input_ref = tags[1]

        steps.append(ParsedStep(
            seq=seq,
            raw=line,
            action=action,
            tag=tag,
            input_ref=input_ref,
        ))

    return steps


def parse_preconditions(raw_text: str | None) -> tuple[list[Precondition], dict[str, str]]:
    """解析前置条件列，返回 (条件列表, 变量映射)。"""
    if not raw_text:
        return [], {}

    text = str(raw_text).strip()
    if not text:
        return [], {}

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    preconditions: list[Precondition] = []
    variables: dict[str, str] = {}

    for line in lines:
        # 提取所有【】内容
        tags = _TAG_RE.findall(line)
        if not tags:
            preconditions.append(Precondition(raw=line, type="descriptive"))
            continue

        content = tags[0]

        # 1. 条件型 — 关键字精确匹配
        if content in _CONDITION_KEYWORDS:
            field, expected = _CONDITION_KEYWORDS[content]
            operator = "in" if field.endswith("__in") else "eq"
            real_field = field.replace("__in", "")
            preconditions.append(Precondition(
                raw=content,
                type="condition",
                kind=content,
                operator=operator,
                expected=expected,
                skip_reason=f"前置条件不满足: 【{content}】",
            ))
            continue

        # 2. 条件型 — 版本检查
        if _VERSION_COND_RE.match(content):
            version = content.replace("-版本执行", "")
            preconditions.append(Precondition(
                raw=content,
                type="condition",
                kind="version",
                operator="ge",
                expected=version,
                skip_reason=f"前置条件不满足: 固件版本 < {version}",
            ))
            continue

        # 3. 变量型 — 输入键-值
        if content.startswith("输入"):
            inner = content[2:]
            dash_idx = inner.find("-")
            if dash_idx > 0:
                key = inner[:dash_idx]
                val = inner[dash_idx + 1:]
                variables[key] = val
                preconditions.append(Precondition(
                    raw=content,
                    type="variable",
                    kind=key,
                    value=val,
                ))
                continue
            preconditions.append(Precondition(raw=content, type="descriptive"))
            continue

        # 4. 描述型
        preconditions.append(Precondition(raw=content, type="descriptive"))

    return preconditions, variables


def _detect_action(text: str, tag: str) -> str:
    """根据文本中的关键词判断操作类型。"""
    for keyword, action in _ACTION_MAP.items():
        if keyword in text:
            return action
    if tag:
        return "click"
    return "skip"
