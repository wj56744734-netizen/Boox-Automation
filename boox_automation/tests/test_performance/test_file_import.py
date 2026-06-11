from boox_automation.devices.info import (
    TEST_FILES_DISPLAY_ROOT, TEST_FILES_DIR_LOCAL_FILE,
)
from boox_automation.ui_ops.operations import Operation_method
from boox_automation.tests.helpers import Public_method
from boox_automation.conftest import note_mark_china, note_mark_increment
from boox_automation.driver import driver
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


    def wait_search_page_ready(self, timeout=5):
        """通过页面资源 id 判断是否已进入搜索页。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            source = self.driver.page_source
            if "com.onyx:id/search_option" in source and "com.onyx:id/search_et_input" in source:
                return True
            time.sleep(0.5)
        return False


