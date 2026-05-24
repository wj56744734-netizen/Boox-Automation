"""项目唯一的运行时健康检查工具集（精简版，仅保留实际被使用的能力）。

提供：
- ``is_port_open``: TCP 端口可达性探测
- ``ensure_appium_server``: 保证 Appium Server 已启动，不存在时自动拉起
- ``ensure_adb_device_ready``: 等待目标设备进入 adb online 状态
- ``run_adb_command_with_retry``: 执行单条 adb 命令并自动重试
"""

import logging
import os
import socket
import subprocess
import time

_appium_process = None


def is_port_open(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def ensure_appium_server(auto_start=True, startup_timeout=15):
    """确保 Appium 服务可用，必要时按 APPIUM_START_CMD 自动拉起。"""
    global _appium_process
    host = os.getenv("APPIUM_HOST", "127.0.0.1")
    port = int(os.getenv("APPIUM_PORT", "4723"))
    appium_cmd = os.getenv(
        "APPIUM_START_CMD",
        f"appium --address {host} -p {port} --session-override",
    )

    if is_port_open(host, port):
        return True
    if not auto_start:
        raise RuntimeError(f"Appium 未启动：{host}:{port}")

    logging.warning(f"检测到 Appium 未监听 {host}:{port}，尝试自动拉起：{appium_cmd}")
    _appium_process = subprocess.Popen(
        appium_cmd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + startup_timeout
    while time.time() < deadline:
        if is_port_open(host, port):
            logging.info(f"Appium 服务已就绪：{host}:{port}")
            return True
        time.sleep(0.5)
    raise RuntimeError(f"Appium 自动拉起失败，{startup_timeout}s 内未监听 {host}:{port}")


def ensure_adb_device_ready(device_id, retries=5, retry_delay=2):
    """等待设备处于 adb online 状态。"""
    last_state = ""
    for attempt in range(1, retries + 1):
        result = subprocess.run(
            ["adb", "-s", device_id, "get-state"],
            capture_output=True,
            text=True,
        )
        state = (result.stdout or "").strip()
        if result.returncode == 0 and state == "device":
            if attempt > 1:
                logging.info(f"设备 {device_id} 恢复在线（第 {attempt} 次探测成功）")
            return
        last_state = (result.stderr or state or "unknown").strip()
        logging.warning(f"设备 {device_id} 当前不可用（第 {attempt}/{retries} 次）：{last_state}")
        time.sleep(retry_delay)
    raise RuntimeError(f"设备未就绪：{device_id}，最后状态：{last_state}")


def run_adb_command_with_retry(command, retries=3, retry_delay=2):
    """执行单条 adb 命令并自动重试。"""
    last_error = ""
    for attempt in range(1, retries + 1):
        with subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        ) as process:
            stdout, stderr = process.communicate()
            if process.returncode == 0:
                return stdout
            last_error = (stderr or stdout or "").strip()
            logging.warning(
                f"ADB命令失败（第 {attempt}/{retries} 次）：{command} | 错误：{last_error}"
            )
        time.sleep(retry_delay)
    raise RuntimeError(f"ADB命令执行失败：{command} | 最终错误：{last_error}")
