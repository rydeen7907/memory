"""
メモリ開放ツール
"""
import tkinter as tk
import psutil # システム情報取得用
import json
import gc
import ctypes # Windows API呼び出し用
import threading # 非同期処理用
import subprocess # タスクマネージャー起動用
import pystray # トレイアイコン用
import sys
import os
from tkinter import ttk, messagebox
from PIL import Image, ImageDraw
from collections import deque 

# Windows固有のライブラリを条件付きでインポート
if os.name == 'nt':
    import winreg
    from ctypes import wintypes


class GraphDrawer:
    """
    メモリ・CPU使用率のグラフ描画を担当するクラス
    """
    def __init__(self, canvas):
        self.canvas = canvas
        self.margin_bottom = 20
        self.margin_left = 35
        self.prev_w = 0
        self.prev_h = 0

    def draw(self, memory_history, cpu_history):
        """履歴データを受け取ってグラフを描画する"""
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        # まだ描画されていない、または最小化されている場合はスキップ
        if w <= 1: return

        # サイズが変更された場合のみ背景を再描画
        if w != self.prev_w or h != self.prev_h:
            self.canvas.delete("all")
            self._draw_background(w, h)
            self.prev_w = w
            self.prev_h = h
        else:
            # グラフデータのみクリア（背景は残す）
            self.canvas.delete("graph_data")

        graph_h = h - self.margin_bottom
        graph_w = w - self.margin_left

        # グラフ線の描画
        self._draw_cpu_line(cpu_history, graph_w, graph_h)
        self._draw_memory_line(memory_history, graph_w, graph_h)

    def _draw_background(self, w, h):
        """背景（グリッド、ラベル）を描画"""
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

    def _draw_cpu_line(self, history, graph_w, graph_h):
        """CPUグラフを描画（単色・一括描画で最適化）"""
        data = list(history)
        if len(data) < 2: return

        max_points = history.maxlen
        step_x = graph_w / (max_points - 1)
        
        coords = []
        for i, val in enumerate(data):
            x = self.margin_left + i * step_x
            y = graph_h - (val / 100 * graph_h)
            coords.extend([x, y])
            
        if coords:
            # 複数の座標を一度に渡して折れ線を描画（tag="graph_data"を付与）
            self.canvas.create_line(*coords, fill="#ff9900", width=1, tags="graph_data")

    def _draw_memory_line(self, history, graph_w, graph_h):
        """メモリグラフを描画（多色・セグメント描画）"""
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

            # 値に応じて色を変更
            if val2 >= 80: draw_color = "#cc3333" # 赤 = 80%以上
            elif val2 >= 50: draw_color = "#e6b800" # 黄 = 50%以上
            else: draw_color = "#496d89" # 青 = 50%未満
            
            # tag="graph_data"を付与して描画
            self.canvas.create_line(x1, y1, x2, y2, fill=draw_color, width=2, tags="graph_data")


