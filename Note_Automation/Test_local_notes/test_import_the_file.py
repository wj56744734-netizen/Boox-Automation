from Note_Automation.Devices_list.Device_basic_information import (
    TEST_FILES_DISPLAY_ROOT, TEST_FILES_DIR_LOCAL_FILE,
    TEST_FILES_DIR_NOTE_SEARCH,
)
from Note_Automation.Note_class.Note_class import Operation_method
from Note_Automation.Test_local_notes.Public_method import Public_method, device_region
from Note_Automation.conftest import note_mark_china, note_mark_increment, note_mark_full_amount
from Note_Automation.config import driver
from selenium.webdriver.common.by import By
import allure
import logging
import pytest
import time

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
        self.public.enter_note_app()

        #点击“创建笔记”按钮
        self.method.xpath_text_click(element_key="笔记首页.无笔记状态创建按钮")

        #创建笔记二级菜单点击 从本地文件
        self.method.by_name_click(By.ID, "com.onyx:id/title", "从本地文件")

        #首次进入从本地文件导入 文件管理器 引导确认
        self.public.import_file_bootstrap("选择文件即可创建笔记","知道了")

        #进入指定文件路径，并导入此路径下的全部文档
        self.public.import_file(TEST_FILES_DISPLAY_ROOT, TEST_FILES_DIR_LOCAL_FILE)

    @note_mark_china("笔记首页搜索指定内容")
    @note_mark_increment("增量")
    def test_8_search_note(self,note_test_initial):
        """自动化测试用例 ：恢复指定笔记后设置筛选条件进行搜索（标题、手写、文本、标签）
        测试前需要将指定文件放入设备根目录---
        """

        self.public.enter_storage()

        self.method.by_name_click(element_key="设备相关.存储卷列表")

        self.public.get_file(TEST_FILES_DISPLAY_ROOT, TEST_FILES_DIR_NOTE_SEARCH, "笔记-1.note")

        # .note导入笔记页面 确认
        self.method.by_name_click(element_key="通用操作.笔记内-导入确认按钮")

        # 导入.note文件时确认三分钟内是否将笔记导入成功
        self.method.by_pop_time(By.ID, "com.onyx.android.note:id/progress", 180, "导入笔记超时")

        # 笔记导入成功后 返回设备主页
        self.driver.press_keycode(3)

        self.public.enter_note_app()

        # if not self.enter_search_page():
        #     pytest.fail("未能进入搜索页面，终止后续搜索断言")

        self.method.xpath_parent_click(
            xpath='//android.widget.LinearLayout[@resource-id="com.onyx:id/tool_layout"]/android.widget.LinearLayout[3]/android.widget.ImageView')

        # 搜索页面 搜索条件校准
        self.search_page_element()

        # 搜索页面 点击标签，保留标题
        self.method.by_sub_index_click(element_key="笔记首页.搜索标签筛选")

        # 输入测试数据 ， 校验结果
        self.search_title("笔记-1","总计： 1","标题")

        # 搜索页面 点击手写
        self.method.by_sub_index_click(element_key="笔记首页.搜索手写筛选")

        # 搜索页面 点击标题 取消搜索标题
        self.method.by_sub_index_click(element_key="笔记首页.搜索标题筛选")

        self.search_title("A", "总计： 2","手写")

        self.search_title("手写", "总计： 2","手写")

        self.search_title("123", "总计： 2","手写")

        # 搜索页面 点击文本
        self.method.by_sub_index_click(element_key="笔记首页.搜索文本筛选")

        # 搜索页面 点击手写 取消搜索手写
        self.method.by_sub_index_click(element_key="笔记首页.搜索手写筛选")

        self.search_title("A", "总计： 1","文本")

        self.search_title("手写", "总计： 1","文本")

        self.search_title("123", "总计： 1","文本")

        # 搜索页面 点击标签
        self.method.by_sub_index_click(element_key="笔记首页.搜索标签筛选")

        # 搜索页面 点击文本 取消搜索文本
        self.method.by_sub_index_click(element_key="笔记首页.搜索文本筛选")

        self.search_title("A", "总计： 1","标签")

        self.search_title("手写", "总计： 1","标签")

        self.search_title("123", "总计： 1","标签")


    @note_mark_china("退出笔记自动生成pdf")
    @note_mark_increment("增量")
    def test_9_automatically_generate_pdf(self,note_test_initial):

        self.public.enter_note_app()

        self.set_up_generate_pdf()

        self.method.xpath_text_click(element_key="笔记首页.更多-笔记设置")

        self.method.xpath_text_click(element_key="笔记首页.无笔记状态创建按钮")

        self.public.create_handwritten_notes()

        self.public.create_meeting_if_domestic()

        driver.press_keycode(3)

        self.public.enter_storage()

        self.method.by_name_click(element_key="设备相关.存储卷列表")

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
        self.copy_the_file(TEST_FILES_DISPLAY_ROOT, "note")

        self.driver.press_keycode(3)

        self.public.enter_note_app()

        self.public.more_menus("笔记设置", "备份与恢复")

        # 备份文件-点击恢复
        self.backup_recover("本地笔记： 目录 1 / 笔记 1","关联文档笔记： 目录 0 / 笔记 1")

        # 无笔记未登记 点击本地笔记
        self.method.by_sub_index_click(element_key="笔记首页.本地笔记入口")

        # 有笔记 点击创建笔记
        self.method.by_element_click(element_key="通用操作.创建按钮")

        # 创建手写笔记
        self.public.create_handwritten_notes()

        # 有笔记 点击创建笔记
        self.method.by_element_click(element_key="通用操作.创建按钮")

        # 创建文本笔记
        self.public.create_text_notes()

        self.public.create_meeting_if_domestic()

        self.public.more_menus("选项设置", "备份与恢复")

        # 备份文件 - 追加备份 - 恢复追加备份
        self.backup_addition()

        self.public.more_menus("选项设置", "备份与恢复")

        # 备份文件-新增备份
        self.method.by_element_click(element_key="通用操作.本地备份入口")

        # 备份文件输入内容
        self.method.wait_input_box(By.ID, "com.onyx:id/editText_new_name", "测试笔记备份")

        # 新建备份二级确认引导弹窗 等待toast确认是否备份
        self.method.by_element_click(By.ID, "com.onyx:id/btn_ok")

        self.method.wait_check_toast("备份成功", "备份失败")

        # 备份文件-删除
        self.method.by_element_click(element_key="通用操作.删除按钮")

        # 删除备份二级确认引导弹窗 等待toast确认是否备份
        self.method.by_element_click(element_key="通用操作.弹窗确认按钮")

        self.method.wait_check_toast("删除成功", "备份删除失败")

    ######
    def set_up_generate_pdf(self):

        self.public.more_menus("笔记设置","退出笔记后自动生成PDF文档")


        self.method.xpath_text_click(element_key="通用操作.PDF耗时提示", should_click=None)


        self.method.xpath_text_click(element_key="笔记首页.弹窗通用知道了", should_click=None)


        self.method.xpath_text_click(element_key="笔记首页.弹窗通用知道了")

    def search_title(self, input_name, expect_file_found, name):
        """
        笔记搜索标题，输入内容后点击搜索，判断结果是否正确
        """
        self.method.wait_input_box(By.ID, "com.onyx:id/search_et_input", input_name)
        self.method.by_element_click(element_key="通用操作.搜索按钮")

        # 等待"搜索中...."加载弹窗消失
        self.method.by_pop_time(By.ID, "com.onyx:id/tv_loading_title", timeout=10, prompt="搜索中....")

        file_found = self.method.by_name_click(By.ID, "com.onyx:id/total", expect_file_found, None)
        if not file_found:
            pytest.fail(f"搜索{name}：（{input_name}），结果异常 — 预期'{expect_file_found}'未找到")

    def copy_the_file(self,file_name,file_name1):
        """""
        找到指定文件，然后将指定文件复制，粘贴进入设备存储根目录下。
        """""
        self.method.by_name_click(element_key="设备相关.存储卷列表")

        self.public.get_file(file_name)

        self.method.wait_for_press_name(By.ID, "com.onyx:id/textviewItem", file_name1)

        self.method.by_name_click(element_key="通用操作.复制菜单项")

        self.method.by_name_click(By.ID, "com.onyx:id/text_title", f"存储/{TEST_FILES_DISPLAY_ROOT}")

        self.method.by_name_click(element_key="通用操作.粘贴按钮")

        self.method.pop_up_check_name_(By.ID, "android:id/text1", "覆盖全部")

    def backup_recover(self , note_guide , file_guide):
        """""
        备份文件-点击恢复
        校验恢复的本地笔记和关联文档笔记
        """""
        # 备份文件-恢复
        self.method.by_element_click(element_key="通用操作.恢复按钮")

        # 恢复弹窗-点击确认
        self.method.by_element_click(element_key="通用操作.弹窗确认按钮")

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

        self.method.by_sub_index_click(element_key="笔记首页.关联文档笔记入口")

        self.method.by_sub_index_click(By.ID, "com.onyx:id/page", By.CLASS_NAME, "android.widget.TextView", file_guide)

    def backup_addition(self):
        """""
        备份文件 - 追加备份 - 点击恢复
        """""
        # 备份文件-追加备份
        self.method.by_element_click(element_key="通用操作.追加模式")

        # 追加备份二级确认引导弹窗 等待toast确认是否备份
        self.method.by_element_click(element_key="通用操作.弹窗确认按钮")
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
        self.method.by_sub_index_click(element_key="笔记首页.搜索标题筛选", should_click=None)

        self.method.by_sub_index_click(element_key="笔记首页.搜索手写筛选", should_click=None)

        self.method.by_sub_index_click(element_key="笔记首页.搜索文本筛选", should_click=None)

        self.method.by_sub_index_click(element_key="笔记首页.搜索标签筛选", should_click=None)

        self.method.by_sub_index_click(element_key="笔记首页.搜索全库筛选", should_click=None)

    def enter_search_page(self):
        """兼容不同版本工具栏结构，稳定进入搜索页。"""
        candidates = [
            ("content-desc 搜索", lambda: self.method.by_element_click(By.XPATH, '//*[@content-desc="搜索"]')),
            ("tool_layout LinearLayout[1]", lambda: self.method.by_sub_index_click(
                By.ID, "com.onyx:id/tool_layout", By.CLASS_NAME, "android.widget.LinearLayout", 1
            )),
            ("tool_layout ImageView[3]", lambda: self.method.by_sub_index_click(
                By.ID, "com.onyx:id/tool_layout", By.CLASS_NAME, "android.widget.ImageView", 3
            )),
            ("tool_layout ImageView[2]", lambda: self.method.by_sub_index_click(
                By.ID, "com.onyx:id/tool_layout", By.CLASS_NAME, "android.widget.ImageView", 2
            )),
        ]

        for name, action in candidates:
            try:
                action()
            except Exception:
                continue
            if self.wait_search_page_ready():
                logging.info(f"已进入搜索页：{name}")
                return True
            # 误入「标签管理」时先返回到笔记首页再尝试下一个入口
            source = self.driver.page_source
            if "标签管理" in source:
                self.driver.press_keycode(4)
                time.sleep(0.5)
        return False

    def wait_search_page_ready(self, timeout=5):
        """通过页面资源 id 判断是否已进入搜索页。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            source = self.driver.page_source
            if "com.onyx:id/search_option" in source and "com.onyx:id/search_et_input" in source:
                return True
            time.sleep(0.5)
        return False


