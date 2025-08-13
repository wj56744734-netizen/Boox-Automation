from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from Note_Automation.Note_Class.Note_class import Operation_method
from Note_Automation.config import driver
from Note_Automation.Test_local_notes.Public_method import Public_method
from Note_Automation.Other_tests.Test_for_test_note.Test_from_local_files import Test_from_local_files
from selenium.webdriver.support import expected_conditions as EC
from Note_Automation.Note_Class.Logcat import Logcat
from Note_Automation.Devices_list.Device_basic_information import Device_basic_information
import logging
import subprocess
import time
import re



class Test_render_time:

    def setup_method(self):

        self.method = Operation_method(driver)
        self.public = Public_method()
        self.driver = driver
        self.Test_from_local_files = Test_from_local_files()
        self.Logcat = Logcat()

    def import_note_rendering_time(self, import_note_logcat , note_name , times = 3):
        """ 导入笔记渲染 """
        n = 1

        while n <= times:

            activity_before_click = self.driver.current_activity

            self.get_file_note(f"{note_name}.note")

            self.method.by_name_click(By.ID, "com.onyx.android.note:id/start_import", "确定")

            import_note = self.Logcat.capture_render_logcat(target_logs=import_note_logcat, test_page=f"{note_name}", match_count=1)

            import_note.join()

            self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')

            while True:
                activity_after_click = self.driver.current_activity
                if activity_before_click == activity_after_click:
                    break
            n += 1

    def open_note_rendering_time(self, open_note_logcat, note_name,times = 3):
        """ 打开笔记渲染 """
        n = 1

        while n <= times:

            activity_before_click = self.driver.current_activity

            self.get_note(note_name, n)

            open_note = self.Logcat.capture_render_logcat(target_logs=open_note_logcat, test_page=f"{note_name}", match_count=1)

            open_note.join()

            time.sleep(1)
            self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')

            while True:
                activity_after_click = self.driver.current_activity
                if activity_before_click == activity_after_click:
                    n += 1
                    break

    def note_page_turning_rendering_time(self, open_note_logcat , note_page_up_logcat , note_name , page_turning = 3):
        """ 笔记内翻页渲染 """
        n = 1

        self.get_note(note_name,n)

        open_note = self.Logcat.capture_render_logcat(target_logs=open_note_logcat, test_page=f"{note_name}", match_count=1, reader_time_log=False)
        open_note.join()

        while n <= page_turning:

            page = self.method.by_father_index_click(By.ID, "com.onyx.android.note:id/fun_menu_list",
                                                     By.ID, "com.onyx.android.note:id/title", index=0,
                                                     should_click=None)

            page_0 = int(page.split("/")[0])

            note_page_up = self.Logcat.capture_render_logcat(target_logs=note_page_up_logcat, test_page=f"{note_name}", match_count=1)

            self.method.by_father_sub_index_click(By.ID, "com.onyx.android.note:id/fun_menu_list",
                                             By.ID, "com.onyx.android.note:id/menu_icon", index=0, index_1=6)

            note_page_up.join()

            page = self.method.by_father_index_click(By.ID, "com.onyx.android.note:id/fun_menu_list",
                                                             By.ID, "com.onyx.android.note:id/title", index=0 , should_click=None )

            page_1 = int(page.split("/")[0])

            if page_0 != page_1:
                if note_page_up_logcat:
                    n += 1
                else:
                    logging.info("画布已翻页 - 画布未渲染")

            if page_0 == page_1:
                logging.info("画布未翻页 - 重新翻页")

        self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')

    def note_thumbnail_rendering_time(self, open_note_logcat , note_thumbnail_logcat , note_name , n = 3):
        # 笔记缩略图半屏渲染耗时测试

        self.get_note(note_name, n)

        note_page = self.Logcat.capture_render_logcat(target_logs=open_note_logcat, test_page=f"{note_name}", match_count=1, reader_time_log=False)

        note_page.join()

        # logging.info("画布渲染完成")

        note_thumbnail = self.Logcat.capture_render_logcat(target_logs=note_thumbnail_logcat, test_page=f"{note_name}", match_count=5)

        self.method.by_element_click(By.ID, "com.onyx.android.note:id/title")

        try:
            wait = WebDriverWait(self.driver, 3)

            texts_to_check = [f"点击页码可进入【缩略图】页面管理" , f"最大支持500页"]
            #
            xpath_expression = '|'.join([f'//*[@text="{text}"]' for text in texts_to_check])

            guide = wait.until(EC.element_to_be_clickable((By.XPATH , xpath_expression)))
            if guide:
                self.method.xpath_text_click("知道了")
        except:
            pass

        note_thumbnail.join()

        devices = Device_basic_information()
        device_info = devices.get_device_info()
        version_info = device_info.get('version_info')

        match = re.search(r'[vV]?\d+\.\d+(?:\.\d+)?', version_info)
        if match:
            version_info = match.group().lstrip('vV')
        else:
            version_info = "未找到符合格式的版本号"

        # logging.info(f"提取的核心版本号: {version_info}")

        if version_info == "4.1":
            self.method.xpath_text_click("返回")  # 4.1
        elif version_info in {"4.0","4.0.3","4.0.2","4.0.1"}:
            self.method.by_element_click(By.ID, "com.onyx.android.note:id/title_iv")  # 4.0
        elif version_info == "3.5.4":
            self.method.by_element_click(By.ID, "com.onyx.android.note:id/text_title")  # 3.5.4
        else:
            logging.info(f"请检查系统版本，缩略图点击返回元素无法判断，当前测试版本为：{version_info}")
            return False

        # noinspection PyInconsistentReturns
        self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')

    def get_note(self, note_name, n):

        time.sleep(3)
        subprocess.run(['adb', 'shell', 'am', 'force-stop', 'com.onyx.android.note'])

        page_info = self.method.obtain_element_text(By.ID, "com.onyx:id/page_info")
        current_page, total_pages = map(int, page_info.split('/'))
        max_page_visits = total_pages * 2

        visit_count = 0
        while visit_count < max_page_visits:
            try:
                texts_to_check = [f"{note_name}({n})", f"{note_name}"]
                xpath_expression = '|'.join([f'//*[@text="{text}"]' for text in texts_to_check])
                wait = WebDriverWait(self.driver, 3)
                element = wait.until(
                        EC.element_to_be_clickable((By.XPATH, xpath_expression))
                    )
                time.sleep(1)
                element.click()
                return True
            except:
                prev_page = current_page
                self.method.click_slice(0.7, 0.5, 0.4, 0.5)
                time.sleep(1)
                page_info = self.method.obtain_element_text(By.ID, "com.onyx:id/page_info")
                current_page, total_pages = map(int, page_info.split('/'))
                if current_page == prev_page:
                        return False
                visit_count += 1
        logging.error(f"达到最大尝试次数，未找到笔记：'{note_name}({n})'尝试寻找笔记原名称")
        return False

    def get_file_note(self,note_name):

        time.sleep(2)
        subprocess.run(['adb', 'shell', 'am', 'force-stop', 'com.onyx.android.note'])

        # time.sleep(1)
        page_info = self.method.obtain_element_text(By.ID, "com.onyx:id/textView_page_info")
        current_page, total_pages = map(int, page_info.split('/'))
        max_page_visits = total_pages * 2
        visit_count = 0
        while visit_count < max_page_visits:
            try:
                wait = WebDriverWait(self.driver, 3)
                element = wait.until(
                    EC.element_to_be_clickable((By.XPATH, f'//*[@text="{note_name}"]'))
                )
                element.click()
                return True
            except:
                if total_pages !=1:
                    prev_page = current_page
                    self.method.click_slice(0.7,0.5,0.4,0.5)
                    page_info = self.method.obtain_element_text(By.ID, "com.onyx:id/textView_page_info")
                    current_page, total_pages = map(int, page_info.split('/'))
                    if current_page == prev_page:
                        logging.info(f"翻页未成功")
                        return False
                else:
                    visit_count += 1
                visit_count += 1
        logging.error(f"达到最大尝试次数，未找到笔记：'{note_name}'")
        return False

    def test_render_time(self, note_test_initial):

        device = Device_basic_information()
        device_info = device.get_device_info()
        version_info = device_info.get('version_info')

        match = re.search(r'[vV]?\d+\.\d+(?:\.\d+)?', version_info)

        if match:

            version_info = match.group().lstrip('vV')
        else:
            logging.info("未找到符合格式的版本号")


        """ 打开笔记和导入笔记通用一个日志 """
        if version_info in {"4.0", "4.1" ,"4.0.3","4.0.2","4.0.1"}:
            open_note_logcat = ''' "render note page point count: " '''   # 4.0 - 4.1

        elif version_info == "3.5.4":
            open_note_logcat = ''' "RxBaseAction: com.onyx.android.note.note.action.render.RenderToSurfaceViewAction" '''   # 3.5.4

        else:
            logging.info(f"请检查系统版本未设置指定版本日志匹配，当前测试版本为：{version_info}")
            return False

        """ 笔记内翻页渲染日志 """
        if version_info in {"4.0", "4.1" ,"4.0.3","4.0.2","4.0.1"}:
            note_page_up_logcat = ''' "render note page point count: " '''

        elif version_info == "3.5.4":
            note_page_up_logcat = ''' "RxBaseAction: com.onyx.android.note.note.action.page.PageNextAction" '''

        else:
            logging.info(f"请检查系统版本未设置指定版本日志匹配，当前测试版本为：{version_info}")
            return False

        """ 笔记缩略图渲染日志 """
        if version_info in {"4.0", "4.1" ,"4.0.3","4.0.2","4.0.1"}:
            note_thumbnail_logcat = ''' render thumbnail note page point count: ,
                                        render note page thumbnail: '''

        elif version_info == "3.5.4":
            note_thumbnail_logcat = ''' "RxBaseAction: com.onyx.android.note.note.action.page.PageThumbnailAction" '''

        else:
            logging.info(f"请检查系统版本未设置指定版本日志匹配，当前测试版本为：{version_info}")
            return False

        open_note_logcat = [line.strip().strip('",') for line in open_note_logcat.split('\n') if line.strip()]

        note_page_up_logcat = [line.strip().strip('",') for line in note_page_up_logcat.split('\n') if line.strip()]

        note_thumbnail_logcat = [line.strip().strip('",') for line in note_thumbnail_logcat.split('\n') if line.strip()]

        logging.info(f"导入和打开笔记捕捉日志:{open_note_logcat}")
        logging.info(f"笔记内翻页捕捉日志:{note_page_up_logcat}")
        logging.info(f"笔记内缩略图渲染捕捉日志:{note_thumbnail_logcat}")

