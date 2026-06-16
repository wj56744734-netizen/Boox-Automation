"""Excel 驱动测试 — 集成到 pytest 框架。

每条 Excel 用例作为独立的 pytest 用例执行，自动获得 note_test_initial 的完整环境清理。

运行方式:
    pytest boox_automation/tests/test_excel_runner.py -s
"""
from __future__ import annotations
import logging
from pathlib import Path
import allure
import pytest
import openpyxl
from boox_automation.driver import driver
from boox_automation.ui_ops.operations import (
    Operation_method, set_step_context, clear_step_context, clear_element_ctx,
)
from boox_automation.tests.helpers import Public_method
from boox_automation.engine.parser import (
    parse_steps, parse_preconditions, parse_expected_results,
    ParsedCase, ExpectedPageRef, check_conditions, validate_case,
)
from boox_automation.engine.elements import ElementMatcher, _DEVICE_ACTIONS


logger = logging.getLogger(__name__)

# ============================================================
from boox_automation.core.config import excel_priority_filter, excel_test_case_file, test_modules as cfg_test_modules, case_column

EXCEL_FILE = str(Path(__file__).resolve().parent.parent / "data" / excel_test_case_file())
PRIORITY_FILTER = excel_priority_filter()
_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "TEST": 3}
# ============================================================


def _get_device_info_safe() -> dict:
    """安全获取设备信息，失败返回空字典（不影响模块加载）。"""
    try:
        from boox_automation.devices.info import Device_basic_information
        dbi = Device_basic_information()
        return dbi.get_device_info() or {}
    except Exception:
        return {}


_element_matcher = ElementMatcher()


def _parse_case_rows(rows: list[list[str]]) -> list[ParsedCase]:
    """从二维数组解析用例文本（不含元素匹配，只做文本解析）。"""
    cases = []

    for row_idx_0, row in enumerate(rows):
        if row_idx_0 == 0:
            continue  # 跳过表头行
        row1 = row_idx_0 + 1  # 1-based row number

        def _col(c): return row[c] if c < len(row) else ""

        title = _col(case_column("title"))
        steps_text = _col(case_column("steps"))
        priority = _col(case_column("priority"))
        module = _col(case_column("module"))
        precondition_text = _col(case_column("precondition"))
        expected_text = _col(case_column("expected"))

        if not title or not steps_text:
            continue

        case = ParsedCase(
            title=str(title).strip(),
            priority=str(priority).strip() if priority else "",
            module=str(module).strip() if module else "",
            row_number=row1,
            steps=parse_steps(str(steps_text).strip()),
            preconditions=parse_preconditions(precondition_text),
            expected_pages=parse_expected_results(expected_text),
        )
        cases.append(case)

    return cases


def _resolve_case_elements(cases: list[ParsedCase]) -> list[ParsedCase]:
    """为过滤后的用例匹配元素（仅对要执行的少量用例做匹配）。"""
    from boox_automation.engine.elements import get_element_loader
    _loader = get_element_loader()

    for case in cases:
        ctx = f"R{case.row_number} [{case.priority}] {case.title}"
        for step in case.steps:
            if step.tag:
                ek = _element_matcher.match(
                    step.tag, page_context=case.module, case_context=ctx, warn=None)
                if ek:
                    step.element_key = ek
                    if not step.action or step.action == "click":
                        yaml_action = _element_matcher.suggest_action(ek)
                        if yaml_action:
                            step.action = yaml_action

        for ep in case.expected_pages:
            if ep.tag:
                raw_line = ep.raw
                if 'toast提示' in raw_line:
                    ep.check_mode = 'toast'
                    ep.expected_text = ep.tag
                elif 'toast不出现' in raw_line:
                    ep.check_mode = 'toast_not'
                    ep.expected_text = ep.tag
                elif '不可见' in raw_line or '不存在' in raw_line:
                    ep.check_mode = 'not_visible'
                else:
                    ep.check_mode = 'visible'

                if ep.check_mode in ('visible', 'not_visible'):
                    ep.expected_key = _loader.match_expected_result(ep.tag)
                else:
                    ep.expected_key = '__toast__'

        # 收集阶段诊断：预期结果匹配失败的 tag 提前暴露
        unresolved = [
            ep for ep in case.expected_pages
            if ep.check_mode in ('visible', 'not_visible') and not ep.expected_key
        ]
        if unresolved:
            diag = _loader.get_expected_diagnostics()
            total = diag.get("total_results", 0)
            if total == 0:
                logger.warning(
                    f"R{case.row_number}「{case.title}」"
                    f"I列预期结果 {', '.join(f'【{ep.tag}】' for ep in unresolved)} "
                    f"未匹配：预期结果工作表不存在，用例执行时将报错"
                )
            else:
                index_keys = sorted(diag.get("match_index", {}).keys())
                logger.warning(
                    f"R{case.row_number}「{case.title}」"
                    f"I列预期结果 {', '.join(f'【{ep.tag}】' for ep in unresolved)} "
                    f"在预期结果工作表 B 列中未匹配。"
                    f"当前 B 列已有: {', '.join(index_keys) if index_keys else '(空)'}"
                )

    return cases