class SettingsWindow(tk.Toplevel):
    """設定ウィンドウ"""
    def __init__(self, parent):
        super().__init__(parent.root)
        self.parent = parent

        self.title("設定")
        self.geometry("300x290")
        self.resizable(False, False)
        self.transient(parent.root) # 親ウィンドウの上に表示

        # --- UI ---
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 一般設定 ---
        general_frame = ttk.LabelFrame(main_frame, text="一般")
        general_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(general_frame, text="常に最前面で表示", variable=self.parent.topmost_var, command=self.parent.toggle_topmost).pack(anchor="w", padx=5)

        # --- スタートアップ設定 ---
        startup_frame = ttk.LabelFrame(main_frame, text="起動設定")
        startup_frame.pack(fill=tk.X, pady=5)

        startup_chk = ttk.Checkbutton(startup_frame, text="Windows起動時に実行", variable=self.parent.startup_var, command=self.parent.update_startup_registry)
        startup_chk.pack(anchor="w", padx=5)
        if os.name != 'nt':
            startup_chk.state(['disabled'])
        
        minimized_chk = ttk.Checkbutton(startup_frame, text="最小化状態で起動", variable=self.parent.start_minimized_var, command=self.parent.update_startup_registry)
        minimized_chk.pack(anchor="w", padx=25) # インデント

        # --- 自動解放と警告 ---
        auto_frame = ttk.LabelFrame(main_frame, text="自動解放と警告")
        auto_frame.pack(fill=tk.X, pady=5)

        # 警告閾値
        warning_row = ttk.Frame(auto_frame)
        warning_row.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(warning_row, text="警告閾値(%):").pack(side=tk.LEFT)
        ttk.Entry(warning_row, textvariable=self.parent.warning_threshold_var, width=5).pack(side=tk.LEFT, padx=5)

        # 定期解放
        interval_row = ttk.Frame(auto_frame)
        interval_row.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(interval_row, text="定期解放の間隔(分):").pack(side=tk.LEFT)
        self.interval_entry = ttk.Entry(interval_row, textvariable=self.parent.interval_var, width=5)
        self.interval_entry.pack(side=tk.LEFT, padx=5)

        button_text = "定期解放を停止" if self.parent.is_auto_free_running else "定期解放を開始"
        self.toggle_auto_button = ttk.Button(auto_frame, text=button_text, command=self.parent.toggle_auto_free)
        self.toggle_auto_button.pack(fill=tk.X, padx=5, pady=(5, 2))

        if self.parent.is_auto_free_running:
            self.interval_entry.config(state="disabled")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        self.parent.settings_win = None
        self.destroy()

