import sys
import subprocess

def open_task_manager():
    """
    OS標準のタスクマネージャー（システムモニター）を起動する
    Raises:
        FileNotFoundError: Linuxでモニターが見つからない場合
        Exception: その他の起動エラー
    """
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
        raise FileNotFoundError("システムモニターが見つかりませんでした。")