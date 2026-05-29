import logging
import re
import subprocess
import time
import os
from Note_Automation.Devices_list.Devices_list import device_list

_CACHED_DEVICE_ID = None
_Fingerprint_information = None
_Version_Information = None

class Device_basic_information:

    def get_connected_device_ids(self):
        """获取已连接的设备ID，仅第一次实际执行，后续返回缓存值"""

        global _CACHED_DEVICE_ID

        if _CACHED_DEVICE_ID is not None:

            return _CACHED_DEVICE_ID

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
            if not device_ids:
                raise RuntimeError("未连接任何设备")

            # 支持外部显式指定设备ID（用于多进程/子进程保持同一设备）
            expected_device_id = os.getenv("NOTE_DEVICE_ID", "").strip()
            if expected_device_id:
                if expected_device_id in device_ids:
                    _CACHED_DEVICE_ID = expected_device_id
                    logging.info(f"使用环境变量指定设备ID: {_CACHED_DEVICE_ID}")
                    return _CACHED_DEVICE_ID
                raise RuntimeError(f"环境变量 NOTE_DEVICE_ID={expected_device_id} 未在当前连接设备中")

            # 多设备场景取第一个设备
            if len(device_ids) >= 2:
                device_id = device_ids[0]
                model_result = subprocess.run(
                    ['adb', '-s', device_id, 'shell', 'getprop', 'ro.product.model'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                model = model_result.stdout.strip()
                logging.info(f'多设备连接，默认使用设备：{model}（ID: {device_id}）')
            # 缓存设备ID到模块变量
            _CACHED_DEVICE_ID = device_ids[0]
            logging.info(f"模块缓存设备ID: {_CACHED_DEVICE_ID}")
            return _CACHED_DEVICE_ID
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"获取设备ID失败: {e}") from None

    def get_android_version(self,device_id):
        """"" 获取指定设备的Android版本 """""

        global _Version_Information

        if _Version_Information is not None:

            return _Version_Information

        try:
            version_result = subprocess.run(
                ['adb', '-s', device_id, 'shell', 'getprop', 'ro.build.version.release'],
                text=True, capture_output=True, check=True
            )
            _Version_Information = version_result.stdout.strip()
            logging.debug(f"当前模块安卓版本: {_Version_Information}")
            return _Version_Information
        except Exception as e:
            logging.error(f"获取Android版本失败: {e}")
            return "未知"

    def get_device_fingerprint(self,device_id):
        """"" 获取设备指纹信息 """""

        global _Fingerprint_information

        if _Fingerprint_information is not None:

            return _Fingerprint_information

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
                    logging.debug(f"使用命令 {' '.join(cmd)} 成功获取指纹")
                    _Fingerprint_information = fingerprint
                    return _Fingerprint_information
            except Exception:
                continue

        logging.error(f"所有指纹获取方法均失败，设备ID: {device_id}")
        return None

    def get_wifi(self, device_id):
        """检查并显示Wi-Fi连接状态"""
        try:
            result = subprocess.run(
                ['adb', '-s', device_id, 'shell', 'dumpsys', 'connectivity'],
                capture_output=True,
                text=True
            )
            output = result.stdout

            # 核心修复：调整正则终止符（Score\{ → Requests:），保留新旧格式匹配逻辑
            wifi_info = re.search(
                r'NetworkAgentInfo\{.*?ni\{(?:\[type: WIFI.*?state: CONNECTED/CONNECTED.*?\]|WIFI CONNECTED.*?)\}(.*?)Requests:',
                output,
                re.DOTALL
            )
            if not wifi_info:
                logging.info("Wi-Fi状态: 未连接 ")
                # ========== 原逻辑完全保留 ==========
                logging.error("请连接Wi-Fi后再开始测试！！！")
                raise RuntimeError("Wi-Fi未连接，无法继续测试")

            # 保留原变量名transport_info，原逻辑完全不变
            transport_info = wifi_info.group(1)

            # 原匹配逻辑完全保留，未做任何修改
            ssid_match = re.search(r'SSID: "([^,]+)"', transport_info)  # 仅调整SSID匹配规则
            ssid = ssid_match.group(1).strip() if ssid_match else "未知"

            ip_match = re.search(r'LinkAddresses: .*?(\d+\.\d+\.\d+\.\d+)', transport_info)  # 仅调整IP匹配规则
            ip = ip_match.group(1).strip() if ip_match else "未分配"

            rssi_match = re.search(r'SignalStrength: (-?\d+)', transport_info)  # 仅调整RSSI匹配规则
            rssi = rssi_match.group(1).strip() if rssi_match else "未知"

            link_speed_match = re.search(r'Link speed: (\d+Mbps)', transport_info)
            link_speed = link_speed_match.group(1).strip() if link_speed_match else "未知"

            logging.info("Wi-Fi状态: 已连接")
            logging.info(f"  SSID: {ssid}")
            logging.info(f"  IP地址: {ip}")
            logging.info(f"  信号强度: {rssi} dBm")
            logging.info(f"  连接速度: {link_speed}")

            if rssi != "未知":
                rssi_value = int(rssi)
                if rssi_value >= -50:
                    quality = "优秀"
                elif rssi_value >= -70:
                    quality = "良好"
                else:
                    quality = "一般"
                logging.info(f"Wi-Fi信号质量: {quality}")

            return {
                "connected": True,
                "ssid": ssid,
                "ip": ip,
                "rssi": rssi,
                "link_speed": link_speed
            }

        except Exception as e:
            logging.error(f"检查Wi-Fi状态时出错: {e}")
            return {"connected": False}

    def get_device_memory_info(self,device_id):
        """"" 获取设备内存信息 """""
        result = subprocess.run(
            ['adb', '-s' , device_id , 'shell', 'cat /proc/meminfo'],
            capture_output=True,
            text=True
        )
        output = result.stdout

        mem_total = re.search(r'MemTotal:\s+(\d+)', output).group(1) if re.search(r'MemTotal:\s+(\d+)', output) else "未知"
        mem_free = re.search(r'MemFree:\s+(\d+)', output).group(1) if re.search(r'MemFree:\s+(\d+)', output) else "未知"
        mem_available = re.search(r'MemAvailable:\s+(\d+)', output).group(1) if re.search(r'MemAvailable:\s+(\d+)',
                                                                                          output) else "未知"

        mem_total_mb = round(int(mem_total) / (1024 * 1024), 2) if mem_total else 0
        mem_free_mb = round(int(mem_free) / (1024 * 1024), 2) if mem_free != "未知" else "未知"
        mem_available_mb = round(int(mem_available) / (1024 * 1024), 2) if mem_available != "未知" else "未知"

        logging.info(f"  总内存: {mem_total_mb}GB")
        logging.info(f"  空闲内存: {mem_free_mb}GB")
        logging.info(f"  可用内存: {mem_available_mb}GB")

        return {"total": f"{mem_total_mb} MB", "free": f"{mem_free_mb} MB", "available": f"{mem_available_mb} MB"}

    def get_device_storage_info(self,device_id):
        """"" 获取设备存储信息 """""
        result = subprocess.run(
            ['adb', '-s' , device_id , 'shell', 'df -h /sdcard'],
            capture_output=True,
            text=True
        )
        output = result.stdout

        if len(output.strip().split('\n')) > 1:
            parts = output.strip().split('\n')[1].split()
            total, used, available, percent = parts[1], parts[2], parts[3], parts[4]
            logging.info(f"  总容量: {total}B")
            logging.info(f"  已使用: {used}B ({percent})")
            logging.info(f"  可用空间: {available}B")
            return {"total": total, "used": used, "available": available, "percent_used": percent}
        logging.error("无法获取存储信息")
        return {"error": "无法获取存储信息"}

    def get_device_resolution(self,device_id):
        """"" 获取设备分辨率 """""
        try:
            size_result = subprocess.run(
                ['adb', '-s', device_id , 'shell', 'wm', 'size'],
                capture_output=True,
                text=True,
                check=True
            )
            android_size = size_result.stdout.strip()
            return android_size.replace("Physical size:", "").strip()
        except Exception as e:
            logging.warning(f"获取设备分辨率失败: {e}")
            return "未知"

    def parse_fingerprint(self,fingerprint):
        """"" 解析指纹信息 """""
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

            return devices_name, build_date, version_info, build_type, build_date_time
        except Exception as e:
            logging.error(f"解析指纹信息失败: {e}")
            return None, None, None, None

    def match_device_info(self,devices_name):
        """"" 在设备列表中匹配设备信息 """""
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

    def get_device_info(self):

        """"" 获取连接的Android设备信息 """""
        device_id = self.get_connected_device_ids()

        """"" 获取Android版本 """""
        android_version = self.get_android_version(device_id)

        """"" 获取设备指纹 """""
        fingerprint = self.get_device_fingerprint(device_id)
        if not fingerprint:
            return None

        """"" 解析指纹信息 """""
        devices_name, build_date, version_info, build_type , build_date_time = self.parse_fingerprint(fingerprint)

        # 匹配设备信息
        device_match = self.match_device_info(devices_name)
        if not device_match:
            return None

        """"" 获取设备分辨率 """""
        resolution = self.get_device_resolution(device_id)

        # 构建设备信息字典
        return {
            **device_match,
            "android_version": android_version,
            "device_id": device_id,
            "build_date": build_date,
            "version_info": version_info,
            "build_type": build_type,
            "filtered_size": resolution,
            "build_date_time":build_date_time
        }

    def basic_device_information(self,device_id):
        """打印设备基础信息"""
        device_info = self.get_device_info()
        if device_info:
            logging.info("===== 设备基础信息 =====")
            logging.info(f"设备型号：{device_info.get('device_name')}")
            logging.info(f"设备平台：{device_info.get('device_platform')}")
            logging.info(f"设备区域：{device_info.get('device_region')}")
            logging.info(f"设备类型：{device_info.get('devices_reader')}")
            logging.info(f"设备尺寸：{device_info.get('device_size')}寸")
            logging.info(f"设备显示：{device_info.get('driver_colour')}")
            logging.info(f"设备分辨率：{device_info.get('filtered_size')}")
            logging.info(f"版本信息：{device_info.get('version_info')}")
            logging.info(f"构建类型：{device_info.get('build_type')}")
            logging.info(f"系统版本信息：{device_info.get('build_date_time')}")
            logging.info(f"设备ID：{device_info.get('device_id')}")

            logging.info(" ===== 系统信息 ===== ")
            time.sleep(3) #部分情况下设备刚唤醒连接WiFi需要时间
            logging.info(f"【网络状态】")
            self.get_wifi(device_id)

            # 记录内存和存储信息
            logging.info(f"【内存信息】")
            self.get_device_memory_info(device_id)
            logging.info(f"【存储信息】")
            self.get_device_storage_info(device_id)