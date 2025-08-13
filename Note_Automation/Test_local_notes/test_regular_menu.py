from Note_Automation.Devices_list.Device_basic_information import Device_basic_information
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from Note_Automation.Note_Class.Note_class import Operation_method
from Note_Automation.Test_local_notes.Public_method import Public_method
from Note_Automation.config import driver
from Note_Automation.conftest import note_mark_china, note_mark_increment, note_mark_full_amount
import allure
import logging
import pytest




#获取设备基础信息
devices = Device_basic_information()
device_info = devices.get_device_info()
if device_info:
    device_region = device_info.get('device_region')


@allure.feature("笔记常规菜单测试类")
@pytest.mark.usefixtures("note_test_initial")
class Test_general_menu:

    def setup_method(self):
        self.driver = driver
        self.method = Operation_method(self.driver)
        self.public = Public_method()

    @note_mark_china("常规菜单功能确认")
    @note_mark_increment("增量")
    def test_12_general_menu_delete_notes(self, note_test_initial):
        """ """
        # 平板桌面 点击笔记应用
        self.method.xpath_text_click("笔记")

        self.method.xpath_text_click("创建笔记")

        # 创建手写笔记
        self.public.create_handwritten_notes()

        #有笔记状态点击创建
        self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

        # 创建文本笔记
        self.public.create_text_notes()

        # 创建会议笔记
        if device_region == "国内" :

            # 有笔记状态点击创建
            self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

            # 创建一个会议笔记
            self.public.create_meeting_notes()

        else:

            logging.info("海外设备无会议笔记")

        self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "笔记-1")

        self.attribute_guide("笔记属性信息已收纳至【属性与安全】模块下的【属性】")

        # 对比内容是否缺少

        self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "文本-1")

        # 对比内容是否缺少


    @note_mark_china("常规菜单删除笔记")
    @note_mark_increment("增量")
    def test_13_general_menu_delete_notes(self,note_test_initial):
        """""
        回归用例P0 ---
        删除手写、会议、文本笔记和文件夹后确认笔记是否在回收站，并且清理回收站
        """""
        # 平板桌面 点击笔记应用
        self.method.xpath_text_click("笔记")

        self.method.xpath_text_click("创建笔记")

        # 创建手写笔记
        self.public.create_handwritten_notes()

        #有笔记状态点击创建
        self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

        # 创建文本笔记
        self.public.create_text_notes()

        # 创建会议笔记
        if device_region == "国内" :

            # 有笔记状态点击创建
            self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

            # 创建一个会议笔记
            self.public.create_meeting_notes()

        else:

            logging.info("海外设备无会议笔记")

        self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "笔记-1")

        self.attribute_guide("笔记属性信息已收纳至【属性与安全】模块下的【属性】")

        self.general_delete()

        self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "文本-1")

        self.general_delete()

        if device_region == "国内":

            self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "会议-1")

            self.general_delete()

        self.public.more_menus("回收站")

        self.method.xpath_text_click("笔记-1",None)

        self.method.xpath_text_click("文本-1",None)

        if device_region == "国内" :
            # 校验回收站内是否有会议笔记
            self.method.xpath_text_click("会议-1",None)

        self.method.xpath_text_click("清空")

        self.method.by_name_click(By.ID, 'com.onyx:id/textView_message', '彻底删除后，将无法恢复！',None)

        self.method.by_name_click(By.ID, 'com.onyx:id/button_negative', '取消',None)

        self.method.by_name_click(By.ID, 'com.onyx:id/button_positive', '确定',None)

        self.method.by_element_click(By.ID, 'com.onyx:id/button_positive')  # 回收站清空弹窗校验完成后点击确认

        self.method.by_name_click(By.ID, "com.onyx:id/no_search", "未找到相关内容")

    @note_mark_china("常规菜单移动笔记")
    @note_mark_increment("增量")
    def test_14_general_menu_move_notes(self,note_test_initial):
        """""
        回归用例P0 ---
        常规菜单 创建手写、文本、会议笔记和文件夹，移动至文件夹中
        """""
        # 平板桌面 点击笔记应用
        self.method.xpath_text_click("笔记")

        # 点击更多菜单
        self.public.more_menus("新建文件夹")

        self.method.xpath_text_click("确定")

        # 有笔记状态点击创建
        self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

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

        # 长按手写笔记
        self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "笔记-1")

        self.attribute_guide("笔记属性信息已收纳至【属性与安全】模块下的【属性】")

        # 移动手写笔记至指定文件路径
        self.general_move("文件夹-1")

        # 长按文本笔记
        self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "文本-1")

        # 移动文本笔记至指定文件路径
        self.general_move("文件夹-1")

        if device_region == "国内":
            #校验会议笔记
            self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "会议-1")

            # 移动会议笔记至指定文件路径
            self.general_move("文件夹-1")


        # 长按文件夹笔记
        self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "文件夹-1")

        # 移动笔记
        self.method.xpath_text_click("移动")

        # 移动菜单 - 点击新建文件夹
        self.method.xpath_text_click("新建文件夹")

        # 文件夹弹窗点击确认
        self.method.by_name_click(By.ID, "com.onyx:id/btn_ok", "确定")

        self.method.xpath_text_click("文件夹-2")

        self.method.xpath_text_click("文件夹-1")

        self.method.xpath_text_click("笔记-1",None)

        self.method.xpath_text_click("文本-1",None)

        if device_region == "国内":
            # 校验移动会议笔记后是否显示在文件夹中
            self.method.xpath_text_click("会议-1",None)

        else:
            # 跳过 --- 会议笔记相关操作
            logging.info("海外设备无会议笔记未移动会议笔记")

    @note_mark_china("常规菜单复制笔记")
    @note_mark_increment("增量")
    def test_15_general_menu_copy_notes(self,note_test_initial):
        """""
        回归用例P0 ---
        常规菜单复制 手写笔记、文本笔记、会议笔记
        """""
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


        self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "笔记-1")

        self.attribute_guide("笔记属性信息已收纳至【属性与安全】模块下的【属性】")

        self.general_copy()

        self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "文本-1")

        self.general_copy()

        if device_region == "国内":

            self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "会议-1")

            self.general_copy()

        # 校验复制的手写笔记
        self.method.xpath_text_click("笔记-1(1)",None)

        # 校验复制的文本笔记
        self.method.xpath_text_click("文本-1(1)",None)

        # 校验复制的手写笔记是否还存在
        self.method.xpath_text_click("笔记-1",None)

        # 校验复制的文本笔记是否还存在
        self.method.xpath_text_click("文本-1",None)

        if device_region == "国内":

            # 校验复制的会议笔记
            self.method.xpath_text_click("会议-1(1)",None)

            # 校验复制的会议笔记是否还存在
            self.method.xpath_text_click("会议-1",None)

    @note_mark_china("常规菜单重命名笔记")
    @note_mark_increment("增量")
    def test_16_general_menu_rename_notes(self,note_test_initial):  # 补充会议笔记 文本笔记
        """""
        回归用例P0 ---
        创建一个手写、文本、会议笔记和文件加后 重命名笔记和文件夹
        """""
        handwritten_name = "手写笔记测试重命名"
        text_name = "文本笔记测试重命名"
        meeting_name = "会议笔记测试重命名"
        folder_name = "文件夹测试重命名"

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

        # 点击更多菜单
        self.method.by_sub_index_click(By.ID, "com.onyx:id/tool_layout", By.ID, "com.onyx:id/more_menu")

        # 点击新建文件夹
        self.method.xpath_text_click("新建文件夹")

        # 校验文件夹弹窗
        self.method.xpath_text_click("文件夹名称",None)
        self.method.xpath_text_click("取消",None)
        self.method.xpath_text_click("确定",None)
        self.method.xpath_text_click("确定")

        # 创建会议笔记
        if device_region == "国内":

            # 有笔记状态点击创建
            self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

            # 创建一个会议笔记
            self.public.create_meeting_notes()

        self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "笔记-1")

        self.attribute_guide("笔记属性信息已收纳至【属性与安全】模块下的【属性】")

        self.general_rename(handwritten_name)

        self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "文本-1")

        self.general_rename(text_name)

        if device_region == "国内":

            self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "会议-1")

            self.general_rename(meeting_name)

        self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "文件夹-1")

        self.general_rename(folder_name)

        self.method.xpath_text_click(handwritten_name,None)

        self.method.xpath_text_click(text_name,None)

        self.method.xpath_text_click(folder_name,None)

        if device_region == "国内":

            self.method.xpath_text_click(meeting_name,None)

        else:
            # 跳过 --- 会议笔记相关操作
            logging.info("海外设备无会议笔记未重命名会议笔记")

    @note_mark_china("常规菜单收藏笔记")
    @note_mark_full_amount("全量")
    def test_general_menu_collection_notes(self,note_test_initial):
        """""
        回归用例P0 ---
        本地创建一个笔记后收藏笔记 收藏下确认笔记是否正常被收藏
        """""
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

        self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "笔记-1")

        self.attribute_guide("笔记属性信息已收纳至【属性与安全】模块下的【属性】")

        self.general_collection()

        self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "文本-1")

        self.general_collection()

        if device_region == "国内":

            self.method.wait_for_press_name(By.ID, "com.onyx:id/title", "会议-1")

            self.general_collection()

        self.method.by_sub_index_click(By.ID, "com.onyx:id/tool", By.CLASS_NAME, "android.widget.ImageView", 2)

        self.method.xpath_text_click("笔记-1",None)

        self.method.xpath_text_click("文本-1",None)

        if device_region == "国内":

            self.method.xpath_text_click("会议-1",None)



    def attribute_guide(self,guide):

        try:
            wait = WebDriverWait(self.driver, 3)
            element = wait.until(
                EC.element_to_be_clickable((By.XPATH, f'//*[@text="{guide}"]'))
            )

            if element:
                self.method.xpath_text_click("知道了")
        except:
            logging.info("属性引导-已跳过")


    def create_notes(self):

        # 有无笔记状态点击创建 - 判断条件

        self.method.xpath_text_click("创建笔记")

        # 创建手写笔记
        self.public.create_handwritten_notes()

        # 有笔记状态点击创建 - 判断条件
        self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

        # 创建文本笔记
        self.public.create_text_notes()

        # 创建会议笔记 - 判断条件
        if device_region == "国内":

            # 有笔记状态点击创建
            self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

            # 创建一个会议笔记
            self.public.create_meeting_notes()

        else:

            logging.info("海外设备无会议笔记")

    def general_collection(self):

        self.method.xpath_text_click("收藏")

    def general_rename(self,text):
        self.method.xpath_text_click("重命名")

        self.method.xpath_text_click("重命名",None)

        self.method.by_element_click(By.ID, "com.onyx:id/imageView_clear")

        self.method.wait_input_box(By.ID, "com.onyx:id/editText_new_name", text)

        self.method.xpath_text_click("取消",None)

        self.method.xpath_text_click("确定",None)

        self.method.xpath_text_click("确定")

    def general_copy(self):

        self.method.xpath_text_click("复制")

        self.method.xpath_text_click("根目录")

        self.method.wait_check_toast("复制成功")

    def general_move(self, move_name ):

        self.method.xpath_text_click("移动")

        self.method.xpath_text_click(move_name)

    def general_delete(self):

        # 常规菜单 - 点击删除按钮
        self.method.xpath_text_click("删除")

        # 删除引导弹窗校验
        self.method.by_name_click(By.ID, 'com.onyx:id/textView_message', ("将会一并删除ONYX云端同步的笔记，是否确认？\n"
                                                                          "（可从笔记回收站中恢复）",None))
        # 删除引导弹窗 - 取消按钮校验
        self.method.by_name_click(By.ID, 'com.onyx:id/button_negative', '取消',None)

        # 删除引导弹窗 - 确定按钮校验
        self.method.by_name_click(By.ID, 'com.onyx:id/button_positive', '确定',None)

        # # 删除引导弹窗 - 点击确定按钮
        self.method.by_element_click(By.ID, 'com.onyx:id/button_positive')



