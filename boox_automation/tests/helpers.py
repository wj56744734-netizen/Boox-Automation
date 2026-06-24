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

devices = Device_basic_information()

_device_info_cache = None
_DEVICE_INFO_KEYS = {'device_region', 'version_info', 'device_size', 'device_id'}


def _get_device_info():
    """懒加载设备信息：首次访问时获取，后续命中缓存。"""
    global _device_info_cache
    if _device_info_cache is None:
        try:
            _device_info_cache = devices.get_device_info()
        except RuntimeError:
            _device_info_cache = {}
    return _device_info_cache


def __getattr__(name):
    if name in _DEVICE_INFO_KEYS:
        info = _get_device_info()
        return info.get(name) if info else None
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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
        version_info = _get_device_info().get('version_info', '')
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
            self.method.xpath_text_click(name='知道了')
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
        elif document_format == "pdf":
            target_logs = [doc_to_note, open_note]
            single_timeout = 100
        else:
            target_logs = [document_convert, doc_to_note, open_note]
            single_timeout = 100

        self.logcat.capture_logcat(
            target_logs=target_logs,
            single_timeout=single_timeout,
            block=False
        )
        time.sleep(1)
        self.method.xpath_text_click(name=f'{click_key}')

        deadline = time.time() + single_timeout + 5
        while time.time() < deadline:
            if not self.logcat.is_running():
                break

            # 首次导入时检查工具条引导并关闭（引导弹窗会遮挡笔记标题）
            if toolbar:
                try:
                    self.driver.find_element(By.ID, "com.onyx.android.note:id/tv_title")
                    self.method.xpath_text_click(name='知道了')
                    continue
                except Exception:
                    pass

            if template_text:
                try:
                    safe = str(template_text).replace("'", "\\'")
                    self.driver.find_element(By.XPATH, f"//*[@text='{safe}']")
                    self.logcat.stop_capture()
                    break
                except Exception:
                    pass

            time.sleep(3)

        if self.logcat.is_running():
            self.logcat.stop_capture()

        logs = self.logcat.wait_result(timeout=2) or {}

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

            # 图片/PDF 日志缺失但已进入笔记页 → 正常现象（导入过快不打印日志），INFO 级别
            if document_format in ("png", "jpeg", "jpg", "pdf") and template_text:
                entered_note = self.method.xpath_text_click(template_text, should_click=None)
                if entered_note:
                    logging.info(f"导入耗时日志部分缺失（导入过快未打印），文档类型：{document_format}")
                else:
                    logging.error(
                        f"导入日志缺失且页面模板文本未显示，文档类型：{document_format}，"
                        f"模板文本：{template_text}，可能原因：1) 应用崩溃 2) 导入仍在进行 3) 标题文本不匹配"
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
            click_key="确认",

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
        self.method.xpath_parent_click(xpath='//android.widget.ImageView[@resource-id="com.onyx.android.note:id/back_icon"]')
        time.sleep(1)
        self.method.xpath_parent_click(xpath='//android.widget.TextView[@text="创建"]')
        self.method.xpath_parent_click(xpath='//android.widget.TextView[@resource-id="com.onyx:id/title" and @text="从本地文件"]')

    def import_file(self, file_route_name, file_route_name2):

        def circular_swipe(swipe):
            max_iterations = 50
            iterations = 0
            while iterations < max_iterations:
                iterations += 1
                page = self.method.obtain_element_text(by_method='xpath',
                                                       locator='//android.widget.TextView[@resource-id="com.onyx.android.note:id/page_info"]')
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

            logging.error(f"circular_swipe 在 {max_iterations} 次翻页后仍未到达目标页 {swipe}")
            return False

        logging.debug(f"首次进入文件夹层级：{file_route_name} → {file_route_name2}")
        self.get_file(file_route_name, file_route_name2)

        circular_swipe(1)

        try:
            page_info = self.method.obtain_element_text(by_method='xpath',
                                                       locator='//android.widget.TextView[@resource-id="com.onyx.android.note:id/page_info"]')
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

        self.method.by_pop_time(by_method=By.ID, locator="com.onyx.android.note:id/progress", timeout=180, prompt="导入笔记超时")

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

