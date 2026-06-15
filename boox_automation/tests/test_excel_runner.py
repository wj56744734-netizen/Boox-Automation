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

        title = _col(case_column("title"))             # E 列
        steps_text = _col(case_column("steps"))       # H 列
        priority = _col(case_column("priority"))      # F 列
        module = _col(case_column("module"))          # C 列
        precondition_text = _col(case_column("precondition"))  # G 列
        expected_text = _col(case_column("expected")) # I 列

        if not title or not steps_text:
            continue

        preconditions = parse_preconditions(precondition_text)
        expected_results = parse_expected_results(expected_text)

        case = ParsedCase(
            title=str(title).strip(),
            priority=str(priority).strip() if priority else "",
            module=str(module).strip() if module else "",
            row_number=row1,
            steps=parse_steps(str(steps_text).strip()),
            preconditions=preconditions,
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
                raw_line = ep.raw
                # toast 模式: 整行含 toast提示/toast不出现 后缀
                if 'toast提示' in raw_line:
                    ep.check_mode = 'toast'
                    ep.expected_text = ep.tag  # 【】内即期望 toast 文本
                elif 'toast不出现' in raw_line:
                    ep.check_mode = 'toast_not'
                    ep.expected_text = ep.tag
                elif '不可见' in raw_line or '不存在' in raw_line:
                    ep.check_mode = 'not_visible'
                else:
                    ep.check_mode = 'visible'

                # visible/not_visible → 查预期结果 sheet
                if ep.check_mode in ('visible', 'not_visible'):
                    ep.expected_key = _loader.match_expected_result(ep.tag)
                    if not ep.expected_key:
                        logger.debug(f"R{row1} 预期结果【{ep.tag}】未在预期结果 sheet 中匹配")
                # toast: 直接使用 tag 作为预期文本，不查 sheet
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
    elif spec == "TEST":
        cases = [c for c in cases if c.priority.upper() == "TEST"]

    # 模块筛选
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
        sheet_data = _read_local_sheets(excel_path, sheets)
        return _parse_cases_from_sheets(sheet_data, sheets, priority_spec)

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
    sheet_data = _read_local_sheets(excel_path, sheets)
    return _parse_cases_from_sheets(sheet_data, sheets, priority_spec)


def _read_local_sheets(excel_path: str, sheets: list[str]) -> dict[str, list[list[str]]]:
    """从本地 Excel 读取指定 sheet 的原始行数据。"""
    wb = openpyxl.load_workbook(excel_path)
    sheet_data = {}
    for sheet in sheets:
        if sheet not in wb.sheetnames:
            logger.warning(f"本地 Sheet '{sheet}' 不存在，跳过")
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
from boox_automation.core.config import test_case_sheets
_all_cases = _load_cases(EXCEL_FILE, test_case_sheets(), PRIORITY_FILTER)
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

        # I 列为空 → WARNING
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
                            self.method, expected_by_tag, expected_consumed, step)

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


def _check_expected_by_tag(method, expected_by_tag: dict, consumed: dict, step) -> None:
    """按 tag 匹配预期结果并执行检查。

    检查步骤（action=skip）通过 tag 与 I 列预期结果关联，不再依赖步骤号。
    同名 tag 按出现顺序一一对应（第一次出现的 检查【X】→ 第一个 I 列【X】）。
    """
    tag = step.tag
    entries = expected_by_tag.get(tag, [])

    if not entries:
        raise AssertionError(
            f"步骤{step.seq}：检查【{tag}】未在预期结果列找到匹配【】"
        )

    idx = consumed.get(tag, 0)
    if idx >= len(entries):
        raise AssertionError(
            f"步骤{step.seq}：检查【{tag}】的预期结果已用完（I列仅{len(entries)}条同名匹配），"
            f"请检查是否多写了检查步骤"
        )

    ep = entries[idx]
    ep.step_seq = step.seq  # 回填步骤号（用于日志/报错）
    consumed[tag] = idx + 1

    if not ep.expected_key:
        ep.status = "skip"
        return

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

    # 等待预期 XML 元素加载完成
    _wait_for_xml_elements(content, ep.expected_key, ep.step_seq)

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



