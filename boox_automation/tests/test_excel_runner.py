"""Excel 驱动测试 — 集成到 pytest 框架。

每条 Excel 用例作为独立的 pytest 用例执行，自动获得 note_test_initial 的完整环境清理。

运行方式:
    pytest boox_automation/tests/test_excel_runner.py -s
"""
from __future__ import annotations
import logging
import re
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
    ParsedCase, check_conditions, validate_case,
)
from boox_automation.engine.elements import ElementMatcher, _DEVICE_ACTIONS


logger = logging.getLogger(__name__)

# ============================================================
from boox_automation.core.config import excel_priority_filter, excel_test_case_file, test_modules as cfg_test_modules

EXCEL_FILE = str(Path(__file__).resolve().parent.parent / "data" / excel_test_case_file())
PRIORITY_FILTER = excel_priority_filter()
_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
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


def _parse_case_rows(rows: list[list[str]], priority_spec: str) -> list[ParsedCase]:
    """从二维数组解析用例列表（Excel 和飞书共用）。rows[0] 为表头。"""
    from boox_automation.engine.elements import get_element_loader
    _loader = get_element_loader()
    cases = []

    for row_idx_0, row in enumerate(rows):
        if row_idx_0 == 0:
            continue  # 跳过表头行
        row1 = row_idx_0 + 1  # 1-based row number

        # 安全取列值（补空字符串）
        def _col(c): return row[c] if c < len(row) else ""

        title = _col(6)        # G 列 (0-based: 6)
        steps_text = _col(9)   # J 列
        priority = _col(7)     # H 列
        module = _col(3)       # D 列
        precondition_text = _col(8)  # I 列
        expected_text = _col(10)     # K 列

        if not title or not steps_text:
            continue

        preconditions, variables = parse_preconditions(precondition_text)
        expected_results = parse_expected_results(expected_text)

        case = ParsedCase(
            title=str(title).strip(),
            priority=str(priority).strip() if priority else "",
            module=str(module).strip() if module else "",
            row_number=row1,
            steps=parse_steps(str(steps_text).strip()),
            preconditions=preconditions,
            variables=variables,
            expected_pages=expected_results,
        )

        ctx = f"R{row1} [{priority}] {title}"
        for step in case.steps:
            if step.tag:
                step.element_key = _element_matcher.match(
                    step.tag, page_context=case.module, case_context=ctx, warn=False)
                if step.element_key:
                    if not step.action or step.action == "click":
                        yaml_action = _element_matcher.suggest_action(step.element_key)
                        if yaml_action:
                            step.action = yaml_action

        for ep in case.expected_pages:
            if ep.tag:
                raw_tag = ep.tag
                # toast 模式: tag 含 toast提示/toast不出现 后缀
                if 'toast提示' in raw_tag:
                    ep.check_mode = 'toast'
                    ep.expected_text = raw_tag.replace('toast提示', '').strip()
                elif 'toast不出现' in raw_tag:
                    ep.check_mode = 'toast_not'
                    ep.expected_text = raw_tag.replace('toast不出现', '').strip()
                # 不可见模式
                elif '不可见' in raw_tag:
                    ep.check_mode = 'not_visible'
                    ep.tag = raw_tag.replace('不可见', '').strip()
                elif '不存在' in raw_tag:
                    ep.check_mode = 'not_visible'
                    ep.tag = raw_tag.replace('不存在', '').strip()
                else:
                    ep.check_mode = 'visible'
                    ep.tag = raw_tag

                # visible/not_visible → 查预期结果 sheet
                if ep.check_mode in ('visible', 'not_visible'):
                    ep.expected_key = _loader.match_expected_result(ep.tag)
                    if not ep.expected_key:
                        logger.warning(f"R{row1} 预期结果【{ep.tag}】未在预期结果 sheet 中匹配")
                # toast: tag 即期望文本，不查 sheet
                else:
                    ep.expected_key = '__toast__'

        cases.append(case)

    # 优先级筛选
    spec = priority_spec.upper().strip()
    if spec == "P0":
        cases = [c for c in cases if c.priority == "P0"]
    elif spec == "P1":
        cases = [c for c in cases if c.priority in ("P1", "P2")]
    elif spec == "P2":
        cases = [c for c in cases if c.priority == "P2"]

    # 模块筛选
    modules_filter = cfg_test_modules()
    if modules_filter:
        cases = [c for c in cases if c.module in modules_filter]

    return cases


