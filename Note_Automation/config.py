from appium import webdriver
from Note_Automation.Devices_list.Devices_list import device_list
import subprocess
import logging


def get_connected_device_ids():
    """获取已连接的设备ID列表"""
    try:
        result = subprocess.run(
            ['adb', 'devices'],
            capture_output=True,
            text=True,
            check=True
        )
        output = result.stdout.strip()
        lines = output.splitlines()
        device_ids = [line.split()[0] for line in lines[1:] if line.strip()]
        return device_ids if device_ids else None
    except Exception as e:
        logging.error(f"获取设备列表失败: {e}")
        return None


def get_android_version(device_id):
    """获取指定设备的Android版本"""
    try:
        version_result = subprocess.run(
            ['adb', '-s', device_id, 'shell', 'getprop', 'ro.build.version.release'],
            text=True, capture_output=True, check=True
        )
        return version_result.stdout.strip()
    except Exception as e:
        logging.error(f"获取Android版本失败: {e}")
        return "未知"


def get_device_fingerprint(device_id):
    """获取设备指纹信息，自动尝试多种方法"""
    fingerprint_commands = [
        ['adb', '-s', device_id, 'shell', 'getprop', 'ro.vendor.build.onyxfp'],
        ['adb', '-s', device_id, 'shell', 'getprop', 'ro.vendor.build.fingerprint'],
        ['adb', '-s', device_id, 'shell', 'getprop', 'ro.build.fingerprint']
    ]

    for cmd in fingerprint_commands:
        try:
            result = subprocess.run(
                cmd,
                text=True, capture_output=True, check=True
            )
            fingerprint = result.stdout.strip()
            if fingerprint:
                logging.info(f"使用命令 {' '.join(cmd)} 成功获取指纹")
                return fingerprint
        except Exception:
            continue

    logging.error(f"所有指纹获取方法均失败，设备ID: {device_id}")
    return None


def parse_fingerprint(fingerprint):
    """解析指纹信息"""
    try:
        parts = fingerprint.split(':')
        if len(parts) < 3:
            return None, None, None, None, None

        # 解析品牌/型号
        brand_model = parts[0].split('/')
        devices_name = brand_model[1] if len(brand_model) > 1 else "未知"

        # 解析构建信息
        build_info = parts[1].split('/')
        build_date_time = build_info[1] if len(build_info) > 1 else ""

        # 解析日期/版本信息
        date_parts = build_date_time.split('_')
        build_date = date_parts[0] if date_parts else "未知"
        version_info = date_parts[2] if len(date_parts) > 2 else "未知"

        # 解析构建类型
        build_type = parts[2].split('/')[0] if len(parts) > 2 else "未知"

        return devices_name, build_date, version_info, build_type
    except Exception as e:
        logging.error(f"解析指纹信息失败: {e}")
        return None, None, None, None


def get_device_resolution(device_id):
    """获取设备分辨率"""
    try:
        size_result = subprocess.run(
            ['adb', '-s', device_id, 'shell', 'wm', 'size'],
            capture_output=True,
            text=True,
            check=True
        )
        android_size = size_result.stdout.strip()
        return android_size.replace("Physical size:", "").strip()
    except Exception as e:
        logging.warning(f"获取设备分辨率失败: {e}")
        return "未知"


def match_device_info(devices_name):
    """在设备列表中匹配设备信息"""
    if devices_name is None:
        return None

    for name, (platform, region, reader, size, colour) in device_list.items():
        if name == devices_name:
            return {
                "device_name": name,
                "device_platform": platform,
                "device_region": region,
                "devices_reader": reader,
                "device_size": size,
                "driver_colour": colour
            }
    logging.info(f"设备型号 {devices_name} 未在设备列表中找到")
    return None


def get_device_info():
    """获取连接的Android设备信息"""
    # 获取设备ID列表
    device_ids = get_connected_device_ids()
    if not device_ids:
        logging.error("未检测到连接的设备")
        return None

    # 只处理第一个设备
    device_id = device_ids[0]

    # 获取Android版本
    android_version = get_android_version(device_id)

    # 获取设备指纹
    fingerprint = get_device_fingerprint(device_id)
    if not fingerprint:
        return None

    # 解析指纹信息
    devices_name, build_date, version_info, build_type = parse_fingerprint(fingerprint)

    # 匹配设备信息
    device_match = match_device_info(devices_name)
    if not device_match:
        return None

    # 获取设备分辨率
    resolution = get_device_resolution(device_id)

    # 构建设备信息字典
    return {
        **device_match,
        "android_version": android_version,
        "device_id": device_id,
        "build_date": build_date,
        "version_info": version_info,
        "build_type": build_type,
        "filtered_size": resolution
    }


device_info = get_device_info()
android_version = device_info.get('android_version')
device_name = device_info.get('device_name')

# 配置 Appium 驱动选项
try:
    desired_caps = {
        "platformName": "android",
        "platformVersion": android_version,
        "deviceName": device_name,
        # "appPackage": "com.onyx",
        # "appActivity": "com.onyx.tablet.main.ui.TabletMainActivity",
        # "noReset": False
        "automationName": "UiAutomator2",
        "newCommandTimeout": 600
    }
    driver = webdriver.Remote("http://localhost:4723/wd/hub", desired_caps)
    driver.implicitly_wait(10)

except (AssertionError, RuntimeError) as e:
    print(f"设备相关错误: {e}")
except Exception as e:
    print(f"未知错误: {e}")