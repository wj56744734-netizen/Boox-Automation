from __future__ import annotations

import contextvars
from functools import wraps
import logging
import sys
import time
from pathlib import Path
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException,
    ElementNotInteractableException,
    InvalidSessionIdException,
    WebDriverException,
)
import allure
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from appium.webdriver.common.touch_action import TouchAction

from boox_automation.ui_ops.element_catalog import describe as _describe_locator

# 仓库根目录，用于将绝对路径缩短为相对路径
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _short_path(p: str) -> str:
    """将绝对路径转为相对于仓库根的短路径，失败则返回原路径。"""
    try:
        return str(Path(p).resolve().relative_to(_REPO_ROOT))
    except ValueError:
        return p


# 仅以下异常类型才参与重试，其它（含 session 级失败）直接抛出
RETRYABLE_EXCEPTIONS = (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException,
    ElementNotInteractableException,
)

# 会话级异常：直接放弃，避免在断开的 driver 上空转
SESSION_FATAL_EXCEPTIONS = (InvalidSessionIdException,)
# 兜底关键字（不同 selenium/appium 版本对 session 失效的异常类名不一致，用消息匹配兜住）
SESSION_FATAL_KEYWORDS = (
    "NoSuchDriverException",
    "invalid session id",
    "session is not created",
    "Instrumentation process is not running",
)


# Thread/asyncio-safe context for propagating element_key through internal call chains.
_element_ctx: contextvars.ContextVar = contextvars.ContextVar('_element_ctx', default=None)

# 步骤上下文：用例行号 + 步骤号，用于错误日志标题
_step_ctx: contextvars.ContextVar = contextvars.ContextVar('_step_ctx', default='')

_MAX_CTX_SIZE = 15  # 调用链最大长度，防止无限增长


def set_step_context(label: str):
    """设置当前步骤上下文标签，错误日志会自动附带。"""
    _step_ctx.set(label)


def clear_step_context():
    """清除步骤上下文。"""
    _step_ctx.set('')


def clear_element_ctx():
    """清除元素调用链上下文（每个步骤执行前调用）。"""
    _element_ctx.set(None)


def _push_element_ctx(method_name: str, element_key: str):
    """Push current method context so downstream errors carry the full call chain."""
    ctx = _element_ctx.get()
    if ctx is None:
        ctx = []
    ctx.append({'method': method_name, 'element_key': element_key})
    if len(ctx) > _MAX_CTX_SIZE:
        ctx = ctx[-_MAX_CTX_SIZE:]
    _element_ctx.set(ctx)


def _format_call_label(func_name, filtered_args):
    """生成调用标签。双参数格式化为 type="value"，单参数加引号。"""
    if not filtered_args:
        return func_name
    # (locator_type, locator_value) pairs → type="value"
    if len(filtered_args) == 2 and len(str(filtered_args[0])) < 20:
        return f'{func_name}({filtered_args[0]}="{filtered_args[1]}")'
    # single text arg → "text"
    if len(filtered_args) == 1:
        text = str(filtered_args[0])
        if len(text) > 50:
            text = text[:47] + "..."
        return f'{func_name}("{text}")'
    parts = []
    for arg in filtered_args:
        text = str(arg)
        if len(text) > 50:
            text = text[:47] + "..."
        parts.append(text)
    joined = ", ".join(parts)
    return f"{func_name}({joined})"


def _annotate_with_catalog(filtered_args):
    """如果 args 中包含已知 locator，从 catalog 取描述。"""
    for arg in filtered_args:
        desc = _describe_locator(str(arg))
        if desc:
            return desc
    return None


def _dedup_chain(methods: list[str]) -> list[str]:
    """压缩调用链中连续重复的方法名：['a','a','a','b','a','a'] → ['a(x3)','b','a(x2)']"""
    if not methods:
        return []
    result = []
    i = 0
    while i < len(methods):
        count = 1
        while i + count < len(methods) and methods[i + count] == methods[i]:
            count += 1
        result.append(f"{methods[i]}(x{count})" if count > 1 else methods[i])
        i += count
    return result


def _format_source(src: str) -> str:
    """格式化元素来源字符串。

    'feishu::手写笔记' → '飞书 → 手写笔记'
    '/path/to/elements.xlsx::手写笔记' → '本地 → 手写笔记'
    """
    if "::" in src:
        prefix, sheet = src.split("::", 1)
        if "feishu" in prefix:
            source_type = "飞书"
        else:
            source_type = "本地"
        return f"{source_type} → {sheet}"
    return src


