import threading
from tkinter import messagebox

class AutoFreeScheduler:
    """
    定期的なメモリ解放のスケジューリングを担当するクラス
    """
    def __init__(self, app):
        """
        Args:
            app (MemoryCleanerApp): メインアプリケーションのインスタンス
        """
        self.app = app
        self.is_running = False
        self.job_id = None

    def toggle(self):
        """定期解放の開始/停止を切り替える"""
        if self.is_running:
            self.stop()
            messagebox.showinfo("停止", "定期解放を停止しました。")
        else:
            try:
                interval_min = int(self.app.interval_var.get())
                if interval_min <= 0:
                    messagebox.showwarning("入力エラー", "間隔は正の整数で指定してください。")
                    return
                self.start(interval_min)
                messagebox.showinfo("開始", f"{interval_min}分ごとの定期解放を開始しました。")
            except ValueError:
                messagebox.showwarning("入力エラー", "間隔は半角数字で入力してください。")

    def start(self, interval_min):
        """定期解放を開始する"""
        if self.is_running:
            return
        self.is_running = True
        self._update_settings_ui()
        self._loop(interval_min)

    def stop(self):
        """定期解放を停止する"""
        if not self.is_running:
            return
        if self.job_id:
            self.app.root.after_cancel(self.job_id)
            self.job_id = None
        self.is_running = False
        self._update_settings_ui()

    def _loop(self, interval_min):
        if not self.is_running:
            return
        
        self.app.flash_window()
        threading.Thread(target=self._task, daemon=True).start()

        self.job_id = self.app.root.after(interval_min * 60 * 1000, lambda: self._loop(interval_min))

    def _task(self):
        try:
            self.app.cleaner_logic.execute()
            self.app.root.after(0, self.app.update_memory_info)
        except Exception:
            pass # エラーが発生しても定期実行は継続する

    def _update_settings_ui(self):
        """設定ウィンドウのUIを更新する"""
        settings_win = self.app.settings_win
        if settings_win and settings_win.winfo_exists():
            if self.is_running:
                settings_win.toggle_auto_button.config(text="定期解放を停止")
                settings_win.interval_entry.config(state="disabled")
            else:
                settings_win.toggle_auto_button.config(text="定期解放を開始")
                settings_win.interval_entry.config(state="normal")