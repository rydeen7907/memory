"""
グラフ表示用モジュール
"""
import tkinter as tk

class GraphDrawer:
    """
    メモリ・CPU使用率のグラフ描画を担当するクラス
    """
    def __init__(self, canvas):
        self.canvas = canvas
        self.margin_bottom = 20
        self.margin_left = 35
        self.prev_w = 0
        self.prev_h = 0

    def draw(self, memory_history, cpu_history):
        """履歴データを受け取ってグラフを描画する"""
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        # まだ描画されていない、または最小化されている場合はスキップ
        if w <= 1: return

        # サイズが変更された場合のみ背景を再描画
        if w != self.prev_w or h != self.prev_h:
            self.canvas.delete("all")
            self._draw_background(w, h)
            self.prev_w = w
            self.prev_h = h
        else:
            # グラフデータのみクリア（背景は残す）
            self.canvas.delete("graph_data")

        graph_h = h - self.margin_bottom
        graph_w = w - self.margin_left

        # グラフ線の描画
        self._draw_cpu_line(cpu_history, graph_w, graph_h)
        self._draw_memory_line(memory_history, graph_w, graph_h)

    def _draw_background(self, w, h):
        """背景（グリッド、ラベル）を描画"""
        graph_h = h - self.margin_bottom
        graph_w = w - self.margin_left

        # --- 縦軸ラベル描画 ---
        self.canvas.create_text(self.margin_left - 5, 5, text="100%", anchor="e", fill="#666666", font=("Helvetica", 8))
        self.canvas.create_text(self.margin_left - 5, graph_h * 0.5, text="50%", anchor="e", fill="#666666", font=("Helvetica", 8))
        self.canvas.create_text(self.margin_left - 5, graph_h - 5, text="0%", anchor="e", fill="#666666", font=("Helvetica", 8))

        # --- 凡例描画 ---
        self.canvas.create_text(self.margin_left + 10, 10, text="― CPU", anchor="w", fill="#ff9900", font=("Helvetica", 8, "bold"))
        self.canvas.create_text(self.margin_left + 60, 10, text="― メモリ", anchor="w", fill="#496d89", font=("Helvetica", 8, "bold"))

        # --- グリッド線を描画 (背景) ---
        # 横線 (20%刻み)
        for i in range(1, 5): # 20%, 40%, 60%, 80%
            y = graph_h * (i * 0.2)
            # 80%ライン(上から20%)は警告色、それ以外はグレー
            color = "#ffcccc" if i == 1 else "#e0e0e0"
            self.canvas.create_line(self.margin_left, y, w, y, fill=color, dash=(2, 2))

        # 縦線 (10秒刻み)
        for i in range(1, 6):
            x = self.margin_left + (graph_w / 6) * i
            self.canvas.create_line(x, 0, x, graph_h, fill="#e0e0e0", dash=(2, 2))
            
        # --- 横軸ラベル描画 ---
        self.canvas.create_text(self.margin_left, h - 10, text="60秒前", anchor="w", fill="#666666", font=("Helvetica", 8))
        self.canvas.create_text(w - 5, h - 10, text="現在", anchor="e", fill="#666666", font=("Helvetica", 8))

    def _draw_cpu_line(self, history, graph_w, graph_h):
        """CPUグラフを描画（単色・一括描画で最適化）"""
        data = list(history)
        if len(data) < 2: return

        max_points = history.maxlen
        step_x = graph_w / (max_points - 1)
        
        coords = []
        for i, val in enumerate(data):
            x = self.margin_left + i * step_x
            y = graph_h - (val / 100 * graph_h)
            coords.extend([x, y])
            
        if coords:
            # 複数の座標を一度に渡して折れ線を描画（tag="graph_data"を付与）
            self.canvas.create_line(*coords, fill="#ff9900", width=1, tags="graph_data")

    def _draw_memory_line(self, history, graph_w, graph_h):
        """メモリグラフを描画（多色・セグメント描画）"""
        data = list(history)
        if len(data) < 2: return

        max_points = history.maxlen
        step_x = graph_w / (max_points - 1)

        for i in range(len(data) - 1):
            val1 = data[i]
            val2 = data[i+1]
            x1 = self.margin_left + i * step_x
            y1 = graph_h - (val1 / 100 * graph_h)
            x2 = self.margin_left + (i + 1) * step_x
            y2 = graph_h - (val2 / 100 * graph_h)

            # 値に応じて色を変更
            if val2 >= 80: draw_color = "#cc3333" # 赤 = 80%以上
            elif val2 >= 50: draw_color = "#e6b800" # 黄 = 50%以上
            else: draw_color = "#496d89" # 青 = 50%未満
            
            # tag="graph_data"を付与して描画
            self.canvas.create_line(x1, y1, x2, y2, fill=draw_color, width=2, tags="graph_data")


class GraphWindow(tk.Toplevel):
    """グラフを表示する別ウィンドウ"""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("リソースモニター")
        self.geometry("450x250")
        self.resizable(False, False)
        
        # キャンバスの作成
        self.canvas = tk.Canvas(self, bg="#f0f0f0", highlightthickness=1, highlightbackground="#cccccc")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.drawer = GraphDrawer(self.canvas)

    def update_graph(self, memory_history, cpu_history):
        """グラフを更新する"""
        if self.winfo_exists():
            self.drawer.draw(memory_history, cpu_history)