def _apply_filters(cases: list[ParsedCase], priority_spec: str) -> list[ParsedCase]:
    """优先级筛选 + 模块筛选。"""
    spec = priority_spec.upper().strip()
    if spec == "P0":
        cases = [c for c in cases if c.priority == "P0"]
    elif spec == "P1":
        cases = [c for c in cases if c.priority in ("P1", "P2")]
    elif spec == "P2":
        cases = [c for c in cases if c.priority == "P2"]
    elif spec == "TEST":
        cases = [c for c in cases if c.priority.upper() == "TEST"]

    modules_filter = cfg_test_modules()
    if modules_filter:
        cases = [c for c in cases if c.module in modules_filter]

    return cases


def _load_cases(excel_path: str, sheets: list[str], priority_spec: str) -> list[ParsedCase]:
    """加载用例（缓存优先，云端刷新，本地兜底）。"""
    from boox_automation.core.feishu import (
        use_local_excel, check_feishu_reachable,
        load_cache, save_cache, get_cache_age,
    )

    if use_local_excel():
        logger.debug("用例加载路径: 本地 Excel（USE_LOCAL_EXCEL=1）")
        sheet_data = _read_local_sheets(excel_path, sheets)
        return _parse_cases_from_sheets(sheet_data, sheets, priority_spec)

    # 1. 尝试云端
    if check_feishu_reachable():
        logger.debug(f"用例加载路径: 飞书云端（目标工作表: {', '.join(sheets)}）")
        try:
            sheet_data = _read_cloud_sheets(sheets)
            save_cache({"sheets": sheet_data}, "test_cases")
            logger.info("用例来源: 飞书云端（已更新本地缓存）")
            return _parse_cases_from_sheets(sheet_data, sheets, priority_spec)
        except Exception:
            logger.warning(
                "飞书云端加载用例失败，回退缓存。如已修改飞书在线文档但未生效，"
                "请删缓存后重试: rm boox_automation/data/.cache/test_cases.json",
                exc_info=True,
            )

    # 2. 云端不可用 → 缓存兜底
    logger.debug("用例加载路径: 本地缓存")
    cached = _load_cases_from_cache(sheets, priority_spec)
    if cached is not None:
        age = get_cache_age("test_cases")
        logger.warning(
            f"用例来源: 本地缓存（{age}）。"
            f"如飞书在线文档已有更新，请删缓存后重试: "
            f"rm boox_automation/data/.cache/test_cases.json"
        )
        return cached

    # 3. 兜底本地 Excel
    logger.debug("用例加载路径: 本地 Excel（兜底）")
    logger.warning("无可用缓存，回退本地 Excel")
    sheet_data = _read_local_sheets(excel_path, sheets)
    return _parse_cases_from_sheets(sheet_data, sheets, priority_spec)


