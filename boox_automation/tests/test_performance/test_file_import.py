from boox_automation.devices.info import (
    TEST_FILES_DISPLAY_ROOT, TEST_FILES_DIR_LOCAL_FILE,
)
from boox_automation.ui_ops.operations import Operation_method
from boox_automation.tests.helpers import Public_method
from boox_automation.driver import driver
from selenium.webdriver.common.by import By
import allure
import pytest

@allure.feature("笔记导入、导出文件相关测试类")
class Test_import_the_file:

    def setup_method(self):
        self.driver = driver
        self.method = Operation_method(self.driver)
        self.public = Public_method()

    @pytest.mark.cleanup_app_data
    @pytest.mark.cleanup_storage_files
    def test_4_local_file_note(self, note_test_initial):
        """""
        回归用例P0 ---
        自动化用例 ： 用于测试在未登录状态下导入各种暂时支持的文件格式的完整流程
        测试前需要将指定文件放入设备根目录---
        """""
        self.public.enter_note_app()

        #点击"创建笔记"按钮
        self.method.xpath_text_click(element_key="笔记首页.无笔记状态创建按钮")

        #创建笔记二级菜单点击 从本地文件
        self.method.by_name_click(By.ID, "com.onyx:id/title", "从本地文件")

        #首次进入从本地文件导入 文件管理器 引导确认
        self.public.import_file_bootstrap("选择文件即可创建笔记","知道了")

        #进入指定文件路径，并导入此路径下的全部文档
        self.public.import_file(TEST_FILES_DISPLAY_ROOT, TEST_FILES_DIR_LOCAL_FILE)


