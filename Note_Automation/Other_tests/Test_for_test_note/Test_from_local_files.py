import logging
import os
import time
from selenium.webdriver.common.by import By
from Note_Automation.Note_Class.Note_class import Operation_method
from Note_Automation.config import driver
from Note_Automation.Test_local_notes.Public_method import Public_method

class Test_from_local_files:

    def setup_method(self):

        self.method = Operation_method(driver)
        self.public = Public_method()
        self.driver = driver

    def test_from_local_files(self,note_test_initial):

        self.method.xpath_text_click("笔记")

        self.method.xpath_text_click("创建笔记")

        self.method.by_name_click(By.ID, "com.onyx:id/title", "从本地文件")

        self.public.import_file_bootstrap("选择文件即可创建笔记", "知道了")

        while True:

            self.import_file("笔记自动化测试文件","测试书籍")

            self.method.xpath_text_click("存储/笔记自动化测试…/测试书籍")

            self.method.xpath_text_click("存储/笔记自动化测试…")


    def test_create_notes_page(self,note_test_initial):

        page = 1000

        note = 0

        self.method.xpath_text_click("笔记")

        self.method.xpath_text_click("创建笔记")

        while note <= page:

            page_note = 0

            self.method.xpath_text_click("手写笔记")

            self.method.xpath_text_click("创建")

            while page_note <= page:

                time.sleep(2)

                os.popen("adb shell am broadcast -a com.onyx.android.note.test.add_custom_shape --ei test_shape_type_index 1 --es test_shape_pressure 0,500#10 --ei test_shape_line_style_index 3 --ei test_shape_stroke_width 10 --ei test_shape_color_index 6 --ei test_shape_count 3 --es test_shape_start_end_point 100,100,1000,100#100,200,1000,200 --ez test_shape_draw_line_path false")

                self.method.by_index_click(By.CLASS_NAME,"android.widget.ImageView",9)

                # self.method.by_element_click(By.ID,"com.onyx.android.note:id/title")

                page_note += 1

            self.method.by_element_click(By.ID, "com.onyx.android.note:id/back_icon")

            self.method.by_element_click(By.ID, "com.onyx:id/create_icon")

            note += 1

    def import_file(self, file_route_name, file_route_name2):

        self.public.get_file(file_route_name, file_route_name2)

        self.import_files_list()

    def import_files_list(self):

        page = 0

        while True:

            page += 1

            logging.info(f"Test:{page}")

            self.circular_swipe(page)

            element = self.driver.find_elements(By.ID, "com.onyx.android.note:id/title")

            page_list = self.method.obtain_element_text(By.ID, "com.onyx.android.note:id/page_info")

            page_list = page_list.split("/")

            file_page = int(page_list[1])

            file_page0 = int(page_list[0])

            # 获取当前文件数量
            file_lists = len(element)

            # 当前列表没有文件退出测试
            if file_lists == 0:
                return False

            # 打印当前列表数 和 文件数
            logging.info(f"当前列表 {page} , {file_lists} 个测试文档")

            self.file_list(element,page)

            if file_lists < 20:
                return False

            if page > file_page:
                return False

    def circular_swipe(self, swipe):

        while True:

            page = self.method.obtain_element_text(By.ID,"com.onyx.android.note:id/page_info")

            page = page.split("/")

            file_page = int(page[0])

            file_page1 = int(page[1])

            if swipe == file_page:
                break

            if swipe > file_page:
                # 往前滑动
                self.method.click_slice(0.8, 0.5, 0.2, 0.5)

            if swipe < file_page:
                # 往后滑动
                self.method.click_slice(0.2, 0.5,0.8 , 0.5)

            if swipe > file_page1:
                return False

    def file_list(self, element , page):

        # 预设空列表
        file_names = []

        # 预设下标值
        index = 0

        # 循环列表
        while index < len(element):

            # 更新元素列表避免元素失效
            element = self.driver.find_elements(By.ID, "com.onyx.android.note:id/title")

            # 获取指定文件
            file_element = element[index].text

            # 执行导入文件
            file_name = self.take_file(file_element)

            # 导入完成后 退出笔记-点击创建-创建二级点击从本地文件导入
            self.import_bake()

            # 检查当前列表是否正确
            self.circular_swipe(page)

            file_names.append(file_name)

            index += 1

        page += 1

        return file_names

    def take_file(self,file_name):

        self.public.get_file(file_name)

        # 查找最后一个小数点的位置
        last_dot = file_name.rfind('.')

        file_name1 = ""  # 小数点前的部分
        file_name2 = ""  # 小数点后的部分

        if last_dot != -1:
            # 存在小数点时分割
            file_name1 = file_name[:last_dot]
            file_name2 = file_name[last_dot + 1:]

        else:
            # 不存在小数点时的处理
            file_name1 = file_name  # 整个文件名作为前缀部分

        # 半小时为导出异常
        self.method.by_take_pop("确认", f"类型:【{file_name2}】, 文档名称:【{file_name1}】, 导入耗时: ",1800)

        return file_name1

    def import_bake(self):
        self.method.by_element_click(By.ID, 'com.onyx.android.note:id/back_icon')

        self.method.by_element_click(By.ID, 'com.onyx:id/create_icon')

        self.method.xpath_text_click("从本地文件")

    def import_file_bootstrap(self , guide_name , guide_ok):

        self.method.by_name_click(By.ID, "com.onyx.android.note:id/tv_sub_title", guide_name,None)

        self.method.by_name_click(By.ID, "com.onyx.android.note:id/btn_ensure", guide_ok,None)

        self.method.xpath_text_click(guide_ok)

