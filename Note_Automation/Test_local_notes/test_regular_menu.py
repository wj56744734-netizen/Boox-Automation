from Note_Automation.Test_local_notes.Public_method import Public_method, device_region
from selenium.webdriver.common.by import By
from Note_Automation.Note_class.Note_class import Operation_method
from Note_Automation.config import driver
from Note_Automation.conftest import note_mark_china, note_mark_increment, note_mark_full_amount
import allure
import logging
import pytest
import time

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

        pass

        # """ """
        # self.public.enter_note_app()
        #
        # self.method.xpath_text_click(element_key="笔记首页.无笔记状态创建按钮")
        #
        # # 创建手写笔记
        # self.public.create_handwritten_notes()
        #
        # #有笔记状态点击创建
        # self.method.by_element_click(element_key="通用操作.创建按钮")
        #
        # # 创建文本笔记
        # self.public.create_text_notes()
        #
        # self.public.create_meeting_if_domestic()
        #
        # self.method.wait_for_press_name(element_key="笔记首页.笔记-1")
        #
        # self.attribute_guide("笔记属性信息已收纳至【属性与安全】模块下的【属性】")
        #
        # # 对比内容是否缺少
        #
        # self.method.wait_for_press_name(element_key="笔记首页.文本-1")
        #
        # # 对比内容是否缺少


    @note_mark_china("常规菜单删除笔记")
    @note_mark_increment("增量")
    def test_13_general_menu_delete_notes(self,note_test_initial):
        """""
        回归用例P0 ---
        删除手写、会议、文本笔记和文件夹后确认笔记是否在回收站，并且清理回收站
        """""
        self.public.enter_note_app()

        self.method.xpath_text_click(element_key="笔记首页.无笔记状态创建按钮")

        # 创建手写笔记
        self.public.create_handwritten_notes()

        #有笔记状态点击创建
        self.method.by_element_click(element_key="通用操作.创建按钮")

        # 创建文本笔记
        self.public.create_text_notes()

        self.public.create_meeting_if_domestic()

        self.method.wait_for_press_name(element_key="笔记首页.笔记-1")

        self.attribute_guide("笔记属性信息已收纳至【属性与安全】模块下的【属性】")

        self.general_delete()

        self.method.wait_for_press_name(element_key="笔记首页.文本-1")

        self.general_delete()

        if device_region == "国内":

            self.method.wait_for_press_name(element_key="笔记首页.会议-1")

            self.general_delete()

        self.public.more_menus("回收站")

        self.method.xpath_text_click(element_key="笔记首页.校验手写笔记", should_click=None)

        self.method.xpath_text_click(element_key="笔记首页.校验文本笔记", should_click=None)

        if device_region == "国内" :
            # 校验回收站内是否有会议笔记
            self.method.xpath_text_click(element_key="笔记首页.校验会议笔记", should_click=None)

        self.method.xpath_text_click(element_key="笔记首页.笔记回收站侧栏清空")

        self.method.by_name_click(element_key="笔记首页.笔记回收站侧栏清空引导", should_click=None)

        self.method.by_name_click(element_key="笔记首页.笔记回收站侧栏清空引导取消", should_click=None)

        self.method.by_name_click(By.ID, 'com.onyx:id/button_positive', '确定',None)

        self.method.by_element_click(element_key="通用操作.弹窗确认按钮")  # 回收站清空弹窗校验完成后点击确认

        self.method.by_name_click(element_key="笔记首页.笔记回收站无笔记")

    @note_mark_china("常规菜单移动笔记")
    @note_mark_increment("增量")
    def test_14_general_menu_move_notes(self,note_test_initial):
        """""
        回归用例P0 ---
        常规菜单 创建手写、文本、会议笔记和文件夹，移动至文件夹中
        """""
        self.public.enter_note_app()

        # 点击更多菜单
        self.public.more_menus("新建文件夹")

        self.method.xpath_text_click(element_key="通用操作.确定按钮")

        # 有笔记状态点击创建
        self.method.by_element_click(element_key="通用操作.创建按钮")

        # 创建手写笔记
        self.public.create_handwritten_notes()

        # 有笔记状态点击创建
        self.method.by_element_click(element_key="通用操作.创建按钮")

        # 创建文本笔记
        self.public.create_text_notes()

        self.public.create_meeting_if_domestic()
        # 长按手写笔记
        self.method.wait_for_press_name(element_key="笔记首页.笔记-1")

        self.attribute_guide("笔记属性信息已收纳至【属性与安全】模块下的【属性】")

        # 移动手写笔记至指定文件路径
        self.general_move("文件夹-1")

        # 长按文本笔记
        self.method.wait_for_press_name(element_key="笔记首页.文本-1")

        # 移动文本笔记至指定文件路径
        self.general_move("文件夹-1")

        if device_region == "国内":
            #校验会议笔记
            self.method.wait_for_press_name(element_key="笔记首页.会议-1")

            # 移动会议笔记至指定文件路径
            self.general_move("文件夹-1")


        # 长按文件夹笔记
        self.method.wait_for_press_name(element_key="笔记首页.文件夹-1")

        # 移动笔记
        self.method.xpath_text_click(element_key="笔记首页.常规菜单-移动")

        # 移动菜单 - 点击新建文件夹
        self.method.xpath_text_click(element_key="笔记首页.新建文件夹")

        # 文件夹弹窗点击确认
        self.method.by_name_click(By.ID, "com.onyx:id/btn_ok", "确定")

        self.method.xpath_text_click("文件夹-2")

        self.method.xpath_text_click(element_key="笔记首页.校验文件夹")

        self.method.xpath_text_click(element_key="笔记首页.校验手写笔记", should_click=None)

        self.method.xpath_text_click(element_key="笔记首页.校验文本笔记", should_click=None)

        if device_region == "国内":
            # 校验移动会议笔记后是否显示在文件夹中
            self.method.xpath_text_click(element_key="笔记首页.校验会议笔记", should_click=None)

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

        self.method.wait_for_press_name(element_key="笔记首页.笔记-1")

        self.attribute_guide("笔记属性信息已收纳至【属性与安全】模块下的【属性】")

        self.general_copy()

        self.method.wait_for_press_name(element_key="笔记首页.文本-1")

        self.general_copy()

        if device_region == "国内":

            self.method.wait_for_press_name(element_key="笔记首页.会议-1")

            self.general_copy()

        # 校验复制的手写笔记
        self.method.xpath_text_click("笔记-1(1)",None)

        # 校验复制的文本笔记
        self.method.xpath_text_click("文本-1(1)",None)

        # 校验复制的手写笔记是否还存在
        self.method.xpath_text_click(element_key="笔记首页.校验手写笔记", should_click=None)

        # 校验复制的文本笔记是否还存在
        self.method.xpath_text_click(element_key="笔记首页.校验文本笔记", should_click=None)

        if device_region == "国内":

            # 校验复制的会议笔记
            self.method.xpath_text_click("会议-1(1)",None)

            # 校验复制的会议笔记是否还存在
            self.method.xpath_text_click(element_key="笔记首页.校验会议笔记", should_click=None)

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

        self.public.enter_note_app()

        # 无笔记未登记 点击创建笔记
        self.method.xpath_text_click(element_key="笔记首页.无笔记状态创建按钮")
        # 创建手写笔记
        self.public.create_handwritten_notes()

        # 有笔记状态点击创建
        self.method.by_element_click(element_key="通用操作.创建按钮")
        # 创建文本笔记
        self.public.create_text_notes()

        # 点击更多菜单
        self.method.by_sub_index_click(element_key="笔记首页.工具栏更多菜单")

        # 点击新建文件夹
        self.method.xpath_text_click(element_key="笔记首页.新建文件夹")

        # 校验文件夹弹窗
        self.method.xpath_text_click(element_key="笔记首页.文件夹名称输入框", should_click=None)
        self.method.xpath_text_click(element_key="通用操作.取消按钮", should_click=None)
        self.method.xpath_text_click(element_key="通用操作.确定按钮", should_click=None)
        self.method.xpath_text_click(element_key="通用操作.确定按钮")

        self.public.create_meeting_if_domestic()
        self.method.wait_for_press_name(element_key="笔记首页.笔记-1")

        self.attribute_guide("笔记属性信息已收纳至【属性与安全】模块下的【属性】")

        self.general_rename(handwritten_name)

        self.method.wait_for_press_name(element_key="笔记首页.文本-1")

        self.general_rename(text_name)

        if device_region == "国内":

            self.method.wait_for_press_name(element_key="笔记首页.会议-1")

            self.general_rename(meeting_name)

        self.method.wait_for_press_name(element_key="笔记首页.文件夹-1")

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
        self.method.wait_for_press_name(element_key="笔记首页.笔记-1")

        self.attribute_guide("笔记属性信息已收纳至【属性与安全】模块下的【属性】")

        self.general_collection()

        self.method.wait_for_press_name(element_key="笔记首页.文本-1")

        self.general_collection()

        if device_region == "国内":

            self.method.wait_for_press_name(element_key="笔记首页.会议-1")

            self.general_collection()

        self.method.by_sub_index_click(element_key="笔记首页.搜索笔记入口")

        self.method.xpath_text_click(element_key="笔记首页.校验手写笔记", should_click=None)

        self.method.xpath_text_click(element_key="笔记首页.校验文本笔记", should_click=None)

        if device_region == "国内":

            self.method.xpath_text_click(element_key="笔记首页.校验会议笔记", should_click=None)



    def attribute_guide(self,guide):
        try:
            self.method.xpath_text_click(guide, None)
            self.method.xpath_text_click(element_key="笔记首页.弹窗通用知道了")
        except Exception:
            logging.info("属性引导-已跳过")


    def create_notes(self):

        # 有无笔记状态点击创建 - 判断条件

        self.method.xpath_text_click(element_key="笔记首页.无笔记状态创建按钮")

        # 创建手写笔记
        self.public.create_handwritten_notes()

        # 有笔记状态点击创建 - 判断条件
        self.method.by_element_click(element_key="通用操作.创建按钮")

        # 创建文本笔记
        self.public.create_text_notes()

        # 创建会议笔记 - 判断条件
        self.public.create_meeting_if_domestic()

    def general_collection(self):

        self.method.xpath_text_click(element_key="笔记首页.常规菜单-收藏")

    def _click_action_entry(self, action_name):
        """在常规菜单弹窗中定位动作入口（跨 tab + 滑动兜底）。"""
        # 引导浮层会拦截标签点击，先尝试关闭
        self.public.dismiss_first_time_guide(timeout=1, max_steps=2)
        last_exc = None
        for tab_name in ("常规", "属性与安全"):
            try:
                self.method.xpath_text_click(tab_name)
            except Exception:
                continue
            for attempt in range(3):
                try:
                    self.method.xpath_text_click(action_name)
                    return
                except Exception as exc:
                    last_exc = exc
                    # 动作按钮可能在同一行右侧，左滑后重试
                    if attempt < 2:
                        self.method.click_slice(0.78, 0.67, 0.30, 0.67)
                        time.sleep(0.3)
        if last_exc:
            raise last_exc
        self.method.xpath_text_click(action_name)

    def general_rename(self,text):
        self._click_action_entry("重命名")

        self.method.xpath_text_click(element_key="笔记首页.常规菜单-重命名", should_click=None)

        self.method.by_element_click(element_key="通用操作.清空输入按钮")

        self.method.wait_input_box(By.ID, "com.onyx:id/editText_new_name", text)

        self.method.xpath_text_click(element_key="通用操作.取消按钮", should_click=None)

        self.method.xpath_text_click(element_key="通用操作.确定按钮", should_click=None)

        self.method.xpath_text_click(element_key="通用操作.确定按钮")

    def general_copy(self):
        self._click_action_entry("复制")

        self.method.xpath_text_click(element_key="笔记首页.常规菜单-复制根目录")

        self.method.wait_check_toast("复制成功")

    def general_move(self, move_name ):
        self._click_action_entry("移动")

        self.method.xpath_text_click(move_name)

    def general_delete(self):

        self._click_action_entry("删除")
        # 常规菜单 - 点击删除按钮
        self.method.by_name_click(By.ID, 'com.onyx:id/textView_message', "将会一并删除ONYX云端同步的笔记，是否确认？\n"
                                                                          "（可从笔记回收站中恢复）", None)
        # 删除引导弹窗 - 取消按钮校验
        self.method.by_name_click(element_key="笔记首页.笔记常规菜单删除引导取消", should_click=None)

        # 删除引导弹窗 - 确定按钮校验
        self.method.by_name_click(By.ID, 'com.onyx:id/button_positive', '确定',None)

        # # 删除引导弹窗 - 点击确定按钮
        self.method.by_element_click(element_key="通用操作.弹窗确认按钮")