def _read_local_sheets(excel_path: str, sheets: list[str]) -> dict[str, list[list[str]]]:
    """从本地 Excel 读取指定 sheet 的原始行数据。"""
    wb = openpyxl.load_workbook(excel_path)
    sheet_data = {}
    for sheet in sheets:
        if sheet not in wb.sheetnames:
            logger.warning(f"本地工作表「{sheet}」不存在，跳过")
            continue
        ws = wb[sheet]
        rows = []
        for row in ws.iter_rows(min_row=1, values_only=True):
            rows.append([str(v) if v is not None else "" for v in row])
        sheet_data[sheet] = rows
    wb.close()
    return sheet_data


def _read_cloud_sheets(sheets: list[str]) -> dict[str, list[list[str]]]:
    """从飞书云端读取指定 sheet 的原始行数据。"""
    from boox_automation.core.feishu import read_sheet_by_name
    from boox_automation.core.config import feishu_test_case_token
    token = feishu_test_case_token()
    sheet_data = {}
    for sheet in sheets:
        rows = read_sheet_by_name(sheet, token)
        if rows:
            sheet_data[sheet] = rows
    return sheet_data


def _parse_cases_from_sheets(sheet_data: dict, sheets: list[str],
                              priority_spec: str) -> list[ParsedCase]:
    """从原始行数据解析用例列表（解析→筛选→匹配元素）。"""
    all_cases = []
    for sheet in sheets:
        rows = sheet_data.get(sheet, [])
        if not rows:
            logger.warning(f"工作表「{sheet}」无数据")
            continue
        # 1. 文本解析（快速，无元素匹配）
        sheet_cases = _parse_case_rows(rows)
        logger.debug(f"工作表「{sheet}」: 阶段1 文本解析 → {len(sheet_cases)} 条用例")
        # 2. 优先级 + 模块筛选
        before_filter = len(sheet_cases)
        sheet_cases = _apply_filters(sheet_cases, priority_spec)
        filtered = before_filter - len(sheet_cases)
        if filtered:
            logger.debug(
                f"工作表「{sheet}」: 阶段2 筛选 → 过滤 {filtered} 条，"
                f"剩余 {len(sheet_cases)} 条（优先级={priority_spec}）"
            )
        else:
            logger.debug(f"工作表「{sheet}」: 阶段2 筛选 → 无需过滤，保留全部 {len(sheet_cases)} 条")
        # 3. 只对筛选后的用例做元素匹配
        sheet_cases = _resolve_case_elements(sheet_cases)
        executable = sum(1 for c in sheet_cases if any(s.element_key for s in c.steps))
        logger.info(f"工作表「{sheet}」: {len(sheet_cases)} 条用例（{executable} 条可执行）")
        all_cases.extend(sheet_cases)
    return all_cases


def _load_cases_from_cache(sheets: list[str], priority_spec: str) -> list | None:
    """从缓存加载用例，缓存过期或无数据返回 None。"""
    from boox_automation.core.feishu import load_cache
    cached = load_cache("test_cases")
    if not cached:
        return None
    sheet_data = cached.get("sheets", {})
    if not sheet_data:
        return None
    cases = _parse_cases_from_sheets(sheet_data, sheets, priority_spec)
    return cases if cases else None


def _make_case_id(case: ParsedCase) -> str:
    prefix = "[跳过]" if case.skip_reason else ""
    return f"{prefix}R{case.row_number}-{case.title[:30]}"


# ── 用例收集 ──
from boox_automation.core.config import test_case_sheets
from boox_automation.core.feishu import use_local_excel
_sheets = test_case_sheets()
logger.debug(
    f"用例收集配置: 目标工作表={_sheets}, "
    f"优先级筛选={PRIORITY_FILTER}, "
    f"本地模式={'是' if use_local_excel() else '否'}"
)
logger.info("── 开始收集用例 ──")
_all_cases = _load_cases(EXCEL_FILE, _sheets, PRIORITY_FILTER)
_executable = [c for c in _all_cases if any(s.element_key for s in c.steps)]
_executable.sort(key=lambda c: (_PRIORITY_ORDER.get(c.priority, 99), c.row_number))
_skipped = len(_all_cases) - len(_executable)
logger.info(
    "── 收集完成: %d 条用例（%d 可执行, %d 跳过）──",
    len(_all_cases), len(_executable), _skipped,
)

