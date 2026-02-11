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
        s.configure("Warning.TFrame", background="tomato")

        app.main_frame = ttk.Frame(app.root, padding="10")
        app.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- メモリ情報表示エリア ---
        # --- ↓↓↓  動作には支障はないが機種によっては表示されない場合がある ↓↓↓ ---
        app.memory_label = ttk.Label(app.main_frame, text="現在のメモリ使用率: ...", font=("Helvetica", 12))
        app.memory_label.pack(pady=5, anchor="w")
        # --- ↑↑↑ ---

        app.memory_progress = ttk.Progressbar(app.main_frame, orient="horizontal", length=300, mode="determinate")
        app.memory_progress.pack(pady=5)
        
        # --- CPU情報表示エリア ---
        app.cpu_label = ttk.Label(app.main_frame, text="CPU使用率: ...", font=("Helvetica", 12))
        app.cpu_label.pack(pady=(5, 0), anchor="w")
        app.cpu_progress = ttk.Progressbar(app.main_frame, orient="horizontal", length=300, mode="determinate")
        app.cpu_progress.pack(pady=5)

        # --- グラフ表示エリア ---
        graph_button = ttk.Button(app.main_frame, text="リソースグラフを表示", command=app.open_graph_window)
        graph_button.pack(pady=5, fill=tk.X)

        # --- 上位プロセス表示エリア ---
        process_frame = ttk.LabelFrame(app.main_frame, text="メモリ使用量トップ3")
        process_frame.pack(pady=5, fill=tk.X)
        
        app.process_labels = []
        for i in range(3):
            lbl = ttk.Label(process_frame, text=f"{i+1}. ---", font=("Helvetica", 9))
            lbl.pack(anchor="w", padx=5, pady=1)
            app.process_labels.append(lbl)

        # --- CPU上位プロセス表示エリア ---
        cpu_process_frame = ttk.LabelFrame(app.main_frame, text="CPU使用率トップ3")
        cpu_process_frame.pack(pady=5, fill=tk.X)
        
        app.cpu_process_labels = []
        for i in range(3):
            lbl = ttk.Label(cpu_process_frame, text=f"{i+1}. ---", font=("Helvetica", 9))
            lbl.pack(anchor="w", padx=5, pady=1)
            app.cpu_process_labels.append(lbl)

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