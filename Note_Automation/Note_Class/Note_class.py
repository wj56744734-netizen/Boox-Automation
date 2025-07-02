from functools import wraps
import logging
import time
from selenium.common.exceptions import TimeoutException
import allure
from appium.webdriver.common.touch_action import TouchAction
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

# from config import driver


# -----------------------------------捕获异常

def retry_and_handle_exceptions(max_retries=3, retry_delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args,**kwargs):
            filtered_args = [arg for arg in args if not isinstance(arg, Operation_method)]
            for attempt in range(max_retries):
                try:
                    return func(*args,**kwargs)
                except TimeoutException:
                    msg = f"获取元素 {filtered_args} ！！！超时 , 重试次数 {attempt + 1}/{max_retries}"
                    logging.error(msg)
                except Exception:
                    msg = f"获取元素 {filtered_args} ！！！未知异常 , 重试次数 {attempt + 1}/{max_retries}"
                    logging.error(msg)
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
            msg = f"获取元素 '{filtered_args}' 在 {max_retries} 次重试后仍失败"
            logging.error(msg)
            from Note_Automation.config import driver
            screenshot = driver.get_screenshot_as_png()
            allure.attach(screenshot, name=f"获取元素 {filtered_args} 失败截图", attachment_type=allure.attachment_type.PNG)
            raise Exception(msg)
        return wrapper
    return decorator


# def note_abnormality(name):
#     def decorator(func):
#         @wraps(func)
#         def wrapper(*args,**kwargs):
#
#             abnormality = driver.find_elements(By.XPATH,f'//*[@text="{name}"]')
#
#             if abnormality:
#
#                 logging.error(f"{name},日志保存路径（D:\log.txt）")
#
#                 os.system("adb logcat -d > D:\log.txt")
#
#                 return func(*args, **kwargs)
#
#         return wrapper
#     return decorator

#----------------------------------初始获取元素方法
class Base_note_class:

    def __init__(self,driver):
        self.driver = driver
        self.default_timeout = 5

    @retry_and_handle_exceptions()
    def xpath_check_timeout(self, name , timeout=None):
        """ xpath 等待确认元素可以点击"""

        timeout = timeout or self.default_timeout

        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, f'//*[@text="{name}"]')))

    @retry_and_handle_exceptions()
    def xpath_check_display_timeout(self, name , timeout=None):
        """ xpath 等待确认元素是否显示"""

        timeout = timeout or self.default_timeout

        return WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located((By.XPATH, f'//*[@text="{name}"]')))

    @retry_and_handle_exceptions()
    def check_list_timeout(self, by_method , locator , timeout=None):
        """等待确认元素列表是否显示"""

        timeout = timeout or self.default_timeout

        return WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_all_elements_located(( by_method , locator)))

    @retry_and_handle_exceptions()
    def check_timeout(self, by_method , locator , timeout=None):
        """等待确认元素可以点击"""

        timeout = timeout or self.default_timeout

        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by_method, locator)))

    @retry_and_handle_exceptions()
    def check_display_timeout(self , by_method , locator ,timeout=None):
        """等待确认元素是否显示"""

        timeout = timeout or self.default_timeout

        return WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located((by_method , locator )))


