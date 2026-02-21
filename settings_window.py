import os
import webbrowser
import psutil
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
from tkinter import messagebox
from tkinter import colorchooser


class SettingsWindow(tk.Toplevel):
    """設定ウィンドウ"""
    def __init__(self, parent):
        super().__init__(parent.root)
        self.parent = parent

        self.title("設定")
        self.geometry("320x350")
        self.resizable(False, False)
        self.transient(parent.root) # 親ウィンドウの上に表示

        # --- UI ---
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- タブ1: 一般 ---
        tab_general = ttk.Frame(notebook)
        notebook.add(tab_general, text="一般")
        
        # 最前面表示
        ttk.Checkbutton(tab_general, text="常に最前面で表示", variable=self.parent.topmost_var, command=self.parent.toggle_topmost).pack(anchor="w", padx=10, pady=10)

        # 起動設定
        startup_frame = ttk.LabelFrame(tab_general, text="起動設定")
        startup_frame.pack(fill=tk.X, padx=10, pady=5)

        startup_chk = ttk.Checkbutton(startup_frame, text="Windows起動時に実行", variable=self.parent.startup_var, command=self.parent.update_startup_registry)
        startup_chk.pack(anchor="w", padx=5, pady=2)
        if os.name != 'nt':
            startup_chk.state(['disabled'])
        
        minimized_chk = ttk.Checkbutton(startup_frame, text="最小化状態で起動", variable=self.parent.start_minimized_var, command=self.parent.update_startup_registry)
        minimized_chk.pack(anchor="w", padx=25, pady=2)

        # ショートカットキー設定
        shortcut_frame = ttk.LabelFrame(tab_general, text="ショートカットキー")
        shortcut_frame.pack(fill=tk.X, padx=10, pady=5)
        
        shortcut_inner = ttk.Frame(shortcut_frame)
        shortcut_inner.pack(fill=tk.X, padx=5, pady=5)
        self.shortcut_entry = ttk.Entry(shortcut_inner, textvariable=self.parent.shortcut_var, width=15)
        self.shortcut_entry.pack(side=tk.LEFT, padx=5)
        self.shortcut_entry.bind("<KeyPress>", self.on_key_press)
        ttk.Label(shortcut_inner, text="(BS/Delで削除)", font=("", 8), foreground="gray").pack(side=tk.LEFT)

        # 表示設定
        appearance_frame = ttk.LabelFrame(tab_general, text="表示設定")
        appearance_frame.pack(fill=tk.X, padx=10, pady=5)
        
        color_row = ttk.Frame(appearance_frame)
        color_row.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(color_row, text="メモリ解放時の点滅色:").pack(side=tk.LEFT)
        
        self.color_preview = tk.Label(color_row, width=4, bg=self.parent.flash_color_var.get(), relief="solid")
        self.color_preview.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(color_row, text="変更...", command=self.choose_color).pack(side=tk.LEFT)
        
        warning_color_row = ttk.Frame(appearance_frame)
        warning_color_row.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(warning_color_row, text="メモリ警告時の背景色:").pack(side=tk.LEFT)
        
        self.warning_color_preview = tk.Label(warning_color_row, width=4, bg=self.parent.warning_color_var.get(), relief="solid")
        self.warning_color_preview.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(warning_color_row, text="変更...", command=self.choose_warning_color).pack(side=tk.LEFT)

        # --- タブ2: 自動解放 ---
        tab_auto = ttk.Frame(notebook)
        notebook.add(tab_auto, text="自動解放")

        # 警告設定
        warning_frame = ttk.LabelFrame(tab_auto, text="警告設定")
        warning_frame.pack(fill=tk.X, padx=10, pady=10)
        
        warning_row = ttk.Frame(warning_frame)
        warning_row.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(warning_row, text="警告閾値(%):").pack(side=tk.LEFT)
        ttk.Entry(warning_row, textvariable=self.parent.warning_threshold_var, width=5).pack(side=tk.LEFT, padx=5)

        # 定期解放設定
        auto_free_frame = ttk.LabelFrame(tab_auto, text="定期解放設定")
        auto_free_frame.pack(fill=tk.X, padx=10, pady=5)

        interval_row = ttk.Frame(auto_free_frame)
        interval_row.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(interval_row, text="定期解放の間隔(分):").pack(side=tk.LEFT)
        self.interval_entry = ttk.Entry(interval_row, textvariable=self.parent.interval_var, width=5)
        self.interval_entry.pack(side=tk.LEFT, padx=5)

        is_running = self.parent.auto_free_scheduler.is_running
        button_text = "定期解放を停止" if is_running else "定期解放を開始"
        self.toggle_auto_button = ttk.Button(auto_free_frame, text=button_text, command=self.parent.toggle_auto_free)
        self.toggle_auto_button.pack(fill=tk.X, padx=5, pady=5)

        if is_running:
            self.interval_entry.config(state="disabled")

        # --- タブ3: 除外リスト ---
        tab_exclude = ttk.Frame(notebook)
        notebook.add(tab_exclude, text="除外リスト")

        exclude_frame = ttk.Frame(tab_exclude)
        exclude_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(exclude_frame, text="解放対象から除外するプロセス名 (例: chrome.exe)").pack(anchor="w")

        # リストボックスとスクロールバー
        list_frame = ttk.Frame(exclude_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.exclude_listbox = tk.Listbox(list_frame, height=6)
        self.exclude_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.exclude_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.exclude_listbox.config(yscrollcommand=scrollbar.set)

        # 既存のリストを読み込み
        for item in self.parent.exclusion_list:
            self.exclude_listbox.insert(tk.END, item)

        # 追加・削除コントロール
        ctrl_frame = ttk.Frame(exclude_frame)
        ctrl_frame.pack(fill=tk.X)
        
        self.exclude_entry = ttk.Entry(ctrl_frame)
        self.exclude_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Button(ctrl_frame, text="追加", command=self.add_exclusion).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl_frame, text="削除", command=self.remove_exclusion).pack(side=tk.LEFT, padx=2)
        ttk.Button(exclude_frame, text="実行中のプロセスから選択...", command=self.open_process_selector).pack(anchor="e", pady=(5, 0))
        
        # --- タブ3: その他 ---
        tab_misc = ttk.Frame(notebook)
        notebook.add(tab_misc, text="その他")
        
        # ログ
        log_frame = ttk.LabelFrame(tab_misc, text="ログ")
        log_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(log_frame, text="解放ログを表示", command=self.open_log_viewer).pack(fill=tk.X, padx=5, pady=5)

        # 設定リセット
        reset_frame = ttk.LabelFrame(tab_misc, text="設定管理")
        reset_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(reset_frame, text="設定を初期化", command=self.reset_settings).pack(fill=tk.X, padx=5, pady=5)

        # バージョン情報
        about_frame = ttk.LabelFrame(tab_misc, text="バージョン情報")
        about_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(about_frame, text="Memory Cleaner Tool", font=("Helvetica", 10, "bold")).pack(pady=(5, 2))
        ttk.Label(about_frame, text=f"Version {self.parent.version}").pack(pady=(0, 5))
        ttk.Label(about_frame, text="© 2026 Memory Cleaner Project All Rights Reserved.", font=("", 8), foreground="gray").pack(pady=(0, 5))
        
        # ボタンエリア
        btn_frame = ttk.Frame(about_frame)
        btn_frame.pack(pady=(0, 5))
        ttk.Button(btn_frame, text="GitHubリポジトリ", command=lambda: webbrowser.open("https://github.com/rydeen7907/memory")).pack(side=tk.LEFT, padx=5)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def choose_color(self):
        """カラーピッカーを開いて点滅色を選択"""
        color = colorchooser.askcolor(color=self.parent.flash_color_var.get(), title="点滅色を選択")[1]
        if color:
            self.parent.flash_color_var.set(color)
            self.color_preview.config(bg=color)
            self.parent.update_flash_style()

    def choose_warning_color(self):
        """カラーピッカーを開いて警告色を選択"""
        color = colorchooser.askcolor(color=self.parent.warning_color_var.get(), title="警告色を選択")[1]
        if color:
            self.parent.warning_color_var.set(color)
            self.warning_color_preview.config(bg=color)
            self.parent.update_warning_style()

    def add_exclusion(self):
        """除外リストにプロセスを追加"""
        name = self.exclude_entry.get().strip()
        if name:
            if name not in self.parent.exclusion_list:
                self.parent.exclusion_list.append(name)
                self.parent.cleaner_logic.exclusion_list = self.parent.exclusion_list # ロジックに即時反映
                self.exclude_listbox.insert(tk.END, name)
                self.exclude_entry.delete(0, tk.END)
            else:
                messagebox.showwarning("重複", "このプロセス名は既に登録されています。")

    def remove_exclusion(self):
        """選択したプロセスを除外リストから削除"""
        sel = self.exclude_listbox.curselection()
        if sel:
            index = sel[0]
            name = self.exclude_listbox.get(index)
            self.parent.exclusion_list.remove(name)
            self.parent.cleaner_logic.exclusion_list = self.parent.exclusion_list # ロジックに即時反映
            self.exclude_listbox.delete(index)

    def open_process_selector(self):
        """プロセス選択ウィンドウを開く"""
        ProcessSelectorWindow(self, self._add_from_selector)

    def _add_from_selector(self, process_names):
        """セレクターから選択されたプロセスを追加"""
        for name in process_names:
            if name not in self.parent.exclusion_list:
                self.parent.exclusion_list.append(name)
                self.exclude_listbox.insert(tk.END, name)
        self.parent.cleaner_logic.exclusion_list = self.parent.exclusion_list

    def reset_settings(self):
        """設定を初期化する"""
        if messagebox.askyesno("確認", "すべての設定を初期化しますか？\nこの操作は取り消せません。"):
            self.parent.config_manager.reset_to_defaults()
            messagebox.showinfo("完了", "設定を初期化しました。")

    def open_log_viewer(self):
        """ログビューアを開く"""
        LogViewerWindow(self)

    def on_close(self):
        self.parent.settings_win = None
        self.destroy()

    def on_key_press(self, event):
        """ショートカットキーの入力を処理"""
        key = event.keysym
        state = event.state

        # 修飾キーのみの場合は無視
        if key in ("Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R", "Win_L", "Win_R"):
            return "break"

        # クリア操作 (BackSpace または Delete)
        if key in ("BackSpace", "Delete"):
            self.parent.shortcut_var.set("")
            self.parent.setup_shortcut()
            return "break"

        parts = []
        # Windowsでのstateマスク (Control=4, Shift=1, Alt=131072 or 8)
        if state & 4: parts.append("Control")
        if state & 131072 or state & 8: parts.append("Alt")
        if state & 1: parts.append("Shift")
        
        parts.append(key)
        
        # Tkinterのバインド文字列形式に変換 (例: <Control-m>)
        sequence = f"<{'-'.join(parts)}>"
        self.parent.shortcut_var.set(sequence)
        self.parent.setup_shortcut()
        return "break" # 入力をEntryに反映させない
    

