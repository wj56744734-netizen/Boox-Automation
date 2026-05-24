import subprocess
import time
import re
from Note_Automation.Devices_list.Device_basic_information import Device_basic_information

try:
    DEVICE_ID = Device_basic_information().get_connected_device_ids()
except RuntimeError:
    DEVICE_ID = None


def get_android_cpu_usage(pid):
    try:
        with subprocess.Popen(['adb', '-s', DEVICE_ID, 'shell', 'cat /proc/stat'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True) as proc:
            cpu_total = sum(map(int, proc.stdout.readline().split()[1:8]))

        with subprocess.Popen(['adb', '-s', DEVICE_ID, 'shell', f'cat /proc/{pid}/stat'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True) as proc:
            stats = proc.stdout.read().split()
            proc_cpu = int(stats[13]) + int(stats[14])

        time.sleep(1)

        with subprocess.Popen(['adb', '-s', DEVICE_ID, 'shell', 'cat /proc/stat'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True) as proc:
            cpu_total2 = sum(map(int, proc.stdout.readline().split()[1:8]))

        with subprocess.Popen(['adb', '-s', DEVICE_ID, 'shell', f'cat /proc/{pid}/stat'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True) as proc:
            stats2 = proc.stdout.read().split()
            proc_cpu2 = int(stats2[13]) + int(stats2[14])

        delta_proc = proc_cpu2 - proc_cpu
        delta_total = cpu_total2 - cpu_total
        if delta_total > 0:
            return f"{(delta_proc / delta_total) * 100:.1f}%"
        return "0.0%"
    except Exception as e:
        return f"错误: {str(e)[:20]}"


def get_android_mem_usage(pid):
    try:
        top_output = subprocess.check_output(
            ['adb', '-s', DEVICE_ID, 'shell', f'top -p {pid} -n 1 -d 0.5'],
            text=True,
            stderr=subprocess.STDOUT
        )
        pattern = rf'{pid}\s+\S+\s+\S+\s+\S+\s+(\S+)\s+\S+\s+S\s+\S+\s+(\S+)\s+'
        match = re.search(pattern, top_output)

        if match:
            res = match.group(1)
            if 'M' in res:
                return res
            elif 'G' in res:
                return f"{float(res[:-1]) * 1024:.1f} MB"
            elif 'K' in res:
                return f"{int(res[:-1]) / 1024:.1f} MB"
            else:
                return f"{int(res) / 1024:.1f} MB"
        return get_mem_from_dumpsys(pid)
    except Exception as e:
        return f"错误: {str(e)[:30]}"


def get_mem_from_dumpsys(pid):
    try:
        mem_output = subprocess.check_output(
            ['adb', '-s', DEVICE_ID, 'shell', f'dumpsys meminfo {pid}'],
            text=True,
            stderr=subprocess.STDOUT
        )
        match = re.search(r'TOTAL\s+(\d+)', mem_output)
        if match:
            return f"{int(match.group(1)) / 1024:.1f} MB"
        return "无法获取"
    except Exception:
        return "无法获取"


def monitor_android_app(package_name, interval=1):
    try:
        while True:
            try:
                pid = subprocess.check_output(
                    ['adb', '-s', DEVICE_ID, 'shell', f'pidof {package_name}'],
                    text=True
                ).strip().split()[0]
            except (IndexError, subprocess.CalledProcessError):
                print(f"应用 {package_name} 未运行")
                time.sleep(interval)
                continue

            cpu_info = get_android_cpu_usage(pid)
            mem_info = get_android_mem_usage(pid)

            print(f"应用 {package_name} (PID:{pid}) - CPU: {cpu_info} | 内存: {mem_info}")
            time.sleep(interval - 0.5)
    except KeyboardInterrupt:
        print("\n监控已停止")


if __name__ == "__main__":
    monitor_android_app("com.onyx.android.note")