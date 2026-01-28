"""
メモリ開放ツール
"""
import tkinter as tk
import psutil
import json
import gc
import ctypes
from ctypes import wintypes
import threading
import subprocess
import pystray
import winreg
import sys
import os
from tkinter import ttk, messagebox
from PIL import Image, ImageDraw
from collections import deque

class GraphDrawer:
    """
    メモリ・CPU使用率のグラフ描画を担当するクラス
    """
    def __init__(self, canvas):
        self.canvas = canvas
        self.margin_bottom = 20
        self.margin_left = 35

    def draw(self, memory_history, cpu_history):
        """履歴データを受け取ってグラフを描画する"""
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        # まだ描画されていない、または最小化されている場合はスキップ
        if w <= 1: return

        graph_h = h - self.margin_bottom
        graph_w = w - self.margin_left

        # --- 縦軸ラベル描画 ---
        self.canvas.create_text(self.margin_left - 5, 5, text="100%", anchor="e", fill="#666666", font=("Helvetica", 8))
        self.canvas.create_text(self.margin_left - 5, graph_h * 0.5, text="50%", anchor="e", fill="#666666", font=("Helvetica", 8))
        self.canvas.create_text(self.margin_left - 5, graph_h - 5, text="0%", anchor="e", fill="#666666", font=("Helvetica", 8))

        # --- 凡例描画 ---
        self.canvas.create_text(self.margin_left + 10, 10, text="― CPU", anchor="w", fill="#ff9900", font=("Helvetica", 8, "bold"))
        self.canvas.create_text(self.margin_left + 60, 10, text="― メモリ", anchor="w", fill="#496d89", font=("Helvetica", 8, "bold"))

        # --- グリッド線を描画 (背景) ---
        # 横線 (20%刻み)
        for i in range(1, 5): # 20%, 40%, 60%, 80%
            y = graph_h * (i * 0.2)
            # 80%ライン(上から20%)は警告色、それ以外はグレー
            color = "#ffcccc" if i == 1 else "#e0e0e0"
            self.canvas.create_line(self.margin_left, y, w, y, fill=color, dash=(2, 2))

        # 縦線 (10秒刻み)
        for i in range(1, 6):
            x = self.margin_left + (graph_w / 6) * i
            self.canvas.create_line(x, 0, x, graph_h, fill="#e0e0e0", dash=(2, 2))
            
        # --- 横軸ラベル描画 ---
        self.canvas.create_text(self.margin_left, h - 10, text="60秒前", anchor="w", fill="#666666", font=("Helvetica", 8))
        self.canvas.create_text(w - 5, h - 10, text="現在", anchor="e", fill="#666666", font=("Helvetica", 8))

        # グラフ線の描画
        self._draw_line(cpu_history, graph_w, graph_h, color="#ff9900", width=1)
        self._draw_line(memory_history, graph_w, graph_h, width=2, use_segments=True)

    def _draw_line(self, history, graph_w, graph_h, color=None, width=1, use_segments=False):
        data = list(history)
        if len(data) < 2: return

        max_points = history.maxlen
        step_x = graph_w / (max_points - 1)

        for i in range(len(data) - 1):
            val1 = data[i]
            val2 = data[i+1]
            x1 = self.margin_left + i * step_x
            y1 = graph_h - (val1 / 100 * graph_h)
            x2 = self.margin_left + (i + 1) * step_x
            y2 = graph_h - (val2 / 100 * graph_h)

            draw_color = color
            if use_segments:
                if val2 >= 80: draw_color = "#cc3333"
                elif val2 >= 50: draw_color = "#e6b800"
                else: draw_color = "#496d89"
            
            self.canvas.create_line(x1, y1, x2, y2, fill=draw_color, width=width)

