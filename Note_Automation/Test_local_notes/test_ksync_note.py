from selenium.webdriver.common.by import By
from Note_Automation.Note_Class.Logcat import Logcat
from Note_Automation.Note_Class.Note_class import Operation_method
from Note_Automation.Test_local_notes.Public_method import Public_method
from Note_Automation.config import driver
from Note_Automation.conftest import note_mark_china,note_mark_increment
from Note_Automation.Devices_list.Device_basic_information import Device_basic_information
import allure
import re
import logging



#获取设备基础信息
devices = Device_basic_information()
device_info = devices.get_device_info()
if device_info:
    device_region = device_info.get('device_region')

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

        self.method.xpath_text_click('笔记')

        self.public.more_menus('笔记设置','第三方账号管理')

        self.login_network_disk("WebDAV","webdav","webdavBoox")

        self.method.xpath_text_click('笔记')

        self.method.xpath_text_click('创建笔记')

        self.public.create_handwritten_notes()

        self.ksync_note()

        self.third_party_note_ksync('位图PDF')

        self.ksync_note()

        self.third_party_note_ksync('.note文件（BOOX笔记格式）')

        self.ksync_note()

    def test_11_ksync_baidu(self):

        pass


    def login_network_disk(self,login,account,password):

        self.method.xpath_text_click(login)

        self.method.wait_input_box(By.ID, 'com.onyx.android.ksync:id/account', account)

        self.method.wait_input_box(By.ID, 'com.onyx.android.ksync:id/password', password)

        self.method.xpath_text_click('确定')

        self.method.xpath_text_click('启用笔记-导出功能')

        self.method.xpath_text_click('确定')

        self.driver.press_keycode(3)

    def ksync_note(self):

        sync_details = "WebDavUploadRequest webdav upload local file:"

        sync_completed = self.logcat.capture_logcat([sync_details])

        if sync_completed['success']:

            sync_details_log = sync_completed['detailed_matches']

            sync_details_log = sync_details_log.get(f'{sync_details}','')

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
            remote_path_end = file_path.rfind("/") + 1  # 包含最后的斜杠
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

            # 提取操作耗时并转换
            time_start = sync_details_log.find("---> ") + len("---> ")
            time_ms = int(sync_details_log[time_start:-2])  # 去除最后的'ms'
            time_sec = round(time_ms / 1000, 2)

            # 输出结果
            logging.info(f"WebDAV 标识目录：{webdav_identifier}")
            logging.info(f"远程文件结构：{remote_structure}")
            logging.info(f"文件名：{file_name}")
            logging.info(f"文件格式：{file_format}")
            logging.info(f"文件大小：{size_bytes} 字节（约 {size_kb}KB)")
            # logging.info(f"操作耗时：{time_ms} 毫秒（约 {time_sec} 秒）")

        else:

            logging.error(f"未捕捉全所有日志: {sync_completed['message']}")
            logging.error(f"未捕捉到的目标: {sync_completed['unmatched_targets']}")

        sync_success_log = "save cloud note success"
        sync_save_note_action_log = "RxBaseAction: com.onyx.android.sdk.cloudstorage.provider.webdav.action.WebDavSaveNoteAction"
        sync_upload_file_action_log = "RxBaseAction: com.onyx.android.sdk.cloudstorage.provider.webdav.action.WebDavUploadFileAction"

        sync_completed = self.logcat.capture_logcat([f"{sync_success_log}",f"{sync_save_note_action_log}",f"{sync_upload_file_action_log}"])

        if sync_completed['success']:

            sync = sync_completed['detailed_matches']

            sync_success  = sync.get(f"{sync_success_log}","")
            sync_save_note_action = sync.get(f"{sync_save_note_action_log}","")
            sync_upload_file_action = sync.get(f"{sync_upload_file_action_log}","")

            sync_save_note_action = re.search(r'(\d+)ms', sync_save_note_action)
            sync_upload_file_action = re.search(r'(\d+)ms', sync_upload_file_action)

            if sync_upload_file_action:
                sync_upload_file_action = sync_upload_file_action.group(0)
            else:
                sync_upload_file_action = None
                logging.info("未找到WebDAV上传文件耗时时间信息")

            if sync_save_note_action:
                sync_save_note_action = sync_save_note_action.group(0)
            else:
                sync_save_note_action = None
                logging.info("未找到WebDAV上传笔记耗时时间信息")

            logging.info(f"WebDAV上传文件耗时：{sync_upload_file_action}")
            logging.info(f"WebDAV上传笔记耗时：{sync_save_note_action}")
            logging.info(f"WebDAV上传成功\n")

        else:

            logging.error(f"未捕捉全所有日志: {sync_completed['message']}")
            logging.error(f"未捕捉到的目标: {sync_completed['unmatched_targets']}")


    def third_party_note_ksync(self,file_format):

        self.public.more_menus('笔记设置', '导出格式')

        self.method.xpath_text_click(f'{file_format}')

        self.method.xpath_text_click('确定')

        self.method.xpath_text_click('笔记设置')

        self.method.xpath_text_click('创建')

        self.public.create_handwritten_notes()