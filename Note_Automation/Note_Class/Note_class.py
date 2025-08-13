from functools import wraps
import logging
import time
from selenium.common.exceptions import TimeoutException
import allure
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from appium.webdriver.common.touch_action import TouchAction


# ------------------------------ 异常处理装饰器 ------------------------------
def retry_and_handle_exceptions(max_retries=3, retry_delay=1):
    """
    装饰器：捕获元素操作的超时/未知异常，自动重试后截图并抛异常。
    - 参数：max_retries（重试次数，默认3）、retry_delay（重试间隔，默认1秒）
    - 逻辑：过滤方法内的类实例，重试失败时截图保存到本地并附加到Allure报告。
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            filtered_args = [arg for arg in args if not isinstance(arg, Operation_method)]
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except TimeoutException:
                    msg = f"获取元素 {filtered_args} ！！！超时 , 重试次数 {attempt + 1}/{max_retries}"
                    logging.debug(msg)
                except Exception:
                    msg = f"获取元素 {filtered_args} ！！！未知异常 , 重试次数 {attempt + 1}/{max_retries}"
                    logging.debug(msg)
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
            msg = f"获取元素 '{filtered_args}' 在 {max_retries} 次重试后仍失败"
            logging.error(msg)
            from Note_Automation.config import driver

            file_path = f"/Users/xiaoyu/Downloads/{filtered_args}.png"
            success = driver.get_screenshot_as_file(file_path)
            if success:
                print(f"截图已保存至: {file_path}")
            else:
                print("截图失败")

            screenshot = driver.get_screenshot_as_png()
            allure.attach(screenshot, name=f"获取元素 {filtered_args} 失败截图", attachment_type=allure.attachment_type.PNG)
            raise Exception(msg)
        return wrapper
    return decorator


# ------------------------------ 基础元素等待类 ------------------------------
class Base_note_class:
    def __init__(self, driver):
        """初始化：接收Driver实例，设置默认超时时间（5秒）"""
        self.driver = driver
        self.default_timeout = 5

    @retry_and_handle_exceptions()
    def xpath_check_timeout(self, name, timeout=None):
        """
        等待“文本匹配”的元素可点击（XPath定位：//*[@text="{name}"]）。
        - 参数：name（元素文本）、timeout（超时时间，默认取default_timeout）
        - 返回：可点击的WebElement（失败由装饰器抛异常）
        """
        timeout = timeout or self.default_timeout
        element = WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, f'//*[@text="{name}"]'))
        )
        logging.debug(f"[DEBUG] 成功获取可点击元素（文本定位）：{name}")  # 新增DEBUG日志
        return element

    @retry_and_handle_exceptions()
    def xpath_check_display_timeout(self, name, timeout=None):
        """
        等待“文本匹配”的元素可见（XPath定位：//*[@text="{name}"]）。
        - 参数：name（元素文本）、timeout（超时时间，默认取default_timeout）
        - 返回：可见的WebElement（失败由装饰器抛异常）
        """
        timeout = timeout or self.default_timeout
        element = WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located((By.XPATH, f'//*[@text="{name}"]'))
        )
        logging.debug(f"[DEBUG] 成功获取可见元素（文本定位）：{name}")  # 新增DEBUG日志
        return element

    @retry_and_handle_exceptions()
    def check_list_timeout(self, by_method, locator, timeout=None):
        """
        等待“定位器匹配”的元素列表可见。
        - 参数：by_method（定位方式，如By.ID）、locator（定位表达式）、timeout（超时时间）
        - 返回：可见的WebElement列表（失败由装饰器抛异常）
        """
        timeout = timeout or self.default_timeout
        elements = WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_all_elements_located((by_method, locator))
        )
        logging.debug(f"[DEBUG] 成功获取元素列表（{by_method}：{locator}），共 {len(elements)} 个元素")  # 新增DEBUG日志
        return elements

    @retry_and_handle_exceptions()
    def check_timeout(self, by_method, locator, timeout=None):
        """
        等待“定位器匹配”的元素可点击。
        - 参数：by_method（定位方式）、locator（定位表达式）、timeout（超时时间）
        - 返回：可点击的WebElement（失败由装饰器抛异常）
        """
        timeout = timeout or self.default_timeout
        element = WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by_method, locator))
        )
        logging.debug(f"[DEBUG] 成功获取可点击元素（{by_method}：{locator}）")  # 新增DEBUG日志
        return element

    @retry_and_handle_exceptions()
    def check_display_timeout(self, by_method, locator, timeout=None):
        """
        等待“定位器匹配”的元素可见。
        - 参数：by_method（定位方式）、locator（定位表达式）、timeout（超时时间）
        - 返回：可见的WebElement（失败由装饰器抛异常）
        """
        timeout = timeout or self.default_timeout
        element = WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located((by_method, locator))
        )
        logging.debug(f"[DEBUG] 成功获取可见元素（{by_method}：{locator}）")  # 新增DEBUG日志
        return element


# ------------------------------ 元素操作方法类 ------------------------------
class Operation_method(Base_note_class):
    def xpath_text_click(self, name, should_click=True):
        """
        通过“文本”定位元素，可选点击。
        - 参数：name（元素文本）、should_click（是否点击，默认True）
        - 返回：成功则返回WebElement，失败返回False
        """
        element = self.xpath_check_timeout(name)
        logging.debug(f"[DEBUG] 通过文本定位到元素：{name}")  # 新增DEBUG日志
        if not element:
            logging.error(f"未获取到元素 {name} ")
            return False
        if should_click is not None:
            element.click()
        return element

    def by_sub_index_click(self, by_method, locator, by_method1, locator1, index=0, should_click=True):
        """
        父元素下按索引定位子元素，可选点击。
        - 步骤：定位父元素→检查可见性→找子元素列表→校验索引→操作子元素
        - 参数：父/子元素的定位方式+表达式、子元素索引、是否点击
        - 返回：成功返回子元素WebElement，失败返回None
        """
        try:
            parent_element = self.check_timeout(by_method, locator)
            logging.debug(f"[DEBUG] 找到父元素（{by_method}：{locator}）")  # 新增DEBUG日志
            if not parent_element:
                logging.error(f"未找到父元素: {locator}")
                return None
            if not parent_element.is_displayed():
                logging.error(f"父元素 {locator} 不可见")
                return None

            child_elements = parent_element.find_elements(by_method1, locator1)
            logging.debug(f"[DEBUG] 在父元素下找到子元素列表（{by_method1}：{locator1}），共 {len(child_elements)} 个元素")  # 新增DEBUG日志
            if not child_elements:
                logging.error(f"在父元素 {locator} 下未找到子元素: {locator1}")
                return None

            if index < 0 or index >= len(child_elements):
                logging.error(f"子元素索引 {index} 越界，列表长度为 {len(child_elements)}")
                return None

            target_element = child_elements[index]
            logging.debug(f"[DEBUG] 定位到子元素，索引 {index}")  # 新增DEBUG日志
            logging.debug(f"成功定位到子元素，索引: {index}，总数量: {len(child_elements)}")
            if should_click:
                target_element.click()
                logging.debug(f"已点击子元素，索引: {index}")
            return target_element
        except Exception as e:
            logging.error(f"定位子元素过程中发生错误: {str(e)}")
            return None

    def by_father_index_click(self, by_method, locator, by_method1, locator1, index=0, should_click=True):
        """
        父元素列表按索引选父元素，再定位子元素（默认选第一个子元素）。
        - 步骤：定位父列表→校验索引→选父元素→找子元素→操作子元素
        - 返回：点击则返回True，否则返回子元素文本；失败返回False
        """
        parent_elements = self.check_list_timeout(by_method, locator)
        logging.debug(f"[DEBUG] 找到父元素列表（{by_method}：{locator}），共 {len(parent_elements)} 个元素")  # 新增DEBUG日志
        if index >= len(parent_elements):
            logging.error(f"下标({index})越界，无法获取元素")
            logging.error(f"当前列表长度 ({len(parent_elements)})")
            return False

        parent_element = parent_elements[index]
        logging.debug(f"[DEBUG] 选中父元素，索引 {index}（{by_method}：{locator}）")  # 新增DEBUG日志
        if not parent_element.is_displayed():
            logging.error(f"未找到 {locator} 父元素")
            return False

        child_element = parent_element.find_elements(by_method1, locator1)
        logging.debug(f"[DEBUG] 在父元素下找到子元素（{by_method1}：{locator1}）")  # 新增DEBUG日志
        if child_element is not None:
            self.check_timeout(by_method1, locator1)
            if should_click is not None:
                if len(child_element) == 0:
                    logging.error(f"未找到 {locator1} 子元素")
                    return False
                child_element[0].click()
                return True
            return child_element[0].text
        return False

    def by_father_sub_index_click(self, by_method, locator, by_method1, locator1, index=0, index_1=0, should_click=True):
        """
        父元素列表+子元素列表双重索引定位，可选点击。
        - 步骤：定位父列表→校验父索引→选父元素→找子列表→校验子索引→操作子元素
        - 返回：点击则返回True，否则返回子元素文本；失败返回False
        """
        parent_elements = self.check_list_timeout(by_method, locator)
        logging.debug(f"[DEBUG] 找到父元素列表（{by_method}：{locator}），共 {len(parent_elements)} 个元素")  # 新增DEBUG日志
        if index >= len(parent_elements):
            logging.error(f"下标({index})越界，无法获取元素")
            logging.error(f"当前列表长度 ({len(parent_elements)})")
            return False

        parent_element = parent_elements[index]
        logging.debug(f"[DEBUG] 选中父元素，索引 {index}（{by_method}：{locator}）")  # 新增DEBUG日志
        if not parent_element.is_displayed():
            logging.error(f"未找到 {locator} 父元素")
            return False

        child_element = parent_element.find_elements(by_method1, locator1)
        logging.debug(f"[DEBUG] 在父元素下找到子元素列表（{by_method1}：{locator1}），共 {len(child_element)} 个元素")  # 新增DEBUG日志
        if child_element is not None:
            self.check_timeout(by_method1, locator1)
            if index_1 >= len(child_element):
                logging.error(f"下标({index_1})越界，无法获取元素")
                logging.error(f"当前列表长度 ({len(child_element)})")
                return False
            if should_click is not None:
                if len(child_element) == 0:
                    logging.error(f"未找到 {locator1} 子元素")
                    return False
                child_element[index_1].click()
                return True
            return child_element[index_1].text
        return False

    def by_element_click(self, by_method, locator, should_click=True):
        """
        直接定位元素，可选点击。
        - 参数：定位方式+表达式、是否点击
        - 返回：成功返回True，失败返回False
        """
        element = self.check_timeout(by_method, locator)
        logging.debug(f"[DEBUG] 找到元素（{by_method}：{locator}）")  # 新增DEBUG日志
        if element:
            if should_click is not None:
                element.click()
            return True
        logging.error(f"未找到 {locator} 元素")
        return False

    def by_name_click(self, by_method, locator, name, should_click=True):
        """
        元素列表中按“文本匹配”定位，可选点击。
        - 步骤：定位列表→遍历找文本→匹配则操作
        - 返回：成功返回元素列表，失败返回False
        """
        elements = self.check_list_timeout(by_method, locator)
        logging.debug(f"[DEBUG] 找到元素列表（{by_method}：{locator}），共 {len(elements)} 个元素")  # 新增DEBUG日志
        if not elements:
            logging.error(f"未找到 {locator} 元素")
            return False
        for element in elements:
            if element.text == name:
                logging.debug(f"[DEBUG] 匹配到文本 {name} 的元素")  # 新增DEBUG日志
                if should_click is not None:
                    element.click()
                return elements
        return False

    def by_index_name_click(self, by_method, locator, name, index=0, should_click=True):
        """
        元素列表中按“索引+文本校验”定位，可选点击。
        - 步骤：定位列表→校验索引→操作元素→校验文本
        - 返回：成功返回True，失败返回False
        """
        elements = self.check_list_timeout(by_method, locator)
        logging.debug(f"[DEBUG] 找到元素列表（{by_method}：{locator}），共 {len(elements)} 个元素")  # 新增DEBUG日志
        if not elements:
            logging.error(f"未找到 {locator} 元素")
            return False
        if index < len(elements):
            element = elements[index]
            logging.debug(f"[DEBUG] 选中元素，索引 {index}")  # 新增DEBUG日志
            if should_click is not None:
                element.click()
            if element.text != name:
                logging.debug(f"[DEBUG] 校验元素文本：预期 {name} ，实际 {element.text}")  # 新增DEBUG日志
                logging.error(f"未找到 {name} 元素")
                return False
            return True
        else:
            logging.error(f"下标({index})越界，无法获取元素")
            return False

    def by_index_click(self, by_method, locator, index=0, should_click=True):
        """
        元素列表中按“索引”定位，可选点击（需元素可点击）。
        - 步骤：定位列表→校验索引→检查元素可点击性→操作
        - 返回：成功返回True，失败返回False
        """
        elements = self.check_list_timeout(by_method, locator)
        logging.debug(f"[DEBUG] 找到元素列表（{by_method}：{locator}），共 {len(elements)} 个元素")  # 新增DEBUG日志
        if not elements:
            logging.error(f"未找到 {locator} 元素")
            return False
        if index < len(elements):
            element = elements[index]
            logging.debug(f"[DEBUG] 选中元素，索引 {index}")  # 新增DEBUG日志
            if should_click is not None:
                logging.debug(f"[DEBUG] 检查元素可点击性：{element.is_enabled()}")  # 新增DEBUG日志
                if element.is_enabled():
                    element.click()
                else:
                    logging.error(f"元素不能点击")
                    return False
            return True
        else:
            logging.error(f"下标({index})越界，无法获取元素")
            return False

    def wait_check_toast(self, toast_true, toast_false=None, toast_timeout=5):
        """
        检查Toast弹窗：支持校验“预期Toast”和“异常Toast”。
        - 参数：toast_true（预期文本）、toast_false（异常文本，可选）、toast_timeout（超时）
        - 返回：找到预期Toast→True；找到异常Toast→False；超时→False
        """
        expected_toast_message = toast_true
        abnormal_toast_message = toast_false
        start_time = time.time()
        while time.time() - start_time < toast_timeout:
            page_source = self.driver.page_source
            if expected_toast_message in page_source:
                return True
            elif toast_false is not None:
                if abnormal_toast_message in page_source:
                    return False
            time.sleep(1)
        return False

    def wait_input_box(self, by_method, locator, name):
        """
        定位输入框并输入内容。
        - 参数：定位方式+表达式、输入内容
        - 返回：固定返回True（原逻辑设计）
        """
        input_box = self.check_timeout(by_method, locator)
        logging.debug(f"[DEBUG] 找到输入框（{by_method}：{locator}），输入内容 {name}")  # 新增DEBUG日志
        input_box.send_keys(name)
        return True

    def wait_for_press_name(self, by_method, locator, name):
        """
        元素列表中按“文本匹配”定位，执行长按操作。
        - 步骤：定位列表→遍历找文本→匹配则长按（click_and_hold）
        - 返回：成功返回True，失败返回False
        """
        elements = self.check_list_timeout(by_method, locator)
        logging.debug(f"[DEBUG] 找到元素列表（{by_method}：{locator}），共 {len(elements)} 个元素")  # 新增DEBUG日志
        for element in elements:
            if element.text == name:
                logging.debug(f"[DEBUG] 匹配到文本 {name} 的元素，执行长按")  # 新增DEBUG日志
                actions = ActionBuilder(self.driver)
                actions.pointer_action.click_and_hold(element)
                actions.perform()
                time.sleep(2)
                return True
        logging.error(f"未找到指定{name}测试文件或笔记")
        return False

    def obtain_element_text(self, by_method, locator):
        """
        获取元素的文本内容（兼容元素不存在的情况）。
        - 参数：定位方式+表达式
        - 返回：元素文本（存在则返回，否则返回None）
        """
        elements = self.check_display_timeout(by_method, locator)
        if elements:
            logging.debug(f"[DEBUG] 获取元素文本（{by_method}：{locator}），文本为 {elements.text}")  # 新增DEBUG日志
        return elements.text if elements else None

    def obtain_element_list_test(self, by_method, locator):
        """
        获取元素列表的**非空文本**集合。
        - 参数：定位方式+表达式
        - 返回：非空文本列表（空列表表示无有效文本）
        """
        element_list = []
        elements = self.check_list_timeout(by_method, locator)
        logging.debug(f"[DEBUG] 找到元素列表（{by_method}：{locator}），共 {len(elements)} 个元素")  # 新增DEBUG日志
        if elements:
            for element in elements:
                text = element.text
                if text:
                    element_list.append(text)
            logging.debug(f"[DEBUG] 提取非空文本，共 {len(element_list)} 个")  # 新增DEBUG日志
        return element_list

    def pop_up_check_name_(self, by_method, locator, name):
        """
        检查弹窗是否显示，若显示则点击弹窗内指定文本的元素。
        - 步骤：定位弹窗→检查可见性→遍历找文本→匹配则点击
        - 返回：成功返回True，失败（含异常）返回False
        """
        try:
            popup = self.check_display_timeout(by_method, locator)
            logging.debug(f"[DEBUG] 找到弹窗元素（{by_method}：{locator}）")  # 新增DEBUG日志
            if popup.is_displayed():
                elements = self.check_list_timeout(by_method, locator)
                for element in elements:
                    if element.text == name:
                        logging.debug(f"[DEBUG] 匹配到弹窗内文本 {name} 的元素，执行点击")  # 新增DEBUG日志
                        self.xpath_check_timeout(name)
                        element.click()
                        return True
            return False
        except TimeoutException:
            logging.error(f"弹窗未显示")
            return False
        except Exception as e:
            logging.error(f"获取异常{e}")
            return False

    def click_slice(self, start_screen_width, start_screen_height, end_screen_width, end_screen_height):
        """
        按**屏幕比例**滑动（起点→终点）。
        - 参数：起点和终点的宽高比例（0~1）
        - 返回：固定返回True（原逻辑设计）
        """
        screen_size = self.driver.get_window_size()
        start_x = int(screen_size['width'] * start_screen_width)
        start_y = int(screen_size['height'] * start_screen_height)
        end_x = int(screen_size['width'] * end_screen_width)
        end_y = int(screen_size['height'] * end_screen_height)
        self.driver.swipe(start_x, start_y, end_x, end_y, duration=100)
        logging.debug(f"[DEBUG] 执行屏幕滑动：起点({start_x},{start_y}) → 终点({end_x},{end_y})")  # 新增DEBUG日志
        return True

    # ----------------------------- 单一方法 ------------------
    def by_pop_time(self, by_method, locator, timeout, prompt):
        """
        检查弹窗是否在超时时间内消失。
        - 参数：定位方式+表达式、超时时间、日志提示
        - 返回：消失→True，超时→False
        """
        try:
            WebDriverWait(self.driver, timeout).until_not(
                EC.presence_of_element_located((by_method, locator))
            )
            logging.debug(f"[DEBUG] 弹窗（{by_method}：{locator}）已消失")  # 新增DEBUG日志
            return True
        except TimeoutException:
            logging.error(f" {prompt} , {timeout} 秒后超时")
            return False

    def wait_for_screen_size(self, start_screen_width, start_screen_height):
        """
        按**绝对坐标**点击页面。
        - 参数：x坐标、y坐标
        - 返回：固定返回True（原逻辑设计）
        """
        action = TouchAction(self.driver)
        logging.debug(f"[DEBUG] 执行绝对坐标点击：({start_screen_width},{start_screen_height})")  # 新增DEBUG日志
        action.press(x=start_screen_width, y=start_screen_height).release().perform()
        return True

    def by_take_pop(self, name_ok, prompt, time_out=180):
        """
        点击元素后，等待“模板”文本出现，计算耗时。
        - 参数：点击元素的文本、日志提示、超时时间（默认180秒）
        - 返回：成功→True，超时/异常→False
        """
        self.xpath_text_click(name_ok)
        while True:
            try:
                start = time.time()
                WebDriverWait(self.driver, time_out, poll_frequency=0.1).until(
                    EC.visibility_of_element_located((By.XPATH, f'//*[@text="模板"]'))
                )
                end = time.time()
                logging.info(f"{prompt}{(end - start):.2f} 秒")
                logging.debug(f"[DEBUG] 等待到“模板”元素出现，耗时 {end - start:.2f} 秒")  # 新增DEBUG日志
                return True
            except TimeoutException as e:
                logging.error(f"导入{prompt}文件，{time_out}秒后导入超时{e}")
                return False
            except Exception as e:
                logging.error(f"{prompt}其他异常{e}")
                return False