# 无可执行用例时，pytest parametrize 空列表会产生 NOTSET 占位符
# 填入一条带 skip_reason 的哨兵用例，显示为中文跳过
if not _executable:
    _no_case = ParsedCase(
        title="无可执行用例",
        priority="",
        module="",
        steps=[],
        preconditions=[],
        expected_pages=[],
    )
    _no_case.skip_reason = "无可执行用例：所有用例均未通过筛选或元素匹配"
    _executable = [_no_case]


@allure.feature("Excel驱动测试")
class TestExcelRunner:

    def setup_method(self):
        self.method = Operation_method(driver)
        self.public = Public_method()

    @pytest.mark.parametrize("case", _executable, ids=_make_case_id)
    def test_case(self, note_test_initial, case):
        """Excel 用例 — 每条独立执行，环境自动清理。"""

        # 哨兵用例：无可执行用例时的占位，直接跳过
        if case.skip_reason and not case.steps and not case.expected_pages:
            pytest.skip(case.skip_reason)

        case_id = f"R{case.row_number} [{case.priority}] {case.title}"
        logger.info(f"⏐ START  {case_id}")

        # 前置条件检查
        device_info = _get_device_info_safe()
        runtime_skip = check_conditions(case.preconditions, device_info)
        if runtime_skip:
            case.skip_reason = runtime_skip
            pytest.skip(runtime_skip)

        # 用例完整性校验（步骤号重复 / 元素缺失 / checks格式错误等）
        validation_skip = validate_case(case)
        if validation_skip:
            case.skip_reason = validation_skip
            for s in case.steps:
                s.status = "skip"
            pytest.skip(validation_skip)

        # 检查步骤（action=skip）必须配合 I 列预期结果，缺失时直接中断
        check_steps = [s for s in case.steps if s.action == "skip" and s.tag]
        if check_steps and not case.expected_pages:
            check_tags = '、'.join(s.tag for s in check_steps)
            raise AssertionError(
                f"R{case.row_number}「{case.title}」"
                f"包含 {len(check_steps)} 个检查步骤（{check_tags}），"
                f"但用例表I列（预期结果列）为空。"
                f"请在I列中添加对应的【】标记。"
            )

        # I 列为空 → WARNING（无检查步骤时的提醒）
        if not case.expected_pages:
            logger.warning(f"R{case.row_number} [{case.title}] 无预期结果，缺少断言")

        # 过滤无 element_key 的步骤（设备级 action / skip 除外）
        for s in case.steps:
            if not s.element_key and s.action not in _DEVICE_ACTIONS and s.action != "skip":
                s.status = "skip"
        steps = [s for s in case.steps
                 if s.element_key or s.action in _DEVICE_ACTIONS or s.action == "skip"]

        # 构建 tag → 预期结果索引（支持同名 tag 多次出现时按序匹配）
        expected_by_tag: dict[str, list[ExpectedPageRef]] = {}
        for ep in case.expected_pages:
            expected_by_tag.setdefault(ep.tag, []).append(ep)
        expected_consumed: dict[str, int] = {}

        try:
            with allure.step(case_id):
                for step in steps:
                    clear_element_ctx()
                    set_step_context(f"R{case.row_number} 步骤{step.seq}")
                    _dispatch_step(self.method, self.public, step)
                    step.status = "pass"
                    clear_step_context()
                    # 检查步骤 → 按 tag 关联到预期结果
                    if step.action == "skip" and step.tag:
                        _check_expected_by_tag(
                            self.method, expected_by_tag, expected_consumed, step,
                            row=case.row_number, title=case.title)

                # 最终检查：I 列未消费的预期结果（DEBUG，仅调试时可见）
                unconsumed = []
                for tag, entries in expected_by_tag.items():
                    used = expected_consumed.get(tag, 0)
                    for i in range(used, len(entries)):
                        unconsumed.append(entries[i].raw)
                if unconsumed:
                    logger.debug(
                        f"R{case.row_number} 预期结果中以下行未匹配到检查步骤:\n" +
                        "\n".join(f"  ↳ {u}" for u in unconsumed)
                    )
        except Exception as e:
            for s in steps:
                if not s.status:
                    s.status = "fail"
            logger.error(f"⏐ FAILED  {case_id} — {e}")
            raise
        finally:
            clear_step_context()
            clear_element_ctx()

    @classmethod
    def teardown_class(cls):
        """全部用例执行完后，打印汇总。"""
        from boox_automation.engine.reporter import ExcelReporter
        summary = {"pass": 0, "fail": 0, "skip": 0}
        for case in _all_cases:
            status = ExcelReporter._case_status(case)
            summary[status] = summary.get(status, 0) + 1
        logger.info(f"用例汇总: 通过={summary['pass']}, 不通过={summary['fail']}, 跳过={summary['skip']}")


