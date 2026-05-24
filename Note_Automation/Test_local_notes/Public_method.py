from threading import Event
from queue import Queue
from threading import Lock
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from Note_Automation.Note_class.Note_class import Operation_method
from Note_Automation.config import driver
from pathlib import Path
from Note_Automation.Devices_list.Device_basic_information import Device_basic_information
import allure
import openpyxl
import pytest
import pypdf
import re
import subprocess
import logging
import time

#获取设备基础信息
devices = Device_basic_information()
try:
    device_info = devices.get_device_info()
except RuntimeError:
    device_info = None
device_region = device_info.get('device_region') if device_info else None
class Public_method:

    def __init__(self):
        self._result_queue = Queue()
        self._logcat_thread = None
        self._stop_event = Event()
        self._lock = Lock()
        self.driver = driver
        self.method = Operation_method(self.driver)

    def get_version(self, short=False):
        """从设备信息中解析版本号；short=True 返回主版本（如 4.2）。"""
        info = Device_basic_information().get_device_info() or {}
        raw = (info.get('version_info') or '').strip()
        if not raw:
            return None
        if re.search(r'dev', raw, re.IGNORECASE):
            return 'dev'
        match = re.search(r'\d+(?:\.\d+){1,2}', raw)
        if not match:
            return raw
        version = match.group()
        if short:
            parts = version.split('.')
            return '.'.join(parts[:2])
        return version

    def dismiss_first_time_guide(self, timeout=3, max_steps=4, dismiss_text="知道了"):
        """关闭首次进入画布等场景出现的引导弹窗。
        - 引导可能是多步骤，按出现顺序连续点击同一确认按钮，直至不再出现为止
        - 全程静默：未出现引导时不抛错，不影响后续操作
        """
        dismissed = 0
        for _ in range(max_steps):
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((By.XPATH, f'//*[@text="{dismiss_text}"]'))
                )
                element.click()
                dismissed += 1
            except Exception:
                break
        if dismissed:
            logging.debug(f"已关闭首进引导 {dismissed} 次（按钮：{dismiss_text}）")
        return dismissed

    def create_handwritten_notes(self):
        """ 创建手写笔记 """

        # 二级菜单中点击手写笔记
        self.method.xpath_text_click("手写笔记")

        # 手写笔记创建页面点击 创建
        self.method.xpath_text_click("创建")

        # 首次进入画布会出现工具条引导，先关闭再退出
        self.dismiss_first_time_guide()

        # 退出手写笔记
        self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')

    def create_text_notes(self,prompt=None):
        """ 创建文本笔记 """

        # 二级菜单中点击文本笔记
        self.method.xpath_text_click("文本笔记")

        # 文本笔记创建页面点击 创建
        self.method.xpath_text_click("创建")

        if prompt is not None:

            logging.info(f"已校验-跳过文本笔记校验提示")

        else:

            self.text_note_guide("文本笔记不支持向V3.3.1或更低版本同步","确定")

        with allure.step("退出文本笔记"):

            self.method.by_element_click(By.ID, 'com.onyx.android.note:id/quit')

    def text_note_guide(self , text_guide , text_guide_ok ):
        """ 确认首次进入文本笔记时出现的引导提示 """

        try:
            self.method.xpath_text_click(text_guide,None)
            self.method.xpath_text_click(text_guide_ok,None)

        except Exception as e :

            logging.warning(f"文本笔记引导 {text_guide} 异常 {e}")

        self.method.xpath_text_click(text_guide_ok)

    def create_meeting_notes(self,prompt=None):
        """ 创建会议笔记 """

        self.method.xpath_text_click("会议笔记")

        if prompt is not None:

            logging.info(f"已校验-跳过会议笔记校验提示")

        else:

            self.meeting_note_guide("仅支持向V3.5.4及以上版本同步","请在录音或转写文字完成后，再使用导出功能","知道了")

        self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')

    def create_boundless_notes(self):
        """ 创建无界笔记 """

        # 二级菜单中点击无界笔记
        self.method.xpath_text_click("无边笔记")

        # 手写笔记创建页面点击 创建
        self.method.xpath_text_click("创建")

        # 首次进入画布会出现工具条引导，先关闭再退出
        self.dismiss_first_time_guide()

        # 退出无界笔记
        self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')

    def meeting_note_guide(self, meeting_guide_1 , meeting_guide_2 , meeting_guide_ok):
        """ 确认首次进入会议笔记时出现的引导提示 """

        try:
            self.method.xpath_text_click(meeting_guide_1,None)
            self.method.xpath_text_click(meeting_guide_ok,None)
        except Exception as e :
            logging.warning(f"会议笔记引导 {meeting_guide_1} 异常 {e}")
        try:
            self.method.click_slice(0.7,0.5 , 0.4, 0.5)
            self.method.xpath_text_click(meeting_guide_2,None)
        except Exception as e :
            logging.warning(f"会议笔记引导 {meeting_guide_2} 异常 {e}")

        # 关闭引导弹窗
        self.method.xpath_text_click(meeting_guide_ok)

    def create_file(self):
        """ 创建文件夹 """

        self.method.xpath_text_click("文件夹名称",None)
        self.method.xpath_text_click("文件夹-1",None)
        self.method.xpath_text_click("取消",None)
        self.method.xpath_text_click("确定")

    def create_notes(self,have_notes=None):

        if have_notes is not None:

            self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

        else:

            self.method.xpath_text_click("创建笔记")

        self.create_handwritten_notes()

        self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

        self.create_text_notes(have_notes)

        if device_region == "国内":

            self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

            self.create_meeting_notes(have_notes)

