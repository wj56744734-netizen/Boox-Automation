import logging
import subprocess
import os

from appium import webdriver
from boox_automation.devices.device_info import Device_basic_information
from boox_automation.core.health import ensure_appium_server
from appium.options.android import UiAutomator2Options

class DriverProxy:
    """
    代理层：保证全项目通过 `from driver import driver` 得到同一对象引用，
    底层 real driver 可在断连后热切换，避免导入绑定失效。
    """

    def __init__(self):
        self._driver = None

    def set_driver(self, real_driver):
        self._driver = real_driver

    def get_driver(self):
        return self._driver

    def clear_driver(self):
        self._driver = None

    def __bool__(self):
        return self._driver is not None

    def __getattr__(self, item):
        if self._driver is None:
            raise RuntimeError("Driver 尚未初始化，请先调用 init_driver()")
        return getattr(self._driver, item)


driver = DriverProxy()


def _compact_error_text(error_text):
    """压缩第三方异常文本，避免日志被超长堆栈淹没。"""
    if not error_text:
        return ""
    compact = str(error_text).split("Stacktrace:")[0].strip()
    compact = compact.replace("\n", " ").strip()
    return compact


def _friendly_driver_error(error_text):
    compact = _compact_error_text(error_text)
    lowered = compact.lower()

    # 设备不在线
    if "device" in lowered and "not found" in lowered:
        return f"设备不在线：{compact}"

    # Driver session 失效
    if "could not retrieve the currently focused package" in lowered:
        return f"Driver session 失效（无法获取当前包名），原错误：{compact}"

    # Appium 服务端错误
    if "an unknown server-side error occurred" in lowered:
        return f"Appium 服务端错误：{compact}"

    # 连接层错误
    if "connection refused" in lowered or "max retries exceeded" in lowered:
        return "Appium 未连接或不可用（已尝试自动连接），请确认 Appium Server 正常后再运行测试。"

    # session 异常
    if any(kw in lowered for kw in (
        "could not proxy command", "socket hang up",
        "the session identified by", "nosuchdriverexception",
        "cannot be proxied to uiautomator2 server",
        "instrumentation process is not running",
    )):
        return "Appium 未连接或会话异常（已尝试自动连接），请先连接 Appium 后再开始测试。"

    # 自动化通道未连接
    if "uiautomation not connected" in lowered:
        return (
            "Driver 初始化失败：设备自动化通道未连接（UiAutomation not connected）。"
            "请重启目标设备的开发者选项/USB调试或重启 Appium 后重试。"
        )

    return f"Driver 初始化失败：{compact or error_text}"


def _build_driver_options():
    devices = Device_basic_information()
    device_info = devices.get_device_info()

    if device_info is None:
        device_id = devices.get_connected_device_ids()
        result = subprocess.run(
            ["adb", "-s", device_id, "shell", "getprop", "ro.product.model"],
            capture_output=True,
            text=True
        )
        raise ValueError(f"设备信息【 {result.stdout.strip()} 】获取结果为空，请检查devices/registry.py 文件是否包含设备信息")

    if not all(key in device_info for key in ['android_version', 'device_name', 'device_id']):
        raise ValueError("未能正确获取设备信息，请检查 devices/device_info 模块")

    from boox_automation.core.config import appium_capabilities

    caps = appium_capabilities()
    options = UiAutomator2Options()
    options.load_capabilities({
        "platformName": caps.get("platformName", "Android"),
        "deviceName": device_info['device_name'],
        "udid": device_info['device_id'],
        "automationName": caps.get("automationName", "UiAutomator2"),
        "newCommandTimeout": caps.get("newCommandTimeout", 3600),
        "adbExecTimeout": caps.get("adbExecTimeout", 120000),
        "settings[enforceXPath1]": True,
    })
    return options


def init_driver():
    """初始化并绑定真实 driver 到代理层，失败时抛出 RuntimeError。"""
    try:
        from boox_automation.core.config import appium_host, appium_port

        ensure_appium_server(auto_start=True)
        options = _build_driver_options()
        server_url = os.getenv(
            "APPIUM_SERVER_URL",
            f"http://{appium_host()}:{appium_port()}"
        )
        real_driver = webdriver.Remote(command_executor=server_url, options=options)
        driver.set_driver(real_driver)
        logging.info("Driver初始化成功")
        return real_driver
    except Exception as e:
        friendly_msg = _friendly_driver_error(str(e))
        logging.error(friendly_msg)
        raise RuntimeError(friendly_msg) from e


def ensure_driver_alive(reason=None):
    """探活 driver；session 失效时自动重建，设备不在线时抛错。"""
    real_driver = driver.get_driver()
    try:
        if real_driver is None:
            real_driver = init_driver()
        # 触发多次轻量请求验证会话可用性（覆盖 UiAutomator2 掉线场景）
        _ = real_driver.current_package
        _ = real_driver.current_activity
        _ = real_driver.get_window_size()
        return real_driver
    except Exception as e:
        friendly_msg = _friendly_driver_error(str(e))
        detail = f"{friendly_msg}（reason={reason}）" if reason else friendly_msg
        logging.warning(f"Driver 探活失败，尝试重建 session：{detail}")
        # 尝试清理旧 session 并重建
        try:
            if real_driver is not None:
                try:
                    real_driver.quit()
                except Exception:
                    pass
                driver.clear_driver()
            real_driver = init_driver()
            _ = real_driver.current_package
            _ = real_driver.current_activity
            _ = real_driver.get_window_size()
            logging.info(f"Driver session 重建成功（reason={reason}）")
            return real_driver
        except Exception as rebuild_error:
            rebuild_msg = _friendly_driver_error(str(rebuild_error))
            logging.error(f"Driver session 重建失败：{rebuild_msg}")
            raise RuntimeError(rebuild_msg) from None

