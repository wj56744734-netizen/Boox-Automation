from threading import Event
from queue import Queue
from threading import Lock
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from boox_automation.ui_ops.operations import Operation_method
from boox_automation.engine.elements import get_element_loader
from boox_automation.ui_ops.logcat import Logcat
from boox_automation.driver import driver
from boox_automation.devices.info import Device_basic_information
from selenium.common.exceptions import TimeoutException
from pathlib import Path
import openpyxl
import os
import pytest
import pypdf
import subprocess
import logging
import time
import re

# 获取设备基础信息
devices = Device_basic_information()
try:
    device_info = devices.get_device_info()
except RuntimeError:
    device_info = None

if device_info:
    device_region = device_info.get('device_region')
    version_info = device_info.get('version_info')
    device_size = device_info.get('device_size')
    device_id = device_info.get('device_id')
else:
    device_region = None
    version_info = None
    device_size = None
    device_id = None

class Public_method:

    def __init__(self):
        self._result_queue = Queue()
        self._logcat_thread = None
        self._stop_event = Event()
        self._lock = Lock()
        self.driver = driver
        self.element_loader = get_element_loader()
        self.logcat = Logcat()
        self.method = Operation_method(self.driver)

    def get_version(self, short=False):
        if not version_info:
            return None
        match = re.search(r'[vV]?\d+\.\d+(?:\.\d+)?', version_info)
        if match:
            full = match.group().lstrip('vV')
        elif re.search(r'dev', version_info, re.IGNORECASE):
            full = "dev"
        else:
            full = "未找到符合格式的版本号"

        if short and full not in ("dev", "未找到符合格式的版本号"):
            parts = full.split('.')
            if len(parts) >= 2:
                return '.'.join(parts[:2])
        return full
    def create_handwritten_notes(self, toolbar=True):
        """创建手写笔记"""

        self.method.xpath_text_click(element_key="笔记首页.创建手写笔记")
        self.method.xpath_text_click("创建")

        if toolbar:
            version_str = self.get_version(short=True)
            if version_str == "4.2" and device_size != "6.13":
                self.toolbar_navigation()

        self.method.by_element_click(element_key="手写笔记.退出手写笔记")

    def create_text_notes(self, prompt=None):
        """创建文本笔记"""

        self.method.xpath_text_click(element_key="文本笔记.进入文本笔记")
        self.method.xpath_text_click("创建")

        if prompt is not None:
            logging.info(f"已校验-跳过文本笔记校验提示")
        else:
            self.text_note_guide(
                "文本笔记不支持向V3.3.1或更低版本同步",
                "确定"
            )

        self.method.by_element_click(element_key="文本笔记.文本笔记退出按钮")

    def text_note_guide(self, text_guide, text_guide_ok):
        """确认首次进入文本笔记时出现的引导提示"""
        try:
            self.method.xpath_text_click(text_guide, should_click=None)
            self.method.xpath_text_click(text_guide_ok, should_click=None)
        except Exception as e:
            logging.warning(f"文本笔记引导 {text_guide} 异常 {e}")
        self.method.xpath_text_click(text_guide_ok)

    def create_meeting_notes(self, prompt=None):
        """创建会议笔记"""

        self.method.xpath_text_click(element_key="会议笔记.进入会议笔记")

        if prompt is not None:
            logging.info(f"已校验-跳过会议笔记校验提示")
        else:
            self.meeting_note_guide(
                "仅支持向V3.5.4及以上版本同步",
                "请在录音或转写文字完成后，再使用导出功能",
                "知道了"
            )

        self.method.by_element_click(element_key="会议笔记.会议笔记退出按钮")
    def create_boundless_notes(self, toolbar=True):
        """创建无界笔记"""

        self.method.xpath_text_click(element_key="无界笔记.进入无界笔记")
        self.method.xpath_text_click("创建")

        if toolbar:
            version_str = self.get_version(short=True)
            if version_str == "4.2" and device_size != "6.13":
                self.toolbar_navigation()

        self.method.by_element_click(element_key="无界笔记.无界笔记退出按钮")

    def meeting_note_guide(self, meeting_guide_1, meeting_guide_2, meeting_guide_ok):
        """确认首次进入会议笔记时出现的引导提示"""
        try:
            self.method.xpath_text_click(meeting_guide_1, should_click=None)
            self.method.xpath_text_click(meeting_guide_ok, should_click=None)
        except Exception as e:
            logging.warning(f"会议笔记引导 {meeting_guide_1} 异常 {e}")
        try:
            self.method.click_slice(0.7, 0.5, 0.4, 0.5)
            self.method.xpath_text_click(meeting_guide_2, should_click=None)
        except Exception as e:
            logging.warning(f"会议笔记引导 {meeting_guide_2} 异常 {e}")

        self.method.xpath_text_click(meeting_guide_ok)

    def enter_note_app(self):
        """进入笔记应用首页"""

        devices_info = devices.get_device_info()
        if device_info:
            devices_reader = devices_info.get('devices_reader')
            if devices_reader == "阅读器":
                # if device_size == "6":
                #     self.method.xpath_parent_click(
                #         xpath='(//android.widget.ImageView[@resource-id="com.onyx:id/function_icon"])[3]')
                # else:
                self.method.xpath_parent_click(
                        xpath='(//android.widget.ImageView[@resource-id="com.onyx:id/function_icon"])[3]')
            else:
                self.method.xpath_parent_click(
                    xpath='(//android.widget.ImageView[@resource-id="com.onyx:id/title_image"])[2]')
    def toolbar_navigation(self):
        """4.2 版本工具条首次引导：直接 find_element + 3s 超时，不经过 retry 装饰器。"""
        time.sleep(2)

        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.wait import WebDriverWait

        try:
            WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.ID, "com.onyx.android.note:id/tv_title"))
            )
        except Exception:
            logging.debug("工具条引导标题未出现，跳过")
            return False

        try:
            self.method.by_element_click(element_key="手写笔记.工具条-首次引导确认")
            return True
        except Exception as e:
            logging.debug(f"工具条引导确认按钮未找到，跳过: {e}")
            return False
    def _import_is_time_consuming(self, click_key, document_format, toolbar=True, template_text=None):
        """通过 logcat 获取文档导入各阶段耗时（ms），返回 (convert_time, create_time, open_time)。"""
        document_format = document_format.lower()
        document_convert = 'ImportDocumentsAction convertDocumentToPdf file='
        doc_to_note = 'ImportDocumentsAction createNoteFromDocFile file='
        open_note = 'open note document:OpenNoteBean{documentId'
        raw_log_debug = os.getenv("NOTE_IMPORT_TIME_DEBUG", "0") == "1"

        convert_time = "0"
        create_time = "0"
        open_time = "0"

        if document_format in ("png", "jpeg", "jpg"):
            target_logs = [open_note]
            single_timeout = 5
        else:
            target_logs = [document_convert, doc_to_note, open_note]
            single_timeout = 100

        self.logcat.capture_logcat(
            target_logs=target_logs,
            single_timeout=single_timeout,
            block=False
        )
        time.sleep(1)
        self.method.xpath_text_click(element_key=click_key)
        logs = self.logcat.wait_result(timeout=single_timeout + 5)

        detailed_matches = logs.get("detailed_matches", {}) if logs else {}
        for k, v in detailed_matches.items():
            if raw_log_debug:
                logging.info(f"[IMPORT_TIME_DEBUG] {document_format} | {k} | raw_log={v}")
            res = re.search(r'--->\s*(\d+)ms', v)
            if not res:
                logging.warning(f"导入耗时日志未匹配到耗时，文档类型：{document_format}，日志：{v}")
                continue
            num = res.group(1)
            if k == document_convert:
                convert_time = num
            elif k == doc_to_note:
                create_time = num
            elif k == open_note:
                open_time = num

        if logs and not logs.get('success'):
            message = logs.get('message', '未知错误')
            unmatched = logs.get('unmatched_targets', [])

            if document_format in ("png", "jpeg", "jpg") and open_time == "0" and template_text:
                entered_note = self.method.xpath_text_click(template_text, should_click=None)
                if entered_note:
                    open_time = "0"
                    logging.warning(
                        f"图片导入已进入笔记页，但未捕获到耗时日志，文档类型：{document_format}，模板文本：{template_text}"
                    )
                else:
                    logging.error(
                        f"图片导入日志缺失且页面模板文本未显示，文档类型：{document_format}，"
                        f"原因：{message}，未捕获：{unmatched}"
                    )
            else:
                logging.error(f"导入耗时日志捕获失败，文档类型：{document_format}，原因：{message}，未捕获：{unmatched}")

        if create_time and open_time and create_time == open_time and create_time != "0":
            logging.warning(
                f"导入耗时疑似重复：文档类型={document_format}，create_time={create_time}ms，open_time={open_time}ms，"
                "可能为底层日志上报值一致"
            )

        if toolbar:
            version_str = self.get_version(short=True)
            if version_str == "4.2" and device_size != "6.13":
                self.toolbar_navigation()

        return convert_time, create_time, open_time

    def take_file(self, file_name, toolbar=True):
        """单个文件导入，返回不含后缀的文件名。"""

        self.get_file(file_name)

        last_dot_index = file_name.rfind('.')
        if last_dot_index != -1:
            file_name1 = file_name[:last_dot_index]
            file_name2 = file_name[last_dot_index + 1:]
        else:
            file_name1 = file_name
            file_name2 = "无后缀"

        convert_time, create_time, open_time = self._import_is_time_consuming(
            click_key="笔记首页.导入确认按钮",
            document_format=file_name2,
            toolbar=toolbar,
            template_text=file_name1
        )

        logging.info(f"文档导入耗时统计，文档类型：{file_name2}，文档名称：{file_name}")
        logging.info(f"流文档转换PDF：{convert_time}ms")
        logging.info(f"PDF文档转换笔记：{create_time}ms")
        logging.info(f"打开笔记：{open_time}ms")
        logging.info('-----------------------------------')

        return file_name1

    def import_bake(self):
        """导入后重置页面，回到文件选择页。"""
        self.method.by_element_click(element_key="通用操作.笔记内-返回按钮")
        time.sleep(1)
        self.method.by_element_click(element_key="通用操作.创建按钮")
        self.method.xpath_text_click(element_key="笔记首页.从本地文件导入")

    def import_file(self, file_route_name, file_route_name2):

        def circular_swipe(swipe):
            while True:
                page = self.method.obtain_element_text(element_key="设备相关.导入页码信息")
                page = page.split("/")
                current_page = int(page[0])
                total_pages = int(page[1])

                if swipe == current_page:
                    return True
                if swipe > current_page:
                    self.method.click_slice(0.8, 0.5, 0.2, 0.5)
                if swipe < current_page:
                    self.method.click_slice(0.2, 0.5, 0.8, 0.5)
                if swipe > total_pages:
                    logging.warning(f"目标页{swipe}超过总页数{total_pages}")
                    return False

        logging.debug(f"首次进入文件夹层级：{file_route_name} → {file_route_name2}")
        self.get_file(file_route_name, file_route_name2)

        circular_swipe(1)

        try:
            page_info = self.method.obtain_element_text(element_key="设备相关.导入页码信息")
            total_pages = int(page_info.split("/")[1])
            logging.debug(f"检测到文件夹总页数：{total_pages}")
        except (IndexError, ValueError) as e:
            logging.error(f"获取文件夹总页数失败: {e}，默认按1页处理")
            total_pages = 1

        all_imported_files = []
        for target_page in range(1, total_pages + 1):
            logging.debug(f"\n========== 开始处理第 {target_page}/{total_pages} 页 ==========")

            if not circular_swipe(target_page):
                logging.error(f"无法翻到第{target_page}页，跳过该页")
                continue

            element = self.driver.find_elements(By.ID, "com.onyx.android.note:id/title")
            current_page_file_count = len(element)
            if current_page_file_count == 0:
                logging.info(f"第{target_page}页无文件，跳过该页")
                continue
            logging.debug(f"第{target_page}页检测到 {current_page_file_count} 个文件")

            index = 0
            current_page_files = []
            toolbar_navigation = True
            while index < current_page_file_count:
                element = self.driver.find_elements(By.ID, "com.onyx.android.note:id/title")
                if index >= len(element):
                    logging.warning(f"第{target_page}页文件列表长度变化，下标{index}越界，跳过剩余文件")
                    break

                file_element = element[index].text
                logging.debug(f"第{target_page}页：处理第{index + 1}/{current_page_file_count}个文件 - {file_element}")

                file_name = self.take_file(file_element, toolbar=toolbar_navigation)
                toolbar_navigation = False

                self.import_bake()
                circular_swipe(target_page)

                current_page_files.append(file_name)
                index += 1

            logging.debug(f"第{target_page}页处理完成，共导入 {len(current_page_files)} 个文件")
            all_imported_files.extend(current_page_files)

        logging.debug(f"\n所有页面处理完成，累计导入文件总数：{len(all_imported_files)}")
        return all_imported_files

    def import_file_bootstrap(self, guide_name, guide_ok):
        """首次进入从本地文件导入页时弹出的引导提示。

        同时支持 YAML 元素键（通过 element_key 参数）和原始 UI 文本（通过 name 参数）。
        """
        try:
            self.method.xpath_text_click(name=guide_name, should_click=None)
        except Exception:
            try:
                self.method.xpath_text_click(name=guide_name, should_click=None)
            except Exception:
                logging.info(f"未检测到导入引导文案，跳过")

        try:
            self.method.xpath_text_click(name=guide_ok)
        except Exception:
            try:
                self.method.xpath_text_click(name=guide_ok)
            except Exception:
                logging.info(f"未检测到导入引导确认按钮，跳过")
    def get_file(self, file_route_name, file_route_name2=None, file_route_name3=None):
        """获取文件，支持 YAML 元素键和动态文件名。"""

        def handle_file(file_name):
            try:
                time.sleep(3)
                return self.method.xpath_text_click(name=file_name)
            except ValueError:
                return self.method.xpath_text_click(name=file_name)

        file = handle_file(file_route_name)
        if not file:
            pytest.skip(f"未找到指定文件名为({file_route_name})的测试文件，跳过当前用例")

        if file_route_name2 is not None:
            file1 = handle_file(file_route_name2)
            if not file1:
                pytest.skip(f"未找到指定文件名为({file_route_name2})的测试文件，跳过当前用例")

        if file_route_name3 is not None:
            file1 = handle_file(file_route_name3)
            if not file1:
                pytest.skip(f"未找到指定文件名为({file_route_name3})的测试文件，跳过当前用例")

    def enter_storage(self):
        """判断设备类型后执行不同操作，阅读器和平板元素定位方式不一样"""
        devices_info = devices.get_device_info()
        if device_info:
            devices_reader = devices_info.get('devices_reader')
            if devices_reader == "阅读器":
                self.method.xpath_text_click(element_key="设备相关.阅读器存储入口")
            else:
                self.method.xpath_parent_click(
                    xpath='(//android.widget.ImageView[@resource-id="com.onyx:id/imageView_cover_border"])[15]')
    def restore_notes(self, file_route_name, file_route_name2=None, file_route_name3=None):
        """从存储恢复 .note 笔记文件"""

        self.enter_storage()

        self.method.by_name_click(element_key="设备相关.存储卷列表")

        self.get_file(f"{file_route_name}", f"{file_route_name2}", f"{file_route_name3}")

        self.method.by_name_click(element_key="通用操作.笔记内-导入确认按钮")

        from boox_automation.core.config import timeout_import_duration
        self.method.by_pop_time(by_method=By.ID, locator="com.onyx.android.note:id/progress", timeout=timeout_import_duration(), prompt="导入笔记超时")

        self.driver.press_keycode(3)

    def attribute_guide(self, guide):
        """处理笔记属性引导弹窗"""
        logging.debug("检查属性引导弹窗")
        try:
            wait = WebDriverWait(self.driver, 5)
            element = wait.until(EC.element_to_be_clickable((By.XPATH, f'//*[@text="{guide}"]')))
            logging.debug(f"找到引导: {element}")
            if element:
                logging.debug("点击弹窗知道了")
                self.method.xpath_text_click(element_key="笔记首页.弹窗通用知道了")
        except TimeoutException:
            logging.debug("未出现属性引导弹窗，跳过")
        except Exception as e:
            logging.error(f"属性引导处理异常: {e}")
            raise

