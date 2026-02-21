import os
import gc
import sys
import psutil
import ctypes
import logging
from logging.handlers import RotatingFileHandler

# Windows固有のライブラリを条件付きでインポート
if os.name == 'nt':
    from ctypes import wintypes

class MemoryCleanerLogic:
    """
    メモリ解放処理のロジックを担当するクラス
    """
    def __init__(self):
        self._setup_logger()
        self.exclusion_list = []

    def _setup_logger(self):
        """ログ出力の設定を行う"""
        self.logger = logging.getLogger("MemoryCleaner")
        self.logger.setLevel(logging.INFO)
        # ハンドラが重複しないようにチェック
        if not self.logger.handlers:
            try:
                # EXE化対応: 実行ファイルの場所を基準にログパスを設定
                if getattr(sys, 'frozen', False):
                    base_dir = os.path.dirname(sys.executable)
                else:
                    base_dir = os.path.dirname(os.path.abspath(__file__))

                # ログローテーションを追加 (1MBで3世代まで)
                handler = RotatingFileHandler(
                    os.path.join(base_dir, "memory_cleaner.log"),
                    maxBytes=1*1024*1024, # 1MB
                    backupCount=3,
                    encoding='utf-8'
                )
                formatter = logging.Formatter('%(asctime)s - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
            except Exception:
                pass

    def execute(self):
        """
        ガベージコレクションとシステムメモリ解放を実行し、解放されたメモリ量(MB)を返す
        """
        try:
            # 初期状態
            vm_start = psutil.virtual_memory()
            
            # Pythonのガベージコレクション
            gc.collect()
            
            # Windows APIによるシステムファイルキャッシュの解放
            # キャッシュ解放の効果は Free メモリの増加で測定
            vm_before_cache = psutil.virtual_memory()
            self._clean_file_cache()
            vm_after_cache = psutil.virtual_memory()
            
            # Windows APIによるワーキングセットの解放
            # ワーキングセット解放の効果は Used メモリの減少で測定
            self._clean_system_memory()
            vm_after_ws = psutil.virtual_memory()
            
            # 集計 (MB単位)
            # スタンバイリスト解放量 = Freeの増加分
            freed_standby = max(0, (vm_after_cache.free - vm_before_cache.free) / (1024 * 1024))
            
            # ワーキングセット解放量 = Usedの減少分 (キャッシュ解放後のUsed - 最終的なUsed)
            freed_ws = max(0, (vm_after_cache.used - vm_after_ws.used) / (1024 * 1024))
            
            # 全体のUsed減少量（ユーザーへの戻り値）
            freed_mb = max(0, (vm_start.used - vm_after_ws.used) / (1024 * 1024))

            # ログ出力
            log_msg = f"Total Freed: {freed_mb:.2f} MB (Working Set: {freed_ws:.2f} MB, Standby List: {freed_standby:.2f} MB)"
            self.logger.info(log_msg)

            return freed_mb
        except Exception:
            # エラー時は例外を再送出して呼び出し元で処理させる
            raise

    def _clean_system_memory(self):
        """Windows APIを使用して全プロセスのワーキングセットを解放する"""
        if os.name != 'nt':
            return

        try:
            psapi = ctypes.WinDLL('psapi.dll')
            kernel32 = ctypes.WinDLL('kernel32.dll')
            
            OpenProcess = kernel32.OpenProcess
            OpenProcess.restype = wintypes.HANDLE
            OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            
            EmptyWorkingSet = psapi.EmptyWorkingSet
            EmptyWorkingSet.restype = wintypes.BOOL
            EmptyWorkingSet.argtypes = (wintypes.HANDLE,)
            
            CloseHandle = kernel32.CloseHandle
            CloseHandle.restype = wintypes.BOOL
            CloseHandle.argtypes = (wintypes.HANDLE,)
            
            PROCESS_SET_QUOTA = 0x0100
            PROCESS_QUERY_INFORMATION = 0x0400
            
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    # 除外リストに含まれるプロセス名はスキップ
                    if proc.info['name'] in self.exclusion_list:
                        continue

                    pid = proc.info['pid']
                    handle = OpenProcess(PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION, False, pid)
                    if handle:
                        EmptyWorkingSet(handle)
                        CloseHandle(handle)
                except Exception:
                    pass
        except Exception:
            pass

    def _clean_file_cache(self):
        """Windowsのシステムファイルキャッシュ（スタンバイリスト）を解放する"""
        if os.name != 'nt':
            return

        try:
            # 特権を有効化 (SeProfileSingleProcessPrivilege)
            self._enable_privilege("SeProfileSingleProcessPrivilege")

            ntdll = ctypes.WinDLL('ntdll.dll')
            NtSetSystemInformation = ntdll.NtSetSystemInformation
            NtSetSystemInformation.restype = wintypes.LONG
            
            SYSTEM_MEMORY_LIST_INFORMATION = 80
            # MemoryPurgeStandbyList = 4
            command = wintypes.DWORD(4)
            
            NtSetSystemInformation(
                SYSTEM_MEMORY_LIST_INFORMATION,
                ctypes.byref(command),
                ctypes.sizeof(command)
            )
        except Exception:
            pass

    def _enable_privilege(self, privilege_name):
        """指定された特権を有効にする"""
        try:
            advapi32 = ctypes.WinDLL('advapi32.dll')
            kernel32 = ctypes.WinDLL('kernel32.dll')
            
            TOKEN_ADJUST_PRIVILEGES = 0x0020
            TOKEN_QUERY = 0x0008
            SE_PRIVILEGE_ENABLED = 0x00000002
            
            class LUID(ctypes.Structure):
                _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]
            
            class LUID_AND_ATTRIBUTES(ctypes.Structure):
                _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]
            
            class TOKEN_PRIVILEGES(ctypes.Structure):
                _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]

            hToken = wintypes.HANDLE()
            if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(hToken)):
                return

            luid = LUID()
            if not advapi32.LookupPrivilegeValueW(None, privilege_name, ctypes.byref(luid)):
                kernel32.CloseHandle(hToken)
                return

            tp = TOKEN_PRIVILEGES()
            tp.PrivilegeCount = 1
            tp.Privileges[0].Luid = luid
            tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
            
            advapi32.AdjustTokenPrivileges(hToken, False, ctypes.byref(tp), 0, None, None)
            kernel32.CloseHandle(hToken)
        except Exception:
            pass

    def clear_log(self):
        """ログファイルをクリアする"""
        # ファイルロックを解除するため、既存のハンドラを閉じて削除
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)
            
        # ファイルを空にする
        try:
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            
            log_path = os.path.join(base_dir, "memory_cleaner.log")
            with open(log_path, "w", encoding='utf-8'):
                pass
        except Exception:
            pass
            
        # ロガーを再設定（ハンドラを作り直す）
        self._setup_logger()