class MemoryCleanerApp:
    """
    メモリ解放を行うデスクトップGUI
    """
    def __init__(self, root):
        self.root = root
        self.root.title("メモリ解放ツール")
        self.root.geometry("380x550")
        self.root.resizable(False, False)

        # アイコンファイルの設定（EXE化対応）
        icon_file = "app_icon.ico"
        if hasattr(sys, "_MEIPASS"):
            # PyInstallerでEXE化された場合の一時フォルダパス
            icon_path = os.path.join(sys._MEIPASS, icon_file)
        else:
            icon_path = icon_file

        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(default=icon_path)
            except Exception:
                pass

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
        self.settings_win = None # 設定ウィンドウのインスタンス
        self.topmost_var = tk.BooleanVar(value=False) # 最前面表示フラグ
        self.startup_var = tk.BooleanVar(value=False) # スタートアップ登録フラグ
        self.start_minimized_var = tk.BooleanVar(value=False) # 最小化起動フラグ
        self.warning_threshold_var = tk.StringVar(value="80")  # デフォルトの警告閾値
        self.interval_var = tk.StringVar(value="1") # 定期解放の間隔

        self.current_mem_percent = 0 # 現在のメモリ使用率
        self.memory_history = deque([0]*60, maxlen=60) # 履歴データ(60秒分)
        self.cpu_history = deque([0]*60, maxlen=60) # CPU履歴データ
        self.procs_cache = {} # CPU使用率計算用のプロセスキャッシュ
        self.top_procs_data = ([], []) # (mem_procs, cpu_procs)
        self._top_procs_thread = None # 上位プロセス取得スレッド

        self.config_file = "config.json" # 設定ファイルのパス
        self.load_config() # 設定ファイルから初期設定を読み込む

        # トレイアイコンの初期化
        self.tray_icon = None
        self.tray_thread = None

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
        
        settings_button = ttk.Button(utility_frame, text="設定", command=self.open_settings_window)
        settings_button.pack(side=tk.LEFT, fill=tk.X, padx=(5, 0))

    def open_settings_window(self):
        """設定ウィンドウを開く"""
        if self.settings_win is None or not self.settings_win.winfo_exists():
            self.settings_win = SettingsWindow(self)
            self.settings_win.grab_set() # モーダルにする
        else:
            self.settings_win.lift() # 既に開いている場合は最前面に

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

        # 上位プロセスの更新を非同期で開始
        if self._top_procs_thread is None or not self._top_procs_thread.is_alive():
            self._top_procs_thread = threading.Thread(target=self._update_top_procs_data, daemon=True)
            self._top_procs_thread.start()

        # UIはキャッシュされたデータで更新
        top_mem_procs, top_cpu_procs = self.top_procs_data
        
        for i, proc in enumerate(top_mem_procs):
            if i < len(self.process_labels):
                # スレッドとUIスレッドでデータ構造が共有されるため、キーの存在を確認
                if 'memory_info' in proc and proc['memory_info']:
                    mem_mb = proc['memory_info'].rss / (1024 * 1024)
                    self.process_labels[i].config(text=f"{i+1}. {proc['name']} ({mem_mb:.1f} MB)")

        for i, proc in enumerate(top_cpu_procs):
            if i < len(self.cpu_process_labels):
                if 'cpu_percent' in proc:
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

    def _update_top_procs_data(self):
        """別スレッドで上位プロセス情報を取得し、結果をキャッシュする"""
        try:
            self.top_procs_data = self.get_top_processes()
        except Exception:
            # スレッド内でエラーが発生してもアプリが落ちないようにする
            pass

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
        if os.name != 'nt':
            # Windows以外ではOS固有の強力な解放手段がないためスキップ(gc.collectのみ)
            return

        psapi = ctypes.WinDLL('psapi.dll') # PSAPI.dll
        kernel32 = ctypes.WinDLL('kernel32.dll') # Kernel32.dll
        
        OpenProcess = kernel32.OpenProcess # プロセスハンドルを取得
        OpenProcess.restype = wintypes.HANDLE # プロセスハンドル
        OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD) # (アクセス権, 継承フラグ, プロセスID)
        
        EmptyWorkingSet = psapi.EmptyWorkingSet # ワーキングセット解放
        EmptyWorkingSet.restype = wintypes.BOOL # BOOL
        EmptyWorkingSet.argtypes = (wintypes.HANDLE,) # (プロセスハンドル,)
        
        CloseHandle = kernel32.CloseHandle # ハンドルを閉じる
        CloseHandle.restype = wintypes.BOOL # BOOL
        CloseHandle.argtypes = (wintypes.HANDLE,) # (ハンドル,)
        
        PROCESS_SET_QUOTA = 0x0100 # 許可
        PROCESS_QUERY_INFORMATION = 0x0400 # 情報取得許可
        
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

    def free_memory(self, from_tray=False):
        """
        ガベージコレクションを実行してメモリを解放する（非同期）
        """
        self.show_status_message("メモリ解放を実行中...", "#0000ff")
        self.flash_window() # 処理開始をUIに通知

        # 重い処理を別スレッドで実行
        threading.Thread(target=self._free_memory_task, args=(from_tray,), daemon=True).start()

    def _free_memory_task(self, from_tray):
        """メモリ解放の重い処理を実行するスレッド関数"""
        try:
            mem_before = psutil.virtual_memory().used
            
            gc.collect()
            self.clean_system_memory()
            
            mem_after = psutil.virtual_memory().used
            freed_mb = max(0, (mem_before - mem_after) / (1024 * 1024))
            msg = f"メモリ解放を実行しました (解放量: {freed_mb:.1f} MB)"
            success = True
        except Exception as e:
            msg = f"エラー: {e}"
            success = False

        # GUIの更新をメインスレッドに依頼
        self.root.after(0, self._on_free_memory_done, msg, success, from_tray)

    def _on_free_memory_done(self, msg, success, from_tray):
        """メモリ解放完了後のUI更新"""
        # 解放後にメモリ情報を即時更新
        self.update_memory_info()

        if success:
            if from_tray and self.tray_icon:
                self.tray_icon.notify(msg, "成功")
            else:
                self.show_status_message(msg, "#008000")
        else:
            if from_tray and self.tray_icon:
                self.tray_icon.notify(f"エラーが発生しました: {msg}", "エラー")
            else:
                self.show_status_message(msg, "#ff0000")

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
            if sys.platform == 'win32':
                subprocess.Popen("taskmgr")
            elif sys.platform == 'darwin':
                subprocess.Popen(["open", "-a", "Activity Monitor"])
            else:
                # Linux: 一般的なシステムモニターを試行
                monitors = ["gnome-system-monitor", "ksysguard", "mate-system-monitor", "htop"]
                for m in monitors:
                    try:
                        subprocess.Popen(m if m != "htop" else ["x-terminal-emulator", "-e", "htop"])
                        return
                    except FileNotFoundError:
                        continue
                messagebox.showinfo("情報", "システムモニターが見つかりませんでした。")
        except Exception as e:
            messagebox.showerror("エラー", f"タスクマネージャーの起動に失敗しました: {e}")

    def toggle_topmost(self):
        """最前面表示を切り替える"""
        self.root.attributes('-topmost', self.topmost_var.get())

    def check_startup_status(self):
        """レジストリを確認してスタートアップ設定の状態を更新する"""
        if os.name != 'nt':
            return

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
        if os.name != 'nt':
            messagebox.showinfo("情報", "スタートアップ機能は現在Windowsのみサポートされています。")
            return

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
            if self.settings_win and self.settings_win.winfo_exists():
                self.settings_win.toggle_auto_button.config(text="定期解放を開始")
                self.settings_win.interval_entry.config(state="normal")
            messagebox.showinfo("停止", "定期解放を停止しました。")
        else:
            # --- 開始処理 ---
            try:
                interval_min = int(self.interval_var.get())
                if interval_min <= 0:
                    messagebox.showwarning("入力エラー", "間隔は正の整数で指定してください。")
                    return
                
                self.is_auto_free_running = True
                if self.settings_win and self.settings_win.winfo_exists():
                    self.settings_win.toggle_auto_button.config(text="定期解放を停止")
                    self.settings_win.interval_entry.config(state="disabled")
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
        
        # UIに処理中であることを示す
        self.flash_window()
        # 重い処理を別スレッドで実行
        threading.Thread(target=self._auto_free_task, daemon=True).start()

        # 次の実行をスケジュールする
        self.auto_free_job_id = self.root.after(interval_min * 60 * 1000, lambda: self.auto_free_loop(interval_min))

    def _auto_free_task(self):
        """自動解放用のバックグラウンドタスク"""
        try:
            gc.collect()
            self.clean_system_memory()
            # 完了後、メインスレッドでメモリ情報を更新
            self.root.after(0, self.update_memory_info)
        except Exception:
            # エラーが発生しても定期実行は継続する
            pass

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
        self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        self.tray_thread.start()

    def restore_window(self, icon=None, item=None):
        """トレイアイコンからウィンドウを復元する"""
        self.root.after(0, self._restore_window_impl)

    def _restore_window_impl(self):
        """
        トレイアイコンを安全に停止させてからウィンドウを復元する。
        pystrayの終了処理とtkinterのウィンドウ表示処理の競合によるフリーズを避ける。
        """
        if self.tray_icon and self.tray_thread and self.tray_thread.is_alive():
            icon_to_stop = self.tray_icon
            thread_to_join = self.tray_thread
            self.tray_icon = None
            self.tray_thread = None

            def wait_for_stop_and_restore():
                """pystrayスレッドの停止を待ってからウィンドウを復元する"""
                icon_to_stop.stop()
                thread_to_join.join() # スレッドが完全に終了するのを待つ
                # GUI操作はメインスレッドに依頼する
                self.root.after(0, self._show_window_actual)

            # GUIをブロックしないように、待機処理を別スレッドで実行
            threading.Thread(target=wait_for_stop_and_restore, daemon=True).start()
        else:
            # アイコン/スレッドがない場合は、単純にウィンドウを表示しようと試みる
            self._show_window_actual()

    def _show_window_actual(self):
        """ウィンドウを表示し、前面に移動させる"""
        self.root.deiconify()
        self.root.state('normal')
        self.root.lift()
        self.root.focus_force()

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
            # pystrayのstop()はGUIスレッドをブロックするため、別スレッドで非同期に呼び出す
            threading.Thread(target=self.tray_icon.stop, daemon=True).start()

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