#------------------------------------------------------------------------------------------------------------------------

        self.public.enter_storage()
        self.method.by_name_click(By.ID, "com.onyx:id/volume_name", "存储")
        self.public.get_file("笔记自动化测试文件", "固件迭代测试项")

        note_names = [
            "笔记测试物料（多笔迹）- 用户提供" ,
            "笔记测试物料（钢笔）" ,
            "笔记测试物料（毛笔）",
            "笔记测试物料（马克笔）" ,
            "笔记测试物料（铅笔 纹理2）" ,
            "笔记测试物料（铅笔 纹理1）" ,
            # "笔记测试物料（书法钢笔）" ,
            # "笔记测试物料（写实钢笔）" ,

            "笔记测试物料（钢笔）3.5.4" ,
            "笔记测试物料（钢笔）4.0"
            # "笔记测试物料（钢笔）4.1"

            # "笔记测试物料（圆珠笔）"
        ]
        for note_name in note_names:
            logging.info(f"--------------------测试场景：导入笔记------------------------")
            self.import_note_rendering_time(open_note_logcat , note_name)

        driver.press_keycode(3)

        self.method.xpath_text_click("笔记")

        for note_name in note_names:
            logging.info(f"--------------------测试场景：打开笔记------------------------")
            self.open_note_rendering_time(open_note_logcat , note_name)

        for note_name in note_names:
            logging.info(f"--------------------测试场景：笔记内翻页------------------------")
            self.note_page_turning_rendering_time(open_note_logcat , note_page_up_logcat , note_name)

        # noinspection PyInconsistentReturns
        for note_name in note_names:
            logging.info(f"--------------------测试场景：缩略图加载------------------------")
            self.note_thumbnail_rendering_time(open_note_logcat , note_thumbnail_logcat , note_name)