class ProcessSelectorWindow(tk.Toplevel):
    """実行中のプロセス一覧を表示して選択させるウィンドウ"""
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.title("プロセス選択")
        self.geometry("300x400")
        self.transient(parent)
        
        # 説明
        ttk.Label(self, text="除外するプロセスを選択してください(複数可):").pack(padx=10, pady=5, anchor="w")

        # リストボックス
        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.listbox = tk.Listbox(frame, selectmode=tk.EXTENDED)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)
        
        # プロセス読み込み
        self._load_processes()
        
        # ボタン
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="追加", command=self._on_add).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="キャンセル", command=self.destroy).pack(side=tk.RIGHT, padx=5)

    def _load_processes(self):
        procs = set()
        try:
            for p in psutil.process_iter(['name']):
                try:
                    if p.info['name']:
                        procs.add(p.info['name'])
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception:
            pass
        
        for name in sorted(procs, key=str.lower):
            self.listbox.insert(tk.END, name)

    def _on_add(self):
        selection = self.listbox.curselection()
        names = [self.listbox.get(i) for i in selection]
        if names:
            self.callback(names)
        self.destroy()
    
    
class LogViewerWindow(tk.Toplevel):
    """ログファイルの内容を表示するウィンドウ"""
    def __init__(self, parent, log_file="memory_cleaner.log"):
        super().__init__(parent)
        self.title("解放ログ")
        self.geometry("500x400")
        self.log_file = log_file

        # ボタンエリア
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="ログをクリア", command=self._clear_log).pack(side=tk.RIGHT)
        
        # テキストエリア（スクロールバー付き）
        self.text_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, font=("Consolas", 9))
        self.text_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        self._load_log(log_file)

    def _load_log(self, log_file):
        try:
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.text_area.insert(tk.END, content)
                    self.text_area.see(tk.END) # 末尾を表示
            else:
                self.text_area.insert(tk.END, "ログファイルはまだ作成されていません。")
        except Exception as e:
            self.text_area.insert(tk.END, f"ログの読み込みエラー: {e}")
        
        self.text_area.config(state=tk.DISABLED) # 編集不可にする

    def _clear_log(self):
        """ログをクリアする"""
        if messagebox.askyesno("確認", "ログをクリアしてもよろしいですか？"):
            try:
                # 親(SettingsWindow)の親(App)経由でロジッククラスのクリアメソッドを呼び出す
                self.master.parent.cleaner_logic.clear_log()
                
                self.text_area.config(state=tk.NORMAL)
                self.text_area.delete("1.0", tk.END)
                self.text_area.insert(tk.END, "ログはクリアされました。")
                self.text_area.config(state=tk.DISABLED)
            except Exception as e:
                messagebox.showerror("エラー", f"ログのクリアに失敗しました: {e}")