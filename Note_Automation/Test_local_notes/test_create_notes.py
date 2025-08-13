from Note_Automation.config import driver
from Note_Automation.Note_Class.Note_class import Operation_method
from Note_Automation.Test_local_notes.Public_method import Public_method
from Note_Automation.Devices_list.Device_basic_information import Device_basic_information
from Note_Automation.conftest import note_mark_china, note_mark_abroad,note_mark_increment
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import allure
import pytest
import logging
import time




#获取设备基础信息
devices = Device_basic_information()
device_info = devices.get_device_info()
if device_info:
    device_region = device_info.get('device_region')

@allure.feature("笔记创建相关测试类")
class Test_create_notes:

    def setup_method(self):
        self.driver = driver
        self.method = Operation_method(self.driver)
        self.public = Public_method()

    @pytest.mark.test
    @note_mark_china("创建手写笔记")
    @note_mark_increment("增量")
    def test_1_create_handwritten_note(self,note_test_initial):
        """""
        回归用例P0 --- 
        自动化用例 ： 用于测试在未登录状态下创建手写笔记的完整流程
        """""

        # 平板桌面 点击笔记应用
        self.method.xpath_text_click("笔记")

        # 无笔记未登记 点击创建笔记
        self.method.xpath_text_click("创建笔记")

        self.public.create_handwritten_notes()

        #校验当前目录是否正常创建手写笔记
        self.method.xpath_text_click("笔记-1",None)


    @note_mark_china("创建文本笔记")
    @note_mark_increment("增量")
    def test_2_create_text_note(self,note_test_initial):
        """""
        回归用例P0 ---
        自动化测试用例 ： 用于测试在未登录状态下创建文本笔记的完整流程
        """""

        # 平板桌面 点击笔记应用
        self.method.xpath_text_click("笔记")

        # 点击“创建笔记”按钮
        self.method.xpath_text_click("创建笔记")

        self.public.create_text_notes()

        # 校验当前目录是否正常创建文本笔记
        self.method.xpath_text_click("文本-1",None)


    @note_mark_abroad("创建会议笔记")
    @note_mark_increment("增量")
    def test_3_create_meeting_note(self,note_test_initial):
        """""
        回归用例P0 ---
        自动化测试用例 ： 用于测试在未登录状态下创建会议笔记的完整流程
        """""

        # 平板桌面 点击笔记应用
        self.method.xpath_text_click("笔记")

        # 点击“创建笔记”按钮
        self.method.xpath_text_click("创建笔记")

        # #判断设备地区后执行对应用例检查项
        if device_region == "国内" :

            # 创建会议笔记和验证会议笔记引导
            self.public.create_meeting_notes()

            # 校验当前目录是否正常创建会议笔记
            self.method.by_name_click(By.ID, "com.onyx:id/title", "会议-1")

        else:

            pytest.skip(f"海外设备无会议笔记，跳过当前用例")


    @note_mark_china("快捷创建手写笔记")
    @note_mark_increment("增量")
    def test_5_create_quick_handwritten_note(self,note_test_initial):
        """""
        回归用例P0 ---
        自动化测试用例，用于测试在未登录状态下使用快捷创建方式创建笔记的流程
        """""

        # 平板桌面 点击笔记应用
        self.method.xpath_text_click("笔记")

        # 点击“创建笔记”按钮
        self.method.xpath_text_click("创建笔记")

        # 创建菜单点击 快捷创建
        self.method.by_name_click(By.ID, "com.onyx:id/title", '快捷创建')

        # 退出手写笔记
        self.method.by_element_click(By.ID, "com.onyx.android.note:id/back_icon")

        # 校验当前目录是否正常创建手写笔记
        self.method.xpath_text_click("笔记-1",None)

        # 打开创建的手写笔记
        self.method.xpath_text_click("笔记-1")


    @note_mark_china("使用自定义模板创建")
    @note_mark_increment("增量")
    def test_6_create_template_note(self,note_test_initial):
        """""
        回归用例P0 ---
        自动化测试用例，用于测试在未登录状态下选择自带模板创建笔记的完整流程
        """""

        template = "大方格 1"

        # 平板桌面 点击笔记应用
        self.method.xpath_text_click("笔记")

        # 点击“创建笔记”按钮
        self.method.xpath_text_click("创建笔记")

        # 创建手写笔记，选择手写笔记类型、具体模板以及点击创建、退出等操作，
        self.create_handwritten_note(template)

        # 校验当前目录是否正常创建手写笔记
        self.method.xpath_text_click("笔记-1",None)

        # 有笔记状态点击创建
        self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

        # 点击手写笔记 --- 进入手写笔记创建页面
        self.method.xpath_text_click("手写笔记")

        # 校验是否选中了指定模板内容
        self.method.by_name_click(By.ID, "com.onyx.android.note:id/tv_selected_bg", "已选：常规\\" + template , None)


    @note_mark_china("创建一个文件夹")
    @note_mark_increment("增量")
    def test_7_create_folder(self,note_test_initial):
        """""
        回归用例P0 ---
        自动化测试用例 ：用于测试新建一个笔记文件夹的完整流程
        """""

        # 平板桌面 点击笔记应用
        self.method.xpath_text_click("笔记")

        # 点击新建文件夹
        self.public.more_menus("新建文件夹")

        self.public.create_file()

        # 验证本地笔记中文件夹是否创建成功
        self.method.xpath_text_click("文件夹-1")


    @note_mark_china("Reader 双开笔记")
    @note_mark_increment("增量")
    def test_17_double_doors(self,note_test_initial):

        pass

    # ---增量用例---

    @note_mark_china("清理最近笔记内打开记录")
    @note_mark_increment("增量")
    def test_39_note(self,note_test_initial):
        """本地创建手写笔记、文本笔记、会议笔记后查看最近笔记中是否有记录"""

        # 平板桌面 点击笔记应用
        self.method.xpath_text_click("笔记")

        # 无笔记未登记 点击创建笔记
        self.method.xpath_text_click("创建笔记")

        # 创建手写笔记
        self.public.create_handwritten_notes()

        # 有笔记状态点击创建
        self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

        # 创建文本笔记
        self.public.create_text_notes()

        # 创建会议笔记
        if device_region == "国内":

            # 有笔记状态点击创建
            self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

            # 创建一个会议笔记
            self.public.create_meeting_notes()

        else:

            logging.info("海外设备无会议笔记")

        self.method.by_sub_index_click(By.ID, "com.onyx:id/tool", By.CLASS_NAME, "android.widget.ImageView", 3 )

        time.sleep(3)

        self.method.xpath_text_click("笔记-1",None)

        self.method.xpath_text_click("文本-1",None)

        if device_region == "国内":

            delete_note = '会议-1'

            self.method.xpath_text_click(f"{delete_note}",None)

            self.method.wait_for_press_name(By.ID, 'com.onyx:id/title', f"{delete_note}")

        else:

            delete_note = '笔记-1'

            self.method.wait_for_press_name(By.ID,'com.onyx:id/title',f"{delete_note}")

        self.method.xpath_text_click('清除当前笔记')

        try:

            wait = WebDriverWait(driver, 3)

            record_1 = wait.until(EC.element_to_be_clickable((By.XPATH, f'//*[@text="{delete_note}"]')))
            if record_1:
                logging.info("单个笔记记录清理失败")
                return False

        except:
            logging.info("成功清理单个笔记记录")

        self.method.wait_for_press_name(By.ID, 'com.onyx:id/title', '文本-1')

        self.method.xpath_text_click('清除全部记录')

        record_2 = self.method.xpath_text_click('暂无笔记记录',should_click=None)

        if record_2:
            logging.info('成功清理全部笔记记录')


    @note_mark_china("列表模式创建笔记和文件夹")
    @note_mark_increment("增量")
    def test_51_list_create_notes(self,note_test_initial):

        self.method.xpath_text_click("笔记")

        self.method.by_element_click(By.ID,"com.onyx:id/style_iv")

        guide = self.method.xpath_text_click("点击即可快速切换封面模式、详细模式和列表模式",should_click=None)

        if guide:

            self.method.xpath_text_click("知道了")

            self.method.xpath_text_click("创建笔记")

            self.public.create_boundless_notes()

            self.method.xpath_text_click("创建")

            self.public.create_handwritten_notes()

            self.method.xpath_text_click("创建")

            self.public.create_text_notes()

            self.public.more_menus("新建文件夹")

            self.public.create_file()

            self.method.xpath_text_click("文件夹-1",should_click=None)

            if device_region == "国内":

                self.method.xpath_text_click("创建")

                self.public.create_meeting_notes()

        else:

            logging.info("切换封面模式引导未显示")


    @note_mark_china("详情模式创建笔记和文件夹")
    @note_mark_increment("增量")
    def test_52_details_create_notes(self,note_test_initial):

        self.method.xpath_text_click("笔记")

        self.method.by_element_click(By.ID, "com.onyx:id/style_iv")

        guide = self.method.xpath_text_click("点击即可快速切换封面模式、详细模式和列表模式", should_click=None)

        if guide:

            self.method.xpath_text_click("知道了")

            self.method.by_element_click(By.ID, "com.onyx:id/style_iv")

            self.method.xpath_text_click("创建笔记")

            self.public.create_boundless_notes()

            self.method.xpath_text_click("创建")

            self.public.create_handwritten_notes()

            self.method.xpath_text_click("创建")

            self.public.create_text_notes()

            self.public.more_menus("新建文件夹")

            self.public.create_file()

            self.method.xpath_text_click("文件夹-1", should_click=None)

            if device_region == "国内":

                self.method.xpath_text_click("创建")

                self.public.create_meeting_notes()

        else:

            logging.info("切换封面模式引导未显示")



    def test_create_back(self,note_test_initial):

        self.method.xpath_text_click("笔记")

        self.method.xpath_text_click("创建笔记")

        self.bake_create_menu("手写笔记")

        self.bake_create_menu("文本笔记")

        # self.method.xpath_text_click("创建笔记")

        self.method.xpath_text_click("快捷创建")

        self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')

        self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

        time.sleep(0.5)
        self.bake_create_menu("手写笔记")

        time.sleep(0.5)
        self.bake_create_menu("文本笔记")

    ####----封装的测试方法
    def bake_create_menu(self, note):

        self.method.xpath_text_click(note)

        self.method.xpath_text_click("取消")

        self.method.xpath_text_click(note)

        self.method.xpath_text_click("返回")

    def text_note_guide(self, steer_text , steer_button):
        """ 确认首次进入文本笔记时出现的引导提示 """

        self.method.by_name_click(By.ID, "com.onyx.android.note:id/textView_message", steer_text)
        self.method.by_name_click(By.ID, "com.onyx.android.note:id/button_positive", steer_button)
        self.method.by_element_click(By.ID, 'com.onyx.android.note:id/button_positive')

    def handwritten_note_creation_page(self):
        """校验手写笔记创建页，手写笔记创建页面"""

        self.method.by_name_click(By.ID, "com.onyx.android.note:id/tv_selected_bg", "已选：常规\空白")
        self.method.by_name_click(By.ID, "com.onyx.android.note:id/note_name", "笔记-1")
        self.method.by_name_click(By.ID, "com.onyx.android.note:id/btn_ok", "创建")
        self.method.by_name_click(By.ID, "com.onyx.android.note:id/btn_cancel", "取消")
        self.method.by_name_click(By.ID, "com.onyx.android.note:id/tv_back", "返回")
        self.method.by_index_name_click(By.CLASS_NAME, "android.widget.TextView", "常规", 4)
        self.method.by_index_name_click(By.CLASS_NAME, "android.widget.TextView", "工作", 5)
        self.method.by_index_name_click(By.CLASS_NAME, "android.widget.TextView", "学习", 6)
        self.method.by_index_name_click(By.CLASS_NAME, "android.widget.TextView", "其他", 7)
        self.method.by_index_name_click(By.CLASS_NAME, "android.widget.TextView", "自定义", 8)

    def text_note_creation_page(self):
        """用于校验文本笔记创建页面的各个元素显示是否符合预期"""

        self.method.by_name_click(By.ID, "com.onyx.android.note:id/tv_selected_bg", "已选：常规\空白")
        self.method.by_name_click(By.ID, "com.onyx.android.note:id/note_name", "文本-1")
        self.method.by_name_click(By.ID, "com.onyx.android.note:id/btn_ok", "创建")
        self.method.by_name_click(By.ID, "com.onyx.android.note:id/btn_cancel", "取消")
        self.method.by_name_click(By.ID, "com.onyx.android.note:id/tv_back", "返回")
        self.method.by_index_name_click(By.ID, "com.onyx.android.note:id/tv_back", "常规", 4)
        self.method.by_index_name_click(By.ID, "com.onyx.android.note:id/tv_back", "工作", 5)
        self.method.by_index_name_click(By.ID, "com.onyx.android.note:id/tv_back", "学习", 6)

    def create_handwritten_note(self, template):
        """创建手写笔记，选择手写笔记类型、具体模板以及点击创建、退出等操作，"""

        self.method.by_name_click(By.ID, "com.onyx:id/title", "手写笔记")
        self.method.by_name_click(By.ID, "com.onyx.android.note:id/title", template)
        self.method.xpath_text_click("创建")
        self.method.by_element_click(By.ID, "com.onyx.android.note:id/back_icon")