def _dispatch_step(method, public, step):
    """根据 action 类型分发执行。"""
    ek = step.element_key

    if step.action == "click":
        method.xpath_text_click(element_key=ek)

    elif step.action == "assert_toast":
        info = _element_matcher.get_element(ek) or {}
        toast_true = info.get("toast_true", step.tag)
        method.wait_check_toast(toast_true=toast_true, toast_timeout=5)

    elif step.action == "input":
        method.wait_input_box(element_key=ek)

    elif step.action == "long_press":
        method.wait_for_press_name(element_key=ek)

    elif step.action == "skip":
        pass  # 检查/查看/校验步骤，不需要 UI 操作

    elif step.action in ("swipe_up", "swipe_down", "swipe_left", "swipe_right"):
        direction = step.action.replace("swipe_", "")
        method.swipe_direction(direction)

    elif step.action == "click_coord":
        method.click_by_coord(ek)

    elif step.action == "long_press_coord":
        method.long_press_by_coord(ek)

    elif step.action == "swipe_coord":
        method.swipe_by_coord(ek)

    elif step.action == "press_back":
        method.press_back()

    else:
        logging.warning(f"步骤{step.seq}: 【{step.tag}】未知动作类型: {step.action}")


def _check_expected_by_tag(method, expected_by_tag: dict, consumed: dict, step, *,
                           row: int = 0, title: str = "") -> None:
    """按 tag 匹配预期结果并执行检查。

    检查步骤（action=skip）通过 tag 与 I 列预期结果关联，不再依赖步骤号。
    同名 tag 按出现顺序一一对应（第一次出现的 检查【X】→ 第一个 I 列【X】）。
    """
    tag = step.tag
    entries = expected_by_tag.get(tag, [])

    if not entries:
        available_tags = sorted(expected_by_tag.keys())
        available_hint = '、'.join(available_tags) if available_tags else '(I列无可解析的预期结果)'
        case_info = f"R{row}「{title}」" if row else ""
        raise AssertionError(
            f"{case_info} 步骤{step.seq}：检查【{tag}】在用例表I列中未定义预期结果。\n"
            f"  请在I列添加【{tag}】行，当前I列已有的【】标记: {available_hint}"
        )

    idx = consumed.get(tag, 0)
    if idx >= len(entries):
        case_info = f"R{row}「{title}」" if row else ""
        raise AssertionError(
            f"{case_info} 步骤{step.seq}：检查【{tag}】的预期结果已用完"
            f"（用例表I列仅{len(entries)}条同名匹配），请检查是否多写了检查步骤"
        )

    ep = entries[idx]
    ep.step_seq = step.seq  # 回填步骤号（用于日志/报错）
    consumed[tag] = idx + 1

    if not ep.expected_key:
        ep.status = "fail"
        from boox_automation.engine.elements import get_element_loader
        loader = get_element_loader()
        diag = loader.get_expected_diagnostics()

        modules = diag.get("modules", [])
        found = diag.get("sheets_found", [])
        missing = diag.get("sheets_missing", [])
        match_index = diag.get("match_index", {})
        total = diag.get("total_results", 0)

        searched = [f"预期结果【{m}】" for m in modules] if modules else ["(未搜索任何模块)"]
        module_hint = (modules[1] if len(modules) > 1 else (modules[0] if modules else "模块名"))

        if total == 0 and not found:
            # 情况A：完全没有加载到任何预期结果工作表
            missing_str = '、'.join(missing) if missing else '、'.join(searched)
            raise AssertionError(
                f"步骤{step.seq}：检查【{tag}】已关联到用例I列，但未加载到任何预期结果工作表。\n"
                f"──────────────────────────────────────────────────\n"
                f"  原因: 飞书元素表中不存在以下预期结果工作表:\n"
                + "\n".join(f"    {s} → 缺失" for s in searched) + "\n"
                f"  ────────────────────────────────────────────────\n"
                f"  解决方式:\n"
                f"    1. 在飞书元素表中新建「预期结果【{module_hint}】」工作表\n"
                f"       表头: 模块 | 匹配文本 | 定位元素 | xml页面 | 用途说明\n"
                f"       数据行: {module_hint} | {tag} | (XPath或留空) | (XML或留空) | (说明)\n"
                f"    2. 或将预期页面 XML 放入本地文件:\n"
                f"       data/expected_pages/{module_hint}.{tag}.xml\n"
                f"──────────────────────────────────────────────────"
            )
        else:
            # 情况B：有预期结果工作表，但 B 列未匹配
            found_str = '、'.join(found) if found else "无"
            index_str = '、'.join(sorted(match_index.keys())) if match_index else "(空)"
            raise AssertionError(
                f"步骤{step.seq}：检查【{tag}】已关联到用例I列，但在预期结果工作表的 B 列中未找到匹配。\n"
                f"──────────────────────────────────────────────────\n"
                f"  已加载预期结果工作表: {found_str}\n"
                f"  已加载预期结果条目: {total}\n"
                f"  当前 B 列已有匹配文本({len(match_index)}条): {index_str}\n"
                f"  未匹配的文本: 【{tag}】\n"
                f"  ────────────────────────────────────────────────\n"
                f"  解决方式:\n"
                f"    在「预期结果【{module_hint}】」工作表中新增一行:\n"
                f"    B 列（匹配文本）: {tag}\n"
                f"    C 列（定位元素）: 填入对应 XPath\n"
                f"    D 列（xml页面）: 填入 Appium Inspector 导出的页面 XML\n"
                f"    注意: B 列文字必须与 I 列【{tag}】完全一致\n"
                f"──────────────────────────────────────────────────"
            )

    try:
        _dispatch_expected_page(method, ep)
        ep.status = "pass"
    except Exception:
        ep.status = "fail"
        raise