def _load_cases_from_cloud(sheets: list[str], priority_spec: str) -> list[ParsedCase]:
    """从飞书电子表格加载用例（支持多个 sheet）。"""
    from boox_automation.core.feishu import read_sheet_by_name
    from boox_automation.core.config import feishu_test_case_token

    token = feishu_test_case_token()
    all_cases = []
    for sheet in sheets:
        rows = read_sheet_by_name(sheet, token)
        if not rows:
            logger.warning(f"飞书 sheet '{sheet}' 无数据")
            continue
        sheet_cases = _parse_case_rows(rows, priority_spec)
        logger.info(f"飞书 sheet '{sheet}': {len(sheet_cases)} 条用例")
        all_cases.extend(sheet_cases)
    return all_cases


def _load_cases_from_local(excel_path: str, sheets: list[str], priority_spec: str) -> list[ParsedCase]:
    """从本地 Excel 加载用例（支持多个 sheet）。"""
    wb = openpyxl.load_workbook(excel_path)
    all_cases = []
    for sheet in sheets:
        if sheet not in wb.sheetnames:
            logger.warning(f"本地 Sheet '{sheet}' 不存在，跳过")
            continue
        ws = wb[sheet]
        rows = []
        for row in ws.iter_rows(min_row=1, values_only=True):
            rows.append([str(v) if v is not None else "" for v in row])
        sheet_cases = _parse_case_rows(rows, priority_spec)
        all_cases.extend(sheet_cases)
    wb.close()
    return all_cases


def _load_cases(excel_path: str, sheets: list[str], priority_spec: str) -> list[ParsedCase]:
    """加载用例（缓存优先，云端刷新，本地兜底）。"""
    from boox_automation.core.feishu import (
        use_local_excel, check_feishu_reachable,
        load_cache, save_cache, get_cache_age,
    )

    if use_local_excel():
        return _load_cases_from_local(excel_path, sheets, priority_spec)

    # 1. 尝试云端
    if check_feishu_reachable():
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
    logger.warning("无可用缓存，回退本地 Excel")
    return _load_cases_from_local(excel_path, sheets, priority_spec)


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
    """从原始行数据解析用例列表。"""
    all_cases = []
    for sheet in sheets:
        rows = sheet_data.get(sheet, [])
        if not rows:
            logger.warning(f"sheet '{sheet}' 无数据")
            continue
        sheet_cases = _parse_case_rows(rows, priority_spec)
        logger.info(f"sheet '{sheet}': {len(sheet_cases)} 条用例")
        all_cases.extend(sheet_cases)
    return all_cases


def _load_cases_from_cloud(sheets: list[str], priority_spec: str) -> list[ParsedCase]:
    """从飞书电子表格加载用例（直接调用，不复用缓存逻辑）。"""
    sheet_data = _read_cloud_sheets(sheets)
    return _parse_cases_from_sheets(sheet_data, sheets, priority_spec)


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


# 模块加载时解析 Excel，生成 parametrize 参数
from boox_automation.core.config import feishu_test_case_sheets
_all_cases = _load_cases(EXCEL_FILE, feishu_test_case_sheets(), PRIORITY_FILTER)
_executable = [c for c in _all_cases if any(s.element_key for s in c.steps)]
_executable.sort(key=lambda c: (_PRIORITY_ORDER.get(c.priority, 99), c.row_number))


