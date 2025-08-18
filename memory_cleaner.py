"""
メモリ開放ツール
"""
import tkinter as tk
from tkinter import ttk, messagebox
import psutil
import json
import gc

class MemoryCleanerApp:
    """
    メモリ解放を行うデスクトップGUIアプリケーション。
    """
    def __init__(self, root):
        self.root = root
        self.root.title("メモリ解放ツール")
        self.root.geometry("380x220")
        self.root.resizable(False, False)

        # 自動解放が実行中かどうかのフラグ
        self.is_auto_free_running = False
        # TkinterのafterメソッドのジョブIDを保持
        self.auto_free_job_id = None
        # メモリ情報更新用のafterジョブID
        self.update_job_id = None
        # 警告状態フラグと閾値
        self.is_warning_state = False
        self.warning_threshold_var = tk.StringVar(value="80")  # デフォルトの警告閾値
        self.interval_var = tk.StringVar(value="1") # 定期解放の間隔

        self.config_file = "config.json" # 設定ファイルのパス
        self.load_config() # 設定ファイルから初期設定を読み込む

        self.setup_ui() # GUIのウィジェットをセットアップ
        self.update_memory_info() # メモリ情報の定期更新を開始

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
        
        # --- 手動解放エリア ---
        manual_free_button = ttk.Button(self.main_frame, text="今すぐメモリを解放", command=self.free_memory)
        manual_free_button.pack(pady=10, fill=tk.X)
        
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
        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        mem_used_gb = mem.used / (1024 ** 3)
        mem_total_gb = mem.total / (1024 ** 3)

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

        # 1秒後に再度この関数を呼び出す
        self.update_job_id = self.root.after(1000, self.update_memory_info)

    def _perform_gc_and_flash(self):
        """ガベージコレクションを実行し、ウィンドウを点滅させるヘルパーメソッド"""
        gc.collect()
        self.flash_window()
        # 解放後にメモリ情報を更新 (エフェクトに対し少し遅らせる)
        self.root.after(250, self.update_memory_info)

    def free_memory(self):
        """
        ガベージコレクションを実行してメモリを解放する
        """
        try:
            self._perform_gc_and_flash()
            messagebox.showinfo("成功", "メモリの解放処理（ガベージコレクション）を実行しました。")
        except Exception as e:
            messagebox.showerror("エラー", f"処理中にエラーが発生しました: {e}")
            # エラー発生時もメモリ情報は更新しておく
            self.update_memory_info()

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
        except (FileNotFoundError, json.JSONDecodeError):
            # ファイルがない、または不正な形式の場合はデフォルト値が使用されるため、何もしない
            pass

    def save_config(self):
        """
        現在の設定をconfig.jsonに保存する
        """
        config_data = {
            "warning_threshold": self.warning_threshold_var.get(),
            "auto_free_interval": self.interval_var.get()
        }
        with open(self.config_file, "w") as f:
            json.dump(config_data, f, indent=4)

if __name__ == "__main__":
    root = tk.Tk()
    app = MemoryCleanerApp(root)
    root.mainloop()