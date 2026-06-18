import logging
import re
import time
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from boox_automation.ui_ops.logcat import Logcat
from boox_automation.driver import driver
from boox_automation.devices.info import (
    TEST_FILES_DISPLAY_ROOT, TEST_FILES_DIR_NOTE_EXPORT,
)
from boox_automation.ui_ops.operations import Operation_method
from boox_automation.tests.helpers import Public_method, device_region

# 笔记导出格式
old_version = ["矢量PDF", "位图PDF", ".note文件（BOOX笔记格式）"]
new_version = ["可编辑PDF", "不可编辑PDF", ".note文件（BOOX笔记格式）"]
note_export_log = 'com.onyx.android.note.note.action.export.ExportNoteAction'

class Test_Note_Export_Time:
    # 类级别标志，控制引导只执行一次
    _guide_shown = False
    # 新增：控制分享与导出引导只执行一次
    _share_export_guide_clicked = False

    def setup_method(self):
        self.driver = driver
        self.method = Operation_method(self.driver)
        self.public = Public_method()
        self.Logcat = Logcat()

    # ========== 弹窗检测辅助方法 ==========
    def _is_overwrite_dialog_visible(self, test_note_name):
        """
        检测"文件已存在，是否替换"弹窗是否出现。
        :param test_note_name: 笔记名称，用于拼接弹窗文本
        :return: True=弹窗存在，False=弹窗不存在
        """
        name = f'“{test_note_name}”已存在，要替换它吗？'
        try:
            wait = WebDriverWait(self.driver, 2)
            element = wait.until(EC.visibility_of_element_located((By.XPATH, f'//*[@text="{name}"]')))
            return element is not None
        except Exception:
            return False

    def is_export_success_dialog_visible(self, export_success="导出成功！"):
        """
        检测"导出成功"弹窗是否出现。
        :return: True=弹窗存在，False=弹窗不存在
        """
        name = export_success
        try:
            wait = WebDriverWait(self.driver, 2)
            element = wait.until(EC.visibility_of_element_located((By.XPATH, f'//*[@text="{name}"]')))
            return element is not None
        except Exception:
            return False

    def _show_guide_once_after_long_press(self):
        """在长按后执行一次引导（使用类标志）"""
        if not Test_Note_Export_Time._guide_shown:
            self.public.attribute_guide("笔记属性信息已收纳至【属性与安全】模块下的【属性】")
            Test_Note_Export_Time._guide_shown = True


