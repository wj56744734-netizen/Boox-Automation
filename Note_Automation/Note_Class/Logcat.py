import subprocess
import logging
import time
from threading import Thread, Event
from queue import Queue
from threading import Lock


class Logcat:

    def __init__(self):
        self._result_queue = Queue()
        self._logcat_thread = None
        self._stop_event = Event()
        self._lock = Lock()

    def capture_render_logcat(self, target_logs, test_page, match_count=1, reader_time_log=True, single_timeout=80):

        with self._lock:
            self._stop_event.clear()  # 重置停止信号
            self._logcat_thread = Thread(
                target=self._run_render_logcat_capture,
                args=(target_logs, test_page, match_count, reader_time_log, single_timeout)
            )
            self._logcat_thread.daemon = True
            self._logcat_thread.start()
            return self._logcat_thread

    def _run_render_logcat_capture(self, target_logs, test_page, match_count, reader_time_log, single_timeout):
        """实际执行logcat捕获（单条日志超时即停止）"""
        subprocess.run(['adb', 'logcat', '-c'], capture_output=True, text=True)

        # logging.info(f"开始捕捉日志{target_logs}")

        log_found = Event()
        result_container = {
            'success': False,
            'message': "",
            'match_count': 0
        }
        current_matched = 0
        last_match_time = time.time()

        def read_logs(process, targets, container, stop_event):
            """实时读取日志流，逐条匹配目标日志"""
            nonlocal current_matched, last_match_time
            try:
                for line in process.stdout:
                    if stop_event.is_set():
                        break

                    for target in targets:
                        if target not in line:
                            continue

                        try:
                            # logging.info(f"成功捕捉到日志{target}")
                            number_str = line.split(target)[1].strip()
                            parts = number_str.split("--->")
                            if len(parts) < 2:
                                continue

                            render, render_time = parts[0].strip(), parts[1].strip()

                            # 异常处理：渲染数据为0
                            if render == "0":
                                container.update({
                                    'success': False,
                                    'message': "渲染数据为0异常",
                                    'match_count': container['match_count'] + 1
                                })
                                log_found.set()
                                stop_event.set()
                                return

                            current_matched += 1
                            container['match_count'] = current_matched
                            last_match_time = time.time()

                            if reader_time_log:
                                logging.info(f"测试笔记：{test_page},渲染耗时:{render_time}")

                            if current_matched >= match_count:
                                container.update({
                                    'success': True,
                                    'message': f"成功匹配 {current_matched} 条日志"
                                })
                                log_found.set()
                                stop_event.set()
                                return

                        except Exception as e:
                            logging.error(f"解析日志行时出错: {e}")
            except Exception as e:
                logging.error(f"读取日志流时出错: {e}")
                container.update({
                    'success': False,
                    'message': f"读取异常: {str(e)}",
                    'match_count': container['match_count']
                })
                log_found.set()
                stop_event.set()

        with subprocess.Popen(
                ['adb', 'logcat'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1
        ) as process:

            # 启动日志读取线程
            reader_thread = Thread(
                target=read_logs,
                args=(process, target_logs, result_container, self._stop_event)
            )
            reader_thread.daemon = True
            reader_thread.start()

            while not log_found.is_set() and not self._stop_event.is_set():
                waiting_for = current_matched + 1
                if time.time() - last_match_time > single_timeout:
                    logging.error(
                        f"{test_page} 第{waiting_for}条日志捕获超时（超过{single_timeout}秒），"
                        f"已匹配: {current_matched}/{match_count}"
                    )
                    process.terminate()
                    result_container.update({
                        'success': False,
                        'message': f"第{waiting_for}条日志超时（超过{single_timeout}秒未捕获）",
                        'match_count': current_matched
                    })
                    self._stop_event.set()
                    log_found.set()
                    break

                time.sleep(0.05)  # 减少CPU占用

            if process.poll() is None:
                process.terminate()

            self._result_queue.put(result_container)

    def get_result(self, block=True, timeout=None):
        """获取日志捕获结果"""
        try:
            return self._result_queue.get(block=block, timeout=timeout)
        except Exception as e:
            return {'success': False, 'message': f'获取结果超时: {str(e)}'}

#------

    def capture_logcat(self, target_logs, single_timeout=80):

        with self._lock:
            self._stop_event.clear()
            self._logcat_thread = Thread(
                target=self._run_logcat_capture,
                args=(target_logs, single_timeout)
            )
            self._logcat_thread.daemon = True
            self._logcat_thread.start()
            self._logcat_thread.join()
            return self._result_queue.get()

    def _run_logcat_capture(self, target_logs, single_timeout):

        subprocess.run(['adb', 'logcat', '-c'], capture_output=True, text=True)

        logging.debug(f"开始捕捉所有目标日志: {target_logs}")

        log_found = Event()
        # 结果容器：记录每个目标的匹配情况
        result_container = {
            'success': False,
            'message': "",
            'total_targets': len(target_logs),  # 总目标数
            'matched_targets': [],  # 已捕捉到的目标列表
            'unmatched_targets': [],  # 未捕捉到的目标列表
            'detailed_matches': {}  # 每个目标对应的最后匹配日志（键：目标日志，值：日志行）
        }
        matched_targets = set()
        start_time = time.time()

        def read_logs(process, targets, container, stop_event):

            nonlocal matched_targets
            try:
                for line in process.stdout:
                    if stop_event.is_set():
                        break

                    for target in targets:

                        if target in line and target not in matched_targets:

                            container['detailed_matches'][target] = line.strip()
                            matched_targets.add(target)
                            logging.debug(f"成功捕捉到目标日志: {target}")

                            container['matched_targets'] = list(matched_targets)

                            if len(matched_targets) == len(targets):
                                container['success'] = True
                                container['message'] = "所有目标日志均已捕捉到"
                                log_found.set()
                                stop_event.set()
                                return

            except Exception as e:
                logging.error(f"读取日志流时出错: {e}")
                container['message'] = f"读取异常: {str(e)}"
                log_found.set()
                stop_event.set()

        with subprocess.Popen(
                ['adb', 'logcat'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1
        ) as process:

            reader_thread = Thread(
                target=read_logs,
                args=(process, target_logs, result_container, self._stop_event)
            )
            reader_thread.daemon = True
            reader_thread.start()


            while not log_found.is_set() and not self._stop_event.is_set():

                if time.time() - start_time > single_timeout:

                    result_container['unmatched_targets'] = [
                        t for t in target_logs if t not in matched_targets
                    ]
                    logging.error(
                        f"超时（超过{single_timeout}秒），未捕捉到的目标: {result_container['unmatched_targets']}"
                    )
                    process.terminate()
                    result_container['message'] = (
                        f"超时未捕捉全所有目标（已捕捉{len(matched_targets)}/{len(target_logs)}）"
                    )
                    self._stop_event.set()
                    log_found.set()
                    break

                time.sleep(0.05)  # 减少CPU占用

            if process.poll() is None:
                process.terminate()

            self._result_queue.put(result_container)