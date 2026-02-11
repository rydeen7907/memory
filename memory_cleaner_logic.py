import os
import gc
import psutil
import ctypes

# Windows固有のライブラリを条件付きでインポート
if os.name == 'nt':
    from ctypes import wintypes

class MemoryCleanerLogic:
    """
    メモリ解放処理のロジックを担当するクラス
    """
    def execute(self):
        """
        ガベージコレクションとシステムメモリ解放を実行し、解放されたメモリ量(MB)を返す
        """
        try:
            mem_before = psutil.virtual_memory().used
            
            # Pythonのガベージコレクション
            gc.collect()
            
            # Windows APIによるワーキングセットの解放
            self._clean_system_memory()
            
            mem_after = psutil.virtual_memory().used
            freed_mb = max(0, (mem_before - mem_after) / (1024 * 1024))
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
            
            for proc in psutil.process_iter():
                try:
                    pid = proc.pid
                    handle = OpenProcess(PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION, False, pid)
                    if handle:
                        EmptyWorkingSet(handle)
                        CloseHandle(handle)
                except Exception:
                    pass
        except Exception:
            pass