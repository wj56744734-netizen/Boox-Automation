from Note_Automation.config import driver
from selenium.webdriver.common.by import By
from Note_Automation.Note_class.Note_class import Operation_method
from Note_Automation.Test_local_notes.Public_method import Public_method, device_region
from Note_Automation.conftest import note_mark_china
import pytest
import logging
import allure
import re


@allure.feature("笔记批量管理测试类")
@pytest.mark.usefixtures("note_test_initial")
class Test_batch_management:

    def setup_method(self):
        self.driver = driver
        self.method = Operation_method(self.driver)
        self.public = Public_method()

    @note_mark_china("批量管理-合并笔记")
    def test_batch_management_merge(self,note_test_initial):

        # 批量创建手写笔记、文本笔记、会议笔记、从本地文件导入
        file_name = self.create_all_notes()

        driver.press_keycode(3)

        self.public.enter_note_app()

        note_page = self.note_page(file_name[0])

        note_page1 = self.note_page(file_name[1])

        # 点击-更多-批量管理
        self.public.more_menus("批量管理")

        #选中单个笔记进行合并toast
        single_toast = f"请至少选中2个笔记"

        self.merge_note_abnormal(file_name[0], single_toast)

        self.merge_note_abnormal("笔记-1", single_toast)

        self.merge_note_abnormal("文本-1", single_toast)

        if device_region == "国内":

            self.merge_note_abnormal("会议-1", single_toast)

        # -----------------------不同笔记合并

        #不同类型笔记合并toast
        different_notes_toast = f"不同类型的笔记无法合并"

        self.merge_notes_abnormal("笔记-1", "文本-1", different_notes_toast)
        self.merge_notes_abnormal("笔记-1", file_name[0], different_notes_toast)
        if device_region == "国内":
            self.merge_notes_abnormal("笔记-1", "会议-1", different_notes_toast)

        self.merge_notes_abnormal("文本-1", "笔记-1", different_notes_toast)
        self.merge_notes_abnormal("文本-1", file_name[0], different_notes_toast)
        if device_region == "国内":
            self.merge_notes_abnormal("文本-1", "会议-1", different_notes_toast)

        self.merge_notes_abnormal(file_name[0], "笔记-1", different_notes_toast)
        self.merge_notes_abnormal(file_name[0], "文本-1", different_notes_toast)
        if device_region == "国内":
            self.merge_notes_abnormal(file_name[0], "会议-1", different_notes_toast)

        if device_region == "国内":
            self.merge_notes_abnormal("会议-1", "笔记-1", different_notes_toast)
            self.merge_notes_abnormal("会议-1", "文本-1", different_notes_toast)
            self.merge_notes_abnormal("会议-1", file_name[0], different_notes_toast)
            

            self.merge_notes_abnormal("会议-1", "会议-2", "不支持会议笔记的合并")


        self.merge_notes_abnormal("文本-1", "文本-2", "不支持文本笔记的合并")

        self.merge_notes("笔记-1","笔记-2","合并笔记-1","已选中笔记2个，共2页\n将按选取顺序合并笔记，是否确定？")

        page = int(note_page.group()) + int(note_page1.group())

        toast = f"已选中笔记2个，共{page}页\n将按选取顺序合并笔记，是否确定？"

        self.merge_notes(file_name[0], file_name[1], "合并笔记-2",toast)

        self.method.xpath_text_click(element_key="通用操作.取消按钮")

        self.method.wait_for_press_name(By.ID, "com.onyx:id/title","合并笔记-2")

        merge = self.method.obtain_element_text(By.ID, "com.onyx:id/info")

        merge_note = re.search(r'\d+', merge)

        if merge_note:

            match_page = int(merge_note.group())

            if match_page != page:

                pytest.fail(f"合并笔记后页数不对预计{page}页，实际{merge_note.group()}页")

    @note_mark_china("批量管理-导出笔记")
    def test_92_note(self,note_test_initial):

        # 批量创建手写笔记、文本笔记、会议笔记、从本地文件导入
        file_name = self.create_all_notes()

        driver.press_keycode(3)

        self.public.enter_note_app()

        note_page = self.note_page(file_name[0])

        note_page1 = self.note_page(file_name[1])

        self.public.more_menus("批量管理")

        different_notes_toast = f"不同类型的笔记无法导出"

        self.merge_notes_abnormal(file_name[0],"笔记-1",different_notes_toast,"导出")

        self.merge_notes_abnormal(file_name[0], "文本-1", different_notes_toast,"导出")

        if device_region == "国内":

            self.merge_notes_abnormal(file_name[0], "会议-1", different_notes_toast, "导出")


        self.merge_notes_abnormal("笔记-1",file_name[0],different_notes_toast,"导出")

        self.merge_notes_abnormal("笔记-1", "文本-1", different_notes_toast,"导出")

        if device_region == "国内":

            self.merge_notes_abnormal("笔记-1", "会议-1", different_notes_toast, "导出")


        self.merge_notes_abnormal("文本-1",file_name[0],different_notes_toast,"导出")

        self.merge_notes_abnormal("文本-1", "笔记-1", different_notes_toast,"导出")

        if device_region == "国内":

            self.merge_notes_abnormal("文本-1", "会议-1", different_notes_toast, "导出")

            self.merge_notes_abnormal("会议-1", "笔记-1", different_notes_toast, "导出")

            self.merge_notes_abnormal("会议-1", file_name[0], different_notes_toast, "导出")

            self.merge_notes_abnormal("会议-1", "文本-1", different_notes_toast, "导出")

        # 单个笔记文件导出
        # self.public.more_menus("批量管理")

        self.method.xpath_text_click(element_key="笔记首页.打开手写笔记")

        self.method.xpath_text_click(element_key="通用操作.导出按钮")

        self.method.xpath_text_click(element_key="通用操作.不可编辑PDF")

        self.method.xpath_text_click(element_key="通用操作.导出按钮")

    @note_mark_china("批量管理-同步笔记")
    def test_93_note(self):
        # 登录测试账号

        # 创建不同类型笔记

        # 点击-更多-批量管理

        # 点击不同类型笔记进行同步 是否可以同步成功

        # 点击取消关闭批量管理（覆盖取消用例）

        pass

    @note_mark_china("批量管理-移动笔记")
    def test_94_note(self):
        # 创建不同类型笔记和文件夹

        # 点击-更多-批量管理

        # 全选所有笔记-移动到文件夹内（覆盖全选用例校验）

        # 单独选中不同笔记移动回根目录

        pass

    @note_mark_china("批量管理-删除笔记")
    def test_95_note(self):
        # 创建不同类型笔记

        # 点击-更多-批量管理

        # 点击-更多-回收站

        # 校验删除的笔记是否显示

        pass

    # @note_mark_china("常规菜单收藏笔记")
    # def test_97_note(self.Tool):
    #     pass

    def create_all_note(self):

        self.public.enter_note_app()

        # 无笔记未登记 点击创建笔记
        self.method.xpath_text_click(element_key="笔记首页.无笔记状态创建按钮")

        # 创建手写笔记
        self.public.create_handwritten_notes()

        # 有笔记状态点击创建
        self.method.by_element_click(element_key="通用操作.创建按钮")

        # 创建文本笔记
        self.public.create_text_notes()

        self.public.create_meeting_if_domestic()

    def create_all_notes(self):

        self.public.enter_note_app()

        # 无笔记状态创建笔记
        self.public.create_notes()

        # 有笔记状态创建笔记
        self.public.create_notes("have_notes")

        self.method.by_element_click(element_key="通用操作.创建按钮")

        self.method.xpath_text_click(element_key="笔记首页.从本地文件导入")

        self.public.import_file_bootstrap("选择文件即可创建笔记", "知道了")

        file_name = self.public.import_file("笔记自动化测试文件", "从本地文件")

        return file_name

    def note_page(self,file_name):

        self.method.wait_for_press_name(By.ID, "com.onyx:id/title", file_name)

        name = self.method.obtain_element_text(By.ID, "com.onyx:id/info")

        the_number_of_pages = re.search(r'\d+', name)

        self.method.by_element_click(element_key="通用操作.关闭按钮")

        return the_number_of_pages

    def merge_notes(self,note_name,note_name2,merge_note,toast,function="合并"):

        self.method.xpath_text_click(note_name)
        self.method.xpath_text_click(note_name2)

        self.method.xpath_text_click(function)
        self.method.xpath_text_click(toast)
        self.method.xpath_text_click(element_key="通用操作.保留模板选项", should_click=None)
        self.method.xpath_text_click(element_key="通用操作.取消按钮", should_click=None)
        self.method.xpath_text_click(element_key="通用操作.确定按钮")

        self.method.xpath_text_click(merge_note,None)

        self.method.xpath_text_click(note_name)
        self.method.xpath_text_click(note_name2)

    def merge_notes_abnormal(self, notes_name, notes_name1, toast,function="合并"):

        self.method.xpath_text_click(notes_name)

        self.method.xpath_text_click(notes_name1)

        self.method.xpath_text_click(function)

        self.method.wait_check_toast(toast)

        self.method.xpath_text_click(notes_name)

        self.method.xpath_text_click(notes_name1)

    def merge_note_abnormal(self, notes_name, toast):

        self.method.xpath_text_click(notes_name)

        self.method.xpath_text_click(element_key="笔记首页.批量管理-合并")

        self.method.wait_check_toast(toast)

        self.method.xpath_text_click(notes_name)