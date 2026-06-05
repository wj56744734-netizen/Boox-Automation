"""用例执行器：将 ParsedStep 映射到 Operation_method 调用并执行。"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from Note_Automation.config import driver
from Note_Automation.Note_class.Note_class import Operation_method
from Note_Automation.Test_local_notes.Public_method import Public_method
from Note_Automation.Note_class.Note_element.element_loader import LOCATOR_TYPE_MAP

from Note_Automation.excel_framework.parser import ParsedCase, ParsedStep, Precondition
from Note_Automation.excel_framework.matcher import ElementMatcher
from Note_Automation.excel_framework.conditions import check_conditions

logger = logging.getLogger(__name__)


def _resolve_checks(checks: list) -> list[dict]:
    """将 matcher 返回的原始 checks 转为 check_multi_elements 可用格式。"""
    result = []
    for c in checks:
        loc = c["locator"]
        loc_type, loc_value = loc[0], loc[1]
        by = LOCATOR_TYPE_MAP.get(loc_type.lower(), LOCATOR_TYPE_MAP["xpath"])
        result.append({"locator": (by, loc_value), "text": c.get("text", "")})
    return result


class ExcelRunner:
    """读取 Excel 解析后的用例，逐步骤执行。"""

    def __init__(self, elements_dir: str | None = None, device_info: dict | None = None):
        self.method = Operation_method(driver)
        self.public = Public_method()
        self.matcher = ElementMatcher(elements_dir)
        self.device_info = device_info or {}
        self._current_variables: dict[str, str] = {}

        self._handlers = {
            "click": self._handle_click,
            "assert": self._handle_assert_visible,
            "assert_visible": self._handle_assert_visible,
            "assert_not": self._handle_assert_not,
            "assert_text": self._handle_assert_text,
            "assert_toast": self._handle_assert_toast,
            "input": self._handle_input,
            "long_press": self._handle_long_press,
            "dismiss": self._handle_dismiss,
        }

    def run_case(self, case: ParsedCase) -> ParsedCase:
        """执行一个用例：前置条件检查 → 变量注入 → 逐步骤执行。"""
        logger.info(f"[{case.priority}] {case.title}")

        # 设置当前变量表
        self._current_variables = case.variables

        # 1. 前置条件检查
        skip_reason = check_conditions(case.preconditions, self.device_info)
        if skip_reason:
            logger.info(f"跳过用例: {skip_reason}")
            for step in case.steps:
                step.status = "skip"
            # 用第一个步骤存储跳过原因（reporter 会读取）
            if case.steps:
                case.steps[0].status = "skip"
            case.skip_reason = skip_reason
            return case

        # 2. 匹配所有 element_key
        for step in case.steps:
            if step.tag:
                step.element_key = self.matcher.match(step.tag, page_context=case.module)
                if not step.action or step.action == "click":
                    yaml_action = self.matcher.suggest_action(step.element_key)
                    if yaml_action:
                        step.action = yaml_action

        # 3. 逐步骤执行
        for step in case.steps:
            self._run_step(step)
            if step.status == "fail":
                break

        return case

    def _run_step(self, step: ParsedStep) -> None:
        if step.action == "skip":
            step.status = "skip"
            return

        if step.action not in self._handlers:
            logger.warning(f"步骤{step.seq}: 不支持的操作类型 '{step.action}'")
            step.status = "skip"
            return

        if not step.tag:
            step.status = "skip"
            return

        if not step.element_key:
            logger.warning(f"步骤{step.seq}: 【{step.tag}】未匹配到元素")
            step.status = "skip"
            return

        try:
            handler = self._handlers[step.action]
            handler(step)
            step.status = "pass"
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"步骤{step.seq} 执行失败: {e}")
            step.status = "fail"

    def _handle_click(self, step: ParsedStep) -> None:
        self.method.xpath_text_click(element_key=step.element_key)

    def _handle_assert_visible(self, step: ParsedStep) -> None:
        info = self.matcher.get_element(step.element_key) or {}
        checks = info.get("checks")
        if checks:
            self.method.check_multi_elements(_resolve_checks(checks), element_key=step.element_key)
        else:
            self.method.xpath_text_click(element_key=step.element_key, should_click=False)

    def _handle_input(self, step: ParsedStep) -> None:
        # 确定输入内容：优先变量引用，其次从步骤文本解析
        input_text = ""
        if step.input_ref:
            # 变量引用 → 查变量表
            input_text = self._current_variables.get(step.input_ref, step.input_ref)
        if not input_text:
            import re
            text_match = re.search(r"输入(.+?)(?:字符|$)", step.raw)
            input_text = text_match.group(1) if text_match else "test"

        self.method.wait_input_box(element_key=step.element_key, name=input_text)

    def _handle_long_press(self, step: ParsedStep) -> None:
        self.method.wait_for_press_name(element_key=step.element_key)

    def _handle_assert_not(self, step: ParsedStep) -> None:
        try:
            self.method.xpath_text_click(element_key=step.element_key, should_click=False)
            raise AssertionError(f"元素【{step.tag}】应不存在但实际存在")
        except AssertionError:
            raise
        except Exception:
            pass

    def _handle_assert_text(self, step: ParsedStep) -> None:
        info = self.matcher.get_element(step.element_key) or {}
        expected = info.get("assert_text", step.tag)
        actual = self.method.obtain_element_text(element_key=step.element_key)
        if actual != expected:
            raise AssertionError(f"文本不匹配: 期望='{expected}', 实际='{actual}'")

    def _handle_assert_toast(self, step: ParsedStep) -> None:
        info = self.matcher.get_element(step.element_key) or {}
        toast_true = info.get("toast_true", step.tag)
        self.method.wait_check_toast(toast_true=toast_true, toast_timeout=5)

    def _handle_dismiss(self, step: ParsedStep) -> None:
        info = self.matcher.get_element(step.element_key) or {}
        dismiss_key = info.get("dismiss_with", "")
        checks = info.get("checks")

        try:
            if checks:
                self.method.check_multi_elements(_resolve_checks(checks), element_key=step.element_key)
            else:
                self.method.xpath_text_click(element_key=step.element_key, should_click=False)

            if dismiss_key:
                self.method.xpath_text_click(element_key=dismiss_key)
            else:
                self.method.xpath_text_click(element_key=step.element_key)
        except Exception:
            pass  # 弹窗不存在则跳过
