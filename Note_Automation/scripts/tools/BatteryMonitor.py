import subprocess
import time
import datetime
import csv
import os
from Note_Automation.Devices_list.Device_basic_information import Device_basic_information


class BatteryMonitor:
    def __init__(self, interval=300, log_file="battery_log.csv"):
        """
        初始化电池监控器
        :param interval: 监控间隔时间(秒)
        :param log_file: 日志文件路径
        """
        self.interval = interval
        self.log_file = log_file
        self.original_battery_state = None  # 用于保存原始电池状态
        self.device_id = Device_basic_information().get_connected_device_ids()
        self.initialize_log()

    def initialize_log(self):
        """初始化日志文件，添加表头（如果文件不存在）"""
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["时间", "电量(%)", "充电状态", "健康状态", "电压(mV)", "温度(°C)", "充电禁用状态"])

    def run_adb_command(self, command):
        """执行ADB命令并返回结果"""
        if command and command[0] == "adb" and "-s" not in command:
            command = ["adb", "-s", self.device_id] + command[1:]
        try:
            result = subprocess.check_output(
                command,
                stderr=subprocess.STDOUT,
                text=True
            )
            return result.strip()
        except subprocess.CalledProcessError as e:
            print(f"ADB命令失败: {' '.join(command)}，错误: {e.output.strip()}")
            return None
        except Exception as e:
            print(f"执行命令出错: {' '.join(command)}，错误: {str(e)}")
            return None

    def disable_charging(self):
        """尝试多种方法禁用设备充电功能"""
        # 保存当前电池状态
        self.original_battery_state = self.run_adb_command(["adb", "shell", "dumpsys", "battery"])

        # 方法1: 使用标准unplug命令
        print("尝试方法1: 标准充电禁用命令...")
        self.run_adb_command(["adb", "shell", "dumpsys", "battery", "unplug"])
        time.sleep(3)  # 等待系统响应
        if self.is_charging_disabled():
            return True

        # 方法2: 直接设置充电状态为未充电
        print("尝试方法2: 直接设置未充电状态...")
        self.run_adb_command(["adb", "shell", "dumpsys", "battery", "set", "status", "4"])
        time.sleep(3)
        if self.is_charging_disabled():
            return True

        # 方法3: 禁用USB充电（需要root）
        print("尝试方法3: 禁用USB充电（可能需要root）...")
        self.run_adb_command(["adb", "shell", "settings", "put", "global", "usb_charging_disabled", "1"])
        time.sleep(3)
        if self.is_charging_disabled():
            return True

        # 方法4: 重置电池状态后再禁用
        print("尝试方法4: 重置电池状态后再禁用...")
        self.run_adb_command(["adb", "shell", "dumpsys", "battery", "reset"])
        time.sleep(2)
        self.run_adb_command(["adb", "shell", "dumpsys", "battery", "unplug"])
        time.sleep(3)
        if self.is_charging_disabled():
            return True

        print("所有方法都尝试过，仍无法禁用充电")
        return False

    def is_charging_disabled(self):
        """检查充电是否已成功禁用"""
        battery_data = self.get_battery_info()
        if not battery_data:
            return False

        status = battery_data.get("status", "")
        is_disabled = status in ["未充电", "4"]
        print(f"当前充电状态: {status}，禁用状态: {'成功' if is_disabled else '失败'}")
        return is_disabled

    def restore_charging(self):
        """恢复设备原始充电状态"""
        print("开始恢复充电功能...")

        # 方法1: 使用reset命令
        self.run_adb_command(["adb", "shell", "dumpsys", "battery", "reset"])

        # 方法2: 启用USB充电（如果之前禁用过）
        self.run_adb_command(["adb", "shell", "settings", "put", "global", "usb_charging_disabled", "0"])

        # 等待系统响应
        time.sleep(3)

        # 验证充电状态
        battery_data = self.get_battery_info()
        status = battery_data.get("status", "") if battery_data else "未知"
        print(f"充电功能恢复后状态: {status}")

    def get_battery_info(self):
        """获取电池信息"""
        try:
            # 执行ADB命令获取电池信息
            result = self.run_adb_command(["adb", "shell", "dumpsys", "battery"])
            if not result:
                return None

            # 解析电池信息
            battery_data = {}
            for line in result.splitlines():
                line = line.strip()
                if "level:" in line:
                    battery_data["level"] = int(line.split(":")[1].strip())
                elif "status:" in line:
                    status = line.split(":")[1].strip()
                    status_map = {
                        "1": "未知",
                        "2": "充电中",
                        "3": "充满",
                        "4": "未充电"
                    }
                    battery_data["status"] = status_map.get(status, status)
                elif "health:" in line:
                    health = line.split(":")[1].strip()
                    health_map = {
                        "1": "未知",
                        "2": "良好",
                        "3": "过热",
                        "4": "损坏",
                        "5": "充电过久",
                        "6": "未知错误"
                    }
                    battery_data["health"] = health_map.get(health, health)
                elif "voltage:" in line:
                    battery_data["voltage"] = int(line.split(":")[1].strip())
                elif "temperature:" in line:
                    # 温度单位是0.1°C，转换为°C
                    battery_data["temperature"] = int(line.split(":")[1].strip()) / 10

            return battery_data

        except Exception as e:
            print(f"获取电池信息出错: {str(e)}")
            return None

    def log_battery_data(self, data, charge_disabled):
        """记录电池数据到CSV文件"""
        if not data:
            return

        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        charge_status = "已禁用" if charge_disabled else "未禁用"

        with open(self.log_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                current_time,
                data.get("level", ""),
                data.get("status", ""),
                data.get("health", ""),
                data.get("voltage", ""),
                data.get("temperature", ""),
                charge_status
            ])

        # 打印当前记录以便实时查看
        print(
            f"[{current_time}] 电量: {data.get('level', '')}% | 状态: {data.get('status', '')} | 温度: {data.get('temperature', '')}°C | 充电禁用: {charge_status}")

    def start_monitoring(self, duration=28800):  # 8小时 = 28800秒
        """
        开始监控电池状态
        :param duration: 监控持续时间(秒)，默认8小时
        """
        # 尝试禁用充电
        charge_disabled = self.disable_charging()

        print(f"开始电池监控，间隔{self.interval}秒，持续{duration / 3600:.1f}小时...")
        print(f"日志将保存到: {self.log_file}")
        print("按Ctrl+C停止监控")

        start_time = time.time()

        try:
            while True:
                # 检查是否超过监控持续时间
                if (time.time() - start_time) > duration:
                    break

                # 获取并记录电池信息
                battery_data = self.get_battery_info()

                # 定期重新检查充电状态，如果又开始充电则尝试再次禁用
                elapsed = time.time() - start_time
                if int(elapsed) % 300 == 0 and not self.is_charging_disabled():
                    print("检测到充电状态已恢复，尝试重新禁用...")
                    charge_disabled = self.disable_charging()

                self.log_battery_data(battery_data, charge_disabled)

                # 检查电量是否过低，避免设备关机
                if battery_data and battery_data.get("level", 100) <= 10:
                    print("警告：电量低于10%，即将停止监控以保护设备")
                    break

                # 等待下一次监控
                time.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n监控已手动停止")
        except Exception as e:
            print(f"监控过程出错: {str(e)}")
        finally:
            # 无论如何都恢复充电功能
            self.restore_charging()
            print("监控结束")


if __name__ == "__main__":
    # 创建监控器实例，设置监控间隔为300秒（5分钟）
    monitor = BatteryMonitor(interval=300)

    # 开始8小时监控
    monitor.start_monitoring()