# -------------------------------------------------------------------------------------------------
    def import_file(self, file_route_name, file_route_name2):

        # 本地文件找到指定文件夹
        self.get_file(file_route_name, file_route_name2)

        file_names = []

        element = self.driver.find_elements(By.ID, "com.onyx.android.note:id/title")

        index = 0

        # 获取元素列表长度
        while index < len(element):

            # 更新元素列表避免元素失效
            element = self.driver.find_elements(By.ID, "com.onyx.android.note:id/title")

            file_element = element[index].text

            file_name = self.take_file(file_element)

            self.import_bake()

            file_names.append(file_name)

            index += 1

        return file_names

    def take_file(self , file_name):

        # 选中指定文件
        self.get_file(file_name)

        parts = file_name.split(".")

        file_name1 = parts[0]

        self.method.by_take_pop("确认", f"文档 （{file_name1}） ，导入耗时 ")

        return file_name1

    def import_bake(self):

        self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')

        self.method.by_element_click(By.ID, 'com.onyx:id/create_icon')

        #创建笔记二级菜单点击 从本地文件
        self.method.xpath_text_click("从本地文件")

    # 首次进入从本地文件导入 文件管理器 引导确认
    def import_file_bootstrap(self , guide_name , guide_ok):

        # 首次进入从本地文件导入 文件管理器 引导确认
        self.method.by_name_click(By.ID, "com.onyx.android.note:id/tv_sub_title", guide_name,None)

        # 引导弹窗点击确认
        self.method.by_name_click(By.ID, "com.onyx.android.note:id/btn_ensure", guide_ok,None)

        # 引导确认校验后 关闭引导弹窗
        self.method.xpath_text_click(guide_ok)

# -----------------------------------------------------------------------------------------------
    def more_menus(self, more_options, function=None):
        """ 笔记首页更多菜单点击 """

        self.method.by_sub_index_click(By.ID, "com.onyx:id/tool_layout", By.ID, "com.onyx:id/more_menu")

        self.method.xpath_text_click(more_options)

        if function is not None:

            slide = 0
            while slide < 3:
                try:
                    wait = WebDriverWait(self.driver, 3)
                    element = wait.until(
                        EC.element_to_be_clickable((By.XPATH, f'//*[@text="{function}"]'))
                    )
                    element.click()
                    break
                except:
                    self.method.click_slice(0.5, 0.7, 0.5, 0.3)
                    slide += 1

            if slide == 3:
                logging.info(f" 翻页后寻找 {slide} 次 , 未找到 {function} ")