@allure.feature("Excel驱动测试")
class TestExcelRunner:

    def setup_method(self):
        self.method = Operation_method(driver)
        self.public = Public_method()

    @pytest.mark.parametrize("case", _executable, ids=_make_case_id)
    def test_case(self, note_test_initial, case):
        """Excel 用例 — 每条独立执行，环境自动清理。"""
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

        # K 列为空 → WARNING
        if not case.expected_pages:
            logger.warning(f"R{case.row_number} [{case.title}] 无预期结果，缺少断言")

        # 过滤无 element_key 的步骤（设备级 action 除外）
        for s in case.steps:
            if not s.element_key and s.action not in _DEVICE_ACTIONS:
                s.status = "skip"
        steps = [s for s in case.steps if s.element_key or s.action in _DEVICE_ACTIONS]

        try:
            with allure.step(case_id):
                for step in steps:
                    clear_element_ctx()
                    set_step_context(f"R{case.row_number} 步骤{step.seq}")
                    _dispatch_step(self.method, self.public, step, case.variables)
                    step.status = "pass"
                    clear_step_context()
                    _check_step_expected_pages(
                        self.method, case.expected_pages, step.seq)

                _check_step_expected_pages(
                    self.method, case.expected_pages, 0)
        except Exception:
            for s in steps:
                if not s.status:
                    s.status = "fail"
            logger.error(f"⏐ FAILED  {case_id}")
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


def _dispatch_step(method, public, step, variables: dict[str, str] | None = None):
    """根据 action 类型分发执行。"""
    ek = step.element_key
    vars_ = variables or {}

    if step.action == "click":
        method.xpath_text_click(element_key=ek)

    elif step.action == "assert_toast":
        info = _element_matcher.get_element(ek) or {}
        toast_true = info.get("toast_true", step.tag)
        method.wait_check_toast(toast_true=toast_true, toast_timeout=5)

    elif step.action == "input":
        # 确定输入内容：优先变量引用 → 步骤文本解析
        input_text = ""
        if step.input_ref:
            input_text = vars_.get(step.input_ref, step.input_ref)
        if not input_text:
            text_match = re.search(r"输入(.+?)(?:字符|$)", step.raw)
            input_text = text_match.group(1) if text_match else "test"
        method.wait_input_box(element_key=ek, name=input_text)

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


def _check_step_expected_pages(method, expected_pages: list, step_seq: int) -> None:
    """检查指定步骤的所有预期结果（step_seq=0 为最终检查）。"""
    for ep in expected_pages:
        if ep.step_seq != step_seq:
            continue
        if not ep.expected_key:
            ep.status = "skip"
            continue
        try:
            _dispatch_expected_page(method, ep)
            ep.status = "pass"
        except Exception:
            ep.status = "fail"
            raise


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
        logger.warning(f"预期结果【{ep.tag}】（key={ep.expected_key}）在预期结果 sheet 中未找到")
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
                logger.error(f"预期结果【{ep.tag}】（key={ep.expected_key}）元素检查失败: {e}")
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
        logger.warning(f"预期结果【{ep.tag}】（key={ep.expected_key}）无匹配的设备内容，跳过")
        ep.status = "skip"
        return

    # XML 签名对比
    try:
        actual_xml = driver.page_source
    except Exception as e:
        logger.error(f"预期结果【{ep.tag}】（key={ep.expected_key}）获取 page_source 失败: {e}")
        ep.status = "skip"
        return

    try:
        result = XmlChecker.check(content, actual_xml, mode=ep.check_mode)
    except Exception as e:
        logger.error(
            f"预期结果【{ep.tag}】（key={ep.expected_key}）XML 解析失败: {e}\n"
            f"XML 前200字符: {content[:200]}"
        )
        ep.status = "skip"
        return

    ep.status = result.status
    status_cn = "通过" if result.status == "pass" else "失败"
    logger.info(
        f"预期结果【{ep.expected_key}】（步骤{ep.step_seq}）XML检查{status_cn} "
        f"({result.matched_count}/{result.expected_count}):\n{result.summary()}"
    )
    if result.status == "fail":
        raise AssertionError(result.summary())



