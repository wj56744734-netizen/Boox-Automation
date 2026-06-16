import subprocess
import logging
import time
from threading import Thread, Event, Condition, Lock
from queue import Queue
from boox_automation.devices.info import Device_basic_information

_LOGCAT_INIT_LOGGED = [False]  # 只输出一次初始化日志

class Logcat:

    def __init__(self):
        self._result_queue = Queue()
        self._logcat_thread = None
        self._logcat_process = None
        self._stop_event = Event()
        self._lock = Lock()
        # 串行化控制
        self._is_capturing = False
        self._capture_cond = Condition(self._lock)
        # 存储当前任务已捕获的部分结果
        self._partial_result = {
            'success': False,
            'message': '',
            'total_targets': 0,
            'matched_targets': [],
            'unmatched_targets': [],
            'detailed_matches': {}
        }
        self._device_id = Device_basic_information().get_connected_device_ids()
        if not _LOGCAT_INIT_LOGGED[0]:
            logging.debug("Logcat 实例已初始化")
            _LOGCAT_INIT_LOGGED[0] = True

    # ========== 释放锁（仅在工作线程 finally 中使用） ==========

    def _release_lock(self):
        """释放串行锁（工作线程自然结束后的清理，不 join 自身）"""
        logging.debug("[_release_lock] 释放串行锁...")
        with self._capture_cond:
            self._is_capturing = False
            self._capture_cond.notify()
        self._logcat_thread = None
        self._logcat_process = None
        logging.debug("[_release_lock] 串行锁已释放，下一个任务可以启动")

    # ========== 外部强制清理（stop_capture 专用，不 join 自身） ==========

    def _cleanup_thread(self, max_wait=15):
        """
        外部调用：强制终止进程和线程。
        流程：发中断信号 → 杀进程 → 等线程完成 → 确认 → 释放串行锁。
        调用方必须在工作线程之外（不在 _run_xxx 内部）。
        """
        logging.debug(f"[cleanup] 开始清理线程，max_wait={max_wait}s")

        # 1. 发中断信号
        with self._lock:
            if not self._stop_event.is_set():
                self._stop_event.set()
                logging.debug("[cleanup] 已发出日志捕获中断信号")
            else:
                logging.debug("[cleanup] 中断信号已设置，跳过")

        # 2. 终止 adb logcat 子进程
        proc = self._logcat_process
        logging.debug(f"[cleanup] 检查进程状态: proc={proc}, poll={proc.poll() if proc else 'None'}")
        if proc is not None and proc.poll() is None:
            try:
                logging.debug("[cleanup] 正在 terminate logcat 进程...")
                proc.terminate()
                proc.wait(timeout=2)
                logging.debug("[cleanup] 已终止 logcat subprocess")
            except subprocess.TimeoutExpired:
                logging.warning("[cleanup] logcat 进程 terminate 超时，尝试 kill")
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                    logging.debug("[cleanup] 已 kill logcat 进程")
                except Exception as e:
                    logging.error(f"[cleanup] kill logcat 进程失败: {e}")
            except Exception as e:
                logging.warning(f"[cleanup] 终止 logcat subprocess 时出错: {e}")
        else:
            logging.debug("[cleanup] 进程无需终止（已结束或为空）")
        self._logcat_process = None

        # 3. 等待线程结束
        thread = self._logcat_thread
        logging.debug(f"[cleanup] 检查线程状态: thread={thread}, is_alive={thread.is_alive() if thread else 'N/A'}")
        if thread is not None and thread.is_alive():
            logging.debug(f"[cleanup] 等待线程结束，最多等待 {max_wait}s...")
            thread.join(timeout=max_wait)
            logging.debug(f"[cleanup] join 返回，线程是否存活: {thread.is_alive()}")

        # 4. 确认线程状态
        if thread is not None and thread.is_alive():
            logging.error(
                f"[cleanup] 日志捕获线程未能终止（已等待{max_wait}秒），"
                "子进程已杀死，线程应自然退出。将清理引用并继续。"
            )
            logging.debug("[cleanup] 再给 5 秒宽限期...")
            thread.join(timeout=5)
            if thread.is_alive():
                logging.error(
                    "[cleanup] 日志捕获线程仍然存活！可能造成线程堆积，但不再阻塞后续任务。"
                )
            else:
                logging.debug("[cleanup] 线程在宽限期内已终止")

        self._logcat_thread = None
        logging.debug("[cleanup] 线程引用已清空")

        # 5. 释放串行锁
        logging.debug("[cleanup] 准备释放串行锁...")
        with self._capture_cond:
            self._is_capturing = False
            self._capture_cond.notify()
            logging.debug("[cleanup] 串行锁已释放，下一个任务可以启动")

    # ========== 修复后的 stop_capture ==========

    def stop_capture(self):
        """外部主动中断日志捕获并等待完全终止"""
        logging.debug("[stop_capture] 调用 stop_capture")
        self._cleanup_thread()

    # ========== capture_render_logcat ==========

    def capture_render_logcat(self, target_logs, test_page, match_count=1,
                               reader_time_log=True, single_timeout=None):
        from boox_automation.core.config import logcat_capture_timeout
        if single_timeout is None:
            single_timeout = logcat_capture_timeout()
        logging.debug(f"[capture_render_logcat] 开始捕获，target_logs={target_logs}, test_page={test_page}, match_count={match_count}")

        # 等待前一个任务结束
        logging.debug("[capture_render_logcat] 等待获取串行锁...")
        with self._capture_cond:
            while self._is_capturing:
                logging.debug("[capture_render_logcat] 前一个任务还在运行，等待...")
                self._capture_cond.wait()
            self._is_capturing = True
            logging.debug("[capture_render_logcat] 已获取串行锁")

        # 清空残留结果
        cleared = 0
        while not self._result_queue.empty():
            try:
                self._result_queue.get_nowait()
                cleared += 1
            except Exception:
                break
        if cleared > 0:
            logging.debug(f"[capture_render_logcat] 清空了 {cleared} 个残留结果")

        self._reset_partial_result()
        self._stop_event.clear()
        logging.debug("[capture_render_logcat] 已重置状态，准备启动线程")

        self._logcat_thread = Thread(
            target=self._run_render_logcat_capture,
            args=(target_logs, test_page, match_count, reader_time_log, single_timeout)
        )
        self._logcat_thread.daemon = True
        self._logcat_thread.start()
        logging.debug(f"[capture_render_logcat] 线程已启动: {self._logcat_thread.name}")
        return self._logcat_thread

    def _reset_partial_result(self):
        """重置部分结果容器"""
        self._partial_result = {
            'success': False,
            'message': '',
            'total_targets': 0,
            'matched_targets': [],
            'unmatched_targets': [],
            'detailed_matches': {}
        }

    def _update_partial_result(self, matched_targets, detailed_matches,
                                total_targets=0, success=False, message=''):
        """更新部分结果（线程安全）"""
        with self._lock:
            self._partial_result['matched_targets'] = list(matched_targets) if matched_targets else []
            self._partial_result['detailed_matches'] = detailed_matches.copy() if detailed_matches else {}
            self._partial_result['total_targets'] = total_targets
            self._partial_result['success'] = success
            self._partial_result['message'] = message

    def _run_render_logcat_capture(self, target_logs, test_page, match_count,
                                    reader_time_log, single_timeout):
        """实际执行 logcat 捕获（单条日志超时即停止）"""
        logging.debug(f"[_run_render_logcat_capture] 线程开始执行，target_logs={target_logs}")
        try:
            try:
                logging.debug("[_run_render_logcat_capture] 执行 adb logcat -c 清空缓冲区...")
                result = subprocess.run(['adb', '-s', self._device_id, 'logcat', '-c'], capture_output=True, text=True, timeout=5)
                if result.returncode != 0:
                    logging.warning(f"[_run_render_logcat_capture] logcat -c 返回非零: {result.stderr}")
                else:
                    logging.debug("[_run_render_logcat_capture] adb logcat -c 完成")
            except subprocess.TimeoutExpired:
                logging.warning("[_run_render_logcat_capture] logcat -c 超时，继续执行")

            log_found = Event()
            result_container = {
                'success': False,
                'message': "",
                'match_count': 0
            }
            current_matched = 0
            last_match_time = time.time()

            def read_logs(process, targets, container, stop_event):
                nonlocal current_matched, last_match_time
                logging.debug("[read_logs] 读取线程开始")
                try:
                    buffer = b''
                    read_count = 0
                    while not stop_event.is_set():
                        chunk = process.stdout.read(1024)
                        if not chunk:
                            logging.debug("[read_logs] stdout 返回空，EOF 到达")
                            break
                        buffer += chunk
                        read_count += 1

                        if read_count % 100 == 0:
                            logging.debug(f"[read_logs] 已读取 {read_count} 个 chunk")

                        try:
                            text = buffer.decode('utf-8')
                            buffer = b''
                        except UnicodeDecodeError:
                            try:
                                text = buffer.decode('utf-8', errors='replace')
                                buffer = b''
                            except Exception:
                                text = buffer.decode('latin-1', errors='replace')
                                buffer = b''

                        for line in text.split('\n'):
                            if not line.strip():
                                continue
                            if stop_event.is_set():
                                logging.debug("[read_logs] stop_event 已设置，退出")
                                return

                            for target in targets:
                                if target not in line:
                                    continue

                                try:
                                    number_str = line.split(target)[1].strip()
                                    parts = number_str.split("--->")
                                    if len(parts) < 2:
                                        continue

                                    render, render_time = parts[0].strip(), parts[1].strip()
                                    logging.debug(f"[read_logs] 匹配到目标 '{target}': render={render}, time={render_time}")

                                    if render == "0":
                                        container.update({
                                            'success': False,
                                            'message': "渲染数据为0异常",
                                            'match_count': container['match_count'] + 1
                                        })
                                        log_found.set()
                                        stop_event.set()
                                        logging.debug("[read_logs] 渲染数据为0，设置停止信号")
                                        return

                                    current_matched += 1
                                    container['match_count'] = current_matched
                                    last_match_time = time.time()

                                    if reader_time_log:
                                        import re
                                        digits_only = re.sub(r'\D', '', str(render_time))
                                        if digits_only:
                                            render_time_int = int(digits_only)
                                            logging.info(
                                                f" 📒 测试笔记：{test_page} ｜ 渲染耗时: {render_time_int} ms"
                                            )
                                        else:
                                            logging.warning(
                                                f"无法从日志中解析耗时: {render_time}, 原始行: {line}"
                                            )

                                    if current_matched >= match_count:
                                        container.update({
                                            'success': True,
                                            'message': f"成功匹配 {current_matched} 条日志"
                                        })
                                        log_found.set()
                                        stop_event.set()
                                        logging.debug(f"[read_logs] 已匹配 {current_matched} 条，达到目标，设置停止信号")
                                        return

                                except Exception as e:
                                    logging.error(f"解析日志行时出错: {e}")
                    logging.debug(f"[read_logs] 读取线程结束，共读取 {read_count} 个 chunk")
                except Exception as e:
                    logging.error(f"读取日志流时出错: {e}")
                    container.update({
                        'success': False,
                        'message': f"读取异常: {str(e)}",
                        'match_count': container['match_count']
                    })
                    log_found.set()
                    stop_event.set()

            logging.debug("[_run_render_logcat_capture] 启动 adb logcat 进程...")
            with subprocess.Popen(
                ['adb', '-s', self._device_id, 'logcat'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1
            ) as process:
                self._logcat_process = process
                logging.debug(f"[_run_render_logcat_capture] adb logcat 进程已启动，pid={process.pid}")

                reader_thread = Thread(
                    target=read_logs,
                    args=(process, target_logs, result_container, self._stop_event)
                )
                reader_thread.daemon = True
                reader_thread.start()
                logging.debug("[_run_render_logcat_capture] 读取线程已启动")

                loop_count = 0
                while not log_found.is_set() and not self._stop_event.is_set():
                    loop_count += 1
                    if loop_count % 200 == 0:
                        elapsed = time.time() - last_match_time
                        logging.debug(f"[_run_render_logcat_capture] 主循环等待中... elapsed={elapsed:.1f}s, current_matched={current_matched}")

                    if not reader_thread.is_alive():
                        logging.error("[_run_render_logcat_capture] 读取线程意外终止")
                        result_container.update({
                            'success': False,
                            'message': "读取线程意外终止",
                            'match_count': current_matched
                        })
                        self._stop_event.set()
                        log_found.set()
                        break

                    waiting_for = current_matched + 1
                    if time.time() - last_match_time > single_timeout:
                        logging.error(
                            f"{test_page} 第{waiting_for}条日志捕获超时"
                            f"（超过{single_timeout}秒），"
                            f"已匹配: {current_matched}/{match_count}"
                        )
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                        result_container.update({
                            'success': False,
                            'message': f"第{waiting_for}条日志超时（超过{single_timeout}秒未捕获）",
                            'match_count': current_matched
                        })
                        self._stop_event.set()
                        log_found.set()
                        logging.debug("[_run_render_logcat_capture] 超时，设置停止信号")
                        break

                    time.sleep(0.05)

                logging.debug(f"[_run_render_logcat_capture] 主循环退出，log_found={log_found.is_set()}, stop_event={self._stop_event.is_set()}")

                if process.poll() is None:
                    logging.debug("[_run_render_logcat_capture] 终止 adb logcat 进程")
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

            self._logcat_process = None
            logging.debug("[_run_render_logcat_capture] 将结果放入队列")
            self._result_queue.put(result_container)

        except Exception as e:
            logging.error(f"[_run_render_logcat_capture] 捕获过程异常: {e}")
            error_result = {
                'success': False,
                'message': f"捕获异常: {str(e)}",
                'match_count': 0
            }
            self._result_queue.put(error_result)
        finally:
            # ★ 修复：工作线程自然结束，只释放锁，不 join 自身
            logging.debug("[_run_render_logcat_capture] 进入 finally，释放串行锁")
            self._release_lock()
            logging.debug("[_run_render_logcat_capture] 线程即将退出")

    # ========== capture_logcat ==========

    def capture_logcat(self, target_logs, single_timeout=80, block=True, strict=False):
        logging.debug(f"[capture_logcat] 开始捕获，target_logs={target_logs}, block={block}, strict={strict}")

        # 等待前一个任务结束
        logging.debug("[capture_logcat] 等待获取串行锁...")
        with self._capture_cond:
            while self._is_capturing:
                logging.debug("[capture_logcat] 前一个任务还在运行，等待...")
                self._capture_cond.wait()
            self._is_capturing = True
            logging.debug("[capture_logcat] 已获取串行锁")

        # 清空残留结果
        cleared = 0
        while not self._result_queue.empty():
            try:
                self._result_queue.get_nowait()
                cleared += 1
            except Exception:
                break
        if cleared > 0:
            logging.debug(f"[capture_logcat] 清空了 {cleared} 个残留结果")

        self._reset_partial_result()
        self._partial_result['total_targets'] = len(target_logs)

        self._stop_event.clear()
        logging.debug("[capture_logcat] 已重置状态，准备启动线程")

        self._logcat_thread = Thread(
            target=self._run_logcat_capture,
            args=(target_logs, single_timeout, strict)
        )
        self._logcat_thread.daemon = True
        self._logcat_thread.start()
        logging.debug(f"[capture_logcat] 线程已启动: {self._logcat_thread.name}")

        if block:
            logging.debug("[capture_logcat] block=True，等待线程结束...")
            self._logcat_thread.join()
            logging.debug("[capture_logcat] 线程已结束，获取结果")
            return self._result_queue.get()
        else:
            return None

    def wait_result(self, timeout=None):
        logging.debug(f"[wait_result] 等待结果，timeout={timeout}")
        if self._logcat_thread is not None and self._logcat_thread.is_alive():
            logging.debug("[wait_result] 线程还在运行，等待 join")
            self._logcat_thread.join(timeout=timeout)

        try:
            result = self._result_queue.get(timeout=timeout if timeout else 5)
            logging.debug(f"[wait_result] 获取到结果: {result}")
            return result
        except Exception:
            logging.warning("[wait_result] 获取结果超时，返回部分结果")
            with self._lock:
                partial = self._partial_result.copy()
                if not partial.get('matched_targets') and not partial.get('detailed_matches'):
                    partial['message'] = '等待日志捕获结果超时，且未捕获到任何目标日志'
                else:
                    partial['message'] = (
                        f"等待超时，已捕获 {len(partial.get('matched_targets', []))} "
                        f"/ {partial.get('total_targets', 0)} 个目标"
                    )
                partial['success'] = False
                return partial

    def is_running(self):
        running = self._logcat_thread is not None and self._logcat_thread.is_alive()
        logging.debug(f"[is_running] 返回 {running}")
        return running

    def _run_logcat_capture(self, target_logs, single_timeout, strict=False):
        """批量目标日志捕获"""
        logging.debug(f"[_run_logcat_capture] 线程开始执行，target_logs={target_logs}, strict={strict}")
        try:
            try:
                logging.debug("[_run_logcat_capture] 执行 adb logcat -c 清空缓冲区...")
                result = subprocess.run(
                    ['adb', '-s', self._device_id, 'logcat', '-c'], capture_output=True, text=True, timeout=5
                )
                if result.returncode != 0:
                    logging.warning(f"[_run_logcat_capture] logcat -c 返回非零: {result.stderr}")
                else:
                    logging.debug("[_run_logcat_capture] adb logcat -c 完成")
            except subprocess.TimeoutExpired:
                logging.warning("[_run_logcat_capture] logcat -c 超时，继续执行")

            logging.debug(f"开始捕捉所有目标日志: {target_logs}")

            log_found = Event()
            result_container = {
                'success': False,
                'message': "",
                'total_targets': len(target_logs),
                'matched_targets': [],
                'unmatched_targets': [],
                'detailed_matches': {}
            }
            matched_targets = set()
            start_time = time.time()

            def read_logs(process, targets, container, stop_event):
                nonlocal matched_targets
                logging.debug("[read_logs] 读取线程开始")
                buffer = b''
                read_count = 0
                try:
                    while not stop_event.is_set():
                        chunk = process.stdout.read(8192)
                        if not chunk:
                            logging.debug("[read_logs] stdout 返回空，EOF 到达")
                            break
                        buffer += chunk
                        read_count += 1

                        if read_count % 50 == 0:
                            logging.debug(f"[read_logs] 已读取 {read_count} 个 chunk, matched={len(matched_targets)}")

                        try:
                            text = buffer.decode('utf-8')
                            buffer = b''
                        except UnicodeDecodeError:
                            text = buffer.decode('utf-8', errors='replace')
                            buffer = b''

                        for line in text.split('\n'):
                            if not line.strip():
                                continue
                            if stop_event.is_set():
                                logging.debug("[read_logs] stop_event 已设置，退出")
                                return

                            for target in targets:
                                if (target in line
                                        and target not in matched_targets):
                                    if strict and '--->' not in line:
                                        continue

                                    container['detailed_matches'][target] = line.strip()
                                    matched_targets.add(target)
                                    logging.debug(f"成功捕捉到目标日志: {target}")

                                    container['matched_targets'] = list(matched_targets)

                                    self._update_partial_result(
                                        matched_targets=matched_targets,
                                        detailed_matches=container['detailed_matches'],
                                        total_targets=len(targets),
                                        success=False,
                                        message=f"已捕获 {len(matched_targets)}/{len(targets)} 个目标"
                                    )

                                    if len(matched_targets) == len(targets):
                                        container['success'] = True
                                        container['message'] = "所有目标日志均已捕捉到"
                                        log_found.set()
                                        stop_event.set()
                                        logging.debug("[read_logs] 所有目标已捕获，设置停止信号")
                                        return

                    logging.debug(f"[read_logs] 读取线程结束，共读取 {read_count} 个 chunk, matched={len(matched_targets)}")
                except Exception as e:
                    logging.error(f"读取日志流时出错: {e}")
                    container['message'] = f"读取异常: {str(e)}"
                    log_found.set()
                    stop_event.set()

            logging.debug("[_run_logcat_capture] 启动 adb logcat 进程...")
            with subprocess.Popen(
                ['adb', '-s', self._device_id, 'logcat'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1
            ) as process:
                self._logcat_process = process
                logging.debug(f"[_run_logcat_capture] adb logcat 进程已启动，pid={process.pid}")

                reader_thread = Thread(
                    target=read_logs,
                    args=(process, target_logs, result_container, self._stop_event)
                )
                reader_thread.daemon = True
                reader_thread.start()
                logging.debug("[_run_logcat_capture] 读取线程已启动")

                try:
                    loop_count = 0
                    while not log_found.is_set() and not self._stop_event.is_set():
                        loop_count += 1
                        if loop_count % 200 == 0:
                            elapsed = time.time() - start_time
                            logging.debug(f"[_run_logcat_capture] 主循环等待中... elapsed={elapsed:.1f}s, matched={len(matched_targets)}/{len(target_logs)}")

                        if not reader_thread.is_alive():
                            logging.error("[_run_logcat_capture] 读取线程意外终止")
                            result_container['message'] = "读取线程意外终止"
                            self._stop_event.set()
                            log_found.set()
                            break

                        if time.time() - start_time > single_timeout:
                            result_container['unmatched_targets'] = [
                                t for t in target_logs if t not in matched_targets
                            ]
                            logging.error(
                                f"超时（超过{single_timeout}秒），"
                                f"未捕捉到的目标: {result_container['unmatched_targets']}"
                            )
                            self._stop_event.set()
                            log_found.set()
                            result_container['message'] = (
                                f"超时未捕捉全所有目标（已捕捉{len(matched_targets)}/{len(target_logs)}）"
                            )
                            logging.debug("[_run_logcat_capture] 超时，设置停止信号")
                            break

                        time.sleep(0.05)

                    logging.debug(f"[_run_logcat_capture] 主循环退出，log_found={log_found.is_set()}, stop_event={self._stop_event.is_set()}")

                except Exception as e:
                    logging.error(f"日志捕获主循环异常: {e}")
                    result_container['message'] = f"捕获异常: {str(e)}"
                finally:
                    if process.poll() is None:
                        logging.debug("[_run_logcat_capture] 终止 adb logcat 进程")
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()

            self._logcat_process = None
            logging.debug("[_run_logcat_capture] 将结果放入队列")
            self._result_queue.put(result_container)

        except Exception as e:
            logging.error(f"[_run_logcat_capture] 捕获过程异常: {e}")
            error_result = {
                'success': False,
                'message': f"捕获异常: {str(e)}",
                'total_targets': len(target_logs),
                'matched_targets': [],
                'unmatched_targets': target_logs,
                'detailed_matches': {}
            }
            self._result_queue.put(error_result)
        finally:
            # ★ 修复：工作线程自然结束，只释放锁，不 join 自身
            logging.debug("[_run_logcat_capture] 进入 finally，释放串行锁")
            self._release_lock()
            logging.debug("[_run_logcat_capture] 线程即将退出")