#---------------- 笔记导出相关方法 -------------------

    def export_from_note_home_page(self, test_note_name):
        """从笔记首页长按笔记导出（引导在第一次长按后执行一次）"""
        def export_from_notebook_home(note_name, export, export_layers=None):
            """ 笔记首页导出相关方法 """
            time.sleep(1)

            self.method.xpath_text_click(name="分享与导出")

            # 点击导出中格式
            self.method.xpath_text_click(name=export)

            if export != ".note文件（BOOX笔记格式）":

                export_size = self.method.xpath_parent_click(
                    xpath='//android.widget.RadioButton[@resource-id="com.onyx:id/default_size"]',
                    should_click=False)

                export_size = export_size.text

                # 点击导出中尺寸
                self.method.xpath_text_click(name=export_size)

                # 点击导出中图层
                self.method.xpath_text_click(name=export_layers)

            else:

                export_size = "无"

            self.method.xpath_text_click(name="导出")

            self.Logcat.capture_logcat(
                target_logs=[note_export_log],
                block=False, single_timeout=2000,
                strict=True
            )

            # 检测覆盖文件弹窗
            if self._is_overwrite_dialog_visible(test_note_name):
                self.method.xpath_text_click(name="确定")

                logging.debug("已覆盖导出文档")
            else:
                logging.debug("未覆盖导出文档")

            toast = self.is_export_success_dialog_visible()

            if toast:
                # 等待最多 10 秒让日志完成捕获（避免因日志延迟导致误判为 0）
                result = self.Logcat.wait_result(timeout=5)
                if result and result.get("success"):
                    log_line = result["detailed_matches"].get(note_export_log, "")
                    match = re.search(r'--->\s*(\d+)\s*ms', log_line)
                    time_ms = match.group(1) if match else "解析失败"

                    export_final_success = True
                else:
                    # 仍无日志，认为导出太快未输出日志，记录为 0
                    export_final_success = True
                    time_ms = 0
                    # logging.info("导出成功但未捕获日志耗时，记录为0")
            else:
                result = self.Logcat.wait_result()

                if result.get("success"):
                    log_line = result["detailed_matches"].get(note_export_log, "")
                    match = re.search(r'--->\s*(\d+)\s*ms', log_line)
                    time_ms = match.group(1) if match else "解析失败"
                    export_final_success = True
                else:
                    # 再次检查弹窗（可能在等待期间出现）
                    toast_retry = self.is_export_success_dialog_visible()
                    if toast_retry:
                        export_final_success = True
                        logging.info("    ✅导出成功，但日志获取失败")
                        time_ms = "❌ 日志获取异常"
                    else:
                        export_final_success = False
                        logging.error(f"❌ 导出失败：{result.get('message', '未知错误')}")
                        time_ms = "0"

            # 确保线程结束
            self.Logcat.stop_capture()

            # 统一输出结果
            if export_final_success:
                export_size = re.sub(r'\s+', ' ', export_size).strip()
                logging.info(f"    ✅ {export} | 图层 {export_layers} | 尺寸 {export_size} | 耗时 {time_ms} ms")
            else:
                logging.error("❌ 导出最终失败")

            # 点击确定关闭弹窗（无论成功与否）
            self.method.xpath_text_click(name="确定")

        version = self.public.get_version(short=True)

        if version == "4.2":
            for export_format in new_version:
                # 长按笔记
                self.method.wait_for_press_name(by_method="id", locator="com.onyx:id/title", name=test_note_name)

                # 在第一次长按后执行引导（只执行一次）
                self._show_guide_once_after_long_press()

                export_from_notebook_home(
                    note_name=test_note_name,
                    export=export_format,
                    export_layers="可见"
                )
        else:
            for export_format in old_version:
                # 长按笔记
                self.method.wait_for_press_name(by_method="id", locator="com.onyx:id/title", name=test_note_name)

                # 在第一次长按后执行引导（只执行一次）
                self._show_guide_once_after_long_press()

                export_from_notebook_home(
                    note_name=test_note_name,
                    export=export_format,
                    export_layers="可见"
                )

    def export_from_within_note(self, test_note_name, share_and_export_guide):
        """"" 笔记内部导出 """""
        def export_inside_note(note_name, export, export_layers):
            # 点击导出中格式
            self.method.xpath_text_click(name=export)

            if export != ".note文件（BOOX笔记格式）":
                export_size = self.method.xpath_parent_click(
                    xpath='//android.widget.RadioButton[@resource-id="com.onyx.android.note:id/default_size"]',
                    should_click=False)
                export_size = export_size.text
                # 点击导出中尺寸
                self.method.xpath_text_click(name=export_size)
                # 点击导出中图层
                self.method.xpath_text_click(name=export_layers)
            else:
                export_size = "无"

            self.method.xpath_text_click(name="导出")

            self.Logcat.capture_logcat(
                target_logs=[note_export_log],
                block=False, single_timeout=2000,
                strict=True
            )

            # 检测覆盖文件弹窗
            if self._is_overwrite_dialog_visible(note_name):
                time.sleep(1)
                self.method.xpath_text_click(name="确定")
                logging.debug("已覆盖导出文档")
            else:
                logging.debug("未覆盖导出文档")

            toast = self.is_export_success_dialog_visible()

            if toast:
                # 等待最多 10 秒让日志完成捕获
                result = self.Logcat.wait_result(timeout=10)
                if result and result.get("success"):
                    log_line = result["detailed_matches"].get(
                        note_export_log, "")
                    match = re.search(r'--->\s*(\d+)\s*ms', log_line)
                    time_ms = match.group(1) if match else "解析失败"
                    export_final_success = True
                else:
                    export_final_success = True
                    time_ms = 0
                    # logging.info("导出成功但未捕获日志耗时，记录为0")
            else:
                result = self.Logcat.wait_result()
                if result.get("success"):
                    log_line = result["detailed_matches"].get(
                        note_export_log, "")
                    match = re.search(r'--->\s*(\d+)\s*ms', log_line)
                    time_ms = match.group(1) if match else "解析失败"
                    export_final_success = True
                else:
                    toast_retry = self.is_export_success_dialog_visible()
                    if toast_retry:
                        export_final_success = True
                        logging.info("    ✅导出成功，但日志获取失败")
                        time_ms = "❌ 日志获取异常"
                    else:
                        export_final_success = False
                        logging.error(f"❌ 导出失败：{result.get('message', '未知错误')}")
                        time_ms = "0"

            # 确保线程结束
            self.Logcat.stop_capture()

            if export_final_success:
                export_size = re.sub(r'\s+', ' ', export_size).strip()
                logging.info(f"    ✅ {export} | 图层 {export_layers} | 尺寸 {export_size} | 耗时 {time_ms} ms")
            else:
                logging.error(f"❌ 导出最终失败")

            self.method.xpath_text_click(name="确定")

        def release_share_and_export():
            # 国内设备需要先将分享导出菜单放入一级工具栏
            self.method.xpath_text_click(name="更多")
            time.sleep(3)
            self.method.wait_for_screen_size(start_screen_width=0.17, start_screen_height=0.96)
            self.method.xpath_text_click(name="全刷")
            self.method.xpath_text_click(name="搜索")
            self.method.xpath_text_click(name="手势")
            self.method.xpath_text_click(name="缩放")
            self.method.xpath_text_click(name="页面+")
            self.method.xpath_text_click(name="文本框")
            self.method.xpath_text_click(name="选项设置")
            self.method.xpath_text_click(name="分享与导出")

        self.method.xpath_text_click(name=test_note_name)
        time.sleep(2)

        if device_region == "国内":
            share_and_export = "分享与导出"
            try:
                wait = WebDriverWait(self.driver, 5)
                element = wait.until(EC.visibility_of_element_located((By.XPATH, f'//*[@text="{share_and_export}"]')))
                if element:
                    logging.debug(f"笔记内工具条一级显示分享与导出: {share_and_export}")
                    self.method.xpath_text_click(name=share_and_export)
            except:
                logging.debug(f"一级菜单未显示分享与导出: {share_and_export}")
                release_share_and_export()
        else:
            self.method.xpath_text_click(name="分享与导出")

        if share_and_export_guide and not Test_Note_Export_Time._share_export_guide_clicked:
            self.method.xpath_text_click(name="知道了")
            Test_Note_Export_Time._share_export_guide_clicked = True
            logging.debug("已点击分享与导出引导「知道了」")

        version = self.public.get_version(short=True)
        time.sleep(3)
        self.method.wait_for_screen_size(start_screen_width=0.87, start_screen_height=0.03)

        if version == "4.2":
            for export_format in new_version:
                self.method.xpath_parent_click(
                    xpath='(//android.widget.ImageView[@resource-id="com.onyx.android.note:id/menu_icon"])[7]'
                )
                export_inside_note(
                    note_name=test_note_name,
                    export=export_format,
                    export_layers="可见"
                )
        else:
            for export_format in old_version:
                logging.info(f"{export_format}")
                self.method.xpath_parent_click(
                    xpath='(//android.widget.ImageView[@resource-id="com.onyx.android.note:id/menu_icon"])[7]'
                )
                export_inside_note(
                    note_name=test_note_name,
                    export=export_format,
                    export_layers="可见"
                )

        self.method.wait_for_screen_size(start_screen_width=0.08, start_screen_height=0.04)
        self.method.by_element_click(element_key="通用操作.笔记内-返回按钮")

    @pytest.mark.cleanup_app_data
    @pytest.mark.cleanup_storage_files
    def test_note_export_time(self, note_perf_initial):

        self.public.enter_note_app()
        self.method.xpath_text_click(element_key="笔记首页.无笔记状态创建按钮")
        self.method.xpath_text_click(element_key="笔记首页.从本地文件导入")
        self.public.import_file_bootstrap("选择文件即可创建笔记", "知道了")
        self.public.import_file("笔记自动化测试文件", "固件迭代测试项（笔记导出）")

        # 返回按钮
        self.method.xpath_parent_click(xpath='//android.widget.LinearLayout[@resource-id="com.onyx.android.note:id/layout_back"]/android.widget.ImageView')

        # 以下注释部分可根据需要开启
        driver.press_keycode(3)
        self.public.restore_notes(file_route_name=TEST_FILES_DISPLAY_ROOT, file_route_name2=TEST_FILES_DIR_NOTE_EXPORT, file_route_name3="手写线条.note")
        time.sleep(3)
        self.public.enter_note_app()
        self.method.xpath_text_click(name="手写线条(1)", should_click=False)


        page_number = self.method.check_list_timeout(element_key="通用操作.笔记列表页码信息")
        for ele in page_number:
            logging.debug(f"页码元素文本：{ele.text}")

        test_note = []
        test_note_name_elements = self.method.check_list_timeout(element_key="通用操作.笔记标题列表")
        for element in test_note_name_elements:
            test_note.append(element.text)
        logging.debug(f"笔记名称列表：{test_note}")

        Test_Note_Export_Time._guide_shown = False
        Test_Note_Export_Time._share_export_guide_clicked = False
        share_and_export_guide = True

        logging.info(f"笔记导出捕捉日志: {note_export_log} ")

        for test_note_name in test_note:
            logging.info(f"🔽 开始执行：笔记首页导出测试 , 测试笔记：{test_note_name}")
            self.export_from_note_home_page(test_note_name)

        for test_note_name in test_note:
            logging.info(f"🔽 开始执行：笔记内部导出测试 , 测试笔记：{test_note_name}")
            self.export_from_within_note(test_note_name, share_and_export_guide=share_and_export_guide)