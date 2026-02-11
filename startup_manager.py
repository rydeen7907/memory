import os
import sys

# Windows固有のライブラリを条件付きでインポート
if os.name == 'nt':
    import winreg

class StartupManager:
    """
    Windowsのスタートアップ登録を管理するクラス
    """
    def __init__(self, app_name="MemoryCleaner"):
        self.app_name = app_name
        self.key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        self.is_windows = (os.name == 'nt')

    def check_status(self):
        """
        レジストリを確認してスタートアップ設定の状態を返す
        Returns:
            tuple: (is_enabled, is_minimized)
        """
        if not self.is_windows:
            return (False, False)

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key_path, 0, winreg.KEY_READ)
            try:
                value, _ = winreg.QueryValueEx(key, self.app_name)
                is_enabled = True
                is_minimized = "--minimized" in value
                return (is_enabled, is_minimized)
            except FileNotFoundError:
                return (False, False)
            finally:
                winreg.CloseKey(key)
        except Exception:
            return (False, False)

    def update_registry(self, is_enabled, is_minimized):
        """
        スタートアップ登録を更新（登録/解除/オプション変更）
        Args:
            is_enabled (bool): スタートアップに登録するかどうか
            is_minimized (bool): 最小化状態で起動するかどうか
        Raises:
            Exception: レジストリ操作に失敗した場合
        """
        if not self.is_windows:
            return

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key_path, 0, winreg.KEY_WRITE)
            if is_enabled:
                if getattr(sys, 'frozen', False):
                    app_path = f'"{sys.executable}"'
                else:
                    app_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
                
                if is_minimized:
                    app_path += ' --minimized'
                winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, app_path)
            else:
                try:
                    winreg.DeleteValue(key, self.app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            raise Exception(f"スタートアップ設定の変更に失敗しました: {e}")