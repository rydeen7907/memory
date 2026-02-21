import tkinter as tk
from tkinter import ttk

class UIBuilder:
    """
    GUIのウィジェットの生成と配置を担当するクラス
    """
    def build(self, app):
        """
        GUIのウィジェットをセットアップする
        Args:
            app (MemoryCleanerApp): メインアプリケーションのインスタンス
        """
        # スタイルを定義して点滅エフェクトに備える
        s = ttk.Style()
        s.configure("Flash.TFrame", background="lightblue")
        s.configure("Flash.TLabel", background="lightblue")
        s.configure("Warning.TFrame", background="tomato")
        s.configure("Warning.TLabel", background="tomato")

        app.main_frame = ttk.Frame(app.root, padding="10")
        app.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- メモリ情報表示エリア ---
        # --- ↓↓↓  動作には支障はないが機種によっては表示されない場合がある ↓↓↓ ---
        app.memory_label = ttk.Label(app.main_frame, text="現在のメモリ使用率: ...", font=("Helvetica", 12))
        app.memory_label.pack(pady=5, anchor="w")
        # --- ↑↑↑ ---

        app.memory_progress = ttk.Progressbar(app.main_frame, orient="horizontal", length=300, mode="determinate")
        app.memory_progress.pack(pady=5)
        
        # --- 手動解放エリア ---
        manual_free_button = ttk.Button(app.main_frame, text="今すぐメモリを解放", command=app.free_memory)
        manual_free_button.pack(pady=(10, 5), fill=tk.X)
        
        # ステータスメッセージ表示用ラベル
        app.status_label = ttk.Label(app.main_frame, text="", font=("Helvetica", 9))
        app.status_label.pack(pady=(0, 5)) 
        
        # --- ユーティリティエリア ---
        utility_frame = ttk.Frame(app.main_frame)
        utility_frame.pack(pady=0, fill=tk.X)
        
        task_manager_button = ttk.Button(utility_frame, text="タスクマネージャー", command=app.open_task_manager)
        task_manager_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        settings_button = ttk.Button(utility_frame, text="設定", command=app.open_settings_window)
        settings_button.pack(side=tk.LEFT, fill=tk.X, padx=(5, 0))