#----------------------------------具体使用方法
class Operation_method(Base_note_class):


    def xpath_text_click(self , name , should_click=True):
        """ 通过 XPath 和 文本定位元素并点击 """

        element = self.xpath_check_timeout(name)

        if not element:

            logging.error(f"未获取到元素 {name} ")

            return False

        if should_click is not None:

            element.click()

        return element

    def by_parent_index_click(self, by_method, locator, by_method1, locator1,index=0,should_click=True):
        """通过获取父元素后通过下标定位子元素"""

        parent_elements = self.check_timeout( by_method , locator)

        if not parent_elements.is_displayed():

            logging.error(f"未找到 {locator} 父元素")

        child_element = parent_elements.find_elements(by_method1, locator1)

        if len(child_element) == 0:

            logging.error(f"未找到 {locator1} 子元素")

        if child_element is not None:

            self.check_timeout(by_method1, locator1)

            if index < len(child_element):

                if should_click is not None:

                    child_element[index].click()

                    return True

            else:

                logging.error(f"下标({index})越界，无法获取元素")

            return child_element

    def by_element_click(self, by_method, locator, should_click=True):
        """直接定位并点击某个元素"""

        element = self.check_timeout( by_method , locator)

        if element:

            if should_click is not None:

                element.click()

            return True

        logging.error(f"未找到 {locator} 元素")

        return False

    def by_name_click(self, by_method , locator , name , should_click=True):
        """通过获取元素列表，定位文本获取元素"""

        elements = self.check_list_timeout( by_method , locator)

        if not elements:

            logging.error(f"未找到 {locator} 元素")

            return False

        for element in elements:

            if element.text == name:

                if should_click is not None:

                    element.click()

                return elements

    def by_index_name_click(self, by_method, locator, name, index=0, should_click=True):
        """通过获取元素列表，定位下标获取元素"""

        elements = self.check_list_timeout(by_method , locator)

        if not elements:

            logging.error(f"未找到 {locator} 元素")

        if index < len(elements):

            element = elements[index]

            if should_click is not None:

                element.click()

            if element.text != name :

                logging.error(f"未找到 {name} 元素")
        else:

            logging.error(f"下标({index})越界，无法获取元素")

            return False

    def by_index_click(self, by_method, locator, index=0, should_click=True):
        """通过获取元素列表，定位下标获取元素"""

        elements = self.check_list_timeout(by_method , locator)

        if not elements:

            logging.error(f"未找到 {locator} 元素")

        if index < len(elements):

            element = elements[index]

            if should_click is not None:

                if element.is_enabled():

                    element.click()

                else:

                    logging.info(f"元素不能点击")
        else:
            logging.error(f"下标({index})越界，无法获取元素")

            return False

    def wait_check_toast(self, toast_true , toast_false=None , toast_timeout = 5):
        """ 判断 当前页面 是否显示 某个toast弹窗 """

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

    def wait_input_box(self, by_method, locator, name):
        """ 定位指定输入框 ， 输入内容 """

        input_box = self.check_timeout(by_method, locator)

        input_box.send_keys(name)

    def wait_for_press_name(self, by_method, locator, name ):
        """ 通过获取文本然后长按某个元素 """

        elements = self.check_list_timeout(by_method, locator)

        for element in elements:

            if element.text == name:

                actions = ActionBuilder(self.driver)

                actions.pointer_action.click_and_hold(element)

                actions.perform()

                time.sleep(2)

                break
        else:
            logging.error(f"未找到指定{name}测试文件或笔记")


    def obtain_element_text(self,by_method, locator):

        elements = self.check_display_timeout(by_method, locator)

        return elements.text

    def obtain_element_list_test(self,by_method, locator):

        element_list = []

        elements = self.check_list_timeout(by_method, locator)

        if elements:

            for element in elements:

                text = element.text

                if text:

                    element_list.append(text)

        return element_list

    def pop_up_check_name_(self , by_method, locator , name ):
        """ 判断弹窗是否显示然后点击弹窗 """

        try:
            popup = self.check_display_timeout(by_method, locator)

            if popup.is_displayed():

                elements = self.check_list_timeout(by_method, locator)

                for element in elements:

                    if element.text == name:

                        self.xpath_check_timeout(name)

                        element.click()

                        return True
            else:
                return False

        except TimeoutException:
            logging.info(f"弹窗未显示")

        except Exception as e:
            logging.error(f"获取异常{e}")
            return False

    # def click_slice(self, start_screen_width, start_screen_height, end_screen_width, end_screen_height):
    #
    #     screen_size = self.driver.get_window_size()
    #
    #     start_x = int(screen_size['width'] * start_screen_width)
    #     start_y = int(screen_size['height'] * start_screen_height)
    #
    #     end_x = int(screen_size['width'] * end_screen_width)
    #     end_y = int(screen_size['height'] * end_screen_height)
    #
    #     action = TouchAction(self.driver)
    #
    #     action.press(x=start_x, y=start_y).wait(50).move_to(x=end_x, y=end_y).release().perform()

    def click_slice(self, start_screen_width, start_screen_height, end_screen_width, end_screen_height):
        screen_size = self.driver.get_window_size()
        start_x = int(screen_size['width'] * start_screen_width)
        start_y = int(screen_size['height'] * start_screen_height)
        end_x = int(screen_size['width'] * end_screen_width)
        end_y = int(screen_size['height'] * end_screen_height)
        # logging.info(f"Calculated start coordinates: ({start_x}, {start_y})")
        # logging.info(f"Calculated end coordinates: ({end_x}, {end_y})")
        self.driver.swipe(start_x, start_y, end_x, end_y, duration=100)

# -----------------------------单一方法------------------
    def by_pop_time(self, by_method, locator, timeout, prompt):
        """""检查某个弹窗是否在指定时间内消失"""""

        try:

            WebDriverWait(self.driver, timeout).until_not(
                EC.presence_of_element_located((by_method, locator)))

        except TimeoutException:

            logging.error(f" {prompt} , {timeout} 秒后超时")

    def wait_for_screen_size(self, start_screen_width , start_screen_height):
        """""通过坐标点击页面"""""

        # screen_size = self.driver.get_window_size()

        start_x = start_screen_width
            # int(screen_size['width'] * start_screen_width)

        start_y = start_screen_height
            # int(screen_size['height'] * start_screen_height)

        action = TouchAction(self.driver)

        action.press(x=start_x, y=start_y).release().perform()

    def by_take_pop(self, name_ok, prompt,time_out = 180):
        """""
        通过某个弹窗显示-消失获取耗时
        """""

        self.xpath_text_click(name_ok)

        while True:
            try:

                start = time.time()

                WebDriverWait(self.driver, time_out , poll_frequency=0.1).until(EC.visibility_of_element_located((By.XPATH, f'//*[@text="模板"]')))

                end = time.time()

                logging.info(f"{prompt}{(end - start):.2f} 秒")

                break

            except TimeoutException as e:

                logging.error(f"导入{prompt}文件，{time_out}秒后导入超时{e}")

            except Exception as e:

                 logging.error(f"{prompt}其他异常{e}")