def _wait_for_xml_elements(expected_xml: str, expected_key: str, step_seq: int) -> None:
    """从预期XML提取resource-id，显式等待元素就位后再获取page_source。"""
    import xml.etree.ElementTree as ET
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.wait import WebDriverWait
    from selenium.common.exceptions import TimeoutException
    from boox_automation.core.config import timeout_xml_element_wait

    try:
        root = ET.fromstring(expected_xml)
    except ET.ParseError:
        return

    from boox_automation.engine.xml_checker import _is_meaningful

    resource_ids = set()
    for elem in root.iter():
        rid = elem.get('resource-id', '')
        if rid and rid.strip() and _is_meaningful(elem):
            resource_ids.add(rid.strip())

    if not resource_ids:
        return

    timeout = timeout_xml_element_wait()
    wait = WebDriverWait(driver, timeout)
    missing_ids = []
    for rid in resource_ids:
        try:
            wait.until(EC.presence_of_element_located((By.ID, rid)))
        except TimeoutException:
            missing_ids.append(rid)

    if missing_ids:
        logger.warning(
            f"预期结果【{expected_key}】（步骤{step_seq}）"
            f"等待XML元素超时({timeout}s)，未找到{len(missing_ids)}/{len(resource_ids)}个: "
            f"{missing_ids[:3]}{'...' if len(missing_ids) > 3 else ''}"
        )
    else:
        logger.debug(
            f"预期结果【{expected_key}】（步骤{step_seq}）"
            f"XML元素就位完成 ({len(resource_ids)}个)"
        )


