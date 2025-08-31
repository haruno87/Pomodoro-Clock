import tkinter as tk
import threading
import time
import random
import pygame
import math
import json
import os
# 导入matplotlib用于数据可视化
import matplotlib.pyplot as plt

# 配置matplotlib支持中文显示
plt.rcParams['font.family'] = ['Songti SC']  # 使用Songti SC字体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号'-'显示为方块的问题
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import ttk
from tkinter import filedialog
from datetime import datetime, timedelta
from collections import OrderedDict

class TimerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("定时提示音程序")
        self.root.geometry("400x400")
        self.root.resizable(False, False)
        
        # 初始化pygame用于播放音效，使用更高的音质设置
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        
        # 程序状态变量
        self.running = False
        self.timer_thread = None
        self.stop_event = threading.Event()
        
        # 数据统计变量
        self.alert_times = []  # 记录每次提示的时间
        self.session_start_time = None  # 本次会话开始时间
        self.total_run_time = 0  # 总运行时间（秒）
        self.current_interval_start_time = None  # 当前随机片段开始时间
        self.last_interval_duration = 0  # 上个随机片段的持续时间
        
        # 纯工作时间记录
        self.pure_work_time = 0  # 纯工作时间（不包括暂停和休息）
        self.work_start_time = None  # 当前工作开始时间
        
        self.work_sessions = []  # 记录工作时间段 [{'start': timestamp, 'end': timestamp, 'duration': seconds}]
        self.current_work_session_start = None  # 当前工作时间段开始时间
        self.stats_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "timer_stats.json")
        self.daily_stats = {}  # 初始化为空字典
        self.load_daily_stats()  # 加载每日统计数据
        
        # 创建UI元素
        self.create_widgets()
        
        # 设置默认参数
        self.work_duration = 90 * 60  # 90分钟工作时间（秒）
        self.break_duration = 20 * 60  # 20分钟休息时间（秒）
        self.min_interval = 3 * 60  # 最小提示间隔（秒）
        self.max_interval = 5 * 60  # 最大提示间隔（秒）
        
        # 尝试加载提示音
        try:
            self.alert_sound = pygame.mixer.Sound("alert.wav")
            # 为外部音频文件设置音量
            self.alert_sound.set_volume(1.0)
        except:
            print("警告：未找到提示音文件 'alert.wav'，将使用默认系统声音")
            # 创建一个简单的提示音作为默认
            self.create_default_sound()
    
    def create_default_sound(self):
        # 创建一个柔和的提示音作为默认
        sample_rate = 44100
        duration = 1.5  # 1.5秒
        # 使用较低的频率（320Hz）使声音更柔和
        frequency = 320
        # 创建缓冲区
        buf = bytearray(int(sample_rate * duration))
        
        # 生成带有淡入淡出效果的正弦波
        for i in range(len(buf)):
            # 计算当前时间点
            t = i / sample_rate
            # 应用淡入淡出效果（ADSR包络）
            if t < 0.3:  # 淡入阶段
                amplitude = t / 0.3
            elif t > duration - 0.5:  # 淡出阶段
                amplitude = (duration - t) / 0.5
            else:  # 持续阶段
                amplitude = 1.0
            
            # 提高音量（最大值为120而不是80）
            value = int(120 * amplitude * math.sin(t * frequency * 2 * math.pi))
            # 居中在128
            buf[i] = 128 + value
        
        self.alert_sound = pygame.mixer.Sound(buf)
    
    def create_widgets(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题标签
        title_label = ttk.Label(main_frame, text="定时提示音程序", font=("SimHei", 16, "bold"))
        title_label.pack(pady=10)
        
        # 状态标签
        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, font=("SimHei", 12))
        status_label.pack(pady=5)
        
        # 计时器标签（显示当前随机片段运行时长）
        self.timer_var = tk.StringVar(value="00:00:00")
        timer_label = ttk.Label(main_frame, textvariable=self.timer_var, font=("SimHei", 24))
        timer_label.pack(pady=10)
        
        # 下一次提示时间标签
        self.next_alert_var = tk.StringVar(value="--:--:--")
        next_alert_label = ttk.Label(main_frame, text="下一次提示时间：")
        next_alert_label.pack()
        next_alert_time = ttk.Label(main_frame, textvariable=self.next_alert_var, font=("SimHei", 12))
        next_alert_time.pack()
        
        # 上个随机片段运行时长标签
        self.last_interval_var = tk.StringVar(value="00:00:00")
        last_interval_label = ttk.Label(main_frame, text="上个片段运行时长：")
        last_interval_label.pack()
        last_interval_time = ttk.Label(main_frame, textvariable=self.last_interval_var, font=("Arial", 12))
        last_interval_time.pack()
        
        # 程序总运行时长标签
        self.total_runtime_var = tk.StringVar(value="00:00:00")
        total_runtime_label = ttk.Label(main_frame, text="程序总运行时长：")
        total_runtime_label.pack()
        total_runtime_time = ttk.Label(main_frame, textvariable=self.total_runtime_var, font=("Arial", 12))
        total_runtime_time.pack()
        
        # 控制按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        self.start_stop_button = ttk.Button(button_frame, text="启动/暂停", command=self.toggle_timer, width=15)
        self.start_stop_button.pack(side=tk.LEFT, padx=5)
        
        quit_button = ttk.Button(button_frame, text="退出", command=self.quit_app, width=15)
        quit_button.pack(side=tk.LEFT, padx=5)
        
        # 新增功能按钮
        new_button_frame = ttk.Frame(main_frame)
        new_button_frame.pack(pady=5)
        
        self.end_fragment_button = ttk.Button(new_button_frame, text="结束小循环", command=self.end_current_fragment, width=15)
        self.end_fragment_button.pack(side=tk.LEFT, padx=5)

        self.end_cycle_button = ttk.Button(new_button_frame, text="结束大循环", command=self.end_current_cycle, width=15)
        self.end_cycle_button.pack(side=tk.LEFT, padx=5)
        
        # 数据统计按钮
        stats_frame = ttk.Frame(main_frame)
        stats_frame.pack(pady=5)
        
        export_button = ttk.Button(stats_frame, text="导出统计数据", command=self.export_stats, width=15)
        export_button.pack(side=tk.LEFT, padx=5)
        
        view_stats_button = ttk.Button(stats_frame, text="查看统计数据", command=self.view_stats, width=15)
        view_stats_button.pack(side=tk.LEFT, padx=5)
        
        # 版权信息
        copyright_label = ttk.Label(main_frame, text="© 2025 定时提示音程序", font=("SimHei", 8))
        copyright_label.pack(side=tk.BOTTOM, pady=5)
    
    def toggle_timer(self):
        if not self.running:
            self.start_timer()
        else:
            self.pause_timer()
    
    def start_timer(self):
        self.running = True
        self.start_stop_button.config(text="暂停")
        self.status_var.set("运行中")
        
        # 记录工作开始时间
        self.work_start_time = time.time()
        
        # 如果是首次启动，记录会话开始时间
        if not self.session_start_time:
            self.session_start_time = time.time()
            self.current_interval_start_time = time.time()
            self.current_work_session_start = time.time()  # 记录工作时间段开始
            # 重置上个片段运行时长
            self.last_interval_duration = 0
            self.update_last_interval_display(self.last_interval_duration)
        else:
            # 从暂停状态恢复，只更新当前片段开始时间，保持会话开始时间不变
            # 累计之前的运行时间
            if hasattr(self, 'pause_start_time'):
                pause_duration = time.time() - self.pause_start_time
                # 调整session_start_time以排除暂停时间
                self.session_start_time += pause_duration
                delattr(self, 'pause_start_time')
            self.current_interval_start_time = time.time()
            self.current_work_session_start = time.time()  # 重新开始工作时间段
        
        # 重置停止事件
        self.stop_event.clear()
        
        # 创建并启动计时器线程
        self.timer_thread = threading.Thread(target=self.timer_loop)
        self.timer_thread.daemon = True
        self.timer_thread.start()
    
    def pause_timer(self):
        """暂停计时器（不清空数据）"""
        if self.running:
            self.running = False
            self.start_stop_button.config(text="启动/暂停")
            self.status_var.set("已暂停")
            self.stop_event.set()
            
            # 累计纯工作时间
            if self.work_start_time:
                self.pure_work_time += time.time() - self.work_start_time
                self.work_start_time = None
            
            # 记录暂停开始时间，用于计算暂停时长
            self.pause_start_time = time.time()
            
            # 记录当前工作时间段结束
            if self.current_work_session_start:
                work_session = {
                    'start': self.current_work_session_start,
                    'end': time.time(),
                    'duration': time.time() - self.current_work_session_start
                }
                self.work_sessions.append(work_session)
                self.current_work_session_start = None
            
            # 不更新total_run_time，保持运行时长连续性
    
    def stop_timer(self):
        """完全停止计时器（用于退出时）"""
        if self.running:
            self.running = False
            self.start_stop_button.config(text="启动/暂停")
            self.status_var.set("已停止")
            self.stop_event.set()
            
            # 更新总运行时间
            if self.session_start_time:
                self.total_run_time += time.time() - self.session_start_time
                self.update_daily_stats()
            
            # 重置计时器显示
            self.timer_var.set("00:00:00")
            self.next_alert_var.set("--:--:--")

    def end_current_fragment(self):
        """结束当前随机片段"""
        if self.running:
            self.status_var.set("当前随机片段已结束，即将开始新的片段。")
            self.play_alert()
            # 计算当前片段持续时间并保存为上个片段时长
            if self.current_interval_start_time:
                current_time = time.time()
                self.last_interval_duration = current_time - self.current_interval_start_time
                self.update_last_interval_display(self.last_interval_duration)
                # 重置当前随机片段开始时间
                self.current_interval_start_time = current_time
            self.status_var.set("运行中")
        else:
            self.status_var.set("计时器未运行，无法结束当前片段。")

    def end_current_cycle(self):
        """结束当前90分钟循环"""
        if self.running:
            self.status_var.set("当前90分钟循环已结束，进入休息时间。")
            self.play_alert()
            # 不调用stop_timer，而是直接进入休息倒计时
            self.start_break_countdown() # 进入休息倒计时
        else:
            self.status_var.set("计时器未运行，无法结束当前循环。")
    
    def timer_loop(self):
        start_time = time.time()
        next_alert_time = start_time + random.randint(self.min_interval, self.max_interval)
        
        # 更新下一次提示时间显示
        self.update_next_alert_display(next_alert_time)
        
        # 初始化当前随机片段开始时间
        self.current_interval_start_time = time.time()
        
        while self.running and not self.stop_event.is_set():
            current_time = time.time()
            
            # 计算当前累计工作时间
            current_total_work_time = self.pure_work_time
            if self.work_start_time:
                current_total_work_time += (current_time - self.work_start_time)
            
            # 检查是否达到90分钟的倍数（90分钟、180分钟、270分钟...）
            current_cycle = int(current_total_work_time // self.work_duration) + 1
            previous_cycle = int(self.pure_work_time // self.work_duration) + 1
            
            # 如果进入了新的90分钟周期，触发休息
            if current_cycle > previous_cycle:
                self.play_alert(3)  # 进入休息时播放三次提示音
                self.start_break_countdown()
                break  # 退出timer_loop，等待用户手动重新启动
            
            # 检查是否到了提示时间
            if current_time >= next_alert_time:
                self.play_alert()  # 小循环提示音播放一次
                # 计算当前片段持续时间并保存为上个片段时长
                if self.current_interval_start_time:
                    self.last_interval_duration = current_time - self.current_interval_start_time
                    self.update_last_interval_display(self.last_interval_duration)
                # 计算下一次提示时间
                next_interval = random.randint(self.min_interval, self.max_interval)
                next_alert_time = current_time + next_interval
                # 更新下一次提示时间显示
                self.update_next_alert_display(next_alert_time)
                # 重置当前随机片段开始时间
                self.current_interval_start_time = current_time
            
            # 更新工作/休息周期计时器（不再显示在主计时器上）
            elapsed = current_time - start_time
            # 在休息时间内不更新主计时器，保持显示当前随机片段运行时长
            
            # 更新当前随机片段运行时长（显示在计时器标签上）
            if self.current_interval_start_time:
                current_interval_elapsed = current_time - self.current_interval_start_time
                self.update_timer_display(current_interval_elapsed)
            
            # 更新程序总运行时长（只计算纯工作时间）
            if self.work_start_time:
                current_work_time = self.pure_work_time + (current_time - self.work_start_time)
                self.update_total_runtime_display(current_work_time)
            else:
                self.update_total_runtime_display(self.pure_work_time)
            
            # 短暂休眠以减少CPU使用
            time.sleep(0.1)
    
    def start_break_countdown(self):
        # 累计纯工作时间
        if self.work_start_time:
            self.pure_work_time += time.time() - self.work_start_time
            self.work_start_time = None
        
        # 暂停主计时器
        self.running = False
        self.stop_event.set()
        
        # 进入休息倒计时
        self.status_var.set("休息时间")
        break_end_time = time.time() + self.break_duration
        
        # 创建一个单独的倒计时窗口
        countdown_window = tk.Toplevel(self.root)
        countdown_window.title("休息倒计时")
        countdown_window.geometry("350x200")
        countdown_window.resizable(False, False)
        
        # 添加倒计时标签
        countdown_label = ttk.Label(countdown_window, text="休息时间剩余：", font=("Arial", 12))
        countdown_label.pack(pady=10)
        
        countdown_var = tk.StringVar(value=f"{self.break_duration // 60}:00")
        countdown_time = ttk.Label(countdown_window, textvariable=countdown_var, font=("SimHei", 24))
        countdown_time.pack(pady=10)
        
        # 添加手动结束休息按钮
        end_break_button = ttk.Button(countdown_window, text="结束休息", 
                                    command=lambda: self.end_break_early(countdown_window, break_end_time))
        end_break_button.pack(pady=10)
        
        # 休息结束标志
        self.break_ended = False
        
        def update_countdown():
            if not self.break_ended:
                remaining = break_end_time - time.time()
                if remaining <= 0:
                    self.end_break_naturally(countdown_window)
                    return
                
                # 更新倒计时显示
                hours, remainder = divmod(int(remaining), 3600)
                minutes, seconds = divmod(remainder, 60)
                countdown_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
                
                # 继续更新
                countdown_window.after(100, update_countdown)
        
        # 开始倒计时更新
        update_countdown()
    
    def end_break_early(self, countdown_window, break_end_time):
        """手动结束休息"""
        self.break_ended = True
        countdown_window.destroy()
        self.finish_break()
    
    def end_break_naturally(self, countdown_window):
        """自然结束休息（时间到）"""
        self.break_ended = True
        countdown_window.destroy()
        self.finish_break()
    
    def finish_break(self):
        """休息结束后的处理"""
        # 播放提示音三次
        self.play_alert(3)
        
        # 更新状态为休息结束，需要手动重新启动
        self.status_var.set("休息结束，请点击启动按钮继续工作")
        
        # 重置按钮状态
        self.start_stop_button.config(text="启动/暂停")
        
        # 重置计时器显示
        self.timer_var.set("00:00:00")
        self.next_alert_var.set("--:--:--")
        
        # 不重置pure_work_time，保持累计工作时间的连续性
        # 只重置当前工作时间段相关的变量
        self.work_start_time = None
        
        # 不重置session_start_time，保持程序总运行时长的连续性
    
    def update_timer_display(self, elapsed_seconds):
        """更新计时器显示（当前随机片段运行时长）"""
        hours, remainder = divmod(int(elapsed_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.timer_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def update_next_alert_display(self, next_time):
        next_time_str = datetime.fromtimestamp(next_time).strftime("%H:%M:%S")
        self.next_alert_var.set(next_time_str)
    
    def update_last_interval_display(self, elapsed_seconds):
        """更新上个随机片段运行时长显示"""
        hours, remainder = divmod(int(elapsed_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.last_interval_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def update_total_runtime_display(self, elapsed_seconds):
        hours, remainder = divmod(int(elapsed_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.total_runtime_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def play_alert(self, repeat_count=1):
        try:
            # 记录提示时间
            alert_time = time.time()
            self.alert_times.append(alert_time)
            
            # 在单独的线程中播放提示音，避免阻塞主线程
            threading.Thread(target=self._play_sound, args=(repeat_count,)).start()
        except Exception as e:
            print(f"播放提示音时出错: {e}")
    
    def _play_sound(self, repeat_count=1):
        try:
            # 设置音量为最大值
            self.alert_sound.set_volume(1.0)
            
            for i in range(repeat_count):
                self.alert_sound.play()
                if i < repeat_count - 1:  # 如果不是最后一次播放，等待一段时间
                    time.sleep(1.0)  # 间隔1秒
        except Exception as e:
            print(f"播放提示音时出错: {e}")
    
    def quit_app(self):
        # 停止计时器并保存当前会话的运行时长
        if self.running:
            self.running = False
            self.stop_event.set()
            
            # 累计纯工作时间
            if self.work_start_time:
                self.pure_work_time += time.time() - self.work_start_time
                self.work_start_time = None
            
            # 计算并累计当前会话的运行时长
            if self.session_start_time:
                current_session_time = time.time() - self.session_start_time
                self.total_run_time += current_session_time
                
                # 记录最后一个工作时间段
                if self.current_work_session_start:
                    work_session = {
                        'start': self.current_work_session_start,
                        'end': time.time(),
                        'duration': time.time() - self.current_work_session_start
                    }
                    self.work_sessions.append(work_session)
                    self.current_work_session_start = None
        
        # 等待线程结束
        if self.timer_thread and self.timer_thread.is_alive():
            self.timer_thread.join(1.0)  # 等待最多1秒
        
        # 更新并保存每日统计数据
        if self.total_run_time > 0 or self.alert_times:
            self.finalize_daily_stats()
        else:
            self.save_daily_stats()
        
        # 退出pygame
        pygame.mixer.quit()
        # 退出应用
        self.root.destroy()
    
    # 数据统计相关方法
    def seconds_to_hms(self, seconds):
        """将秒数转换为时分秒格式字符串"""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def hms_to_seconds(self, hms_str):
        """将时分秒格式字符串转换为秒数"""
        try:
            parts = hms_str.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
            return 0
        except (ValueError, AttributeError):
            return 0
    
    def load_daily_stats(self):
        """加载每日统计数据"""
        try:
            with open(self.stats_file, "r", encoding="utf-8") as f:
                self.daily_stats = json.load(f)
                # 兼容旧格式：如果total_time是数字，转换为时分秒格式
                for date, data in self.daily_stats.items():
                    if isinstance(data.get("total_time"), (int, float)):
                        data["total_time"] = self.seconds_to_hms(data["total_time"])
                    # 兼容旧格式：如果work_sessions中的duration是数字，转换为时分秒格式
                    if "work_sessions" in data:
                        for session in data["work_sessions"]:
                            if isinstance(session.get("duration"), (int, float)):
                                session["duration"] = self.seconds_to_hms(session["duration"])
        except FileNotFoundError:
            self.daily_stats = {}
        except json.JSONDecodeError:
            self.daily_stats = {}
        except Exception as e:
            print(f"加载统计数据出错: {e}")
            self.daily_stats = {}
    
    def save_daily_stats(self):
        """保存每日统计数据"""
        try:
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(self.daily_stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存统计数据出错: {e}")
    
    def update_daily_stats(self):
        """更新每日统计数据"""
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.daily_stats:
            self.daily_stats[today] = {"total_time": "00:00:00", "alert_times": []}
        
        # 更新总时间（使用纯工作时间，转换为时分秒格式）
        current_total_seconds = self.hms_to_seconds(self.daily_stats[today].get("total_time", "00:00:00"))
        new_total_seconds = current_total_seconds + self.pure_work_time
        self.daily_stats[today]["total_time"] = self.seconds_to_hms(new_total_seconds)
        
        # 更新提示时间
        for alert_time in self.alert_times:
            alert_time_str = datetime.fromtimestamp(alert_time).strftime("%H:%M:%S")
            self.daily_stats[today]["alert_times"].append(alert_time_str)
        
        # 更新工作时间段
        if "work_sessions" not in self.daily_stats[today]:
            self.daily_stats[today]["work_sessions"] = []
        
        for session in self.work_sessions:
            session_data = {
                'start_time': datetime.fromtimestamp(session['start']).strftime("%H:%M:%S"),
                'end_time': datetime.fromtimestamp(session['end']).strftime("%H:%M:%S"),
                'duration': self.seconds_to_hms(session['duration'])
            }
            self.daily_stats[today]["work_sessions"].append(session_data)
        
        # 只在程序退出时重置会话数据，其他时候保持运行时长连续性
        self.total_run_time = 0
        self.alert_times = []
        self.work_sessions = []  # 重置工作时间段
        # 不重置session_start_time，保持运行时长连续性
        
        # 保存数据
        self.save_daily_stats()
    
    def finalize_daily_stats(self):
        """程序退出时最终保存每日统计数据并重置所有会话数据"""
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.daily_stats:
            self.daily_stats[today] = {"total_time": "00:00:00", "alert_times": []}
        
        # 更新总时间（使用纯工作时间，转换为时分秒格式）
        current_total_seconds = self.hms_to_seconds(self.daily_stats[today].get("total_time", "00:00:00"))
        new_total_seconds = current_total_seconds + self.pure_work_time
        self.daily_stats[today]["total_time"] = self.seconds_to_hms(new_total_seconds)
        
        # 更新提示时间
        for alert_time in self.alert_times:
            alert_time_str = datetime.fromtimestamp(alert_time).strftime("%H:%M:%S")
            self.daily_stats[today]["alert_times"].append(alert_time_str)
        
        # 更新工作时间段
        if "work_sessions" not in self.daily_stats[today]:
            self.daily_stats[today]["work_sessions"] = []
        
        for session in self.work_sessions:
            session_data = {
                'start_time': datetime.fromtimestamp(session['start']).strftime("%H:%M:%S"),
                'end_time': datetime.fromtimestamp(session['end']).strftime("%H:%M:%S"),
                'duration': self.seconds_to_hms(session['duration'])
            }
            self.daily_stats[today]["work_sessions"].append(session_data)
        
        # 程序退出时完全重置所有会话数据
        self.total_run_time = 0
        self.alert_times = []
        self.work_sessions = []
        self.session_start_time = None
        self.current_work_session_start = None
        
        # 保存数据
        self.save_daily_stats()
    
    def export_stats(self):
        """导出统计数据到文件"""
        # 确保数据是最新的
        if self.running and self.session_start_time:
            current_run_time = time.time() - self.session_start_time
            temp_total = self.total_run_time + current_run_time
        else:
            temp_total = self.total_run_time
        
        # 准备导出数据
        export_data = {
            "daily_stats": self.daily_stats,
            "current_session": {
                "start_time": datetime.fromtimestamp(self.session_start_time).strftime("%Y-%m-%d %H:%M:%S") if self.session_start_time else None,
                "run_time": temp_total,
                "alert_times": [datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S") for t in self.alert_times]
            }
        }
        
        # 选择保存位置
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
            initialdir=os.path.dirname(os.path.abspath(__file__)),
            title="保存统计数据"
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                self.status_var.set(f"数据已导出到: {os.path.basename(file_path)}")
            except Exception as e:
                self.status_var.set(f"导出数据出错: {e}")
    
    def view_stats(self):
        """查看统计数据（使用matplotlib进行可视化）"""
        # 创建新窗口
        stats_window = tk.Toplevel(self.root)
        stats_window.title("统计数据")
        stats_window.geometry("700x500")
        stats_window.resizable(True, True)
        
        # 创建选项卡
        notebook = ttk.Notebook(stats_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 当前会话选项卡
        current_frame = ttk.Frame(notebook, padding=10)
        notebook.add(current_frame, text="当前会话")
        
        # 历史数据选项卡
        history_frame = ttk.Frame(notebook, padding=10)
        notebook.add(history_frame, text="历史数据")
        
        # 图表分析选项卡
        chart_frame = ttk.Frame(notebook, padding=10)
        notebook.add(chart_frame, text="图表分析")
        
        # 填充当前会话数据
        if self.running and self.session_start_time:
            current_run_time = time.time() - self.session_start_time
            temp_total = self.total_run_time + current_run_time
        else:
            temp_total = self.total_run_time
        
        hours, remainder = divmod(int(temp_total), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        # 创建当前会话信息框
        info_frame = ttk.LabelFrame(current_frame, text="会话信息", padding=10)
        info_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(info_frame, text=f"会话开始时间: {datetime.fromtimestamp(self.session_start_time).strftime('%Y-%m-%d %H:%M:%S') if self.session_start_time else '未开始'}", font=("SimHei", 10)).pack(anchor="w", pady=2)
        ttk.Label(info_frame, text=f"运行时长: {hours:02d}:{minutes:02d}:{seconds:02d}", font=("SimHei", 10)).pack(anchor="w", pady=2)
        ttk.Label(info_frame, text=f"提示次数: {len(self.alert_times)}", font=("SimHei", 10)).pack(anchor="w", pady=2)
        
        # 提示时间列表和分布图框架
        alert_frame = ttk.Frame(current_frame)
        alert_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 提示时间列表
        alert_list_frame = ttk.LabelFrame(alert_frame, text="提示时间列表", padding=10)
        alert_list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 创建滚动条
        scrollbar = ttk.Scrollbar(alert_list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建列表框
        alert_listbox = tk.Listbox(alert_list_frame, yscrollcommand=scrollbar.set, font=("SimHei", 9))
        alert_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=alert_listbox.yview)
        
        # 填充提示时间
        for i, alert_time in enumerate(self.alert_times):
            alert_time_str = datetime.fromtimestamp(alert_time).strftime("%Y-%m-%d %H:%M:%S")
            alert_listbox.insert(tk.END, f"{i+1}. {alert_time_str}")
        
        # 当前会话提示时间分布图
        if len(self.alert_times) > 0:
            alert_chart_frame = ttk.LabelFrame(alert_frame, text="提示时间分布", padding=10)
            alert_chart_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
            
            # 创建图表
            fig, ax = plt.subplots(figsize=(4, 3), dpi=80)
            
            # 提取小时和分钟
            times = [datetime.fromtimestamp(t) for t in self.alert_times]
            hours = [t.hour + t.minute/60 for t in times]
            
            # 绘制散点图
            ax.scatter(range(len(hours)), hours, color='blue', s=50, alpha=0.7)
            ax.set_xlabel('提示序号')
            ax.set_ylabel('时间 (小时)')
            ax.set_title('当前会话提示时间分布')
            ax.grid(True, linestyle='--', alpha=0.7)
            
            # 设置y轴刻度为小时格式
            ax.set_yticks([i for i in range(24)])
            ax.set_yticklabels([f"{i:02d}:00" for i in range(24)])
            
            # 添加到Tkinter窗口
            canvas = FigureCanvasTkAgg(fig, master=alert_chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            plt.close(fig)  # 避免显示独立窗口
        
        # 填充历史数据
        # 创建历史数据表格
        history_table_frame = ttk.LabelFrame(history_frame, text="每日使用统计", padding=10)
        history_table_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 创建表格头部
        columns = ("日期", "总运行时长", "提示次数", "工作时间段数")
        tree = ttk.Treeview(history_table_frame, columns=columns, show="headings")
        
        # 设置列宽和对齐方式
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, anchor="center", width=100)
        
        # 添加滚动条
        tree_scroll = ttk.Scrollbar(history_table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)
        
        # 填充历史数据
        for date, data in sorted(self.daily_stats.items(), reverse=True):
            time_str = data.get("total_time", "00:00:00")
            alert_count = len(data.get('alert_times', []))
            work_session_count = len(data.get('work_sessions', []))
            tree.insert("", tk.END, values=(date, time_str, alert_count, work_session_count))
        
        # 填充图表分析选项卡
        if len(self.daily_stats) > 0:
            # 创建上下分栏
            top_chart_frame = ttk.Frame(chart_frame)
            top_chart_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 5))
            
            bottom_chart_frame = ttk.Frame(chart_frame)
            bottom_chart_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=(5, 0))
            
            # 在上部分创建左右分栏
            left_chart_frame = ttk.Frame(top_chart_frame)
            left_chart_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
            
            right_chart_frame = ttk.Frame(top_chart_frame)
            right_chart_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
            
            # 每日运行时长趋势图
            runtime_frame = ttk.LabelFrame(left_chart_frame, text="每日运行时长趋势", padding=10)
            runtime_frame.pack(fill=tk.BOTH, expand=True, pady=5)
            
            # 准备数据
            dates = []
            runtimes = []
            
            # 按日期排序
            for date, data in sorted(self.daily_stats.items()):
                dates.append(date)
                # 转换为小时
                total_seconds = self.hms_to_seconds(data.get("total_time", "00:00:00"))
                runtimes.append(total_seconds / 3600)
            
            # 创建图表
            fig1, ax1 = plt.subplots(figsize=(4, 3), dpi=80)
            ax1.plot(dates, runtimes, marker='o', linestyle='-', color='blue', linewidth=2, markersize=6)
            ax1.set_xlabel('日期')
            ax1.set_ylabel('运行时长 (小时)')
            ax1.set_title('每日运行时长趋势')
            ax1.grid(True, linestyle='--', alpha=0.7)
            
            # 旋转x轴标签以避免重叠
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            # 添加到Tkinter窗口
            canvas1 = FigureCanvasTkAgg(fig1, master=runtime_frame)
            canvas1.draw()
            canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            plt.close(fig1)
            
            # 提示频率分析图
            alert_freq_frame = ttk.LabelFrame(right_chart_frame, text="提示频率分析", padding=10)
            alert_freq_frame.pack(fill=tk.BOTH, expand=True, pady=5)
            
            # 准备数据
            alert_counts = []
            
            for date, data in sorted(self.daily_stats.items()):
                alert_counts.append(len(data.get('alert_times', [])))
            
            # 创建图表
            fig2, ax2 = plt.subplots(figsize=(4, 3), dpi=80)
            ax2.bar(dates, alert_counts, color='green', alpha=0.7)
            ax2.set_xlabel('日期')
            ax2.set_ylabel('提示次数')
            ax2.set_title('每日提示频率')
            ax2.grid(True, linestyle='--', alpha=0.7, axis='y')
            
            # 旋转x轴标签以避免重叠
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            # 添加到Tkinter窗口
            canvas2 = FigureCanvasTkAgg(fig2, master=alert_freq_frame)
            canvas2.draw()
            canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            plt.close(fig2)
            
            # 工作时间段分布图
            work_session_frame = ttk.LabelFrame(bottom_chart_frame, text="工作时间段分布", padding=10)
            work_session_frame.pack(fill=tk.BOTH, expand=True, pady=5)
            
            # 创建工作时间段可视化
            self.create_work_session_chart(work_session_frame)
    
    def create_work_session_chart(self, parent_frame):
        """创建工作时间段分布图表"""
        # 准备数据：收集所有工作时间段
        all_sessions = []
        for date, data in sorted(self.daily_stats.items()):
            work_sessions = data.get('work_sessions', [])
            for session in work_sessions:
                # 解析时间
                start_time = datetime.strptime(f"{date} {session['start_time']}", "%Y-%m-%d %H:%M:%S")
                end_time = datetime.strptime(f"{date} {session['end_time']}", "%Y-%m-%d %H:%M:%S")
                duration_seconds = self.hms_to_seconds(session.get('duration', '00:00:00'))
                all_sessions.append({
                    'date': date,
                    'start': start_time,
                    'end': end_time,
                    'duration': duration_seconds
                })
        
        if not all_sessions:
            # 如果没有工作时间段数据，显示提示信息
            ttk.Label(parent_frame, text="暂无工作时间段数据", font=("SimHei", 12)).pack(expand=True)
            return
        
        # 创建图表
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3), dpi=80)
        
        # 左图：每日工作时间段时间线
        dates = sorted(list(set([s['date'] for s in all_sessions])))
        y_positions = {date: i for i, date in enumerate(dates)}
        
        for session in all_sessions:
            y_pos = y_positions[session['date']]
            start_hour = session['start'].hour + session['start'].minute / 60
            end_hour = session['end'].hour + session['end'].minute / 60
            duration_hours = session['duration'] / 3600
            
            # 绘制时间段条形图
            ax1.barh(y_pos, duration_hours, left=start_hour, height=0.6, 
                    alpha=0.7, color='skyblue', edgecolor='navy')
        
        ax1.set_yticks(range(len(dates)))
        ax1.set_yticklabels(dates)
        ax1.set_xlabel('时间 (小时)')
        ax1.set_title('每日工作时间段分布')
        ax1.set_xlim(0, 24)
        ax1.set_xticks(range(0, 25, 4))
        ax1.set_xticklabels([f"{i:02d}:00" for i in range(0, 25, 4)])
        ax1.grid(True, axis='x', linestyle='--', alpha=0.7)
        
        # 右图：工作时间段时长分布
        durations = [s['duration'] / 3600 for s in all_sessions]  # 转换为小时
        ax2.hist(durations, bins=10, alpha=0.7, color='lightgreen', edgecolor='darkgreen')
        ax2.set_xlabel('时间段时长 (小时)')
        ax2.set_ylabel('频次')
        ax2.set_title('工作时间段时长分布')
        ax2.grid(True, axis='y', linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        
        # 添加到Tkinter窗口
        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        plt.close(fig)


if __name__ == "__main__":
    root = tk.Tk()
    app = TimerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.quit_app)  # 处理窗口关闭事件
    root.mainloop()