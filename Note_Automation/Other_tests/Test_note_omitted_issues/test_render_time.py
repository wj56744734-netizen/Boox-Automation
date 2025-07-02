import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from Note_Automation.Note_Class.Note_class import Operation_method
from Note_Automation.config import driver
from Note_Automation.Test_local_notes.Public_method import Public_method
from Note_Automation.Other_tests.Test_for_test_note.Test_from_local_files import Test_from_local_files
from selenium.webdriver.support import expected_conditions as EC
from Note_Automation.conftest import get_device_info


class Test_render_time:

    def setup_method(self):

        self.method = Operation_method(driver)
        self.public = Public_method()
        self.driver = driver
        self.Test_from_local_files = Test_from_local_files()

    def import_note_rendering_time(self, target, note_name ,times = 3):
        """ 导入笔记渲染 """
        n = 1
        while n <= times:
            activity_before_click = self.driver.current_activity
            self.get_file_note(f"{note_name}.note")
            self.method.by_name_click(By.ID, "com.onyx.android.note:id/start_import", "确定")
            self.public.capture_logcat(target, f"测试笔记：{note_name}，测试耗时")
            self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')
            while True:
                activity_after_click = self.driver.current_activity
                if activity_before_click == activity_after_click:
                    break
            n += 1


    def open_note_rendering_time(self, target, note_name,times = 3):
        """ 打开笔记渲染 """
        n = 1
        while n <= times:
            activity_before_click = self.driver.current_activity
            self.get_note(note_name, n)
            self.public.capture_logcat(target, f"测试笔记：{note_name}，测试耗时：")
            self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')
            while True:
                activity_after_click = self.driver.current_activity
                if activity_before_click == activity_after_click:
                    n += 1
                    break

    def note_page_turning_rendering_time(self, target , note_name , times = 3):
        """ 笔记内翻页渲染 """
        n = 1
        self.get_note(note_name, n)
        self.public.capture_logcat(target, "页面加载完成")
        while n <= times:
            page = self.method.obtain_element_text(By.ID, "com.onyx.android.note:id/title")
            page = page.split("/")
            page_1 = page[0]
            while True:
                test_max = 1
                self.method.click_slice(0.7, 0.5, 0.4, 0.5)
                # self.method.by_index_click(By.ID,"com.onyx.android.note:id/menu_icon",6)
                page_log = self.public.capture_logcat(target, f"测试笔记：{note_name}，测试耗时：")
                if page_log:
                    n += 1
                    break
                else:
                    time.sleep(1)
                    page = self.method.obtain_element_text(By.ID, "com.onyx.android.note:id/title")
                    page = page.split("/")
                    page_2 = page[0]

                if page_1 == page_2:
                    logging.info(f"翻页未成功-重新翻页")
                    test_max += 1

                if page_1 != page_2:
                    logging.info(f"成功翻页未获取到渲染日志-页面无需渲染")
                    self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')
                    return True

                if test_max == 3:
                    logging.info(f"重试次数已达到最大{test_max}")
                    return False

        self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')


    def note_thumbnail_rendering_time(self, target, note_name,n = 3):
        # 笔记缩略图半屏渲染耗时测试
        self.get_note(note_name, n)

        # self.method.by_index_click(By.ID, "com.onyx.android.note:id/dot_icon",2)

        self.method.by_element_click(By.ID, "com.onyx.android.note:id/title")

        n = 1

        try:
            wait = WebDriverWait(self.driver, 1)
            guide = wait.until(
                EC.element_to_be_clickable((By.XPATH, f'//*[@text="点击页码可进入【缩略图】页面管理"]'))
            )
            if guide:
                self.method.xpath_text_click("知道了")
        except:
            logging.info(f"缩略图无相关引导跳过---")

        while True:

            page_time = self.public.capture_logcat(target, f"测试笔记：{note_name}，测试第{n}页耗时：")

            if page_time:
                n += 1

                if n == 6:

                    break
            else:

                break

        # 关闭缩略图
        self.method.xpath_text_click("返回")
        # self.method.by_element_click(By.ID, "com.onyx.android.note:id/text_title")
        # 退出当前笔记
        self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')

    def get_page_numbers(self):
         page_list = self.method.obtain_element_list_test(By.CLASS_NAME, "android.widget.TextView")
         valid_pages = []

         for page in page_list:
            if page.isdigit():
                page_num = int(page)
                valid_pages.append(page_num)

            if valid_pages:
                max_page = max(valid_pages)
                return max_page

    def get_note(self, note_name, n):
            time.sleep(1)
            page_info = self.method.obtain_element_text(By.ID, "com.onyx:id/page_info")
            current_page, total_pages = map(int, page_info.split('/'))
            max_page_visits = total_pages * 2  # 设置最大尝试次数，这里假设最多遍历两倍总页数
            visit_count = 0
            while visit_count < max_page_visits:
                try:
                    wait = WebDriverWait(self.driver, 3)
                    element = wait.until(
                        EC.element_to_be_clickable((By.XPATH, f'//*[@text="{note_name}({n})"]'))
                    )
                    element.click()
                    return True
                except:
                    prev_page = current_page
                    self.method.click_slice(0.7, 0.5, 0.4, 0.5)
                    page_info = self.method.obtain_element_text(By.ID, "com.onyx:id/page_info")
                    current_page, total_pages = map(int, page_info.split('/'))
                    if current_page == prev_page:
                        return False
                    visit_count += 1
            logging.error(f"达到最大尝试次数，未找到笔记：'{note_name}({n})'")
            return False

    def get_file_note(self,note_name):
        time.sleep(1)
        page_info = self.method.obtain_element_text(By.ID, "com.onyx:id/textView_page_info")
        current_page, total_pages = map(int, page_info.split('/'))
        max_page_visits = total_pages * 2  # 设置最大尝试次数，这里假设最多遍历两倍总页数
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
                prev_page = current_page
                self.method.click_slice(0.7,0.5 , 0.4, 0.5)
                # logging.info(f"执行翻页")
                page_info = self.method.obtain_element_text(By.ID, "com.onyx:id/textView_page_info")
                current_page, total_pages = map(int, page_info.split('/'))
                if current_page == prev_page:
                    logging.info(f"翻页未成功")
                    return False
                visit_count += 1
        logging.error(f"达到最大尝试次数，未找到笔记：'{note_name}'")
        return False

    def test_render_time(self, note_test_initial):
        # 获取设备相关信息
        # from Note_Automation.conftest import get_device_info
        version_info = None
        device_info = get_device_info()
        if device_info:
            version_info = device_info.get('version_info')

        if version_info == "4.1":
            # 4.1版本渲染日志
            # logging.info(f"4.1 {version_info}")
            note_rendering_time = "render note page point count: "
            thumbnail_rendering = "render note page thumbnail: "

        else:
            # logging.info(f"4.0 {version_info}")
            # 4.0版本渲染日志
            note_rendering_time = "RxBaseAction: com.onyx.android.note.note.action.render.RenderToEditorViewAction"
            thumbnail_rendering = "RxBaseAction: com.onyx.android.note.note.action.render.RenderPageThumbnailAction"

        self.public.enter_storage()
        self.method.by_name_click(By.ID, "com.onyx:id/volume_name", "存储")
        self.public.get_file("笔记自动化测试文件", "固件迭代测试项")
        logging.info(f"--------------------测试场景：导入笔记------------------------")
        note_names = [
            "笔记测试物料（多笔迹）-用户提供",
            "笔记测试物料（钢笔）",
            "笔记测试物料（毛笔）",
            "笔记测试物料（马克笔）",
            "笔记测试物料（铅笔 纹理2）",
            "笔记测试物料（铅笔 纹理1）"
        ]
        for note_name in note_names:
            self.import_note_rendering_time(note_rendering_time, note_name)

        self.driver = driver
        driver.press_keycode(3)
        self.method.xpath_text_click("笔记")
        self.method.xpath_text_click("笔记测试物料")
        logging.info(f"--------------------测试场景：打开笔记------------------------")
        for note_name in note_names:
            self.open_note_rendering_time(note_rendering_time, note_name)

        logging.info(f"--------------------测试场景：笔记内翻页------------------------")
        for note_name in note_names:
            if version_info == "4.1":
                self.note_page_turning_rendering_time(note_rendering_time, note_name)
            else:
                note_rendering_time = "RxBaseAction: com.onyx.android.note.note.action.render.RefreshScreenAction"
                self.note_page_turning_rendering_time(note_rendering_time, note_name)

        logging.info(f"--------------------测试场景：缩略图加载------------------------")
        for note_name in note_names:
            self.note_thumbnail_rendering_time(thumbnail_rendering, note_name)

    def test_123(self):
        pass
        # s = get_device_info()
        #
        # print(f"获取的返回值{s}")