# ------------------------------ 异常处理装饰器 ------------------------------
def retry_and_handle_exceptions(max_retries=None, retry_delay=None):
    """
    装饰器：捕获"可重试"的元素查找异常，重试 N 次仍失败则截图并抛出。
    - 会话级异常（InvalidSessionId / NoSuchDriver）直接抛出，不再重试
    - 其它非可重试异常也直接抛出，保留原始堆栈
    """
    from boox_automation.core.config import retry_max_attempts, retry_delay as cfg_retry_delay
    if max_retries is None:
        max_retries = retry_max_attempts()
    if retry_delay is None:
        retry_delay = cfg_retry_delay()

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            filtered_args = [arg for arg in args if not isinstance(arg, Operation_method)]
            call_label = _format_call_label(func.__name__, filtered_args)

            # 如果调用方传了 element_key，附到错误标签里
            ek = kwargs.get('element_key')
            if ek:
                call_label = f"{func.__name__}(element_key='{ek}')"
            elif not filtered_args:
                # 没有 positional args 时从 kwargs 提取定位信息
                xpath_val = kwargs.get('xpath')
                locator_val = kwargs.get('locator')
                name_val = kwargs.get('name')
                if xpath_val and xpath_val != By.XPATH:
                    display = str(xpath_val)
                    if len(display) > 60:
                        display = display[:57] + "..."
                    call_label = f"{func.__name__}(xpath='{display}')"
                elif locator_val:
                    call_label = f"{func.__name__}(locator='{locator_val}')"
                elif name_val:
                    call_label = f'{func.__name__}("{name_val}")'

            last_exc = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except SESSION_FATAL_EXCEPTIONS:
                    raise
                except RETRYABLE_EXCEPTIONS as e:
                    last_exc = e
                    logging.debug(
                        f"{call_label} 超时/未找到，重试 {attempt + 1}/{max_retries}"
                    )
                except WebDriverException as e:
                    # 部分 driver 异常无法明确分类：用消息匹配把"会话失效"过滤为致命
                    text = str(e)
                    if any(k in text for k in SESSION_FATAL_KEYWORDS):
                        raise
                    last_exc = e
                    logging.debug(
                        f"{call_label} WebDriver 异常，重试 {attempt + 1}/{max_retries}: {type(e).__name__}"
                    )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

            desc = _annotate_with_catalog(filtered_args)
            ctx_list = _element_ctx.get()
            ctx = ctx_list[-1] if ctx_list else None
            ctx_key = ctx.get('element_key') if ctx else None
            ek = kwargs.get('element_key')  # 直接传入的 element_key

            # 判断是否直接定位调用（有显式 by/locator 但无 element_key）
            direct_by = kwargs.get('by_method') or kwargs.get('by')
            direct_loc = kwargs.get('locator')
            is_direct_call = bool(direct_by and direct_loc and not ek)

            # 统一的元素标识（直接调用不继承 ctx_key）
            display_key = ek or (None if is_direct_call else ctx_key)

            # 步骤上下文
            step_label = _step_ctx.get()

            # 错误标题：有元素键用短格式，否则用函数签名
            if display_key:
                title = f"元素查找失败「{display_key}」（重试 {max_retries} 次）"
            else:
                title = f"{call_label} 在 {max_retries} 次重试后仍失败"
            if step_label:
                title = f"[{step_label}] {title}"
            lines = [title]

            # 定位信息分行显示
            def _append_locator_lines(loc_type, loc_value):
                lines.append(f"  ↳ 定位方式: {loc_type}")
                lines.append(f"  ↳ 定位值:   {loc_value}")

            if is_direct_call:
                _append_locator_lines(direct_by, direct_loc)
                if ctx_key:
                    lines.append(f"  ↳ 容器元素: {ctx_key}")
            elif ek:
                try:
                    info = args[0].get_element(ek)
                    loc = info.get('locator')
                    if loc and len(loc) == 2:
                        _append_locator_lines(loc[0], loc[1])
                except Exception:
                    pass
            elif ctx_key:
                try:
                    info = args[0].get_element(ctx_key)
                    loc = info.get('locator')
                    if loc and len(loc) == 2:
                        _append_locator_lines(loc[0], loc[1])
                except Exception:
                    pass
            else:
                xpath_val = kwargs.get('xpath')
                locator_val = kwargs.get('locator')
                if xpath_val and xpath_val != By.XPATH:
                    _append_locator_lines("xpath", xpath_val)
                elif locator_val:
                    _append_locator_lines("locator", locator_val)

            # 元素键 + 来源
            if display_key:
                label = "元素键" if ek else "容器元素"
                lines.append(f"  ↳ {label}: {display_key}")
                try:
                    src = args[0].get_element_source(display_key)
                    if src:
                        source_label = _format_source(src)
                        lines.append(f"  ↳ 数据来源: {source_label}")
                except Exception:
                    pass

            # 调用链：去重连续相同方法
            if ctx_list:
                raw_callers = [item['method'] for item in ctx_list if item.get('method')]
                while raw_callers and raw_callers[-1] == func.__name__:
                    raw_callers.pop()
                if raw_callers:
                    deduped = _dedup_chain(raw_callers)
                    chain = ' → '.join(deduped) + f' → {func.__name__}'
                    lines.append(f'  ↳ 调用链: {chain}')
                elif not is_direct_call:
                    lines.append(f'  ↳ 调用链: {func.__name__}')

            if desc:
                lines.append(f"  ↳ 元素用途: {desc}")

            from boox_automation.driver import driver
            from boox_automation.core.paths import safe_screenshot_path

            file_path = str(safe_screenshot_path(call_label))
            screenshot_ok = False
            try:
                driver.get_screenshot_as_file(file_path)
                screenshot_ok = True
                screenshot = driver.get_screenshot_as_png()
                attach_name = f"{call_label} 失败截图" + (f"｜{desc}" if desc else "")
                allure.attach(
                    screenshot,
                    name=attach_name,
                    attachment_type=allure.attachment_type.PNG,
                )
            except Exception as screenshot_err:
                logging.warning(f"截图失败：{screenshot_err}")

            if screenshot_ok:
                lines.append(f"  ↳ 截图: {_short_path(file_path)}")

            msg = "\n".join(lines)
            logging.error(msg)

            raise AssertionError(msg) from last_exc
        return wrapper
    return decorator


