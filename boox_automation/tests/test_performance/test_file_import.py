import sys
import os

# 确保项目根目录在 sys.path 中（兼容直接 python 运行及 VS Code 等不以项目根为 cwd 的方式）
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from boox_automation.devices.info import (
    TEST_FILES_DISPLAY_ROOT, TEST_FILES_DIR_LOCAL_FILE,
)
from boox_automation.ui_ops.operations import Operation_method
from boox_automation.tests.helpers import Public_method
from boox_automation.driver import driver
from selenium.webdriver.common.by import By
import allure
import logging
import pytest

@allure.feature("笔记导入、导出文件相关测试类")
class Test_import_the_file:

    def setup_method(self):
        self.driver = driver
        self.method = Operation_method(self.driver)
        self.public = Public_method()

    @pytest.mark.cleanup_app_data
    @pytest.mark.cleanup_storage_files
    def test_4_local_file_note(self, note_perf_initial):
        """""
        回归用例P0 ---
        自动化用例 ： 用于测试在未登录状态下导入各种暂时支持的文件格式的完整流程
        测试前需要将指定文件放入设备根目录---
        """""
        logging.info("=" * 60)
        logging.info("  性能测试：从本地文件导入")
        logging.info("=" * 60)
        self.public.enter_note_app()

        #点击"创建笔记"按钮
        self.method.xpath_parent_click(xpath='//android.widget.TextView[@resource-id="com.onyx:id/on_new_note"]')

        #创建笔记二级菜单点击 从本地文件
        self.method.by_name_click(By.ID, "com.onyx:id/title", "从本地文件")

        #首次进入从本地文件导入 文件管理器 引导确认
        self.public.import_file_bootstrap("选择文件即可创建笔记","知道了")

        #进入指定文件路径，并导入此路径下的全部文档
        imported_files = self.public.import_file(TEST_FILES_DISPLAY_ROOT, TEST_FILES_DIR_LOCAL_FILE)
        assert len(imported_files) > 0, f"未导入任何文件，导入流程可能失败"
        logging.info(f"成功导入 {len(imported_files)} 个文件")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-s"] + sys.argv[1:]))
