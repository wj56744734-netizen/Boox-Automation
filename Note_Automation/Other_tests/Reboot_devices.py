import subprocess
import sys
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from appium import webdriver


class DeviceReboot:
    def __init__(self, stats_file="reboot_stats.json", appium_server='http://localhost:4723/wd/hub'):
        self.stats_file = stats_file
        self.appium_server = appium_server
        self.driver = None
        self.reboot_count = 0  # 记录重启次数

    def _init_driver(self):
        """初始化Appium驱动"""
        print("正在初始化Appium驱动...")
        desired_caps = {
            'platformName': 'Android',
            'deviceName': 'Android Device',
            'automationName': 'UiAutomator2',
            'newCommandTimeout': 300,  # 延长命令超时时间
            'noReset': True,  # 不重置应用状态
            'fullReset': False
        }
        try:
            self.driver = webdriver.Remote(self.appium_server, desired_caps)
            print("Appium驱动初始化成功")
            return True
        except Exception as e:
            print(f"Appium驱动初始化失败: {e}")
            self.driver = None
            return False

    def _close_driver(self):
        """关闭Appium驱动"""
        try:
            if self.driver:
                self.driver.quit()
                # print("Appium驱动已关闭")
        except Exception as e:
            print(f"关闭Appium驱动失败: {e}")
        finally:
            self.driver = None

    def execute_device_reboot(self):
        """设备重启主流程"""
        self.reboot_count += 1
        print(f"\n===== 开始第 {self.reboot_count} 次设备重启 =====")

        try:
            # 关闭现有驱动会话
            self._close_driver()

            # 执行ADB重启命令
            subprocess.run(
                ['adb', 'reboot'],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            print("设备重启命令已发送")

            # 等待设备离线
            self._wait_for_device_offline()

            # 等待设备重启完成
            self._wait_for_device_online()

            # 初始化Appium驱动
            if not self._init_driver():
                raise Exception("Appium驱动初始化失败")

            # 执行重启后操作（包含元素查找）
            if not self._post_reboot_operations():
                print(f"第 {self.reboot_count} 次重启后元素查找失败，程序终止")
                sys.exit(1)

            # print(f"===== 第 {self.reboot_count} 次重启成功=====")

        except subprocess.CalledProcessError as e:
            print(f"重启命令执行失败: {e.stderr}")
            sys.exit(1)
        except TimeoutError as e:
            print(f"等待设备超时: {str(e)}")
            sys.exit(1)
        except Exception as e:
            print(f"发生未知错误: {str(e)}")
            sys.exit(1)
        finally:
            # 确保关闭驱动
            self._close_driver()

    def _wait_for_device_offline(self):
        """等待设备离线（开始重启过程）"""
        print("等待设备离线...")
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                result = subprocess.run(
                    ['adb', 'get-state'],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                print(f"尝试 {attempt + 1}/{max_attempts}: 设备仍在线，状态: {result.stdout.strip()}")
                time.sleep(2)
            except subprocess.CalledProcessError:
                print("设备已离线，开始重启过程")
                return
        raise TimeoutError("等待设备离线超时")

    def _wait_for_device_online(self):
        """等待设备完全启动"""
        print("等待设备重启并可用...")
        max_attempts = 60
        for attempt in range(max_attempts):
            try:
                result = subprocess.run(
                    ['adb', 'shell', 'getprop', 'sys.boot_completed'],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if "1" in result.stdout:
                    print("设备已完全启动")
                    time.sleep(5)
                    return
                # print(f"尝试 {attempt + 1}/{max_attempts}: 设备未完全就绪")
            except subprocess.CalledProcessError:
                print(f"尝试 {attempt + 1}/{max_attempts}: 设备尚未就绪")
            time.sleep(3)
        raise TimeoutError("等待设备重启超时")

    def _post_reboot_operations(self):
        """设备重启后执行元素查找操作"""
        print("等待应用加载...")
        time.sleep(5)  # 延长应用加载时间

        try:
            note_element = WebDriverWait(self.driver, 60).until(
                EC.visibility_of_element_located((By.ID,'com.onyx:id/name'))
            )
            if note_element:
                print(f"===== 设备未白屏，继续测试 =====")

        except Exception as e:
                print(f"进入系统KCB桌面异常")
                subprocess.run(["adb", "screencap", "-p", "/Users/xiaoyu/Downloads/1.png"])
                subprocess.run(["adb", "logcat", "-d", ">", "/Users/xiaoyu/Downloads/log.txt"])
                return False

        try:
            # 防止monkey关闭usb调试
            time.sleep(3)
            usb = subprocess.run(["adb" , "shell" , "service" , "call" , "adb" , "16" , "i32" , "1"],check=True)

            if usb:
                monkey = subprocess.run(["adb" , "shell" , "monkey" , "-p" , "com.onyx" , "10000"],check=True)

                if monkey:
                    print(f"===== 第 {self.reboot_count} 次执行 monkey 成功 =====")
                    return True

        except Exception as e:
            print(f"monkey 命令执行失败")
            return True

if __name__ == "__main__":
    reboot_tool = DeviceReboot()

    try:
        while True:
            reboot_tool.execute_device_reboot()
    except KeyboardInterrupt:
        sys.exit(0)