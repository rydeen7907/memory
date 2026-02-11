import pystray
import threading
from PIL import Image, ImageDraw

class TrayManager:
    """
    システムトレイアイコンの管理を担当するクラス
    """
    def __init__(self, app):
        """
        Args:
            app (MemoryCleanerApp): メインアプリケーションのインスタンス
        """
        self.app = app
        self.icon = None
        self.thread = None

    @property
    def is_running(self):
        """トレイアイコンが実行中かどうかを返す"""
        return self.icon is not None and self.thread is not None and self.thread.is_alive()

    def run(self):
        """トレイアイコンを別スレッドで実行する"""
        if self.is_running:
            return

        image = self._create_icon_image(self.app.current_mem_percent)
        menu = pystray.Menu(
            pystray.MenuItem("開く", self._handle_restore_request),
            pystray.MenuItem("今すぐメモリ解放", self._handle_free_memory),
            pystray.MenuItem("タスクマネージャー", self._handle_open_task_manager),
            pystray.MenuItem("終了", self._handle_quit)
        )
        self.icon = pystray.Icon("MemoryCleaner", image, "メモリ解放ツール", menu)
        self.thread = threading.Thread(target=self.icon.run, daemon=True)
        self.thread.start()

    def stop(self):
        """トレイアイコンを停止する"""
        if self.is_running:
            # GUIをブロックしないように、停止処理を別スレッドで実行
            threading.Thread(target=self.icon.stop, daemon=True).start()
            self.icon = None # 後続の処理でis_runningがFalseになるように

    def update(self, usage_percent):
        """アイコンの画像とツールチップを更新する"""
        if self.is_running:
            self.icon.icon = self._create_icon_image(usage_percent)
            self.icon.title = f"メモリ使用率: {usage_percent}%"

    def notify(self, message, title):
        """トレイから通知を表示する"""
        if self.is_running:
            self.icon.notify(message, title)

    # --- Menu Handlers ---

    def _handle_restore_request(self):
        """「開く」メニューのアクション。アイコンを停止し、ウィンドウを復元する"""
        if not self.is_running:
            return

        icon_to_stop = self.icon
        thread_to_join = self.thread
        self.icon = None
        self.thread = None

        def wait_for_stop_and_restore():
            """pystrayスレッドの停止を待ってからウィンドウを復元する"""
            icon_to_stop.stop()
            thread_to_join.join() # スレッドが完全に終了するのを待つ
            # GUI操作はメインスレッドに依頼する
            self.app.root.after(0, self.app.restore_window)

        # GUIをブロックしないように、待機処理を別スレッドで実行
        threading.Thread(target=wait_for_stop_and_restore, daemon=True).start()

    def _handle_free_memory(self):
        """「今すぐメモリ解放」メニューのアクション"""
        self.app.root.after(0, lambda: self.app.free_memory(from_tray=True))

    def _handle_open_task_manager(self):
        """「タスクマネージャー」メニューのアクション"""
        self.app.root.after(0, self.app.open_task_manager)

    def _handle_quit(self):
        """「終了」メニューのアクション"""
        self.app.root.after(0, self.app.on_closing)

    # --- Icon Image Creation ---

    def _create_icon_image(self, usage_percent=None):
        """トレイアイコン用の画像を生成する"""
        image = Image.new('RGB', (64, 64), color=(73, 109, 137))
        draw = ImageDraw.Draw(image)

        if usage_percent is None:
            draw.rectangle((16, 16, 48, 48), fill=(255, 255, 255))
        else:
            draw.rectangle((16, 8, 48, 56), outline=(255, 255, 255), width=2)
            bar_height = int(44 * (usage_percent / 100))
            if usage_percent >= 80:
                fill_color = (255, 80, 80) # 赤
            elif usage_percent >= 50:
                fill_color = (255, 255, 80) # 黄
            else:
                fill_color = (80, 255, 80) # 緑

            draw.rectangle((19, 54 - bar_height, 45, 54), fill=fill_color)

        return image