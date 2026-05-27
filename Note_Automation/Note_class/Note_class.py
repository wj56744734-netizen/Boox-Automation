import contextvars
from functools import wraps
import logging
import time
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException,
    ElementNotInteractableException,
    InvalidSessionIdException,
    WebDriverException,
)
import allure
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from appium.webdriver.common.touch_action import TouchAction

from Note_Automation.Note_class.element_catalog import describe as _describe_locator


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
# Public methods (xpath_text_click, wait_for_press_name, etc.) push their element_key
# before calling internal helpers; the decorator reads it as fallback when the failing
# method itself has no element_key kwarg.
_element_ctx: contextvars.ContextVar = contextvars.ContextVar('_element_ctx', default=None)


def _push_element_ctx(method_name: str, element_key: str):
    """Set current element context so downstream errors carry the original element_key."""
    _element_ctx.set({'method': method_name, 'element_key': element_key})


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


# ------------------------------ 异常处理装饰器 ------------------------------
def retry_and_handle_exceptions(max_retries=3, retry_delay=1):
    """
    装饰器：捕获"可重试"的元素查找异常，重试 N 次仍失败则截图并抛出。
    - 会话级异常（InvalidSessionId / NoSuchDriver）直接抛出，不再重试
    - 其它非可重试异常也直接抛出，保留原始堆栈
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            filtered_args = [arg for arg in args if not isinstance(arg, Operation_method)]
            call_label = _format_call_label(func.__name__, filtered_args)

            # 如果调用方传了 element_key，附到错误标签里
            ek = kwargs.get('element_key')
            if ek:
                call_label = f"{func.__name__}(element_key='{ek}')"

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
            ctx = _element_ctx.get()
            ctx_key = ctx.get('element_key') if ctx else None
            ctx_method = ctx.get('method') if ctx else None
            ek = kwargs.get('element_key')  # directly passed to this method

            # Build structured multi-line error message
            lines = [f"{call_label} 在 {max_retries} 次重试后仍失败"]

            # Resolve actual locator from YAML when element_key is available
            display_key = ek or ctx_key
            if display_key:
                try:
                    info = args[0].get_element(display_key)
                    loc = info.get('locator')
                    if loc and len(loc) == 2:
                        lines.append(f'  ↳ 定位:   {loc[0]}="{loc[1]}"')
                except Exception:
                    pass

            # Show element_key & YAML source; add source method for context-propagated keys
            if display_key:
                if ek:
                    lines.append(f"  ↳ 元素键: {ek}")
                else:
                    via = f" (来自 {ctx_method})" if ctx_method else ""
                    lines.append(f"  ↳ 元素键: {ctx_key}{via}")
                try:
                    src = args[0].get_element_source(display_key)
                    if src:
                        line_no = args[0].get_element_line(display_key)
                        tag = f"{src}:{line_no}" if line_no else src
                        lines.append(f"  ↳ YAML:   {tag}")
                except Exception:
                    pass

            if desc:
                lines.append(f"  ↳ 元素用途: {desc}")

            from Note_Automation.config import driver
            from Note_Automation.framework.paths import safe_screenshot_path

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
                lines.append(f"  ↳ 截图: {file_path}")

            msg = "\n".join(lines)
            logging.error(msg)

            raise Exception(msg) from last_exc
        return wrapper
    return decorator


# ------------------------------ 基础元素等待类 ------------------------------
class Base_note_class:
    def __init__(self, driver, yaml_path=None):
        """初始化：接收Driver实例，设置默认超时时间（5秒），加载YAML元素配置。"""
        self.driver = driver
        self.default_timeout = 5
        from Note_Automation.Note_class.Note_element.element_loader import ElementLoader
        self.element_loader = ElementLoader(yaml_path=yaml_path)

    # ---- YAML 元素访问 ----

    def get_element(self, element_key):
        """从YAML配置获取元素信息（locator已转为(By, value)元组）。"""
        return self.element_loader.get_element_info(element_key)

    def get_element_source(self, element_key):
        """返回元素键所在的 YAML 文件路径，用于错误日志溯源。"""
        return self.element_loader.get_key_source(element_key)

    def get_element_line(self, element_key):
        """返回元素键在 YAML 文件中的行号。"""
        return self.element_loader.get_key_line(element_key)

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

    def _safe_click(self, by, value, retries=3):
        """
        安全点击：自动处理 StaleElementReferenceException，并对 XPath 文本搜索做换行符回退。

        :param by: 定位类型（如 By.XPATH, By.ID 等）
        :param value: 定位值
        :param retries: 遇到 StaleElement 时的最大重试次数
        """
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
                logging.debug(f"[_safe_click] 点击成功: ({by}, {value})")
                return element
            except StaleElementReferenceException:
                logging.debug(f"[_safe_click] 元素已过时 (尝试 {attempt + 1}/{retries})，重新定位...")
                time.sleep(0.5)
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
        """对已定位的元素执行长按（带 StaleElement 重试）。"""
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
        return self._wait_for_xpath(element_key, xpath, locator, timeout, need_clickable=True)

    @retry_and_handle_exceptions()
    def xpath_element_visible(self, element_key=None, xpath=By.XPATH,
                               locator=None, timeout=None):
        """等待 XPath 元素可见（支持 YAML / 动态 / 直接字符串）。"""
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
        elif name is not None:
            text_value = name
        else:
            raise AssertionError("必须提供 name 或 element_key")

        if should_click:
            # 点击路径统一走 _safe_click，确保"等待后真实点击"
            return self._safe_click(By.XPATH, text_value)
        else:
            if self._is_xpath_expression(text_value):
                return self.xpath_element_visible(xpath=text_value)
            return self.xpath_check_display_timeout(text_value)

    def xpath_parent_click(self, xpath=None, *, element_key=None, by=None, locator=None, should_click=True):
        """
        灵活 XPath 定位并点击（按优先级）：
        1. xpath_parent_click(xpath="//div[@class='parent']/button")
        2. xpath_parent_click(element_key="my_element")
        3. xpath_parent_click(by=By.XPATH, locator="//...")
        """
        if xpath is not None:
            final_by, final_locator = By.XPATH, xpath
        elif by is not None and locator is not None:
            final_by, final_locator = by, locator
        elif element_key is not None:
            _push_element_ctx('xpath_parent_click', element_key)
            info = self.get_element(element_key)
            final_by, final_locator = info['locator']
        else:
            raise AssertionError("必须提供 xpath、element_key 或 (by, locator) 之一")

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
        elif (by_method is not None and locator is not None
              and by_method1 is not None and locator1 is not None):
            parent_by, parent_loc = by_method, locator
            child_by, child_loc = by_method1, locator1
            child_index = index
        else:
            raise AssertionError(
                "必须提供 element_key 或 (by_method, locator, by_method1, locator1)")

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
        elif (by_method is not None and locator is not None
              and by_method1 is not None and locator1 is not None):
            parent_by, parent_loc = by_method, locator
            child_by, child_loc = by_method1, locator1
            parent_index = index
        else:
            raise AssertionError(
                "必须提供 element_key 或 (by_method, locator, by_method1, locator1)")

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
        elif (by_method is not None and locator is not None
              and by_method1 is not None and locator1 is not None):
            parent_by, parent_loc = by_method, locator
            child_by, child_loc = by_method1, locator1
            parent_index = index
            sub_index = index_1
        else:
            raise AssertionError(
                "必须提供 element_key 或 (by_method, locator, by_method1, locator1)")

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
        elif by_method is not None and locator is not None:
            locator_type, locator_value = by_method, locator
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator)")

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
        elif by_method is not None and locator is not None:
            locator_type, locator_value = by_method, locator
            if not name:
                raise AssertionError("动态元素必须传入 name 参数")
            target_name = name
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator, name)")

        elements = self.check_list_timeout(locator_type, locator_value)
        target = str(target_name).strip()
        for element in elements:
            try:
                actual = (element.text or "").strip()
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
        elif by_method is not None and locator is not None:
            locator_type, locator_value = by_method, locator
            target_name = name
            target_index = index
            if not target_name:
                raise AssertionError("动态元素必须传入 name 参数")
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator, name)")

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
        elif by_method is not None and locator is not None:
            locator_type, locator_value = by_method, locator
            target_index = index
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator)")

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

    def wait_check_toast(self, toast_true=None, toast_false=None, toast_timeout=5,
                         *, toast_true_key=None, toast_false_key=None):
        """
        检查Toast弹窗：支持校验"预期Toast"和"异常Toast"。
        - 旧用法: wait_check_toast("保存成功", "保存失败", 5)
        - 新用法: wait_check_toast(toast_true_key="toast_save_success")
        """
        if toast_true_key is not None:
            info = self._resolve_locator(toast_true_key)
            expected_toast_message = info.get('name') or info.get('value') or toast_true or ''
        elif toast_true is not None:
            expected_toast_message = toast_true
        else:
            raise AssertionError("必须提供 toast_true 或 toast_true_key")

        if toast_false_key is not None:
            info = self._resolve_locator(toast_false_key)
            abnormal_toast_message = info.get('name') or info.get('value')
        else:
            abnormal_toast_message = toast_false

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

    def wait_input_box(self, by_method=None, locator=None, name=None, *, element_key=None):
        """
        定位输入框并输入内容。
        - 旧用法: wait_input_box(By.ID, "com.onyx:id/search_et_input", "搜索词")
        - 新用法: wait_input_box(element_key="search_input")  # name 从 YAML 取
        """
        if element_key is not None:
            loc = self._resolve_locator(element_key)
            locator_type, locator_value = loc['by'], loc['value']
            input_text = name or loc.get('name')
            if not input_text:
                raise AssertionError(f"元素 '{element_key}' 未配置 'name' 字段且未传入 name 参数")
        elif by_method is not None and locator is not None:
            locator_type, locator_value = by_method, locator
            input_text = name
            if not input_text:
                raise AssertionError("必须提供 name 参数（输入内容）")
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator, name)")

        input_box = self.check_timeout(locator_type, locator_value)
        self._clear_input(input_box)
        if hasattr(input_box, 'set_text'):
            input_box.set_text(input_text)
        else:
            input_box.send_keys(input_text)
        try:
            self.driver.hide_keyboard()
        except Exception:
            pass
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
        elif by_method is not None and locator is not None:
            locator_type, locator_value = by_method, locator
            target_name = name
            if not target_name:
                raise AssertionError("动态元素必须传入 name 参数")
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator, name)")

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
        elif by_method is not None and locator is not None:
            locator_type, locator_value = by_method, locator
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator)")

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
        elif by_method is not None and locator is not None:
            locator_type, locator_value = by_method, locator
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator)")

        element_list = []
        elements = self.check_list_timeout(locator_type, locator_value)
        if elements:
            for element in elements:
                text = element.text
                if text:
                    element_list.append(text)
            logging.debug(f"[DEBUG] 提取非空文本，共 {len(element_list)} 个")
        return element_list

    # 向后兼容别名
    def obtain_element_list_test(self, by_method=None, locator=None):
        """已废弃：请使用 obtain_element_list_text。保留此方法以兼容旧测试。"""
        return self.obtain_element_list_text(by_method=by_method, locator=locator)

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
        elif by_method is not None and locator is not None:
            locator_type, locator_value = by_method, locator
            target_name = name
            if not target_name:
                raise AssertionError("动态元素必须传入 name 参数")
        else:
            raise AssertionError("必须提供 element_key 或 (by_method, locator, name)")

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
        screen_size = self.driver.get_window_size()
        start_x = int(screen_size['width'] * start_screen_width)
        start_y = int(screen_size['height'] * start_screen_height)
        end_x = int(screen_size['width'] * end_screen_width)
        end_y = int(screen_size['height'] * end_screen_height)
        self.driver.swipe(start_x, start_y, end_x, end_y, duration=100)
        logging.debug(f"[DEBUG] 执行屏幕滑动：起点({start_x},{start_y}) → 终点({end_x},{end_y})")
        return True

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
        elif by_method is None or locator is None:
            raise AssertionError("必须提供 element_key 或 (by_method, locator)")

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
        elif start_screen_width is not None and start_screen_height is not None:
            actual_x, actual_y = start_screen_width, start_screen_height
        else:
            raise AssertionError("必须提供 (start_screen_width, start_screen_height) 或 element_key")

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
        elif name_ok is not None:
            self.xpath_text_click(name_ok)
        else:
            raise AssertionError("必须提供 name_ok 或 element_key")

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