# ------------------------------ 基础元素等待类 ------------------------------
class Base_note_class:
    def __init__(self, driver):
        """初始化：接收Driver实例，设置默认超时时间（5秒），加载元素配置。"""
        self.driver = driver
        self.default_timeout = 5
        self._settle_seconds = 0.3  # 操作后 UI 沉降等待
        from boox_automation.engine.elements import get_element_loader
        self.element_loader = get_element_loader()

    # ---- 通用加固方法 ----

    def _settle_ui(self, seconds: float = None):
        """操作后等待 UI 动画/过渡完成。"""
        time.sleep(seconds if seconds is not None else self._settle_seconds)

    def wait_popup_gone(self, element_key: str, checks: list | None = None,
                        timeout: int = 2, max_retries: int = 1) -> bool:
        """等待弹窗消失。返回 True=已消失。单次轮询最多 {timeout} 秒。"""
        info = self.get_element(element_key)
        loc_type, loc_value = self._extract_locator(info, checks)
        if not loc_type or not loc_value:
            return True

        for attempt in range(max_retries):
            if self._poll_element_gone(loc_type, loc_value, timeout):
                return True
        return False

    def _poll_element_gone(self, loc_type, loc_value, timeout: int) -> bool:
        """轮询检查元素是否已从屏幕消失（原生等待，不走装饰器，不打 ERROR）。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                WebDriverWait(self.driver, 0.3).until(
                    EC.presence_of_element_located((loc_type, loc_value))
                )
                time.sleep(0.2)
            except TimeoutException:
                return True  # 元素已消失
        return False

    @staticmethod
    def _extract_locator(info: dict, checks: list | None) -> tuple:
        """从元素信息或 checks 中提取第一个 locator。"""
        if checks:
            first = checks[0] if isinstance(checks, list) and checks else None
            if first:
                loc = first["locator"]
                return loc[0], loc[1]
            return None, None
        loc = info.get("locator", (None, None))
        return (loc[0], loc[1]) if len(loc) >= 2 else (None, None)

    # ---- 元素访问 ----

    def get_element(self, element_key):
        """从元素定义获取元素信息（locator已转为(By, value)元组）。"""
        return self.element_loader.get_element_info(element_key)

    def get_element_source(self, element_key):
        """返回元素键所在的 YAML 文件路径，用于错误日志溯源。"""
        return self.element_loader.get_key_source(element_key)

    def get_element_line(self, element_key):
        """返回元素键来源（Sheet 名）。"""
        return self.element_loader.get_key_source(element_key)

    @staticmethod
    def escape_xpath_text(text):
        """XPath文本转义：安全处理单/双引号混合的情况。"""
        if '"' in text and "'" in text:
            parts = text.split('"')
            return "concat(" + ", ".join(
                ('"%s"' % p) if '"' not in p else ("'%s'" % p)
                for p in parts
            ) + ")"
        elif '"' in text:
            return "'%s'" % text
        else:
            return '"%s"' % text

    # ---- 定位解析与校验 ----

    def _resolve_locator(self, element_key=None, by=None, locator=None,
                         require_name=False, require_index=False):
        """
        统一解析定位信息。

        优先级: (by, locator) 直接使用 > element_key YAML 解析

        Returns: dict with keys: by, value, operation, name, index, parent_key, info
        """
        if by is not None and locator is not None:
            return {
                'by': by,
                'value': locator,
                'operation': '动态操作',
                'name': None,
                'index': None,
                'parent_key': None,
                'info': {'locator': (by, locator), 'operation': '动态操作'},
            }
        elif element_key is not None:
            info = self.get_element(element_key)
            loc = info.get('locator', (None, None))
            result = {
                'by': loc[0],
                'value': loc[1],
                'operation': info.get('operation', ''),
                'name': info.get('name'),
                'index': info.get('index'),
                'parent_key': info.get('parent_key'),
                'info': info,
            }
            if require_name and not result['name']:
                raise AssertionError(f"元素 '{element_key}' 在 YAML 中缺少 'name' 字段")
            if require_index and result['index'] is None:
                raise AssertionError(f"元素 '{element_key}' 在 YAML 中缺少 'index' 字段")
            return result
        else:
            raise AssertionError("必须提供 element_key 或 (by, locator)")

    @staticmethod
    def _validate_locator_type(locator_type, allowed_types, context=""):
        """验证定位类型是否合法。"""
        if locator_type not in allowed_types:
            allowed_str = ", ".join(str(t) for t in allowed_types)
            raise AssertionError(
                f"{context} 定位类型错误：需要 {allowed_str}，实际为 {locator_type}"
            )

    # ---- 安全点击 / 长按 / 输入 ----

    @staticmethod
    def _is_xpath_expression(value):
        """判断字符串是否是完整 XPath 表达式，而不是纯文本。"""
        if not isinstance(value, str):
            return False
        s = value.strip()
        return s.startswith('/') or (s.startswith('(') and '//' in s) or ('::' in s)

    def _safe_click(self, by, value, retries=None):
        """
        安全点击：自动处理 StaleElementReferenceException，并对 XPath 文本搜索做换行符回退。

        :param by: 定位类型（如 By.XPATH, By.ID 等）
        :param value: 定位值
        :param retries: 遇到 StaleElement 时的最大重试次数
        """
        from boox_automation.core.config import retry_element_click, retry_stale_element_delay
        if retries is None:
            retries = retry_element_click()
        tried_space_fallback = False
        for attempt in range(retries):
            try:
                if by == By.XPATH:
                    if self._is_xpath_expression(value):
                        element = self.xpath_element_is_clickable(xpath=value)
                    else:
                        element = self.xpath_check_timeout(value)
                else:
                    element = self.check_timeout(by_method=by, locator=value)
                element.click()
                self._settle_ui()
                logging.debug(f"[_safe_click] 点击成功: ({by}, {value})")
                return element
            except StaleElementReferenceException:
                logging.debug(f"[_safe_click] 元素已过时 (尝试 {attempt + 1}/{retries})，重新定位...")
                from boox_automation.core.config import retry_stale_element_delay
                time.sleep(retry_stale_element_delay())
            except (NoSuchElementException, TimeoutException) as e:
                if (by == By.XPATH
                        and not self._is_xpath_expression(value)
                        and '\n' in value
                        and not tried_space_fallback):
                    logging.debug(f"[_safe_click] 换行文本未命中，尝试空格替换")
                    value = value.replace('\n', ' ')
                    tried_space_fallback = True
                    continue
                raise
        raise AssertionError(f"点击失败：重试 {retries} 次后仍不可点击")

    def _safe_long_press_by_element(self, element, duration=2):
        """对已定位的元素执行长按（带 StaleElement 重试 + 沉降等待）。"""
        duration_ms = int(duration * 1000) if isinstance(duration, (int, float)) else duration
        for attempt in range(2):
            try:
                try:
                    _ = element.is_displayed()
                except StaleElementReferenceException:
                    element = self.driver.find_element(
                        By.XPATH, f'//*[@text="{element.text}"]'
                    )
                action = TouchAction(self.driver)
                action.long_press(element, duration=duration_ms).release().perform()
                self._settle_ui()
                return
            except StaleElementReferenceException:
                if attempt < 1:
                    time.sleep(0.5)
                    continue
                raise

    def _clear_input(self, element):
        """增强的输入框清空逻辑（跨平台兼容）。"""
        try:
            if hasattr(element, 'set_text'):
                element.set_text("")
            else:
                element.clear()
        except Exception:
            try:
                element.click()
                from selenium.webdriver.common.keys import Keys
                element.send_keys(Keys.CONTROL + "a")
                element.send_keys(Keys.DELETE)
            except Exception:
                pass

    # ---- XPath 等待方法 ----

    @staticmethod
    def _xpath_text(name):
        """生成稳健文本定位 XPath，同时兼容 text/content-desc。"""
        safe_name = str(name).replace("'", "\\'")
        primary = (
            f"//*[normalize-space(@text)='{safe_name}' "
            f"or normalize-space(@content-desc)='{safe_name}']"
        )
        fallback = (
            f"//*[contains(@text,'{safe_name}') "
            f"or contains(@content-desc,'{safe_name}')]"
        )
        return primary, fallback

    def _wait_for_xpath(self, element_key=None, xpath=By.XPATH, locator=None,
                        timeout=None, need_clickable=False):
        """
        等待 XPath 元素（支持三种模式）：
        1. 通过 element_key 从 YAML 配置获取
        2. 动态传入文本值：xpath=By.XPATH, locator="文本"
        3. 直接传入完整 XPath 字符串：xpath="//android..."
        """
        if isinstance(element_key, str) and element_key.startswith('//') and locator is None:
            xpath_locator = element_key
            text_value = xpath_locator
        elif isinstance(xpath, str) and xpath != By.XPATH and locator is None:
            xpath_locator = xpath
            text_value = xpath_locator
        elif xpath == By.XPATH and locator is not None:
            text_value = locator
            xpath_locator = f'//*[@text={self.escape_xpath_text(text_value)}]'
        elif element_key is not None:
            element = self.get_element(element_key)
            by_method, text_value = element['locator']
            if by_method != By.XPATH:
                raise ValueError(f"元素 '{element_key}' 的定位类型必须是 XPath，当前为 {by_method}")
            xpath_locator = f'//*[@text={self.escape_xpath_text(text_value)}]'
        else:
            raise ValueError("必须传入 element_key 或 (xpath, locator)")

        timeout = timeout or self.default_timeout
        condition = EC.element_to_be_clickable if need_clickable else EC.visibility_of_element_located
        target_element = WebDriverWait(self.driver, timeout).until(
            condition((By.XPATH, xpath_locator))
        )
        if need_clickable:
            WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath_locator)))
        logging.debug(f"[_wait_for_xpath] 成功等待元素：{text_value}")
        return target_element

    @retry_and_handle_exceptions()
    def xpath_element_is_clickable(self, element_key=None, xpath=By.XPATH,
                                    locator=None, timeout=None):
        """等待 XPath 元素可点击（支持 YAML / 动态 / 直接字符串）。"""
        if element_key is not None:
            _push_element_ctx('xpath_element_is_clickable', element_key)
        return self._wait_for_xpath(element_key, xpath, locator, timeout, need_clickable=True)

    @retry_and_handle_exceptions()
    def xpath_element_visible(self, element_key=None, xpath=By.XPATH,
                               locator=None, timeout=None):
        """等待 XPath 元素可见（支持 YAML / 动态 / 直接字符串）。"""
        if element_key is not None:
            _push_element_ctx('xpath_element_visible', element_key)
        return self._wait_for_xpath(element_key, xpath, locator, timeout, need_clickable=False)

    @retry_and_handle_exceptions()
    def xpath_check_timeout(self, name, timeout=None):
        """
        等待"文本匹配"的元素可点击（先精确，再 contains 兜底）。
        """
        timeout = timeout or self.default_timeout
        primary, fallback = self._xpath_text(name)
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, primary))
            )
        except TimeoutException:
            element = WebDriverWait(self.driver, max(timeout // 2, 2)).until(
                EC.element_to_be_clickable((By.XPATH, fallback))
            )
            logging.debug(f"[DEBUG] 文本定位用 contains 兜底命中：{name}")
        logging.debug(f"[DEBUG] 成功获取可点击元素（文本定位）：{name}")
        return element

    @retry_and_handle_exceptions()
    def xpath_check_display_timeout(self, name, timeout=None):
        """
        等待"文本匹配"的元素可见（先精确，再 contains 兜底）。
        """
        timeout = timeout or self.default_timeout
        primary, fallback = self._xpath_text(name)
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((By.XPATH, primary))
            )
        except TimeoutException:
            element = WebDriverWait(self.driver, max(timeout // 2, 2)).until(
                EC.visibility_of_element_located((By.XPATH, fallback))
            )
            logging.debug(f"[DEBUG] 文本定位用 contains 兜底命中：{name}")
        logging.debug(f"[DEBUG] 成功获取可见元素（文本定位）：{name}")
        return element

    @retry_and_handle_exceptions()
    def check_list_timeout(self, by_method=None, locator=None, timeout=None, *, element_key=None, by=None):
        """
        等待"定位器匹配"的元素列表可见。
        - 参数：by_method（定位方式）、locator（定位表达式）、timeout（超时时间）
        - 新用法: check_list_timeout(element_key="my_list")
        - 返回：可见的WebElement列表（失败由装饰器抛异常）
        """
        by_method = by_method if by_method is not None else by

        if element_key is not None:
            loc = self._resolve_locator(element_key)
            by_method, locator = loc['by'], loc['value']
        elif by_method is None or locator is None:
            raise AssertionError("必须提供 element_key 或 (by_method, locator)")

        timeout = timeout or self.default_timeout
        elements = WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_all_elements_located((by_method, locator))
        )
        logging.debug(f"[DEBUG] 成功获取元素列表（{by_method}：{locator}），共 {len(elements)} 个元素")
        return elements

    @retry_and_handle_exceptions()
    def check_timeout(self, by_method=None, locator=None, timeout=None, *, element_key=None, by=None):
        """
        等待"定位器匹配"的元素可点击。
        - 参数：by_method（定位方式）、locator（定位表达式）、timeout（超时时间）
        - 新用法: check_timeout(element_key="手写笔记.退出手写笔记")
        - 返回：可点击的WebElement（失败由装饰器抛异常）
        """
        by_method = by_method if by_method is not None else by

        if element_key is not None:
            loc = self._resolve_locator(element_key)
            by_method, locator = loc['by'], loc['value']
        elif by_method is None or locator is None:
            raise AssertionError("必须提供 element_key 或 (by_method, locator)")

        timeout = timeout or self.default_timeout
        element = WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by_method, locator))
        )
        logging.debug(f"[DEBUG] 成功获取可点击元素（{by_method}：{locator}）")
        return element

    @retry_and_handle_exceptions()
    def check_display_timeout(self, by_method=None, locator=None, timeout=None, *, element_key=None, by=None):
        """
        等待"定位器匹配"的元素可见。
        - 参数：by_method（定位方式）、locator（定位表达式）、timeout（超时时间）
        - 新用法: check_display_timeout(element_key="手写笔记.退出手写笔记")
        - 返回：可见的WebElement（失败由装饰器抛异常）
        """
        by_method = by_method if by_method is not None else by

        if element_key is not None:
            loc = self._resolve_locator(element_key)
            by_method, locator = loc['by'], loc['value']
        elif by_method is None or locator is None:
            raise AssertionError("必须提供 element_key 或 (by_method, locator)")

        timeout = timeout or self.default_timeout
        element = WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located((by_method, locator))
        )
        logging.debug(f"[DEBUG] 成功获取可见元素（{by_method}：{locator}）")
        return element


# ------------------------------ 元素操作方法类 ------------------------------
class Operation_method(Base_note_class):

    # ---- XPath 文本点击 ----

    def xpath_text_click(self, name=None, should_click=True, *, element_key=None):
        """
        通过"文本"定位元素，可选点击。
        - 旧用法: xpath_text_click("手写笔记")
        - 新用法: xpath_text_click(element_key="handwritten_note")
        - should_click: None=只校验存在不点击；其余真值=点击
        """
        if element_key is not None:
            _push_element_ctx('xpath_text_click', element_key)
            info = self.get_element(element_key)
            loc_type, text_value = info['locator']
            if loc_type != By.XPATH:
                raise AssertionError(f"元素 '{element_key}' 的定位类型必须是 XPath，当前为 {loc_type}")
            display = info.get('operation') or info.get('name') or text_value
            step_msg = f"点击「{display}」" if should_click else f"校验存在「{display}」"
        elif name is not None:
            _push_element_ctx('xpath_text_click', None)
            text_value = name
            step_msg = f"点击\"{name}\"" if should_click else f"校验存在\"{name}\""
        else:
            raise AssertionError("必须提供 name 或 element_key")

        with allure.step(step_msg):
            if should_click:
                return self._safe_click(By.XPATH, text_value)
            else:
                if self._is_xpath_expression(text_value):
                    return self.xpath_element_visible(xpath=text_value)
                return self.xpath_check_display_timeout(text_value)

    def check_multi_elements(self, checks: list[dict], *, element_key: str = "", timeout: int = None) -> bool:
        """多元素检查：逐个等待可见 + 可选文本校验。

        checks 格式: [{"locator": (By, value), "text": "期望文本"}, ...]
        文本为空则仅检查可见性。
        任一元素不可见或文本不匹配 → 抛出 AssertionError。
        """
        from boox_automation.core.config import timeout_default
        if timeout is None:
            timeout = timeout_default()
        if element_key:
            _push_element_ctx('check_multi_elements', element_key)
            info = self.get_element(element_key)
            display = info.get('operation') or info.get('name') or element_key
        else:
            display = "多元素检查"

        with allure.step(f"多元素检查「{display}」"):
            for i, check in enumerate(checks):
                by, loc = check["locator"]
                expected = check.get("text", "")

                el = self.check_timeout(by, loc, timeout=timeout)
                if not el or not el.is_displayed():
                    raise AssertionError(f"多元素断言[{i}]: ({by}, {loc}) 不可见")

                if expected:
                    actual = (el.text or "").strip()
                    # 飞书单元格中用户可能用字面量 \n 代替真实换行，统一标准化后比较
                    expected_normalized = expected.replace("\\n", "\n")
                    if actual != expected_normalized:
                        self._log_check_multi_error(
                            element_key, i, by, loc, expected_normalized, actual
                        )
                        raise AssertionError(
                            f"多元素断言[{i}]: 文本不匹配\n"
                            f"  ↳ 期望: {expected_normalized!r}\n"
                            f"  ↳ 实际: {actual!r}"
                        )

        return True

    def _log_check_multi_error(self, element_key, idx, by_method, locator,
                                expected, actual):
        """为 check_multi_elements 文本不匹配生成结构化日志 + 截图。"""
        lines = [f"check_multi_elements[{idx}] 文本不匹配"]
        lines.append(f"  ↳ 元素键: {element_key}")
        lines.append(f"  ↳ 定位方式: {by_method}")
        lines.append(f"  ↳ 定位值:   {locator}")
        lines.append(f"  ↳ 期望文本: {expected!r}")
        lines.append(f"  ↳ 实际文本: {actual!r}")

        try:
            src = self.get_element_source(element_key)
            if src:
                source_label = _format_source(src)
                lines.append(f"  ↳ 数据来源: {source_label}")
        except Exception:
            pass

        # 截图
        from boox_automation.driver import driver
        from boox_automation.core.paths import safe_screenshot_path
        file_path = str(safe_screenshot_path("check_multi_elements_text_mismatch"))
        try:
            driver.get_screenshot_as_file(file_path)
            lines.append(f"  ↳ 截图: {_short_path(file_path)}")
        except Exception:
            pass

        msg = "\n".join(lines)
        logging.error(msg)

    def xpath_parent_click(self, xpath=None, *, element_key=None, by=None, locator=None, should_click=True):
        """
        灵活 XPath 定位并点击（按优先级）：
        1. xpath_parent_click(xpath="//div[@class='parent']/button")
        2. xpath_parent_click(element_key="my_element")
        3. xpath_parent_click(by=By.XPATH, locator="//...")
        """
        if xpath is not None:
            _push_element_ctx('xpath_parent_click', None)
            final_by, final_locator = By.XPATH, xpath
            step_msg = f"父节点点击({final_by}, {final_locator})" if should_click else f"父节点校验({final_by}, {final_locator})"
        elif by is not None and locator is not None:
            _push_element_ctx('xpath_parent_click', None)
            final_by, final_locator = by, locator
            step_msg = f"父节点点击({final_by}, {final_locator})" if should_click else f"父节点校验({final_by}, {final_locator})"
        elif element_key is not None:
            _push_element_ctx('xpath_parent_click', element_key)
            info = self.get_element(element_key)
            final_by, final_locator = info['locator']
            display = info.get('operation') or info.get('name') or str(final_locator)
            step_msg = f"父节点点击「{display}」" if should_click else f"父节点校验「{display}」"
        else:
            raise AssertionError("必须提供 xpath、element_key 或 (by, locator) 之一")

        with allure.step(step_msg):
            if should_click:
                return self._safe_click(final_by, final_locator)
            else:
                if final_by == By.XPATH:
                    return self.xpath_element_visible(xpath=final_locator)
                else:
                    return self.check_display_timeout(by=final_by, locator=final_locator)

    # ---- 父子元素定位 ----

    def by_sub_index_click(self, by_method=None, locator=None,
                           by_method1=None, locator1=None,
                           index=0, should_click=True, *, element_key=None):
        """
        父元素下按索引定位子元素，可选点击。
        - 旧用法: by_sub_index_click(By.ID, "parent", By.CLASS_NAME, "child", 3)
        - 新用法: by_sub_index_click(element_key="toolbar_sort_icon")
        """
        if element_key is not None:
            _push_element_ctx('by_sub_index_click', element_key)
            info = self.get_element(element_key)
            parent_by, parent_loc = info['locator']
            child_info = info.get('child_locator')
            if not child_info:
                raise AssertionError(f"元素 '{element_key}' 缺少 'child_locator' 字段")
            child_by, child_loc = child_info
            child_index = index if index != 0 else info.get('index', 0)
            display = info.get('operation') or info.get('name') or str(child_loc)
            step_msg = f"子元素「{display}」"
        elif (by_method is not None and locator is not None
              and by_method1 is not None and locator1 is not None):
            parent_by, parent_loc = by_method, locator
            child_by, child_loc = by_method1, locator1
            child_index = index
            step_msg = f"子元素[{child_index}]({child_loc})"
        else:
            raise AssertionError(
                "必须提供 element_key 或 (by_method, locator, by_method1, locator1)")

        with allure.step(step_msg):
            try:
                parent_element = self.check_timeout(parent_by, parent_loc)
                if not parent_element:
                    logging.error(f"未找到父元素: {parent_loc}")
                    return None
                if not parent_element.is_displayed():
                    logging.error(f"父元素 {parent_loc} 不可见")
                    return None

                child_elements = parent_element.find_elements(child_by, child_loc)
                if not child_elements:
                    logging.error(f"在父元素 {parent_loc} 下未找到子元素: {child_loc}")
                    return None

                if child_index < 0 or child_index >= len(child_elements):
                    logging.error(f"子元素索引 {child_index} 越界，列表长度为 {len(child_elements)}")
                    return None

                target_element = child_elements[child_index]
                logging.debug(f"成功定位到子元素，索引: {child_index}，总数量: {len(child_elements)}")
                if should_click:
                    target_element.click()
                    logging.debug(f"已点击子元素，索引: {child_index}")
                return target_element
            except Exception as e:
                logging.error(f"定位子元素过程中发生错误: {str(e)}")
                return None

    def by_father_index_click(self, by_method=None, locator=None,
                               by_method1=None, locator1=None,
                               index=0, should_click=True, *, element_key=None):
        """
        父元素列表按索引选父元素，再定位子元素（默认选第一个子元素）。
        - 旧用法: by_father_index_click(By.ID, "parent", By.ID, "child", 0)
        - 新用法: by_father_index_click(element_key="dock_cover_3")
        """
        if element_key is not None:
            info = self.get_element(element_key)
            parent_by, parent_loc = info['locator']
            child_info = info.get('child_locator')
            if not child_info:
                raise AssertionError(f"元素 '{element_key}' 缺少 'child_locator' 字段")
            child_by, child_loc = child_info
            parent_index = index if index != 0 else info.get('index', 0)
            display = info.get('operation') or info.get('name') or str(child_loc)
            step_msg = f"父级下标[{parent_index}]「{display}」"
        elif (by_method is not None and locator is not None
              and by_method1 is not None and locator1 is not None):
            parent_by, parent_loc = by_method, locator
            child_by, child_loc = by_method1, locator1
            parent_index = index
            step_msg = f"父级下标[{parent_index}]({child_loc})"
        else:
            raise AssertionError(
                "必须提供 element_key 或 (by_method, locator, by_method1, locator1)")

        with allure.step(step_msg):
            parent_elements = self.check_list_timeout(parent_by, parent_loc)
            if parent_index >= len(parent_elements):
                logging.error(f"下标({parent_index})越界，无法获取元素")
                logging.error(f"当前列表长度 ({len(parent_elements)})")
                return False

            parent_element = parent_elements[parent_index]
            if not parent_element.is_displayed():
                logging.error(f"未找到 {parent_loc} 父元素")
                return False

            child_element = parent_element.find_elements(child_by, child_loc)
            if child_element is not None:
                self.check_timeout(child_by, child_loc)
                if should_click:
                    if len(child_element) == 0:
                        logging.error(f"未找到 {child_loc} 子元素")
                        return False
                    child_element[0].click()
                    return True
                return child_element[0].text
            return False

    def by_father_sub_index_click(self, by_method=None, locator=None,
                                   by_method1=None, locator1=None,
                                   index=0, index_1=0, should_click=True, *, element_key=None):
        """
        父元素列表+子元素列表双重索引定位，可选点击。
        - 旧用法: by_father_sub_index_click(By.ID, "parent", By.ID, "child", 2, 0)
        - 新用法: by_father_sub_index_click(element_key="dock_cover_3")
        """
        if element_key is not None:
            info = self.get_element(element_key)
            parent_by, parent_loc = info['locator']
            child_info = info.get('child_locator')
            if not child_info:
                raise AssertionError(f"元素 '{element_key}' 缺少 'child_locator' 字段")
            child_by, child_loc = child_info
            parent_index = index if index != 0 else info.get('index', 0)
            sub_index = index_1 if index_1 != 0 else info.get('sub_index', 0)
            display = info.get('operation') or info.get('name') or str(child_loc)
            step_msg = f"父级下标[{parent_index}]子元素[{sub_index}]「{display}」"
        elif (by_method is not None and locator is not None
              and by_method1 is not None and locator1 is not None):
            parent_by, parent_loc = by_method, locator
            child_by, child_loc = by_method1, locator1
            parent_index = index
            sub_index = index_1
            step_msg = f"父级下标[{parent_index}]子元素[{sub_index}]({child_loc})"
        else:
            raise AssertionError(
                "必须提供 element_key 或 (by_method, locator, by_method1, locator1)")

        with allure.step(step_msg):
            parent_elements = self.check_list_timeout(parent_by, parent_loc)
            if parent_index >= len(parent_elements):
                logging.error(f"下标({parent_index})越界，无法获取元素")
                logging.error(f"当前列表长度 ({len(parent_elements)})")
                return False

            parent_element = parent_elements[parent_index]
            if not parent_element.is_displayed():
                logging.error(f"未找到 {parent_loc} 父元素")
                return False

            child_element = parent_element.find_elements(child_by, child_loc)
            if child_element is not None:
                self.check_timeout(child_by, child_loc)
                if sub_index >= len(child_element):
                    logging.error(f"下标({sub_index})越界，无法获取元素")
                    logging.error(f"当前列表长度 ({len(child_element)})")
                    return False
                if should_click:
                    if len(child_element) == 0:
                        logging.error(f"未找到 {child_loc} 子元素")
                        return False
                    child_element[sub_index].click()
                    return True
                return child_element[sub_index].text
            return False

    # ---- ID/CLASS_NAME 定位 ----

    def by_element_click(self, by_method=None, locator=None, should_click=True, *, element_key=None):
        """
        直接定位元素，可选点击。
        - 旧用法: by_element_click(By.ID, "com.onyx:id/back_icon")
        - 新用法: by_element_click(element_key="手写笔记.退出手写笔记")
        """
        if element_key is not None:
            _push_element_ctx('by_element_click', element_key)
            loc = self._resolve_locator(element_key)
            locator_type, locator_value = loc['by'], loc['value']
            self._validate_locator_type(locator_type, (By.ID, By.CLASS_NAME),
                                        f"by_element_click[{element_key}]")
            step_msg = f"「{loc['operation']}」"
        elif by_method is not None and locator is not None:
            _push_element_ctx('by_element_click', None)
            locator_type, locator_value = by_method, locator
            step_msg = f"点击({locator_type}, {locator_value})"
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator)")

        with allure.step(step_msg):
            if should_click:
                return self._safe_click(locator_type, locator_value)
            else:
                element = self.check_timeout(locator_type, locator_value)
                return element

    # ---- 按名称匹配列表元素 ----

    def by_name_click(self, by_method=None, locator=None, name=None, should_click=True, *, element_key=None):
        """
        元素列表中按"文本匹配"定位，可选点击（strip 后比较，避免空白差异）。
        - 旧用法: by_name_click(By.ID, "com.onyx:id/title", "会议-1")
        - 新用法: by_name_click(element_key="note_title_regular")
        """
        if element_key is not None:
            _push_element_ctx('by_name_click', element_key)
            loc = self._resolve_locator(element_key, require_name=True)
            locator_type, locator_value = loc['by'], loc['value']
            target_name = name or loc['name']
            step_msg = f"列表{'点击' if should_click else '查找'}「{target_name}」"
        elif by_method is not None and locator is not None:
            _push_element_ctx('by_name_click', None)
            locator_type, locator_value = by_method, locator
            if not name:
                raise AssertionError("动态元素必须传入 name 参数")
            target_name = name
            step_msg = f"列表{'点击' if should_click else '查找'}\"{target_name}\""
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator, name)")

        with allure.step(step_msg):
            elements = self.check_list_timeout(locator_type, locator_value)
            target = ' '.join(str(target_name).split())
            for element in elements:
                try:
                    actual = ' '.join((element.text or "").split())
                except StaleElementReferenceException:
                    continue
                if actual == target:
                    logging.debug(f"[DEBUG] 匹配到文本 '{target}' 的元素")
                    if should_click:
                        element.click()
                    return element
            logging.error(f"在 {locator_value} 列表中未匹配到文本：{target}")
            return False

    # ---- 按索引+名称联合定位 ----

    def by_index_name_click(self, by_method=None, locator=None, name=None,
                            index=0, should_click=True, *, element_key=None):
        """
        元素列表中按"索引+文本校验"定位，可选点击。
        - 旧用法: by_index_name_click(By.CLASS_NAME, "android.widget.TextView", "常规", 4)
        - 新用法: by_index_name_click(element_key="template_regular_indexed")
        """
        if element_key is not None:
            loc = self._resolve_locator(element_key, require_name=True, require_index=True)
            locator_type, locator_value = loc['by'], loc['value']
            target_name = name or loc['name']
            target_index = index if index != 0 else loc['index']
            step_msg = f"下标[{target_index}]校验「{target_name}」"
        elif by_method is not None and locator is not None:
            locator_type, locator_value = by_method, locator
            target_name = name
            target_index = index
            if not target_name:
                raise AssertionError("动态元素必须传入 name 参数")
            step_msg = f"下标[{target_index}]校验\"{target_name}\""
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator, name)")

        with allure.step(step_msg):
            elements = self.check_list_timeout(locator_type, locator_value)
            if not elements:
                logging.error(f"未找到 {locator_value} 元素")
                return False
            if target_index < len(elements):
                element = elements[target_index]
                if should_click:
                    element.click()
                if element.text != target_name:
                    logging.debug(f"[DEBUG] 校验元素文本：预期 {target_name}，实际 {element.text}")
                    logging.error(f"未找到 '{target_name}' 元素")
                    return False
                return True
            else:
                logging.error(f"下标({target_index})越界，无法获取元素")
                return False

    # ---- 按索引定位 ----

    def by_index_click(self, by_method=None, locator=None, index=0, should_click=True, *, element_key=None):
        """
        元素列表中按"索引"定位，可选点击（需元素可点击）。
        - 旧用法: by_index_click(By.ID, "com.onyx:id/textviewItem", 0)
        - 新用法: by_index_click(element_key="first_note_title")
        """
        if element_key is not None:
            loc = self._resolve_locator(element_key, require_index=True)
            locator_type, locator_value = loc['by'], loc['value']
            target_index = index if index != 0 else loc['index']
            display = loc.get('operation') or loc.get('name') or str(locator_value)
            step_msg = f"列表下标[{target_index}]「{display}」"
        elif by_method is not None and locator is not None:
            locator_type, locator_value = by_method, locator
            target_index = index
            step_msg = f"列表下标[{target_index}]({locator_value})"
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator)")

        with allure.step(step_msg):
            elements = self.check_list_timeout(locator_type, locator_value)
            if not elements:
                logging.error(f"未找到 {locator_value} 元素")
                return False
            if target_index < len(elements):
                element = elements[target_index]
                if should_click:
                    if element.is_enabled():
                        element.click()
                    else:
                        logging.error(f"元素不能点击")
                        return False
                return True
            else:
                logging.error(f"下标({target_index})越界，无法获取元素")
                return False

    # ---- Toast 检测 ----

    def wait_check_toast(self, toast_true=None, toast_false=None, toast_timeout=None,
                         *, toast_true_key=None, toast_false_key=None):
        """
        检查Toast弹窗：支持校验"预期Toast"和"异常Toast"。
        - 旧用法: wait_check_toast("保存成功", "保存失败", 5)
        - 新用法: wait_check_toast(toast_true_key="toast_save_success")
        """
        from boox_automation.core.config import get_int
        if toast_timeout is None:
            toast_timeout = get_int("toast.timeout", 5)
        if toast_true_key is not None:
            info = self._resolve_locator(toast_true_key)
            expected_toast_message = info.get('name') or info.get('value') or toast_true or ''
            step_msg = f"等待Toast「{expected_toast_message}」"
        elif toast_true is not None:
            expected_toast_message = toast_true
            step_msg = f"等待Toast\"{expected_toast_message}\""
        else:
            raise AssertionError("必须提供 toast_true 或 toast_true_key")

        if toast_false_key is not None:
            info = self._resolve_locator(toast_false_key)
            abnormal_toast_message = info.get('name') or info.get('value')
        else:
            abnormal_toast_message = toast_false

        with allure.step(step_msg):
            start_time = time.time()
            while time.time() - start_time < toast_timeout:
                page_source = self.driver.page_source
                if expected_toast_message in page_source:
                    return True
                elif abnormal_toast_message is not None:
                    if abnormal_toast_message in page_source:
                        return False
                time.sleep(1)
            return False

    # ---- 输入框 ----

    def wait_input_box(self, by_method=None, locator=None, name=None, *, element_key=None, hide_keyboard=True):
        """
        定位输入框并输入内容。
        - 旧用法: wait_input_box(By.ID, "com.onyx:id/search_et_input", "搜索词")
        - 新用法: wait_input_box(element_key="search_input")  # name 从 YAML 取
        - hide_keyboard=False 时跳过收起键盘（部分弹窗收起键盘后会关闭）
        """
        if element_key is not None:
            loc = self._resolve_locator(element_key)
            locator_type, locator_value = loc['by'], loc['value']
            input_text = name or loc.get('name')
            if not input_text:
                raise AssertionError(f"元素 '{element_key}' 未配置 'name' 字段且未传入 name 参数")
            display = loc.get('operation') or loc.get('name') or str(locator_value)
            step_msg = f"输入\"{input_text}\" →「{display}」"
        elif by_method is not None and locator is not None:
            locator_type, locator_value = by_method, locator
            input_text = name
            if not input_text:
                raise AssertionError("必须提供 name 参数（输入内容）")
            step_msg = f"输入\"{input_text}\" → ({locator_type}, {locator_value})"
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator, name)")

        with allure.step(step_msg):
            input_box = self.check_timeout(locator_type, locator_value)
            self._clear_input(input_box)
            if hasattr(input_box, 'set_text'):
                input_box.set_text(input_text)
            else:
                input_box.send_keys(input_text)
            self._settle_ui(0.2)

            # 验证输入内容是否正确写入
            try:
                actual = (input_box.get_attribute('text') or input_box.text or "").strip()
            except Exception:
                actual = ""
            if actual and actual != str(input_text).strip():
                logging.debug(f"输入验证失败: 期望='{input_text}' 实际='{actual}'，重试")
                self._clear_input(input_box)
                input_box.send_keys(input_text)
                self._settle_ui(0.2)

            if hide_keyboard:
                try:
                    self.driver.hide_keyboard()
                except Exception:
                    pass
            self._settle_ui(0.2)
            return True

    # ---- 长按 ----

    def wait_for_press_name(self, by_method=None, locator=None, name=None, *, element_key=None):
        """
        元素列表中按"文本匹配"定位，执行长按操作（strip 后比较）。
        - 旧用法: wait_for_press_name(By.ID, "com.onyx:id/title", "笔记标题")
        - 新用法: wait_for_press_name(element_key="note_title_regular")
        """
        if element_key is not None:
            _push_element_ctx('wait_for_press_name', element_key)
            loc = self._resolve_locator(element_key, require_name=True)
            locator_type, locator_value = loc['by'], loc['value']
            target_name = name or loc['name']
            step_msg = f"长按「{target_name}」"
        elif by_method is not None and locator is not None:
            _push_element_ctx('wait_for_press_name', None)
            locator_type, locator_value = by_method, locator
            target_name = name
            if not target_name:
                raise AssertionError("动态元素必须传入 name 参数")
            step_msg = f"长按\"{target_name}\""
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator, name)")

        with allure.step(step_msg):
            elements = self.check_list_timeout(locator_type, locator_value)
            target = str(target_name).strip()
            for element in elements:
                try:
                    actual = (element.text or "").strip()
                except StaleElementReferenceException:
                    continue
                if actual == target:
                    logging.debug(f"[DEBUG] 匹配到文本 '{target}' 的元素，执行长按")
                    self._safe_long_press_by_element(element, duration=2)
                    return True
            logging.error(f"未找到指定 '{target_name}' 元素")
            return False

    # ---- 获取元素文本 ----

    def obtain_element_text(self, by_method=None, locator=None, *, element_key=None):
        """
        获取元素的文本内容（兼容元素不存在的情况）。
        - 旧用法: obtain_element_text(By.ID, "com.onyx:id/title")
        - 新用法: obtain_element_text(element_key="手写笔记.退出手写笔记")
        """
        if element_key is not None:
            loc = self._resolve_locator(element_key)
            locator_type, locator_value = loc['by'], loc['value']
            display = loc.get('operation') or loc.get('name') or str(locator_value)
            step_msg = f"获取文本「{display}」"
        elif by_method is not None and locator is not None:
            locator_type, locator_value = by_method, locator
            step_msg = f"获取文本({locator_type}, {locator_value})"
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator)")

        with allure.step(step_msg):
            elements = self.check_display_timeout(locator_type, locator_value)
            if elements:
                logging.debug(f"[DEBUG] 获取元素文本（{locator_type}：{locator_value}），文本为 {elements.text}")
            return elements.text if elements else None

    def obtain_element_list_text(self, by_method=None, locator=None, *, element_key=None):
        """
        获取元素列表的**非空文本**集合。
        - 旧用法: obtain_element_list_text(By.ID, "com.onyx:id/title")
        - 新用法: obtain_element_list_text(element_key="...")
        """
        if element_key is not None:
            loc = self._resolve_locator(element_key)
            locator_type, locator_value = loc['by'], loc['value']
            display = loc.get('operation') or loc.get('name') or str(locator_value)
            step_msg = f"获取文本列表「{display}」"
        elif by_method is not None and locator is not None:
            locator_type, locator_value = by_method, locator
            step_msg = f"获取文本列表({locator_type}, {locator_value})"
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator)")

        with allure.step(step_msg):
            element_list = []
            elements = self.check_list_timeout(locator_type, locator_value)
            if elements:
                for element in elements:
                    text = element.text
                    if text:
                        element_list.append(text)
                logging.debug(f"[DEBUG] 提取非空文本，共 {len(element_list)} 个")
            return element_list

    # ---- 弹窗处理 ----

    def pop_up_check_name_(self, by_method=None, locator=None, name=None, *, element_key=None):
        """
        检查弹窗是否显示，若显示则点击弹窗内指定文本的元素。
        - 旧用法: pop_up_check_name_(By.ID, "android:id/text1", "覆盖全部")
        - 新用法: pop_up_check_name_(element_key="overwrite_all_option")
        """
        if element_key is not None:
            loc = self._resolve_locator(element_key, require_name=True)
            locator_type, locator_value = loc['by'], loc['value']
            target_name = name or loc['name']
            step_msg = f"弹窗点击「{target_name}」"
        elif by_method is not None and locator is not None:
            locator_type, locator_value = by_method, locator
            target_name = name
            if not target_name:
                raise AssertionError("动态元素必须传入 name 参数")
            step_msg = f"弹窗点击\"{target_name}\""
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator, name)")

        with allure.step(step_msg):
            try:
                popup = self.check_display_timeout(locator_type, locator_value)
                if popup.is_displayed():
                    elements = self.check_list_timeout(locator_type, locator_value)
                    for element in elements:
                        if element.text == target_name:
                            logging.debug(f"[DEBUG] 匹配到弹窗内文本 '{target_name}' 的元素，执行点击")
                            self.xpath_check_timeout(target_name)
                            element.click()
                            return True
                return False
            except TimeoutException:
                logging.error(f"弹窗未显示")
                return False
            except Exception as e:
                logging.error(f"获取异常{e}")
                return False

    # ---- 滑动 ----

    def click_slice(self, start_screen_width, start_screen_height, end_screen_width, end_screen_height):
        """
        按**屏幕比例**滑动（起点→终点）。
        """
        with allure.step(f"滑动({start_screen_width:.2f},{start_screen_height:.2f})→({end_screen_width:.2f},{end_screen_height:.2f})"):
            screen_size = self.driver.get_window_size()
            start_x = int(screen_size['width'] * start_screen_width)
            start_y = int(screen_size['height'] * start_screen_height)
            end_x = int(screen_size['width'] * end_screen_width)
            end_y = int(screen_size['height'] * end_screen_height)
            self.driver.swipe(start_x, start_y, end_x, end_y, duration=100)
            logging.debug(f"[DEBUG] 执行屏幕滑动：起点({start_x},{start_y}) → 终点({end_x},{end_y})")
            return True

    # ---- 方向滑动 ----

    def swipe_direction(self, direction: str):
        """全屏方向滑动。direction: up/down/left/right。"""
        direction_map = {
            "up": (0.5, 0.35, 0.5, 0.65),
            "down": (0.5, 0.65, 0.5, 0.35),
            "left": (0.65, 0.5, 0.35, 0.5),
            "right": (0.35, 0.5, 0.65, 0.5),
        }
        if direction not in direction_map:
            raise ValueError(f"不支持的滑动方向: {direction}，可选: {list(direction_map.keys())}")
        x1, y1, x2, y2 = direction_map[direction]
        with allure.step(f"方向滑动 {direction}"):
            self.click_slice(x1, y1, x2, y2)
            self._settle_ui()

    # ---- 坐标操作 ----

    def click_by_coord(self, element_key: str):
        """按元素 locator 中的比例坐标点击。locator 格式: x,y（如 0.5,0.3）。"""
        _push_element_ctx('click_by_coord', element_key)
        info = self.get_element(element_key)
        loc_str = info['locator'][1] if isinstance(info.get('locator'), (list, tuple)) else str(info.get('locator', ''))
        try:
            parts = [p.strip() for p in loc_str.split(',')]
            x_ratio, y_ratio = float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            raise ValueError(f"坐标元素【{element_key}】locator 格式错误: {loc_str}，应为 x,y")

        screen_size = self.driver.get_window_size()
        x = int(screen_size['width'] * x_ratio)
        y = int(screen_size['height'] * y_ratio)

        with allure.step(f"点击坐标 ({x_ratio:.2f},{y_ratio:.2f})"):
            self.driver.tap([(x, y)])
            self._settle_ui()

    def long_press_by_coord(self, element_key: str, duration: int = 2000):
        """按元素 locator 中的比例坐标长按。locator 格式: x,y（如 0.5,0.3）。"""
        _push_element_ctx('long_press_by_coord', element_key)
        info = self.get_element(element_key)
        loc_str = info['locator'][1] if isinstance(info.get('locator'), (list, tuple)) else str(info.get('locator', ''))
        try:
            parts = [p.strip() for p in loc_str.split(',')]
            x_ratio, y_ratio = float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            raise ValueError(f"坐标元素【{element_key}】locator 格式错误: {loc_str}，应为 x,y")

        screen_size = self.driver.get_window_size()
        x = int(screen_size['width'] * x_ratio)
        y = int(screen_size['height'] * y_ratio)

        with allure.step(f"长按坐标 ({x_ratio:.2f},{y_ratio:.2f}) {duration}ms"):
            self.driver.tap([(x, y)], duration)
            self._settle_ui()

    # ---- 系统键 ----

    def press_back(self):
        """按系统返回键（Android keycode 4）。"""
        with allure.step("按返回键"):
            self.driver.press_keycode(4)
            self._settle_ui()

    # ---- 等待弹窗消失 ----

    def by_pop_time(self, by_method=None, locator=None, timeout=None, prompt=None, *, element_key=None):
        """
        检查弹窗是否在超时时间内消失。
        - 旧用法: by_pop_time(By.ID, "com.onyx:id/progress", 180, "导入")
        - 新用法: by_pop_time(element_key="import_progress", timeout=180, prompt="导入")
        """
        if element_key is not None:
            loc = self._resolve_locator(element_key)
            by_method, locator = loc['by'], loc['value']
            display = loc.get('operation') or loc.get('name') or str(locator)
            step_msg = f"等待弹窗消失({timeout}s)「{display}」"
        elif by_method is None or locator is None:
            raise AssertionError("必须提供 element_key 或 (by_method, locator)")
        else:
            step_msg = f"等待弹窗消失({timeout}s) ({by_method}, {locator})"

        with allure.step(step_msg):
            try:
                WebDriverWait(self.driver, timeout).until_not(
                    EC.presence_of_element_located((by_method, locator))
                )
                logging.debug(f"[DEBUG] 弹窗（{by_method}：{locator}）已消失")
                return True
            except TimeoutException:
                logging.error(f" {prompt} , {timeout} 秒后超时")
                return False

    # ---- 按坐标点击 ----

    def wait_for_screen_size(self, start_screen_width=None, start_screen_height=None, *, element_key=None):
        """
        按坐标点击页面。
        - 旧用法: wait_for_screen_size(500, 800)         → 绝对像素
        - 新用法: wait_for_screen_size(element_key="center_point") → YAML 比例
        """
        if element_key is not None:
            info = self.get_element(element_key)
            x_ratio = info.get('x_ratio')
            y_ratio = info.get('y_ratio')
            if x_ratio is None or y_ratio is None:
                raise AssertionError(f"元素 '{element_key}' 缺少 'x_ratio' 或 'y_ratio' 字段")
            screen_size = self.driver.get_window_size()
            actual_x = int(screen_size['width'] * x_ratio)
            actual_y = int(screen_size['height'] * y_ratio)
            display = info.get('operation') or info.get('name') or element_key
            step_msg = f"坐标点击「{display}」"
        elif start_screen_width is not None and start_screen_height is not None:
            actual_x, actual_y = start_screen_width, start_screen_height
            step_msg = f"坐标点击({actual_x}, {actual_y})"
        else:
            raise AssertionError("必须提供 (start_screen_width, start_screen_height) 或 element_key")

        with allure.step(step_msg):
            action = TouchAction(self.driver)
            action.press(x=actual_x, y=actual_y).release().perform()
            return True

    # ---- 带耗时日志的导入等待 ----

    def by_take_pop(self, name_ok=None, prompt="", time_out=180, *, element_key=None):
        """
        点击元素后，等待"模板"文本出现，计算耗时。
        - 旧用法: by_take_pop("确认", "导入耗时")
        - 新用法: by_take_pop(element_key="confirm_ok", prompt="导入耗时")
        """
        if element_key is not None:
            self.xpath_text_click(element_key=element_key)
            step_msg = f"耗时等待「{element_key}」({time_out}s)"
        elif name_ok is not None:
            self.xpath_text_click(name_ok)
            step_msg = f"耗时等待\"{name_ok}\"({time_out}s)"
        else:
            raise AssertionError("必须提供 name_ok 或 element_key")

        with allure.step(step_msg):
            while True:
                try:
                    start = time.time()
                    WebDriverWait(self.driver, time_out, poll_frequency=0.1).until(
                        EC.visibility_of_element_located((By.XPATH, f'//*[@text="模板"]'))
                    )
                    end = time.time()
                    logging.info(f"{prompt}{(end - start):.2f} 秒")
                    return True
                except TimeoutException as e:
                    logging.error(f"导入{prompt}文件，{time_out}秒后导入超时{e}")
                    return False
                except Exception as e:
                    logging.error(f"{prompt}其他异常{e}")
                    return False
