"""步骤解析器：从 Excel 操作步骤文本中提取【】标记和动作类型。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_TAG_RE = re.compile(r"【(.+?)】")
_STEP_RE = re.compile(r"(\d+)[\.\、](.*)")
_VERSION_COND_RE = re.compile(r"^\d+\.\d+\.\d+-版本执行$")

# ---- 条件型前置：关键字 → (设备字段, 操作符, 期望值) ----
# 同时兼容旧 _CONDITION_KEYWORDS 格式（前缀 __in 表 in 操作）

_COND_SPEC: dict[str, tuple[str, str, str]] = {
    "国内设备执行": ("device_region", "eq", "国内"),
    "海外设备执行": ("device_region", "in", "海外,全球"),
    "平板设备执行": ("devices_reader", "eq", "平板"),
    "阅读器设备执行": ("devices_reader", "eq", "阅读器"),
    "黑白设备执行": ("driver_colour", "eq", "黑白"),
    "彩色设备执行": ("driver_colour", "eq", "彩色"),
}

# 向后兼容：旧 _CONDITION_KEYWORDS 格式 (字段, 期望值)，in 操作通过 __in 后缀编码
_CONDITION_KEYWORDS = {
    k: (f"{v[0]}__in" if v[1] == "in" else v[0], v[2])
    for k, v in _COND_SPEC.items()
}


@dataclass
class ParsedStep:
    seq: int
    raw: str
    action: str  # 解析阶段: click / skip；运行时由元素表 D 列覆盖
    tag: str = ""  # 第一个【】= 元素标记
    element_key: str = ""  # 由 matcher 填入
    status: str = ""  # pass / fail / skip


@dataclass
class Precondition:
    """前置条件 — 条件型/清理型/描述型。"""
    raw: str  # 原始文本内容（不含"前置条件【】"外壳）
    type: str  # "condition" | "cleanup" | "descriptive"
    kind: str = ""  # 条件型: 条件名  清理型: 清理类型
    value: str = ""  # 清理型: 操作参数
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
    expected_pages: list[ExpectedPageRef] = field(default_factory=list)
    row_number: int = 0
    skip_reason: str = ""  # 前置条件不满足时的跳过原因


@dataclass
class ExpectedPageRef:
    """预期结果 — 关联到预期结果 sheet 中的页面 XML。

    断言类型（可见/不可见/toast/无toast）由预期结果 Sheet E 列（操作）唯一决定。
    """
    step_seq: int           # 步骤号
    tag: str                # 【】内的文本
    expected_key: str = ""  # 预期结果 sheet 中的 key
    raw: str = ""           # 原始行
    status: str = ""        # pass / fail / skip


def parse_steps(raw_text: str) -> list[ParsedStep]:
    """解析一个用例的操作步骤文本，返回结构化步骤列表。"""
    if not raw_text:
        return []

    lines = [l.strip() for l in str(raw_text).split("\n") if l.strip()]
    steps = []

    for line in lines:
        seq_match = _STEP_RE.match(line)
        seq = int(seq_match.group(1)) if seq_match else len(steps) + 1
        content = (seq_match.group(2) if seq_match else line).strip()

        tags = _TAG_RE.findall(content)
        tag = tags[0] if tags else ""

        action = _detect_action(content, tag)

        steps.append(ParsedStep(
            seq=seq,
            raw=line,
            action=action,
            tag=tag,
        ))

    return steps


def parse_preconditions(raw_text: str | None) -> list[Precondition]:
    """解析前置条件列，返回条件列表。"""
    if not raw_text:
        return []

    text = str(raw_text).strip()
    if not text:
        return []

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    preconditions: list[Precondition] = []

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

        # 3. 清理型 — 需在 fixture 阶段执行
        if content in ("清理应用数据", "清理存储文件"):
            kind = "app_data" if content == "清理应用数据" else "storage_files"
            preconditions.append(Precondition(
                raw=content,
                type="cleanup",
                kind=kind,
            ))
            continue

        # 4. 描述型（保留完整行文本，【】只是内联引用非条件关键字）
        preconditions.append(Precondition(raw=line, type="descriptive"))

    return preconditions


def has_cleanup(preconditions: list, kind: str) -> bool:
    """检查前置条件中是否包含指定清理类型。kind: 'app_data' | 'storage_files'"""
    return any(pc.type == "cleanup" and pc.kind == kind for pc in preconditions)


def _detect_action(text: str, tag: str) -> str:
    """根据文本中的关键词判断操作类型。

    操作类型由元素表 D 列（操作）唯一决定，解析阶段只区分 skip/click。
    """
    for prefix in ("检查", "查看", "校验"):
        if text.startswith(prefix):
            return "skip"
    if tag:
        return "click"
    return "skip"


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
    """检查固件版本 >= 期望版本。dev/非标版本视为最高，全通过。"""
    actual_str = str(device_info.get("version_info", ""))
    match = re.search(r"(\d+\.\d+\.\d+)", actual_str)
    if not match:
        return True  # dev / userdebug 等非标版本，视为最高固件，全通过

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


def validate_case(case: ParsedCase) -> str | None:
    """校验用例完整性，有问题返回跳过原因，无问题返回 None。

    检查项：
      1. 步骤号是否重复（Excel 中编号错误）
      2. 含【】标记的步骤是否有未匹配到元素的情况
    """
    # 1. 步骤号重复检查
    seqs = [s.seq for s in case.steps if s.tag]
    seen: set[int] = set()
    dupes: set[int] = set()
    for seq in seqs:
        if seq in seen:
            dupes.add(seq)
        seen.add(seq)
    if dupes:
        return f"步骤号重复: {sorted(dupes)}，请检查操作步骤列的编号"

    # 2. 元素缺失检查（skip 无需 element_key）
    missing = [(s.seq, s.tag) for s in case.steps
               if s.tag and not s.element_key
               and s.action != "skip"]
    if missing:
        items = "、".join(f"步骤{n}【{t}】" for n, t in missing)
        return f"元素未匹配: {items}"

    return None


# ---- 预期结果解析 ----


def parse_expected_results(raw_text: str | None) -> list[ExpectedPageRef]:
    """解析预期结果列。

    格式: 每行包含【预期结果匹配文本】，位置不限。
    不含【】的行视为文档描述，跳过。
    I 列为空 → 返回空列表（兼容老用例）。

    step_seq 在执行时通过 tag 匹配到 H 列的检查步骤后回填。
    """
    if not raw_text:
        return []

    text = str(raw_text).strip()
    if not text:
        return []

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    results = []

    for line in lines:
        tags = _TAG_RE.findall(line)
        if not tags:
            continue  # 不含【】的行视为描述，跳过

        tag = tags[0].strip()
        results.append(ExpectedPageRef(
            step_seq=0,  # 占位，执行时按 tag 匹配后回填
            tag=tag,
            raw=line,
        ))

    return results
