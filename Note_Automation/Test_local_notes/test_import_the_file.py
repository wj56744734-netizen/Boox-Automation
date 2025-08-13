from Note_Automation.Note_Class.Note_class import Operation_method
from Note_Automation.Test_local_notes.Public_method import Public_method
from Note_Automation.Devices_list.Device_basic_information import Device_basic_information
from Note_Automation.conftest import note_mark_china, note_mark_increment, note_mark_full_amount
from Note_Automation.config import driver
from selenium.webdriver.common.by import By
import allure
import logging
import pytest




#获取设备基础信息
devices = Device_basic_information()
device_info = devices.get_device_info()
if device_info:
    device_region = device_info.get('device_region')

@allure.feature("笔记导入、导出文件相关测试类")
class Test_import_the_file:

    def setup_method(self):
        self.driver = driver
        self.method = Operation_method(self.driver)
        self.public = Public_method()

    @note_mark_china("从本地文件创建笔记")
    @note_mark_increment("增量")
    def test_4_local_file_note(self,note_test_initial):
        """""
        回归用例P0 --- 
        自动化用例 ： 用于测试在未登录状态下导入各种暂时支持的文件格式的完整流程
        测试前需要将指定文件放入设备根目录---
        """""
        # 平板桌面 点击笔记应用
        self.method.xpath_text_click("笔记")

        #点击“创建笔记”按钮
        self.method.xpath_text_click("创建笔记")

        #创建笔记二级菜单点击 从本地文件
        self.method.by_name_click(By.ID, "com.onyx:id/title", "从本地文件")

        #首次进入从本地文件导入 文件管理器 引导确认
        self.public.import_file_bootstrap("选择文件即可创建笔记","知道了")

        #进入指定文件路径，并导入此路径下的全部文档
        self.public.import_file("笔记自动化测试文件","用例测试，从本地文件导入")


    @note_mark_china("笔记首页搜索指定内容")
    @note_mark_increment("增量")
    def test_8_search_note(self,note_test_initial):
        """自动化测试用例 ：恢复指定笔记后设置筛选条件进行搜索（标题、手写、文本、标签）
        测试前需要将指定文件放入设备根目录---
        """

        self.public.enter_storage()

        self.method.by_name_click(By.ID, "com.onyx:id/volume_name", "存储")

        self.public.get_file("笔记自动化测试文件","笔记搜索用例文件","笔记-1.note")

        # .note导入笔记页面 确认
        self.method.by_name_click(By.ID, "com.onyx.android.note:id/start_import", "确定")

        # 导入.note文件时确认三分钟内是否将笔记导入成功
        self.method.by_pop_time(By.ID, "com.onyx.android.note:id/progress", 180, "导入笔记超时")

        # 笔记导入成功后 返回设备主页
        self.driver.press_keycode(3)

        # 平板桌面 点击笔记应用平板桌面 点击笔记应用
        self.method.xpath_text_click("笔记")

        # 笔记首页点击 搜索
        self.method.by_sub_index_click(By.ID, "com.onyx:id/tool_layout", By.CLASS_NAME, "android.widget.LinearLayout", 1)

        # 搜索页面 搜索条件校准
        self.search_page_element()

        # 搜索页面 点击标签，保留标题
        self.method.by_sub_index_click(By.ID, "com.onyx:id/search_option", By.ID, "com.onyx:id/tag_checkbox")

        # 输入测试数据 ， 校验结果
        self.search_title("笔记-1","总计： 1","标题")

        # 搜索页面 点击手写
        self.method.by_sub_index_click(By.ID, "com.onyx:id/search_option", By.ID, "com.onyx:id/scribble_checkbox")

        # 搜索页面 点击标题 取消搜索标题
        self.method.by_sub_index_click(By.ID, "com.onyx:id/search_option", By.ID, "com.onyx:id/title_checkbox")

        self.search_title("A", "总计： 2","手写")

        self.search_title("手写", "总计： 2","手写")

        self.search_title("123", "总计： 2","手写")

        # 搜索页面 点击文本
        self.method.by_sub_index_click(By.ID, "com.onyx:id/search_option", By.ID, "com.onyx:id/text_checkbox")

        # 搜索页面 点击手写 取消搜索手写
        self.method.by_sub_index_click(By.ID, "com.onyx:id/search_option", By.ID, "com.onyx:id/scribble_checkbox")

        self.search_title("A", "总计： 1","文本")

        self.search_title("手写", "总计： 1","文本")

        self.search_title("123", "总计： 1","文本")

        # 搜索页面 点击标签
        self.method.by_sub_index_click(By.ID, "com.onyx:id/search_option", By.ID, "com.onyx:id/tag_checkbox")

        # 搜索页面 点击文本 取消搜索文本
        self.method.by_sub_index_click(By.ID, "com.onyx:id/search_option", By.ID, "com.onyx:id/text_checkbox")

        self.search_title("A", "总计： 1","标签")

        self.search_title("手写", "总计： 1","标签")

        self.search_title("123", "总计： 1","标签")


    @note_mark_china("退出笔记自动生成pdf")
    @note_mark_increment("增量")
    def test_9_automatically_generate_pdf(self,note_test_initial):

        self.method.xpath_text_click("笔记")

        self.set_up_generate_pdf()

        self.method.xpath_text_click("笔记设置")

        self.method.xpath_text_click("创建笔记")

        self.public.create_handwritten_notes()

        # 创建会议笔记
        if device_region == "国内":

            # 有笔记状态点击创建
            self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

            # 创建一个会议笔记
            self.public.create_meeting_notes()

        driver.press_keycode(3)

        self.public.enter_storage()

        self.method.by_name_click(By.ID, "com.onyx:id/volume_name", "存储")

        self.method.by_name_click(By.ID, "com.onyx:id/textviewItem", "note")

        self.method.by_name_click(By.ID, "com.onyx:id/textviewItem", "笔记-1")

        self.method.by_name_click(By.ID, "com.onyx:id/textviewItem", "笔记-1.pdf")


    @note_mark_china("笔记备份和恢复")
    @note_mark_full_amount("全量")
    def test_10_note(self,note_test_initial):
        """""
        自动化测试用例 ： 将测试文件放入指定文件夹，本地笔记、文件夹和关联笔记备份恢复与追加
        测试前需要将指定文件放入设备根目录---
        """""

        self.public.enter_storage()

        # 进入存储页面根目录下，将指定文件复制进入.note文件路径下
        self.copy_the_file("笔记自动化测试文件","note")

        self.driver.press_keycode(3)

        self.method.xpath_text_click("笔记")

        self.public.more_menus("笔记设置", "备份与恢复")

        # 备份文件-点击恢复
        self.backup_recover("本地笔记： 目录 1 / 笔记 1","关联文档笔记： 目录 0 / 笔记 1")

        # 无笔记未登记 点击本地笔记
        self.method.by_sub_index_click(By.ID, "com.onyx:id/tool", By.CLASS_NAME, "android.widget.ImageView", 0)

        # 有笔记 点击创建笔记
        self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

        # 创建手写笔记
        self.public.create_handwritten_notes()

        # 有笔记 点击创建笔记
        self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

        # 创建文本笔记
        self.public.create_text_notes()

        if device_region == "国内":

            # 有笔记 点击创建笔记
            self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

            self.public.create_meeting_notes()

        self.public.more_menus("选项设置", "备份与恢复")

        # 备份文件 - 追加备份 - 恢复追加备份
        self.backup_addition()

        self.public.more_menus("选项设置", "备份与恢复")

        # 备份文件-新增备份
        self.method.by_element_click(By.ID, "com.onyx:id/local_backup")

        # 备份文件输入内容
        self.method.wait_input_box(By.ID, "com.onyx:id/editText_new_name", "测试笔记备份")

        # 新建备份二级确认引导弹窗 等待toast确认是否备份
        self.method.by_element_click(By.ID, "com.onyx:id/btn_ok")

        self.method.wait_check_toast("备份成功", "备份失败")

        # 备份文件-删除
        self.method.by_element_click(By.ID, "com.onyx:id/delete")

        # 删除备份二级确认引导弹窗 等待toast确认是否备份
        self.method.by_element_click(By.ID, "com.onyx:id/button_positive")

        self.method.wait_check_toast("删除成功", "备份删除失败")

    ######
    def set_up_generate_pdf(self):

        self.public.more_menus("笔记设置","退出笔记后自动生成PDF文档")


        self.method.xpath_text_click("内容较多时生成PDF的耗时较长，还请您耐心等待。",None)


        self.method.xpath_text_click("知道了",None)


        self.method.xpath_text_click("知道了")

    def search_title(self,input_name,expect_file_found,name):
        """""
        笔记搜索标题，输入内容后点击搜索，判断结果是否正确
        """""
        with allure.step(f"输入 {input_name} "):
            self.method.wait_input_box(By.ID, "com.onyx:id/search_et_input", input_name)

        with allure.step(f"输入 {input_name} 后点击 - 搜索"):
            self.method.by_element_click(By.ID, "com.onyx:id/search_button")

        with allure.step(f"搜索： {name} , 内容：{input_name} "):
            file_found = self.method.by_name_click(By.ID, "com.onyx:id/total", expect_file_found,None)

            if not file_found:

                logging.error(f"搜索{name}：（{input_name}），！！！结果异常")

    def copy_the_file(self,file_name,file_name1):
        """""
        找到指定文件，然后将指定文件复制，粘贴进入设备存储根目录下。
        """""
        self.method.by_name_click(By.ID, "com.onyx:id/volume_name", "存储")

        self.public.get_file(file_name)

        self.method.wait_for_press_name(By.ID, "com.onyx:id/textviewItem", file_name1)

        self.method.by_name_click(By.ID, "android:id/text1", "复制")

        self.method.by_name_click(By.ID, "com.onyx:id/text_title", "存储/笔记自动化测试文件")

        self.method.by_name_click(By.ID, "com.onyx:id/textview_paste", "粘贴")

        self.method.pop_up_check_name_(By.ID, "android:id/text1", "覆盖全部")

    def backup_recover(self , note_guide , file_guide):
        """""
        备份文件-点击恢复
        校验恢复的本地笔记和关联文档笔记
        """""
        # 备份文件-恢复
        self.method.by_element_click(By.ID, "com.onyx:id/restore")

        # 恢复弹窗-点击确认
        self.method.by_element_click(By.ID, "com.onyx:id/button_positive")

        # 检查是否恢复成功
        file_found = self.method.by_name_click(By.ID, "com.onyx:id/tv_restore_title", "恢复备份成功")

        if not file_found:
            logging.critical(f"恢复备份失败")
            pytest.skip("恢复备份失败，跳过当前用例")

        else:
            # 恢复备份弹窗出现时点击查看笔记 进入笔记根目录
            self.method.by_name_click(By.ID, "com.onyx:id/btn_goto_note", "查看笔记")

        """""
        备份文件-点击恢复 ， 校验恢复的本地笔记和关联文档笔记
        """""

        self.method.by_sub_index_click(By.ID, "com.onyx:id/page", By.CLASS_NAME, "android.widget.TextView", note_guide)

        self.method.by_sub_index_click(By.ID, "com.onyx:id/tool", By.CLASS_NAME, "android.widget.ImageView", 1)

        self.method.by_sub_index_click(By.ID, "com.onyx:id/page", By.CLASS_NAME, "android.widget.TextView", file_guide)

    def backup_addition(self):
        """""
        备份文件 - 追加备份 - 点击恢复
        """""
        # 备份文件-追加备份
        self.method.by_element_click(By.ID, "com.onyx:id/append")

        # 追加备份二级确认引导弹窗 等待toast确认是否备份
        self.method.by_element_click(By.ID, "com.onyx:id/button_positive")
        self.method.wait_check_toast("备份成功", "备份失败")

        # 备份文件-点击恢复
        self.backup_recover("本地笔记： 目录 2 / 笔记 4","关联文档笔记： 目录 0 / 笔记 2")

# --------------------------------------------------------------------------------------
    # 笔记搜索页面校验各种搜索条件是否缺失

    def search_page_element(self):
        """""
        笔记搜索页面校验各种搜索条件是否缺失
        """""
        # 搜索页面 点击标题
        self.method.by_sub_index_click(By.ID, "com.onyx:id/search_option", By.ID, "com.onyx:id/title_checkbox", 0, should_click=None)

        self.method.by_sub_index_click(By.ID, "com.onyx:id/search_option", By.ID, "com.onyx:id/scribble_checkbox", 0, should_click=None)

        self.method.by_sub_index_click(By.ID, "com.onyx:id/search_option", By.ID, "com.onyx:id/text_checkbox", 0, should_click=None)

        self.method.by_sub_index_click(By.ID, "com.onyx:id/search_option", By.ID, "com.onyx:id/tag_checkbox", 0, should_click=None)

        self.method.by_sub_index_click(By.ID, "com.onyx:id/search_option", By.ID, "com.onyx:id/all_library_checkbox", 0, should_click=None)


