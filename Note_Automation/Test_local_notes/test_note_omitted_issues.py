import logging
import os
import time
from selenium.webdriver.common.by import By
from Note_Automation.Note_class.Note_class import Operation_method
from Note_Automation.config import driver
from Note_Automation.Test_local_notes.Public_method import Public_method
# from Note_Automation.Other_tests.Test_Stress.Test_from_local_files import Test_from_local_files


class Test_note_omitted_issues:

    def setup_method(self):

        self.method = Operation_method(driver)
        self.public = Public_method()
        self.driver = driver
        # self.Test_from_local_files = Test_from_local_files()
        # self.test = test

    def test_note_pdf_link_jump_to(self,note_test_initial):
        self.method.xpath_text_click("笔记")
        self.method.xpath_text_click("创建笔记")
        self.method.by_name_click(By.ID, "com.onyx:id/title", "从本地文件")
        self.public.import_file_bootstrap("笔记首页.从本地文件导入引导", "笔记首页.从本地文件导入引导确认")
        self.public.get_file("笔记自动化测试文件","pdf内链")
        file_names = []
        element = self.driver.find_elements(By.ID, "com.onyx.android.note:id/title")
        index = 0
        while index < len(element):
            element = self.driver.find_elements(By.ID, "com.onyx.android.note:id/title")
            file_element = element[index].text
            file_name = self.public.take_file(file_element)
            file_names.append(file_name)
            index += 1
        self.method.wait_for_screen_size(0.7,0.4)
        time.sleep(1)
        self.method.by_index_click(By.CLASS_NAME,"android.widget.ImageView",2)
        time.sleep(5)

    def test_note_123(self,note_test_initial):
        self.method.xpath_text_click("笔记")
        self.method.xpath_text_click("创建笔记")
        self.public.create_handwritten_notes()
        self.method.xpath_text_click("笔记-1")
        n = 0
        while True:
            time.sleep(2)
            page = self.method.obtain_element_text(By.ID, "com.onyx.android.note:id/title")
            page = page.split("/")
            page_1 = page[0]
            page_2 = page[1]
            logging.info(f"当前页：{page_1},总页数：{page_2}")
            os.popen(
                "adb shell am broadcast -a com.onyx.android.note.test.add_custom_shape --ei test_shape_type_index 1 --es test_shape_pressure 0,500#10 --ei test_shape_line_style_index 3 --ei test_shape_stroke_width 10 --ei test_shape_color_index 6 --ei test_shape_count 3 --es test_shape_start_end_point 100,100,1000,100#100,200,1000,200 --ez test_shape_draw_line_path false")
            n += 1
            logging.info(f"生成笔画数据第{n}次")
            activity_before_click = self.driver.current_activity
            driver.press_keycode(3)
            time.sleep(1)
            self.method.xpath_text_click("笔记-1")
            time.sleep(1)
            while True:
                page = self.method.obtain_element_text(By.ID, "com.onyx.android.note:id/title")
                page = page.split("/")
                page_1 = page[0]
                logging.info(f"更新后当前页：{page_1}")
                if page_1 == page_2:
                    break
                if page_1 >= page_2:
                    self.method.wait_for_screen_size(71, 1831)
            time.sleep(3)
            activity_after_click = self.driver.current_activity
            if activity_before_click != activity_after_click:
                logging.info(f"笔记数据未保存")
                break
            self.method.wait_for_screen_size(1831, 71)
