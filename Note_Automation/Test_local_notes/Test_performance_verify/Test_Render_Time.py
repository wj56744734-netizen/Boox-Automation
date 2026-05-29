from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from Note_Automation.Note_class.Note_class import Operation_method
from Note_Automation.config import driver
from Note_Automation.Note_class.Logcat import Logcat
from selenium.webdriver.support import expected_conditions as EC
from Note_Automation.Test_local_notes.Public_method import Public_method, device_size, device_id
import logging
import subprocess
import time


class Test_Render_Time:

    def setup_method(self):
        self.method = Operation_method(driver)
        self.public = Public_method()
        self.driver = driver
        self.Logcat = Logcat()
        # 引导标志（只处理一次）
        self.note_page_turn_guide_done = False
        self.note_thumbnail_guide_done = False
        self.toolbar_guide_done = False   # 工具条引导标志

    def note_page_flip_guide(self , guide_done_flag):
        """
        安全处理引导弹窗（仅当未处理过时执行）
        :param guide_done_flag: 实例属性名（字符串），用于访问和修改标志
        :return: None
        """
        # version_str = None
        #
        # version_str = self.public.get_version(short=True)
        #
        # if version_str == "4.2":
        #     guide_text = "点击页码，快速管理页面缩略图"
        # else:
        #     guide_text = "点击页码可进入【缩略图】页面管理"

        guide_text = "在【笔记设置】中可设置“翻页缩放偏好"

        if getattr(self, guide_done_flag, False):
            logging.debug(f"引导已处理过，跳过: {guide_text}")
            return

        try:
            wait = WebDriverWait(self.driver, 5)
            element = wait.until(EC.visibility_of_element_located((By.XPATH, f'//*[@text="{guide_text}"]')))
            if element:
                self.method.xpath_text_click(element_key="笔记首页.弹窗通用知道了")
                logging.debug(f"检测到引导并已处理: {guide_text}")
        except Exception:
            logging.debug(f"未检测到引导: {guide_text}")
        finally:
            setattr(self, guide_done_flag, True)



    def note_thumbnail_guide(self , guide_done_flag):
        """
        安全处理引导弹窗（仅当未处理过时执行）
        :param guide_done_flag: 实例属性名（字符串），用于访问和修改标志
        :return: None
        """
        version_str = None

        version_str = self.public.get_version(short=True)

        if version_str == "4.2":
            guide_text = "点击页码，快速管理页面缩略图"
        else:
            guide_text = "点击页码可进入【缩略图】页面管理"

        if getattr(self, guide_done_flag, False):
            logging.debug(f"引导已处理过，跳过: {guide_text}")
            return

        try:
            wait = WebDriverWait(self.driver, 5)
            element = wait.until(EC.visibility_of_element_located((By.XPATH, f'//*[@text="{guide_text}"]')))
            if element:
                self.method.xpath_text_click(element_key="笔记首页.弹窗通用知道了")
                logging.debug(f"检测到引导并已处理: {guide_text}")
        except Exception:
            logging.debug(f"未检测到引导: {guide_text}")
        finally:
            setattr(self, guide_done_flag, True)

    def handle_toolbar_guide(self):
        """
        处理 4.2 版本（非 6.13 寸设备）的工具条首次引导，只执行一次。
        """
        if self.toolbar_guide_done:
            logging.debug("工具条引导已处理过，跳过")
            return

        version_str = self.public.get_version(short=True)
        # 注意：device_size 为模块级变量，需在方法内声明 global 才能修改（此处只读，无需 global）
        if version_str == "4.2" and device_size != "6.13":
            try:
                self.public.toolbar_navigation()
                logging.debug("已处理 4.2 版本工具条引导")
            except Exception as e:
                logging.error(f"处理工具条引导失败: {e}")
        else:
            logging.debug(f"当前版本 {version_str} 或尺寸 {device_size} 不需要工具条引导")

        self.toolbar_guide_done = True

    def import_note_rendering_time(self, import_note_logcat, note_name, times=3):
        """ 导入笔记渲染 """
        n = 1
        while n <= times:
            activity_before_click = self.driver.current_activity
            self.get_file_note(f"{note_name}.note")
            self.method.by_name_click(element_key="通用操作.笔记内-导入确认按钮")
            import_note = self.Logcat.capture_render_logcat(target_logs=import_note_logcat, test_page=f"{note_name}", match_count=1)
            import_note.join()

            # 处理工具条引导（只执行一次）
            self.handle_toolbar_guide()

            self.method.by_element_click(element_key="通用操作.笔记内-返回按钮")
            activity_timeout = time.time() + 30
            while time.time() < activity_timeout:
                activity_after_click = self.driver.current_activity
                if activity_before_click == activity_after_click:
                    break
                time.sleep(0.5)
            else:
                logging.warning("等待activity恢复超时")
            n += 1

    def open_note_rendering_time(self, open_note_logcat, note_name, times=3):
        """ 打开笔记渲染 """
        n = 1
        while n <= times:
            activity_before_click = self.driver.current_activity
            self.get_note(note_name, n)
            open_note = self.Logcat.capture_render_logcat(target_logs=open_note_logcat, test_page=f"{note_name}", match_count=1)
            open_note.join()
            time.sleep(1)
            self.method.by_element_click(element_key="通用操作.笔记内-返回按钮")
            activity_timeout = time.time() + 30
            while time.time() < activity_timeout:
                activity_after_click = self.driver.current_activity
                if activity_before_click == activity_after_click:
                    n += 1
                    break
                time.sleep(0.5)
            else:
                logging.warning("等待activity恢复超时，继续执行")

    def note_page_turning_rendering_time(self, open_note_logcat, note_page_up_logcat, note_name, page_turning=3):
        """ 笔记内翻页渲染 """
        n = 1
        retry_count = 0
        self.get_note(note_name, n)
        open_note = self.Logcat.capture_render_logcat(target_logs=open_note_logcat, test_page=f"{note_name}", match_count=1, reader_time_log=False)
        open_note.join()

        while n <= page_turning:
            page_element = self.method.xpath_parent_click(
                xpath='//android.widget.TextView[@resource-id="com.onyx.android.note:id/title"]',
                should_click=False
            )
            page_text = page_element.text
            page_0 = int(page_text.split("/")[0])

            note_page_up = self.Logcat.capture_render_logcat(target_logs=note_page_up_logcat, test_page=f"{note_name}", match_count=1)

            self.method.xpath_parent_click(xpath='(//android.widget.ImageView[@resource-id="com.onyx.android.note:id/menu_icon"])[7]')

            note_page_up.join()
            time.sleep(3)

            # 处理首次翻页引导（只处理一次）
            self.note_page_flip_guide("note_page_turn_guide_done")

            time.sleep(2)

            page_element = self.method.xpath_parent_click(
                xpath='//android.widget.TextView[@resource-id="com.onyx.android.note:id/title"]',
                should_click=False
            )
            page_text = page_element.text
            page_1 = int(page_text.split("/")[1])

            if page_0 != page_1:
                n += 1
                retry_count = 0
            else:
                retry_count += 1
                logging.info(f"画布未翻页 - 重新翻页 (重试{retry_count})")
                if retry_count >= 3:
                    logging.warning("翻页重试超过3次，跳过当前页")
                    n += 1
                    retry_count = 0

        self.method.by_element_click(element_key="通用操作.笔记内-返回按钮")

    def note_thumbnail_rendering_time(self, open_note_logcat, note_thumbnail_logcat, note_name, n=3):
        """ 笔记缩略图半屏渲染耗时测试 """
        self.get_note(note_name, n)

        note_page = self.Logcat.capture_render_logcat(target_logs=open_note_logcat, test_page=f"{note_name}", match_count=1, reader_time_log=False)
        note_page.join()

        note_thumbnail = self.Logcat.capture_render_logcat(target_logs=note_thumbnail_logcat, test_page=f"{note_name}", match_count=5)

        self.method.by_element_click(element_key="通用操作.笔记内-标题入口")

        # 处理缩略图引导（只处理一次）
        self.note_thumbnail_guide( "note_thumbnail_guide_done")

        note_thumbnail.join()

        version = self.public.get_version(short=True)

        if version in {"4.1", "4.1.1","4.2", "dev"}:
            self.method.xpath_text_click("返回")
        elif version in {"4.0", "4.0.3", "4.0.2", "4.0.1"}:
            self.method.by_element_click(element_key="通用操作.笔记内-标题图标")
        elif version == "3.5.4":
            self.method.by_element_click(element_key="通用操作.笔记内-标题文本")
        else:
            logging.info(f"请检查系统版本，缩略图点击返回元素无法判断，当前测试版本为：{version}")
            return False

        self.method.by_element_click(element_key="通用操作.笔记内-返回按钮")

    def get_note(self, note_name, n):
        time.sleep(3)
        subprocess.run(['adb', '-s', device_id, 'shell', 'am', 'force-stop', 'com.onyx.android.note'])
        page_info = self.method.obtain_element_text(element_key="通用操作.笔记列表页码信息")
        try:
            current_page, total_pages = map(int, page_info.split('/'))
        except (ValueError, AttributeError):
            logging.warning(f"get_note page_info格式异常: {page_info}")
            current_page, total_pages = 1, 1
        max_page_visits = total_pages * 2
        visit_count = 0
        while visit_count < max_page_visits:
            try:
                texts_to_check = [f"{note_name}({n})", f"{note_name}"]
                xpath_expression = '|'.join([f'//*[@text="{text}"]' for text in texts_to_check])
                wait = WebDriverWait(self.driver, 3)
                element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_expression)))
                time.sleep(1)
                element.click()
                return True
            except (TimeoutException, NoSuchElementException):
                prev_page = current_page
                self.method.click_slice(0.7, 0.5, 0.4, 0.5)
                time.sleep(1)
                page_info = self.method.obtain_element_text(element_key="通用操作.笔记列表页码信息")
                try:
                    current_page, total_pages = map(int, page_info.split('/'))
                except (ValueError, AttributeError):
                    logging.warning(f"get_note翻页后page_info格式异常: {page_info}")
                    return False
                if current_page == prev_page:
                    return False
                visit_count += 1
        logging.error(f"达到最大尝试次数，未找到笔记：'{note_name}({n})'尝试寻找笔记原名称")
        return False

    def get_file_note(self, note_name):
        time.sleep(2)
        subprocess.run(['adb', '-s', device_id, 'shell', 'am', 'force-stop', 'com.onyx.android.note'])
        time.sleep(1)
        page_info = self.method.obtain_element_text(element_key="通用操作.文件管理页码信息")
        logging.debug(f"{page_info}")
        try:
            current_page, total_pages = map(int, page_info.split('/'))
        except (ValueError, AttributeError):
            logging.warning(f"get_file_note page_info格式异常: {page_info}")
            current_page, total_pages = 1, 1
        max_page_visits = total_pages * 2
        visit_count = 0
        while visit_count < max_page_visits:
            try:
                wait = WebDriverWait(self.driver, 3)
                element = wait.until(EC.element_to_be_clickable((By.XPATH, f'//*[@text="{note_name}"]')))
                element.click()
                return True
            except (TimeoutException, NoSuchElementException):
                if total_pages != 1:
                    prev_page = current_page
                    self.method.click_slice(0.7, 0.5, 0.4, 0.5)
                    page_info = self.method.obtain_element_text(element_key="通用操作.文件管理页码信息")
                    try:
                        current_page, total_pages = map(int, page_info.split('/'))
                    except (ValueError, AttributeError):
                        logging.warning(f"page_info格式异常: {page_info}")
                        return False
                    if current_page == prev_page:
                        logging.info(f"翻页未成功")
                        return False
                visit_count += 1
        logging.error(f"达到最大尝试次数，未找到笔记：'{note_name}'")
        return False

    def test_render_time(self, note_test_initial):
        version_str = self.public.get_version(short=True)

        if version_str in {"4.0", "4.1", "4.0.3", "4.0.2", "4.0.1", "4.1.1", "4.2", "dev"}:
            open_note_logcat = ''' "render note page point count: " '''
        elif version_str == "3.5.4":
            open_note_logcat = ''' "RxBaseAction: com.onyx.android.note.note.action.render.RenderToSurfaceViewAction" '''
        else:
            logging.info(f"请检查系统版本未设置指定版本日志匹配，当前测试版本为：{version_str}")
            return False

        if version_str in {"4.0", "4.1", "4.0.3", "4.0.2", "4.0.1", "4.1.1", "4.2", "dev"}:
            note_page_up_logcat = ''' "render note page point count: " '''
        elif version_str == "3.5.4":
            note_page_up_logcat = ''' "RxBaseAction: com.onyx.android.note.note.action.page.PageNextAction" '''
        else:
            logging.info(f"请检查系统版本未设置指定版本日志匹配，当前测试版本为：{version_str}")
            return False

        if version_str in {"4.0", "4.1", "4.0.3", "4.0.2", "4.0.1", "4.1.1", "4.2", "dev"}:
            note_thumbnail_logcat = ''' render thumbnail note page point count: ,
                                        render note page thumbnail: '''
        elif version_str == "3.5.4":
            note_thumbnail_logcat = ''' "RxBaseAction: com.onyx.android.note.note.action.page.PageThumbnailAction" '''
        else:
            logging.info(f"请检查系统版本未设置指定版本日志匹配，当前测试版本为：{version_str}")
            return False

        open_note_logcat = [line.strip().strip('",') for line in open_note_logcat.split('\n') if line.strip()]
        note_page_up_logcat = [line.strip().strip('",') for line in note_page_up_logcat.split('\n') if line.strip()]
        note_thumbnail_logcat = [line.strip().strip('",') for line in note_thumbnail_logcat.split('\n') if line.strip()]

        logging.info(f"导入和打开笔记捕捉日志:{open_note_logcat}")
        logging.info(f"笔记内翻页捕捉日志:{note_page_up_logcat}")
        logging.info(f"笔记内缩略图渲染捕捉日志:{note_thumbnail_logcat}")

        self.public.enter_storage()
        self.method.by_name_click(element_key="设备相关.存储卷列表")
        self.public.get_file("笔记自动化测试文件", "固件迭代测试项（笔记渲染）")

        note_names = [
            "笔记测试物料（多笔迹）- 用户提供",
            "笔记测试物料（钢笔）",
            "笔记测试物料（毛笔）",
            "笔记测试物料（马克笔）",
            "笔记测试物料（铅笔 纹理2）",
            "笔记测试物料（铅笔 纹理1）",
            "笔记测试物料（书法钢笔）",
            "笔记测试物料（写实钢笔）"
        ]

        logging.info(f"--------------------测试场景：导入笔记------------------------")
        for note_name in note_names:
            self.import_note_rendering_time(open_note_logcat, note_name)
            logging.info(f"==================================================")

        driver.press_keycode(3)
        self.method.xpath_text_click(element_key="笔记首页.进入笔记首页")


        logging.info(f"--------------------测试场景：打开笔记------------------------")
        for note_name in note_names:
            self.open_note_rendering_time(open_note_logcat, note_name)
            logging.info(f"==================================================")


        logging.info(f"--------------------测试场景：笔记内翻页------------------------")
        for note_name in note_names:
            self.note_page_turning_rendering_time(open_note_logcat, note_page_up_logcat, note_name)
            logging.info(f"==================================================")


        logging.info(f"--------------------测试场景：缩略图加载------------------------")
        for note_name in note_names:
            self.note_thumbnail_rendering_time(open_note_logcat, note_thumbnail_logcat, note_name)
            logging.info(f"==================================================")