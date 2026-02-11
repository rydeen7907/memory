import tkinter as tk
from tkinter import ttk
import os

class SettingsWindow(tk.Toplevel):
    """設定ウィンドウ"""
    def __init__(self, parent):
        super().__init__(parent.root)
        self.parent = parent

        self.title("設定")
        self.geometry("275x250")
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

        is_running = self.parent.auto_free_scheduler.is_running
        button_text = "定期解放を停止" if is_running else "定期解放を開始"
        self.toggle_auto_button = ttk.Button(auto_frame, text=button_text, command=self.parent.toggle_auto_free)
        self.toggle_auto_button.pack(fill=tk.X, padx=5, pady=(5, 2))

        if is_running:
            self.interval_entry.config(state="disabled")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        self.parent.settings_win = None
        self.destroy()