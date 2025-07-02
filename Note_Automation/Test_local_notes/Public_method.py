import allure
import logging
import pytest
from selenium.webdriver.common.by import By
from Note_Automation.Note_Class.Note_class import Operation_method
from Note_Automation.config import driver
from Note_Automation.conftest import get_device_info
from pathlib import Path
import time
import PyPDF2
import subprocess

device_info = get_device_info()

if device_info:

    device_region = device_info.get('device_region')

class Public_method:

    def __init__(self):
    
        self.driver = driver

        self.method = Operation_method(self.driver)

    # 创建一个手写笔记
    def create_handwritten_notes(self):

        # 二级菜单中点击手写笔记
        self.method.xpath_text_click("手写笔记")

        # 手写笔记创建页面点击 创建
        self.method.xpath_text_click("创建")

        # 退出手写笔记
        self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')

    # 创建一个文本笔记
    def create_text_notes(self,prompt=None):

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

    # 文本笔记引导确认
    def text_note_guide(self , text_guide , text_guide_ok ):
        """ 确认首次进入文本笔记时出现的引导提示 """

        try:
            self.method.xpath_text_click(text_guide,None)
            self.method.xpath_text_click(text_guide_ok,None)

        except Exception as e :

            logging.warning(f"文本笔记引导 {text_guide} 异常 {e}")

        self.method.xpath_text_click(text_guide_ok)

    # 创建一个会议笔记
    def create_meeting_notes(self,prompt=None):

        self.method.xpath_text_click("会议笔记")

        if prompt is not None:

            logging.info(f"已校验-跳过会议笔记校验提示")

        else:

            self.meeting_note_guide("仅支持向V3.5.4及以上版本同步","请在录音或转写文字完成后，再使用导出功能","知道了")

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

        # 校验文件夹弹窗

    def create_file(self):

        self.method.xpath_text_click("文件夹名称",None)
        self.method.xpath_text_click("文件夹-1",None)
        self.method.xpath_text_click("取消",None)
        self.method.xpath_text_click("确定")

#--------------------------------------------------------------------------------------------------

    def create_notes(self,have_notes=None):

        if have_notes is not None:

            self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

        else:

            self.method.xpath_text_click("创建笔记")

        self.create_handwritten_notes()

        self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

        self.create_text_notes(have_notes)

        # device_name, device_platform, device_region, devices_reader, device_size, driver_colour = get_device_info()

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

        self.method.by_parent_index_click(By.ID, "com.onyx:id/tool_layout", By.ID, "com.onyx:id/more_menu")

        self.method.xpath_text_click(more_options)

        if function is not None:
            self.method.xpath_text_click(function)

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
                    pdf_reader = PyPDF2.PdfReader(file)
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
        device_info = get_device_info()
        if device_info:
            devices_reader = device_info.get('devices_reader')

            if devices_reader == "阅读器":

                self.method.xpath_text_click("存储")

            else:

                self.method.by_parent_index_click(By.ID, "com.onyx:id/dock", By.ID, "com.onyx:id/imageView_cover_border", 2)


# --------------------------------------------------------------------------------------

    def capture_logcat(self, target_log, test_page, timeout=90):
        subprocess.run(['adb', 'logcat', '-c'])  # 清理旧日志
        start_time = time.time()

        # 使用 with 语句确保进程资源自动释放
        with subprocess.Popen(
                ['adb', 'logcat'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8'
        ) as process:

            try:
                for line in process.stdout:
                    current_time = time.time()
                    if current_time - start_time > timeout:
                        logging.info(f"{test_page} 在 {timeout} 秒内未获取到渲染日志。")
                        process.terminate()
                        process.wait()
                        return False

                    if target_log in line:
                        number_str = line.split(target_log)[1].strip()
                        parts = number_str.strip().split("--->")
                        # logging.info(f"ceshi 1 {parts}")

                        render, render_time = parts
                        # logging.info(f"ceshi 2 {render}")
                        # logging.info(f"ceshi 2 {render_time}")

                        if not render:
                            logging.info(f"{test_page} ：{render_time}")
                            process.terminate()
                            process.wait()
                            return True

                        elif render == 0:
                            logging.info(f"渲染数据为 0 异常")
                            return False

                        else:
                            logging.info(f"{test_page} ：{render_time}")

                        process.terminate()
                        process.wait()
                        return True


            except Exception as e:
                logging.error(f"捕获日志时发生异常: {e}")
                process.terminate()  # 异常时强制终止进程
                process.wait()  # 等待进程结束
                return False