class MemoryCleanerApp:
    """
    メモリ解放を行うデスクトップGUI
    """
    def __init__(self, root):
        self.root = root
        self.root.title("メモリ解放ツール")
        self.root.geometry("380x640")
        self.root.resizable(False, False)

        # 自動解放が実行中かどうかのフラグ
        self.is_auto_free_running = False
        # TkinterのafterメソッドのジョブIDを保持
        self.auto_free_job_id = None
        # メモリ情報更新用のafterジョブID
        self.update_job_id = None
        # ステータスメッセージ消去用のジョブID
        self.status_clear_job = None
        # 警告状態フラグと閾値
        self.is_warning_state = False
        self.topmost_var = tk.BooleanVar(value=False) # 最前面表示フラグ
        self.startup_var = tk.BooleanVar(value=False) # スタートアップ登録フラグ
        self.start_minimized_var = tk.BooleanVar(value=False) # 最小化起動フラグ
        self.warning_threshold_var = tk.StringVar(value="80")  # デフォルトの警告閾値
        self.interval_var = tk.StringVar(value="1") # 定期解放の間隔

        self.current_mem_percent = 0 # 現在のメモリ使用率
        self.memory_history = deque([0]*60, maxlen=60) # 履歴データ(60秒分)
        self.cpu_history = deque([0]*60, maxlen=60) # CPU履歴データ
        self.procs_cache = {} # CPU使用率計算用のプロセスキャッシュ

        self.config_file = "config.json" # 設定ファイルのパス
        self.load_config() # 設定ファイルから初期設定を読み込む

        # トレイアイコンの初期化
        self.tray_icon = None

        self.setup_ui() # GUIのウィジェットをセットアップ
        self.check_startup_status() # スタートアップ状態を確認
        self.update_memory_info() # メモリ情報の定期更新を開始

        # 起動引数チェック: 最小化オプションがあればトレイに格納
        if "--minimized" in sys.argv:
            self.minimize_to_tray()

        # 最小化イベントをフック
        self.root.bind("<Unmap>", self.check_minimize)
        # ウィンドウを閉じる際のイベントをフック
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_ui(self):
        """
        GUIのウィジェットをセットアップする
        """
        # スタイルを定義して点滅エフェクトに備える
        s = ttk.Style()
        s.configure("Flash.TFrame", background="lightblue")
        s.configure("Warning.TFrame", background="tomato")

        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- メモリ情報表示エリア ---
        # --- ↓↓↓  動作には支障はないが機種によっては表示されない場合がある ↓↓↓ ---
        self.memory_label = ttk.Label(self.main_frame, text="現在のメモリ使用率: ...", font=("Helvetica", 12))
        self.memory_label.pack(pady=5, anchor="w")
        # --- ↑↑↑ ---

        self.memory_progress = ttk.Progressbar(self.main_frame, orient="horizontal", length=300, mode="determinate")
        self.memory_progress.pack(pady=5)
        
        # --- CPU情報表示エリア ---
        self.cpu_label = ttk.Label(self.main_frame, text="CPU使用率: ...", font=("Helvetica", 12))
        self.cpu_label.pack(pady=(5, 0), anchor="w")
        self.cpu_progress = ttk.Progressbar(self.main_frame, orient="horizontal", length=300, mode="determinate")
        self.cpu_progress.pack(pady=5)

        # --- グラフ表示エリア ---
        self.graph_canvas = tk.Canvas(self.main_frame, height=120, bg="#f0f0f0", highlightthickness=1, highlightbackground="#cccccc")
        self.graph_canvas.pack(pady=5, fill=tk.X)
        self.graph_drawer = GraphDrawer(self.graph_canvas)

        # --- 上位プロセス表示エリア ---
        process_frame = ttk.LabelFrame(self.main_frame, text="メモリ使用量トップ3")
        process_frame.pack(pady=5, fill=tk.X)
        
        self.process_labels = []
        for i in range(3):
            lbl = ttk.Label(process_frame, text=f"{i+1}. ---", font=("Helvetica", 9))
            lbl.pack(anchor="w", padx=5, pady=1)
            self.process_labels.append(lbl)

        # --- CPU上位プロセス表示エリア ---
        cpu_process_frame = ttk.LabelFrame(self.main_frame, text="CPU使用率トップ3")
        cpu_process_frame.pack(pady=5, fill=tk.X)
        
        self.cpu_process_labels = []
        for i in range(3):
            lbl = ttk.Label(cpu_process_frame, text=f"{i+1}. ---", font=("Helvetica", 9))
            lbl.pack(anchor="w", padx=5, pady=1)
            self.cpu_process_labels.append(lbl)

        # --- 手動解放エリア ---
        manual_free_button = ttk.Button(self.main_frame, text="今すぐメモリを解放", command=self.free_memory)
        manual_free_button.pack(pady=(10, 5), fill=tk.X)
        
        # ステータスメッセージ表示用ラベル
        self.status_label = ttk.Label(self.main_frame, text="", font=("Helvetica", 9))
        self.status_label.pack(pady=(0, 5))
        
        # --- ユーティリティエリア ---
        utility_frame = ttk.Frame(self.main_frame)
        utility_frame.pack(pady=0, fill=tk.X)
        
        task_manager_button = ttk.Button(utility_frame, text="タスクマネージャー", command=self.open_task_manager)
        task_manager_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Checkbutton(utility_frame, text="最前面", variable=self.topmost_var, command=self.toggle_topmost).pack(side=tk.LEFT)
        ttk.Checkbutton(utility_frame, text="スタートアップ", variable=self.startup_var, command=self.update_startup_registry).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Checkbutton(utility_frame, text="最小化起動", variable=self.start_minimized_var, command=self.update_startup_registry).pack(side=tk.LEFT, padx=(5, 0))

        # --- 警告閾値設定エリア ---
        warning_frame = ttk.Frame(self.main_frame)
        warning_frame.pack(pady=5, fill=tk.X)

        ttk.Label(warning_frame, text="警告閾値(%):").pack(side=tk.LEFT)
        self.warning_threshold_entry = ttk.Entry(warning_frame, textvariable=self.warning_threshold_var, width=5)
        self.warning_threshold_entry.pack(side=tk.LEFT, padx=5)

        # --- 自動解放設定エリア ---
        auto_frame = ttk.Frame(self.main_frame)
        auto_frame.pack(pady=5, fill=tk.X, anchor="s")

        ttk.Label(auto_frame, text="定期解放の間隔(分):").pack(side=tk.LEFT)
        self.interval_entry = ttk.Entry(auto_frame, textvariable=self.interval_var, width=5)
        self.interval_entry.pack(side=tk.LEFT, padx=5)

        self.toggle_auto_button = ttk.Button(auto_frame, text="定期解放を開始", command=self.toggle_auto_free)
        self.toggle_auto_button.pack(side=tk.LEFT, expand=True, fill=tk.X)

    def update_memory_info(self):
        """
        メモリ使用率を定期的に取得し、GUIを更新する
        """
        # CPU情報の取得
        cpu_percent = psutil.cpu_percent(interval=None)
        self.cpu_history.append(cpu_percent)
        self.cpu_label.config(text=f"CPU使用率: {cpu_percent}%")
        self.cpu_progress['value'] = cpu_percent

        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        self.current_mem_percent = mem_percent
        mem_used_gb = mem.used / (1024 ** 3)
        mem_total_gb = mem.total / (1024 ** 3)

        # 履歴を更新してグラフを描画
        self.memory_history.append(mem_percent)
        self.graph_drawer.draw(self.memory_history, self.cpu_history)

        # 上位プロセスを更新 (メモリ・CPU)
        top_mem_procs, top_cpu_procs = self.get_top_processes()
        
        for i, proc in enumerate(top_mem_procs):
            if i < len(self.process_labels):
                mem_mb = proc['memory_info'].rss / (1024 * 1024)
                self.process_labels[i].config(text=f"{i+1}. {proc['name']} ({mem_mb:.1f} MB)")

        for i, proc in enumerate(top_cpu_procs):
            if i < len(self.cpu_process_labels):
                self.cpu_process_labels[i].config(text=f"{i+1}. {proc['name']} ({proc['cpu_percent']:.1f}%)")

        self.memory_label.config(text=f"メモリ使用率: {mem_percent}% ({mem_used_gb:.2f} GB / {mem_total_gb:.2f} GB)")
        self.memory_progress['value'] = mem_percent
        
        # 警告状態をチェックしてフラグを更新
        try:
            threshold = int(self.warning_threshold_var.get())
            self.is_warning_state = (mem_percent >= threshold)
        except (ValueError, AttributeError):
            # 不正な入力値の場合は警告しない
            self.is_warning_state = False
            
        # 点滅中でなければ背景スタイルを更新
        # (点滅エフェクトを優先させるため)
        if self.main_frame.cget("style") != "Flash.TFrame":
            self.update_background_style()

        # トレイアイコンが表示されている場合、アイコンとツールチップを更新
        if self.tray_icon:
            self.tray_icon.icon = self.create_icon_image(mem_percent)
            self.tray_icon.title = f"メモリ使用率: {mem_percent}%"

        # 1秒後に再度この関数を呼び出す
        self.update_job_id = self.root.after(1000, self.update_memory_info)

    def get_top_processes(self):
        """メモリとCPU使用率の高いプロセス上位3つを取得"""
        mem_list = []
        cpu_list = []
        current_procs = {}

        # プロセスを走査
        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                pid = proc.info['pid']
                name = proc.info['name']
                
                # CPU使用率計算のため、プロセスインスタンスをキャッシュから取得または新規作成
                if pid in self.procs_cache:
                    p = self.procs_cache[pid]
                else:
                    p = proc
                    # 初回呼び出し時は0.0になるため初期化のみ
                    try:
                        p.cpu_percent(interval=None)
                    except:
                        pass
                
                current_procs[pid] = p
                
                # 情報をリストに追加
                mem_list.append(proc.info)
                
                # キャッシュされたインスタンスを使ってCPU使用率を取得
                cpu_val = p.cpu_percent(interval=None)
                cpu_list.append({'name': name, 'cpu_percent': cpu_val})

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # キャッシュを更新（存在しないプロセスは削除される）
        self.procs_cache = current_procs

        # ソートして上位3件を返す
        top_mem = sorted(mem_list, key=lambda p: p['memory_info'].rss, reverse=True)[:3]
        top_cpu = sorted(cpu_list, key=lambda p: p['cpu_percent'], reverse=True)[:3]
        
        return top_mem, top_cpu

    def clean_system_memory(self):
        """Windows APIを使用して全プロセスのワーキングセットを解放する"""
        # Windows APIの定義
        psapi = ctypes.WinDLL('psapi.dll')
        kernel32 = ctypes.WinDLL('kernel32.dll')
        
        OpenProcess = kernel32.OpenProcess
        OpenProcess.restype = wintypes.HANDLE
        OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        
        EmptyWorkingSet = psapi.EmptyWorkingSet
        EmptyWorkingSet.restype = wintypes.BOOL
        EmptyWorkingSet.argtypes = (wintypes.HANDLE,)
        
        CloseHandle = kernel32.CloseHandle
        CloseHandle.restype = wintypes.BOOL
        CloseHandle.argtypes = (wintypes.HANDLE,)
        
        PROCESS_SET_QUOTA = 0x0100
        PROCESS_QUERY_INFORMATION = 0x0400
        
        # 全プロセスに対して実行
        for proc in psutil.process_iter():
            try:
                pid = proc.pid
                # 自分自身はスキップしても良いが、念のため含めても問題ない
                handle = OpenProcess(PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION, False, pid)
                if handle:
                    EmptyWorkingSet(handle)
                    CloseHandle(handle)
            except Exception:
                # アクセス拒否などは無視
                pass

    def _perform_gc_and_flash(self):
        """ガベージコレクションを実行し、ウィンドウを点滅させるヘルパーメソッド"""
        gc.collect() # Python自体のメモリ解放
        self.clean_system_memory() # システム全体のメモリ解放
        self.flash_window()
        # 解放後にメモリ情報を更新 (エフェクトに対し少し遅らせる)
        self.root.after(250, self.update_memory_info)

    def free_memory(self, from_tray=False):
        """
        ガベージコレクションを実行してメモリを解放する
        """
        try:
            # 解放前のメモリ使用量を取得
            mem_before = psutil.virtual_memory().used

            self._perform_gc_and_flash()

            # 解放後のメモリ使用量を取得
            mem_after = psutil.virtual_memory().used
            freed_mb = max(0, (mem_before - mem_after) / (1024 * 1024))
            msg = f"メモリ解放を実行しました (解放量: {freed_mb:.1f} MB)"

            if from_tray and self.tray_icon:
                self.tray_icon.notify(msg, "成功")
            else:
                self.show_status_message(msg, "#008000") # 緑色
        except Exception as e:
            if from_tray and self.tray_icon:
                self.tray_icon.notify(f"エラーが発生しました: {e}", "エラー")
            else:
                self.show_status_message(f"エラー: {e}", "#ff0000") # 赤色
            # エラー発生時もメモリ情報は更新しておく
            self.update_memory_info()

    def show_status_message(self, message, color, duration=3000):
        """UI上にステータスメッセージを表示し、一定時間後に消去する"""
        self.status_label.config(text=message, foreground=color)
        # 既存のクリアタイマーがあればキャンセル（連打対策）
        if self.status_clear_job:
            self.root.after_cancel(self.status_clear_job)
        
        self.status_clear_job = self.root.after(duration, lambda: self.status_label.config(text=""))

    def open_task_manager(self):
        """タスクマネージャーを起動する"""
        try:
            # Windowsのタスクマネージャーを起動
            subprocess.Popen("taskmgr")
        except Exception as e:
            messagebox.showerror("エラー", f"タスクマネージャーの起動に失敗しました: {e}")

    def toggle_topmost(self):
        """最前面表示を切り替える"""
        self.root.attributes('-topmost', self.topmost_var.get())

    def check_startup_status(self):
        """レジストリを確認してスタートアップ設定の状態を更新する"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            try:
                val, _ = winreg.QueryValueEx(key, "MemoryCleaner")
                self.startup_var.set(True)
                # 登録値に --minimized が含まれているか確認
                self.start_minimized_var.set("--minimized" in val)
            except FileNotFoundError:
                self.startup_var.set(False)
            finally:
                winreg.CloseKey(key)
        except Exception:
            self.startup_var.set(False)

    def update_startup_registry(self):
        """スタートアップ登録の更新（登録/解除/オプション変更）"""
        app_name = "MemoryCleaner"
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
            if self.startup_var.get():
                # 登録
                if getattr(sys, 'frozen', False):
                    # PyInstallerなどでexe化されている場合
                    app_path = f'"{sys.executable}"'
                else:
                    # Pythonスクリプトとして実行されている場合
                    app_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
                
                # 最小化オプションが有効なら引数を追加
                if self.start_minimized_var.get():
                    app_path += ' --minimized'

                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, app_path)
            else:
                # 解除
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            messagebox.showerror("エラー", f"スタートアップ設定の変更に失敗しました: {e}")

    def toggle_auto_free(self):
        """
        定期解放の開始/停止を切り替える
        """
        if self.is_auto_free_running:
            # --- 停止処理 ---
            if self.auto_free_job_id:
                self.root.after_cancel(self.auto_free_job_id)
                self.auto_free_job_id = None
            self.is_auto_free_running = False
            self.toggle_auto_button.config(text="定期解放を開始")
            self.interval_entry.config(state="normal") # 入力欄を有効化
            messagebox.showinfo("停止", "定期解放を停止しました。")
        else:
            # --- 開始処理 ---
            try:
                interval_min = int(self.interval_var.get())
                if interval_min <= 0:
                    messagebox.showwarning("入力エラー", "間隔は正の整数で指定してください。")
                    return
                
                self.is_auto_free_running = True
                self.toggle_auto_button.config(text="定期解放を停止")
                self.interval_entry.config(state="disabled") # 入力欄を無効化
                # 分単位でタイマー設定
                self.auto_free_loop(interval_min)
                messagebox.showinfo("開始", f"{interval_min}分ごとの定期解放を開始しました。")

            except ValueError:
                messagebox.showwarning("入力エラー", "間隔は半角数字で入力してください。")

    def auto_free_loop(self, interval_min):
        """
        指定された間隔でメモリ解放を繰り返す
        """
        if not self.is_auto_free_running:
            return
        
        self._perform_gc_and_flash()
        # 次の実行をスケジュールする
        self.auto_free_job_id = self.root.after(interval_min * 60 * 1000, lambda: self.auto_free_loop(interval_min))

    def flash_window(self):
        """
        ウィンドウを点滅させ可視化
        """
        self.main_frame.config(style="Flash.TFrame")
        # 200ミリ秒後に現状に基づいたスタイルに戻す
        self.root.after(200, self.update_background_style)
        
    def update_background_style(self):
        """
        現在の警告状態に基づいて背景スタイルを更新
        """
        if self.is_warning_state:
            self.main_frame.config(style="Warning.TFrame")
        else:
            self.main_frame.config(style="TFrame")

    def check_minimize(self, event):
        """
        ウィンドウの状態を監視し、最小化された場合にトレイに格納する
        """
        if self.root.state() == 'iconic':
            self.minimize_to_tray()

    def minimize_to_tray(self):
        """
        ウィンドウを非表示にし、トレイアイコンを表示する
        """
        self.root.withdraw()
        if self.tray_icon is None:
            self.run_tray_icon()

    def create_icon_image(self, usage_percent=None):
        """
        トレイアイコン用の画像を生成する
        usage_percent: メモリ使用率(0-100)。Noneの場合はデフォルト表示。
        """
        # 64x64のシンプルなアイコンを生成
        image = Image.new('RGB', (64, 64), color=(73, 109, 137))
        draw = ImageDraw.Draw(image)
        
        if usage_percent is None:
            draw.rectangle((16, 16, 48, 48), fill=(255, 255, 255))
        else:
            # メモリ使用率をバーで表示
            # 外枠
            draw.rectangle((16, 8, 48, 56), outline=(255, 255, 255), width=2)
            # バーの高さ (最大44px)
            bar_height = int(44 * (usage_percent / 100))
            # 色分け
            if usage_percent >= 80:
                fill_color = (255, 80, 80) # 赤
            elif usage_percent >= 50:
                fill_color = (255, 255, 80) # 黄
            else:
                fill_color = (80, 255, 80) # 緑
            
            draw.rectangle((19, 54 - bar_height, 45, 54), fill=fill_color)
            
        return image

    def run_tray_icon(self):
        """
        トレイアイコンを別スレッドで実行する
        """
        image = self.create_icon_image(self.current_mem_percent)
        menu = pystray.Menu(
            pystray.MenuItem("開く", self.restore_window),
            pystray.MenuItem("今すぐメモリ解放", self.free_memory_from_tray),
            pystray.MenuItem("タスクマネージャー", self.open_task_manager_from_tray),
            pystray.MenuItem("終了", self.quit_app_from_tray)
        )
        self.tray_icon = pystray.Icon("MemoryCleaner", image, "メモリ解放ツール", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def restore_window(self, icon=None, item=None):
        """トレイアイコンからウィンドウを復元する"""
        self.root.after(0, self._restore_window_impl)

    def _restore_window_impl(self):
        self.root.deiconify()
        self.root.state('normal')
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None

    def free_memory_from_tray(self, icon=None, item=None):
        """トレイからメモリ解放を実行"""
        self.root.after(0, lambda: self.free_memory(from_tray=True))

    def open_task_manager_from_tray(self, icon=None, item=None):
        """トレイからタスクマネージャーを起動"""
        self.root.after(0, self.open_task_manager)

    def quit_app_from_tray(self, icon=None, item=None):
        self.root.after(0, self.on_closing)

    def on_closing(self):
        """
        ウィンドウが閉じられるときに実行される処理
        """
        # 定期解放が実行中の場合、ユーザーに確認
        if self.is_auto_free_running:
            if not messagebox.askyesno("確認", "定期解放が実行中です。アプリケーションを終了しますか？"):
                return  # 終了をキャンセル

        # 実行中のタイマーをすべてキャンセル
        if self.update_job_id:
            self.root.after_cancel(self.update_job_id)
        if self.auto_free_job_id:
            self.root.after_cancel(self.auto_free_job_id)

        # トレイアイコンが実行中なら停止
        if self.tray_icon:
            self.tray_icon.stop()

        # 設定を保存
        self.save_config()
        # ウィンドウを破棄
        self.root.destroy()

    def load_config(self):
        """
        config.jsonから設定を読み込む
        """
        try:
            with open(self.config_file, "r") as f:
                config_data = json.load(f)
                # 設定ファイルの値があれば上書きする。なければ初期値のまま。
                self.warning_threshold_var.set(config_data.get("warning_threshold", self.warning_threshold_var.get()))
                self.interval_var.set(config_data.get("auto_free_interval", self.interval_var.get()))
                self.topmost_var.set(config_data.get("topmost", False))
                self.start_minimized_var.set(config_data.get("start_minimized", False))
                self.toggle_topmost() # 読み込んだ設定を反映
        except FileNotFoundError:
            # ファイルがない場合はデフォルト設定で作成する
            self.save_config()
        except json.JSONDecodeError:
            # 不正な形式の場合はデフォルト値が使用されるため、何もしない
            pass

    def save_config(self):
        """
        現在の設定をconfig.jsonに保存する
        """
        config_data = {
            "warning_threshold": self.warning_threshold_var.get(),
            "auto_free_interval": self.interval_var.get(),
            "topmost": self.topmost_var.get(),
            "start_minimized": self.start_minimized_var.get()
        }
        with open(self.config_file, "w") as f:
            json.dump(config_data, f, indent=4)

if __name__ == "__main__":
    root = tk.Tk()
    app = MemoryCleanerApp(root)
    root.mainloop()