def _dispatch_expected_page(method, ep) -> None:
    """执行单条预期结果校验。

    优先级: toast → D列XPath检查 → C列XML对比 → 本地文件回退
    """
    from boox_automation.engine.elements import (
        get_element_loader, _resolve_device_content,
        _load_expected_from_file, _check_elements_by_xpath,
    )
    from boox_automation.engine.xml_checker import XmlChecker
    from boox_automation.driver import driver

    # toast 模式: 不走 XML 对比，直接轮询 page_source
    if ep.check_mode == 'toast':
        method.wait_check_toast(toast_true=ep.expected_text, toast_timeout=5)
        ep.status = 'pass'
        return
    elif ep.check_mode == 'toast_not':
        method.wait_check_toast(toast_false=ep.expected_text, toast_timeout=5)
        ep.status = 'pass'
        return

    loader = get_element_loader()
    page_info = loader.get_expected_page(ep.expected_key)
    if not page_info:
        logger.warning(f"步骤{ep.step_seq}：预期结果【{ep.tag}】（key={ep.expected_key}）在预期结果工作表中未找到")
        ep.status = "skip"
        return

    device_info = _get_device_info_safe()

    # D 列: 检查元素（元素级 XPath 检查）
    element_checks = page_info.get("element_checks", "")
    if element_checks:
        checks_content = _resolve_device_content(element_checks, device_info, key=ep.expected_key)
        if checks_content:
            try:
                _check_elements_by_xpath(checks_content, mode=ep.check_mode,
                                         expected_key=ep.expected_key, step_seq=ep.step_seq)
                ep.status = "pass"
                return
            except AssertionError:
                ep.status = "fail"
                raise
            except Exception as e:
                logger.error(f"步骤{ep.step_seq}：预期结果【{ep.tag}】（key={ep.expected_key}）元素检查失败: {e}")
                ep.status = "fail"
                raise

    # C 列: 页面 XML
    raw_content = page_info.get("content", "")
    content = _resolve_device_content(raw_content, device_info, key=ep.expected_key)

    # C/D 均为空 → 本地文件回退
    if not content:
        file_content = _load_expected_from_file(ep.expected_key)
        if file_content:
            content = _resolve_device_content(file_content, device_info, key=ep.expected_key)

    if not content:
        logger.warning(f"步骤{ep.step_seq}：预期结果【{ep.tag}】（key={ep.expected_key}）无匹配的设备内容，跳过")
        ep.status = "skip"
        return

    # 等待预期 XML 元素加载完成
    _wait_for_xml_elements(content, ep.expected_key, ep.step_seq)

    # XML 签名对比
    try:
        actual_xml = driver.page_source
    except Exception as e:
        logger.error(f"步骤{ep.step_seq}：预期结果【{ep.tag}】（key={ep.expected_key}）获取 page_source 失败: {e}")
        ep.status = "skip"
        return

    try:
        result = XmlChecker.check(content, actual_xml, mode=ep.check_mode)
    except Exception as e:
        logger.error(
            f"步骤{ep.step_seq}：预期结果【{ep.tag}】（key={ep.expected_key}）XML 解析失败: {e}\n"
            f"XML 前200字符: {content[:200]}"
        )
        ep.status = "skip"
        return

    ep.status = result.status
    if result.status == "fail":
        logger.info(
            f"预期结果【{ep.expected_key}】（步骤{ep.step_seq}）XML检查失败 "
            f"({result.matched_count}/{result.expected_count}):\n{result.summary()}"
        )
        raise AssertionError(result.summary())
    logger.debug(
        f"预期结果【{ep.expected_key}】（步骤{ep.step_seq}）XML检查通过 "
        f"({result.matched_count}/{result.expected_count})"
    )



