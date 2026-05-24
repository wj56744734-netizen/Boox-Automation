import os
import allure
from selenium.webdriver.common.by import By

from Note_Automation.scripts.Note_page_contrast.OpenCV import OpenCV
from Note_Automation.Note_class.Note_class import Operation_method
from Note_Automation.Test_local_notes.Public_method import Public_method
from Note_Automation.config import driver
from Note_Automation.Devices_list.Device_basic_information import Device_basic_information


# 获取设备基础信息（无设备时静默置 None，避免 collect 阶段炸）
devices = Device_basic_information()
try:
    device_info = devices.get_device_info()
except RuntimeError:
    device_info = None
device_size = device_info.get("device_size") if device_info else None


@allure.feature("笔记默认页面校验类")
class Test_page:

    def setup_method(self):
        self.driver = driver
        self.method = Operation_method(self.driver)
        self.public = Public_method()
        self.OpenCV = OpenCV()

    # @note_mark_china("笔记首页默认状态校验")
    def test_heck_the_inside_of_the_notes(self, note_test_initial):
        """""
        回归用例P0 ---
        自动化用例 ： 用于测试在未登录状态下校验本地笔记、关联文档笔记、收藏笔记、最近笔记 无笔记时的完整流程
        """""
        # 平板桌面 点击笔记应用
        self.method.xpath_text_click("笔记")

        self.screenshot_contrast("Local Notes", device_size)

        # 点击切换关联文档笔记
        self.method.by_sub_index_click(By.ID, "com.onyx:id/tool", By.CLASS_NAME, "android.widget.ImageView", True, 1)

        self.screenshot_contrast("Associated Notes", device_size)

        # # 点击切换收藏笔记
        self.method.by_sub_index_click(By.ID, "com.onyx:id/tool", By.CLASS_NAME, "android.widget.ImageView", True, 2)

        self.screenshot_contrast("Favorite Notes", device_size)

        # # 无笔记未登记 点击切换最近笔记
        self.method.by_sub_index_click(By.ID, "com.onyx:id/tool", By.CLASS_NAME, "android.widget.ImageView", True, 3)

        self.screenshot_contrast("Recent Notes", device_size)

    def screenshot_contrast(self, screenshot_name, size):
        """对比当前截图与基线图片，差异结果输出到 artifacts/screenshots 下。"""
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # 程序运行时截图目录（按设备尺寸归类）
        pictures1 = os.path.join(script_dir, "Page", str(size), "Notes_home")

        # 基线图片目录（人工预置）
        pictures2 = os.path.join(script_dir, "Page_screenshot", str(size), "Notes_home")

        pictures1 = self.OpenCV.screenshot(pictures1, screenshot_name)
        pictures2 = os.path.join(pictures2, f"{screenshot_name}.png")

        # 差异结果统一写入项目产物目录
        from Note_Automation.framework.paths import tmp_path
        result_path = str(tmp_path(f"exception_{screenshot_name}.jpg"))

        self.OpenCV.compare_pictures(pictures1, pictures2, result_path)
