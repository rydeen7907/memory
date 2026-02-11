import psutil

class ProcessMonitor:
    """
    システム上のプロセス情報を監視・取得するクラス
    """
    def __init__(self):
        self.procs_cache = {} # CPU使用率計算用のプロセスキャッシュ

    def get_top_processes(self):
        """メモリとCPU使用率の高いプロセス上位3つを取得"""
        mem_list = []
        cpu_list = []
        current_procs = {}

        # プロセスを走査
        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                pid = proc.info['pid']
                name = proc.info['name']
                
                # CPU使用率計算のため、プロセスインスタンスをキャッシュから取得または新規作成
                if pid in self.procs_cache:
                    p = self.procs_cache[pid]
                else:
                    p = proc
                    # 初回呼び出し時は0.0になるため初期化のみ
                    try:
                        p.cpu_percent(interval=None)
                    except:
                        pass
                
                current_procs[pid] = p
                
                # 情報をリストに追加
                mem_list.append(proc.info)
                
                # キャッシュされたインスタンスを使ってCPU使用率を取得
                cpu_val = p.cpu_percent(interval=None)
                cpu_list.append({'name': name, 'cpu_percent': cpu_val})

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # キャッシュを更新（存在しないプロセスは削除される）
        self.procs_cache = current_procs

        # ソートして上位3件を返す
        top_mem = sorted(mem_list, key=lambda p: p['memory_info'].rss, reverse=True)[:3]
        top_cpu = sorted(cpu_list, key=lambda p: p['cpu_percent'], reverse=True)[:3]
        
        return top_mem, top_cpu