# ----------------------------------------------------------------------------------------------------
    def get_file(self , file_route_name , file_route_name2=None , file_route_name3=None):
        """ 本地文件找到指定文件夹 """

        file = self.method.xpath_text_click(file_route_name)
        if not file:
            pytest.skip(f"未找到指定文件名为({file_route_name})的测试文件，跳过当前用例")

        if file_route_name2 is not None:
            file1 = self.method.xpath_text_click(file_route_name2)
            if not file1:
                pytest.skip(f"未找到指定文件名为({file_route_name2})的测试文件，跳过当前用例")

        if file_route_name3 is not None:
            file1 = self.method.xpath_text_click(file_route_name3)
            if not file1:
                pytest.skip(f"未找到指定文件名为({file_route_name3})的测试文件，跳过当前用例")

    @staticmethod
    def get_pdf_info(pdf_path):

        pdf_path = Path(pdf_path)
        if pdf_path.exists():
            try:
                # 获取文件大小（字节）
                file_size_bytes = pdf_path.stat().st_size
                # 将字节转换为兆字节（MB）
                file_size_mb = file_size_bytes / (1024 * 1024)
                print(f"文件大小为: {file_size_mb:.2f} MB")

                # 获取文件的元数据信息
                file_stat = pdf_path.stat()

                # 将时间戳转换为年月日格式
                creation_time = time.strftime('%Y-%m-%d', time.localtime(file_stat.st_ctime))
                access_time = time.strftime('%Y-%m-%d', time.localtime(file_stat.st_atime))
                modification_time = time.strftime('%Y-%m-%d', time.localtime(file_stat.st_mtime))

                print(f"文件的创建时间: {creation_time}")
                print(f"文件的最后访问时间: {access_time}")
                print(f"文件的最后修改时间: {modification_time}")

                # 获取 PDF 页面尺寸
                with open(pdf_path, 'rb') as file:
                    pdf_reader = pypdf.PdfReader(file)
                    # 获取第一页
                    first_page = pdf_reader.pages[0]
                    # 获取页面的宽度和高度，单位是点（points）
                    width_points = first_page.mediabox[2]
                    height_points = first_page.mediabox[3]
                    # 换算成厘米
                    width_cm = width_points * 2.54 / 72
                    height_cm = height_points * 2.54 / 72
                    print(f"PDF 文件: {pdf_path}")
                    print(f"页面宽度: {width_cm:.3f} 厘米")
                    print(f"页面高度: {height_cm:.3f} 厘米")
            except Exception as e:
                print(f"处理 PDF 文件 {pdf_path} 时出错: {e}")
        else:
            print(f"文件 {pdf_path} 未找到，请检查文件路径是否正确。")

    def enter_storage(self):
        """""
        判断设备类型后执行不同操作，阅读器和平板元素定位方式不一样
        """""
        devices_info = devices.get_device_info()

        if device_info:

            devices_reader = devices_info.get('devices_reader')

            if devices_reader == "阅读器":

                self.method.xpath_text_click("存储")

            else:

                self.method.by_sub_index_click(By.ID, "com.onyx:id/dock", By.ID, "com.onyx:id/imageView_cover_border", 2)

# --------------------------------------------------------------------------------------

    def shape_test(self , uid , shape_type=None, width=None, pressure=None, color=None, line_style=None, count=None, point=None):
        # 完整shape生成命令
        cmd = f'adb -s {uid} shell am broadcast -a com.onyx.android.note.test.add_custom_shape '\
              + '--ei test_shape_type_index %s ' % shape_type\
              + '--es test_shape_pressure "%s" ' % pressure \
              + '--ei test_shape_line_style_index %s ' % line_style\
              + '--es test_shape_stroke_width %s ' % width\
              + '--ei test_shape_color_index %s ' % color\
              + '--ei test_shape_count %s ' % count\
              + '--es test_shape_start_end_point %s ' % point\
              + '--ez test_shape_draw_line_path true'
        print(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        exit_code = process.wait()

        # 打印输出和退出码
        print(f'Exit Code: {exit_code}\nOutput:\n{stdout}\nError:\n{stderr}')

    def get_screen_size(self ,uid):
        # 获取设备尺寸
        cmd = f'adb -s {uid} shell wm size'
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        # exit_code = process.wait()
        # print(f'Exit Code: {exit_code}\nOutput:\n{stdout}\nError:\n{stderr}')
        size = stdout.decode('utf-8').split()
        w_and_h = size[2].split('x')

        width = w_and_h[0]
        height = w_and_h[1]
        # print(w_and_h, width, height)
        return int(width), int(height)

    def start_end_point(self ,width, height, x1=50,):
        start_x = x1
        end_x = width - 100
        start_y = 0
        end_y = 50
        height = height

        def new_point():
            nonlocal start_y, end_y
            new_start_y = start_y + 50
            new_end_y = end_y + 50
            if new_start_y > height:
                start_y = 0
                end_y = 0
            else:
                start_y = new_start_y
                end_y = new_end_y
            return f'{start_x},{start_y},{end_x},{end_y}'

        return new_point

    def read_excel(self ,filepath, sheetname: str):
        """
        读取excel中指定sheet
        :param filepath: excel表位置
        :param sheetname: 要读取的表名
        :return: 表数据
        """
        workbook = openpyxl.load_workbook(filepath)
        worksheet = workbook[sheetname]
        data = []
        for row in worksheet.iter_rows(min_row=2, min_col=1, values_only=True):
            # print(row)
            data.append(row)
        return data

    def create_shape(self,uid):
        width, height = self.get_screen_size(uid)
        get_point = self.start_end_point(width, height)
        test_data_list = self.read_excel('/Users/xiaoyu/Downloads/shapeTestdata.xlsx', 'Sheet2')
        # 获取参数
        for i, data in enumerate(test_data_list):
            point = get_point()
            test_data = data + (point,)
            print(test_data)
            if int(point.split(',')[-1]) == 0:
                cmd = f'adb -s {uid} shell am broadcast -a com.onyx.android.note.test.change_page --ez test_next_page true'
                subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print('next page')
                time.sleep(1)
                self.shape_test(uid, *test_data)
            else:
                self.shape_test(uid, *test_data)
            time.sleep(3)
