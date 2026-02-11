"""
メモリ開放ツール
"""
import tkinter as tk
import psutil # システム情報取得用
import json
import threading # 非同期処理用
import pystray # トレイアイコン用
import sys
import os
from tkinter import ttk, messagebox
from PIL import Image, ImageDraw
from collections import deque 
# --- 自作モジュール ---
from graph_monitor import GraphWindow
from process_monitor import ProcessMonitor
from settings_window import SettingsWindow
from tray_manager import TrayManager
from memory_cleaner_logic import MemoryCleanerLogic
from startup_manager import StartupManager
from config_manager import ConfigManager
from ui_builder import UIBuilder
from auto_free_scheduler import AutoFreeScheduler
import os_utils
from icon_data import APP_ICON_NORMAL, APP_ICON_WARNING, APP_ICON_CAUTION


class MemoryCleanerApp:
    """
    メモリ解放を行うデスクトップGUI
    """
    def __init__(self, root):
        self.root = root
        self.root.title("メモリ解放ツール")
        self.root.geometry("350x475")
        self.root.resizable(False, False)

        # アイコン設定
        self.current_icon_type = "NORMAL" # 現在のアイコン状態
        self.set_app_icon(APP_ICON_NORMAL)

        # メモリ情報更新用のafterジョブID
        self.update_job_id = None
        # ステータスメッセージ消去用のジョブID
        self.status_clear_job = None
        # 警告状態フラグと閾値
        self.is_warning_state = False
        self.settings_win = None # 設定ウィンドウのインスタンス
        self.topmost_var = tk.BooleanVar(value=False) # 最前面表示フラグ
        self.graph_window = None # グラフウィンドウのインスタンス
        self.startup_var = tk.BooleanVar(value=False) # スタートアップ登録フラグ
        self.start_minimized_var = tk.BooleanVar(value=False) # 最小化起動フラグ
        self.warning_threshold_var = tk.StringVar(value="80")  # デフォルトの警告閾値
        self.interval_var = tk.StringVar(value="1") # 定期解放の間隔

        self.current_mem_percent = 0 # 現在のメモリ使用率
        self.memory_history = deque([0]*60, maxlen=60) # 履歴データ(60秒分)
        self.cpu_history = deque([0]*60, maxlen=60) # CPU履歴データ
        self.process_monitor = ProcessMonitor() # プロセス監視用クラス
        self.top_procs_data = ([], []) # (mem_procs, cpu_procs)
        self._top_procs_thread = None # 上位プロセス取得スレッド

        self.tray_manager = TrayManager(self) # トレイアイコン管理クラス
        self.cleaner_logic = MemoryCleanerLogic() # メモリ解放ロジッククラス
        self.startup_manager = StartupManager() # スタートアップ管理クラス
        self.config_manager = ConfigManager(self) # 設定管理クラス
        self.ui_builder = UIBuilder() # UI構築クラス
        self.auto_free_scheduler = AutoFreeScheduler(self) # 定期解放スケジューラ
 
        self.config_manager.load() # 設定を読み込む
        self.ui_builder.build(self) # GUIのウィジェットをセットアップ
        self.check_startup_status() # スタートアップ状態を確認
        self.update_memory_info() # メモリ情報の定期更新を開始

        # 起動引数チェック: 最小化オプションがあればトレイに格納
        if "--minimized" in sys.argv:
            self.minimize_to_tray()

        # 最小化イベントをフック
        self.root.bind("<Unmap>", self.check_minimize)
        # ウィンドウを閉じる際のイベントをフック
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def set_app_icon(self, icon_data):
        """アプリケーションのアイコンを変更する"""
        try:
            icon_img = tk.PhotoImage(data=icon_data)
            self.root.iconphoto(True, icon_img)
        except Exception:
            pass
        
    def open_graph_window(self):
        """グラフウィンドウを開く"""
        if self.graph_window is None or not self.graph_window.winfo_exists():
            self.graph_window = GraphWindow(self.root)
        else:
            self.graph_window.lift()

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
        if self.graph_window and self.graph_window.winfo_exists():
            self.graph_window.update_graph(self.memory_history, self.cpu_history)

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
        new_icon_type = "NORMAL"
        try:
            warning_val = int(self.warning_threshold_var.get())
            # 注意閾値は警告閾値の75%とする (例: 80% -> 60%)
            caution_val = int(warning_val * 0.75)
            
            self.is_warning_state = (mem_percent >= warning_val)
            
            if mem_percent >= warning_val:
                new_icon_type = "WARNING"
            elif mem_percent >= caution_val:
                new_icon_type = "CAUTION"
        except (ValueError, AttributeError):
            # 不正な入力値の場合は警告しない
            self.is_warning_state = False
            
        # 点滅中でなければ背景スタイルを更新
        # (点滅エフェクトを優先させるため)
        if self.main_frame.cget("style") != "Flash.TFrame":
            self.update_background_style()

        # 警告状態に応じてアイコンを切り替える
        if new_icon_type != self.current_icon_type:
            if new_icon_type == "WARNING":
                self.set_app_icon(APP_ICON_WARNING)
            elif new_icon_type == "CAUTION":
                self.set_app_icon(APP_ICON_CAUTION)
            else:
                self.set_app_icon(APP_ICON_NORMAL)
            self.current_icon_type = new_icon_type

        # トレイアイコンが表示されている場合、アイコンとツールチップを更新
        if self.tray_manager.is_running:
            self.tray_manager.update(mem_percent)
 
        # 1秒後に再度この関数を呼び出す
        self.update_job_id = self.root.after(1000, self.update_memory_info)

    def _update_top_procs_data(self):
        """別スレッドで上位プロセス情報を取得し、結果をキャッシュする"""
        try:
            self.top_procs_data = self.process_monitor.get_top_processes()
        except Exception:
            # スレッド内でエラーが発生してもアプリが落ちないようにする
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
            freed_mb = self.cleaner_logic.execute()
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
            if from_tray:
                self.tray_manager.notify(msg, "成功")
            else:
                self.show_status_message(msg, "#008000")
        else:
            if from_tray:
                self.tray_manager.notify(f"エラーが発生しました: {msg}", "エラー")
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
            os_utils.open_task_manager()
        except FileNotFoundError:
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
        
        is_enabled, is_minimized = self.startup_manager.check_status()
        self.startup_var.set(is_enabled)
        self.start_minimized_var.set(is_minimized)

    def update_startup_registry(self):
        """スタートアップ登録の更新（登録/解除/オプション変更）"""
        if os.name != 'nt':
            messagebox.showinfo("情報", "スタートアップ機能は現在Windowsのみサポートされています。")
            return
        
        try:
            is_enabled = self.startup_var.get()
            is_minimized = self.start_minimized_var.get()
            self.startup_manager.update_registry(is_enabled, is_minimized)
        except Exception as e:
            messagebox.showerror("エラー", str(e))

    def toggle_auto_free(self):
        """
        定期解放の開始/停止を切り替える
        """
        self.auto_free_scheduler.toggle()

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
        if not self.tray_manager.is_running:
            self.tray_manager.run()

    def restore_window(self):
        """ウィンドウを表示し、前面に移動させる"""
        self.root.deiconify()
        self.root.state('normal')
        self.root.lift()
        self.root.focus_force()

    def on_closing(self):
        """
        ウィンドウが閉じられるときに実行される処理
        """
        # 定期解放が実行中の場合、ユーザーに確認
        if self.auto_free_scheduler.is_running:
            if not messagebox.askyesno("確認", "定期解放が実行中です。アプリケーションを終了しますか？"):
                return  # 終了をキャンセル

        # 実行中のタイマーをすべてキャンセル
        if self.update_job_id:
            self.root.after_cancel(self.update_job_id)
        self.auto_free_scheduler.stop() # 実行中の定期解放を停止

        # グラフウィンドウが開いていれば閉じる
        if self.graph_window and self.graph_window.winfo_exists():
            self.graph_window.destroy()

        # トレイアイコンが実行中なら停止
        if self.tray_manager.is_running:
            self.tray_manager.stop()

        # 設定を保存
        self.config_manager.save()
        # ウィンドウを破棄
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MemoryCleanerApp(root)
    root.mainloop()