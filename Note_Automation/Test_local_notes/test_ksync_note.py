from selenium.webdriver.common.by import By
from Note_Automation.Note_class.Logcat import Logcat
from Note_Automation.Note_class.Note_class import Operation_method
from Note_Automation.config import driver
from Note_Automation.Test_local_notes.Public_method import Public_method, device_region
from Note_Automation.conftest import note_mark_china,note_mark_increment
import allure
import re
import logging


@allure.feature("笔记同步相关测试类")
class Test_ksync_note:

    def setup_method(self):
        self.driver = driver
        self.method = Operation_method(self.driver)
        self.public = Public_method()
        self.logcat = Logcat()

    @note_mark_china("同步各种格式的笔记")
    @note_mark_increment("增量")
    def test_10_ksync_onyx(self,note_test_initial):

        self.public.enter_note_app()

        self.public.more_menus('笔记设置','第三方账号管理')

        self.login_network_disk("WebDAV","webdav","webdavBoox")

        self.public.enter_note_app()

        self.method.xpath_text_click(element_key='笔记首页.无笔记状态创建按钮')

        self.public.create_handwritten_notes()

        if not self.ksync_note():
            logging.warning("默认格式同步日志未捕获")

        self.third_party_note_ksync('不可编辑PDF')

        if not self.ksync_note():
            logging.warning("不可编辑PDF格式同步日志未捕获")

        self.third_party_note_ksync('.note文件（BOOX笔记格式）')

        if not self.ksync_note():
            logging.warning(".note文件格式同步日志未捕获")

    def test_11_ksync_baidu(self):

        pass


    def login_network_disk(self,login,account,password):

        self.method.xpath_text_click(login)

        self.method.wait_input_box(By.ID, 'com.onyx.android.ksync:id/account', account)

        self.method.wait_input_box(By.ID, 'com.onyx.android.ksync:id/password', password)

        self.method.xpath_text_click(element_key='通用操作.确定按钮')

        self.method.xpath_text_click(element_key='笔记首页.同步弹窗开启导出笔记')

        self.method.xpath_text_click(element_key='通用操作.确定按钮')

        self.driver.press_keycode(3)

    def ksync_note(self):

        targets = [
            "WebDavUploadRequest webdav upload local file:",
            "save cloud note success",
            "RxBaseAction: com.onyx.android.sdk.cloudstorage.provider.webdav.action.WebDavSaveNoteAction",
            "RxBaseAction: com.onyx.android.sdk.cloudstorage.provider.webdav.action.WebDavUploadFileAction",
        ]

        sync_completed = self.logcat.capture_logcat(targets, single_timeout=80)

        if not sync_completed['success']:
            logging.error(f"未捕捉全所有日志: {sync_completed['message']}")
            logging.error(f"未捕捉到的目标: {sync_completed['unmatched_targets']}")
            return False

        detailed = sync_completed.get('detailed_matches', {})

        # === 解析上传文件信息 ===
        sync_details_log = detailed.get(targets[0], '')
        if sync_details_log:
            # 提取文件路径
            file_path_start = sync_details_log.find("/storage/")
            file_path_end = sync_details_log.find(" file size:")
            file_path = sync_details_log[file_path_start:file_path_end]

            # 提取WebDAV标识目录
            webdav_id_start = file_path.find("WEBDAV/") + len("WEBDAV/")
            webdav_id_end = file_path.find("/remote.php")
            webdav_identifier = file_path[webdav_id_start:webdav_id_end]

            # 提取远程文件结构
            remote_path_start = file_path.find("webdav/") + len("webdav/")
            remote_path_end = file_path.rfind("/") + 1
            remote_structure = file_path[remote_path_start:remote_path_end]

            # 提取文件名和格式
            file_name_full = file_path.split("/")[-1]
            file_name = file_name_full.rsplit(".", 1)[0]
            file_format = file_name_full.rsplit(".", 1)[1].upper()

            # 提取文件大小并转换
            size_start = sync_details_log.find("file size: ") + len("file size: ")
            size_end = sync_details_log.find(" --->")
            size_bytes = int(sync_details_log[size_start:size_end])
            size_kb = round(size_bytes / 1024, 2)

            # 输出结果
            logging.info(f"WebDAV 标识目录：{webdav_identifier}")
            logging.info(f"远程文件结构：{remote_structure}")
            logging.info(f"文件名：{file_name}")
            logging.info(f"文件格式：{file_format}")
            logging.info(f"文件大小：{size_bytes} 字节（约 {size_kb}KB)")

        # === 解析同步耗时 ===
        sync_save_line = detailed.get(targets[2], '')
        sync_upload_line = detailed.get(targets[3], '')

        save_match = re.search(r'(\d+)ms', sync_save_line) if sync_save_line else None
        upload_match = re.search(r'(\d+)ms', sync_upload_line) if sync_upload_line else None

        if upload_match:
            upload_time = upload_match.group(0)
        else:
            upload_time = None
            logging.info("未找到WebDAV上传文件耗时时间信息")

        if save_match:
            save_time = save_match.group(0)
        else:
            save_time = None
            logging.info("未找到WebDAV上传笔记耗时时间信息")

        logging.info(f"WebDAV上传文件耗时：{upload_time}")
        logging.info(f"WebDAV上传笔记耗时：{save_time}")
        logging.info(f"WebDAV上传成功\n")

        return True

    def third_party_note_ksync(self,file_format):

        self.public.more_menus('笔记设置', '导出格式')

        self.method.xpath_text_click(f'{file_format}')

        self.method.xpath_text_click(element_key='通用操作.确定按钮')

        self.method.xpath_text_click(element_key='笔记首页.更多-笔记设置')

        self.method.xpath_text_click('创建')

        self.public.create_handwritten_notes()
