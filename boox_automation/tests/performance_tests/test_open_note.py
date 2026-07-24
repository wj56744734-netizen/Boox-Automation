import sys
import os
import logging
import re

# 确保项目根目录在 sys.path 中（兼容直接 python 运行及 VS Code 等不以项目根为 cwd 的方式）
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pytest
from boox_automation.ui_ops.logcat import Logcat
from boox_automation.driver import driver
from boox_automation.ui_ops.actions import Operation_method
from boox_automation.tests.helpers import Public_method
from datetime import datetime

now = datetime.now()
formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")


class Testopennote:
    # 类级别标志，控制引导只执行一次
    _guide_shown = False
    # 新增：控制分享与导出引导只执行一次
    _share_export_guide_clicked = False

    def setup_method(self):
        self.driver = driver
        self.method = Operation_method(self.driver)
        self.public = Public_method()
        self.Logcat = Logcat()

    def test_open_note(self,note_perf_initial):
        """ 测试打开笔记  """

        logging.info(f"测试开始：{formatted_time}")

        opens = 0

        self.method.xpath_parent_click('//android.widget.TextView[@resource-id="com.onyx:id/title" and @text="笔记"]')

        while True:

            note_list = self.method.obtain_element_list_text(by_method='id',locator='com.onyx:id/title')

            for note_title in note_list:

                self.method.xpath_parent_click(f'//android.widget.TextView[@resource-id="com.onyx:id/title" and @text="{note_title}"]')
        
                note_page = self.method.xpath_parent_click('//android.widget.TextView[@resource-id="com.onyx.android.note:id/title"]',should_click=False).text

                note_page = re.sub(r'\s+', '', note_page)

                logging.debug(f"当前笔记页标题: {note_page}")

                page_0 = int(note_page.split("/")[0])

                page_1 = int(note_page.split("/")[1])

                logging.debug(f"当前笔记页数: {page_0}/{page_1}")

                if page_1 == 1 and page_1 == 1:
                    logging.error("笔记总页数为1，可能是笔记未正确加载或存在问题。")
                    logging.info(f"测试结束：{formatted_time}")
                    assert False
                else:
                    opens += 1
                    logging.debug("笔记总页数不为1，测试通过。")
                    assert True
                    self.method.xpath_parent_click('//android.widget.ImageView[@resource-id="com.onyx.android.note:id/back_icon"]')
                    logging.info(f"成功打开笔记 {opens} 次。")

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-s"] + sys.argv[1:]))