import os
import allure
from selenium.webdriver.common.by import By
from Note_Automation.Other_tests.Note_page_contrast.OpenCV import OpenCV
from Note_Automation.Note_Class.Note_class import Operation_method
from Note_Automation.Test_local_notes.Public_method import Public_method
from Note_Automation.config import driver
from Note_Automation.Devices_list.Device_basic_information import Device_basic_information


#获取设备基础信息
devices = Device_basic_information()
device_info = devices.get_device_info()
device_size = device_info.get("device_size")

@allure.feature("笔记默认页面校验类")
class Test_page:

    def setup_method(self):

        self.driver = driver

        self.method = Operation_method(self.driver)

        self.public = Public_method()

        self.OpenCV = OpenCV()

    # @note_mark_china("笔记首页默认状态校验")
    def test_heck_the_inside_of_the_notes(self , note_test_initial):
        """""
        回归用例P0 --- 
        自动化用例 ： 用于测试在未登录状态下校验本地笔记、关联文档笔记、收藏笔记、最近笔记 无笔记时的完整流程
        """""
        # 平板桌面 点击笔记应用
        self.method.xpath_text_click("笔记")

        self.screenshot_contrast("Local Notes",device_size)

        # 点击切换关联文档笔记
        self.method.by_sub_index_click(By.ID, "com.onyx:id/tool", By.CLASS_NAME, "android.widget.ImageView", True, 1)

        self.screenshot_contrast("Associated Notes",device_size)

        # # 点击切换收藏笔记
        self.method.by_sub_index_click(By.ID, "com.onyx:id/tool", By.CLASS_NAME, "android.widget.ImageView", True, 2)

        self.screenshot_contrast("Favorite Notes",device_size)

        # # 无笔记未登记 点击切换最近笔记
        self.method.by_sub_index_click(By.ID, "com.onyx:id/tool", By.CLASS_NAME, "android.widget.ImageView", True, 3)

        self.screenshot_contrast("Recent Notes",device_size)

        # 进入选项设置内
        # self.method.by_parent_index_click(By.ID, "com.onyx:id/tool", By.CLASS_NAME, "android.widget.ImageView", True,0)

        # self.public.more_menus("选项设置")

        # self.screenshot_contrast("Option settings",device_size)

        # 退出选项设置页面
        # self.method.xpath_text_click("选项设置")

        # 进入同步设置内
        # self.public.more_menus("同步设置")
        #
        # self.screenshot_contrast("Sync Settings",device_size)
        #
        # # 退出同步设置页面
        # self.method.xpath_text_click("同步设置")
        #
        # # 批量管理校验
        # self.public.more_menus("批量管理")
        #
        # self.screenshot_contrast("batch management",device_size)
        #
        # # 退出批量管理
        # self.method.xpath_text_click("取消")
        #
        # # 筛选设置校验
        # self.public.more_menus("筛选排序")
        #
        # self.screenshot_contrast("Filter and sort1",device_size)
        #
        # self.method.xpath_text_click("排序")
        #
        # self.screenshot_contrast("Filter and sort2",device_size)
        #
        # # 退出筛选排序弹窗
        # self.method.xpath_text_click("确定")
        #
        # # 回收站校验
        # self.public.more_menus("回收站")
        #
        # self.screenshot_contrast("recycle bin",device_size)
        #
        # self.method.xpath_text_click("取消")
        #
        # # 手写笔记创建页面校验
        #
        # self.method.xpath_text_click("创建笔记")
        #
        # self.method.xpath_text_click("手写笔记")

    def screenshot_contrast(self, screenshot_name , size):

        # 获取当前测试脚本路径
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # 程序截图路径
        pictures1 = fr"Page/{size}/Notes_home"

        # 正确页面图片路径
        pictures2 = f"Page_screenshot/{size}/Notes_home"

        pictures1 = os.path.join(script_dir, pictures1)
        pictures2 = os.path.join(script_dir, pictures2)

        # logging.info(f"图1{pictures1}")
        # logging.info(f"图2{pictures2}")

        pictures1 = self.OpenCV.screenshot(pictures1, screenshot_name)
        pictures2 = os.path.join(pictures2,f"{screenshot_name}.png")

        # logging.info(f"图3{pictures1}")
        # logging.info(f"图4{pictures2}")

        result_path = f"exception_page/exception_{screenshot_name}.jpg"
        result_path1 = os.path.join(script_dir, result_path)

        self.OpenCV.compare_pictures(pictures1, pictures2 , result_path1)
