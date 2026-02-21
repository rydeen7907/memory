import json

class ConfigManager:
    """
    設定ファイルの読み書きを管理するクラス
    """
    def __init__(self, app, config_file="config.json"):
        """
        Args:
            app (MemoryCleanerApp): メインアプリケーションのインスタンス
            config_file (str): 設定ファイル名
        """
        self.app = app
        self.config_file = config_file

    def load(self):
        """
        config.jsonから設定を読み込む
        """
        try:
            with open(self.config_file, "r") as f:
                config_data = json.load(f)
                # 設定ファイルの値があれば上書きする。なければ初期値のまま。
                self.app.warning_threshold_var.set(config_data.get("warning_threshold", self.app.warning_threshold_var.get()))
                self.app.interval_var.set(config_data.get("auto_free_interval", self.app.interval_var.get()))
                self.app.topmost_var.set(config_data.get("topmost", False))
                self.app.start_minimized_var.set(config_data.get("start_minimized", False))
                self.app.shortcut_var.set(config_data.get("shortcut_key", ""))
                self.app.exclusion_list = config_data.get("exclusion_list", [])
                self.app.flash_color_var.set(config_data.get("flash_color", "lightblue"))
                self.app.warning_color_var.set(config_data.get("warning_color", "tomato"))
                self.app.cleaner_logic.exclusion_list = self.app.exclusion_list # ロジッククラスに反映
                self.app.toggle_topmost() # 読み込んだ設定を反映
                self.app.setup_shortcut() # ショートカットキーを反映
                self.app.update_flash_style() # 点滅色を反映
                self.app.update_warning_style() # 警告色を反映
        except FileNotFoundError:
            # ファイルがない場合はデフォルト設定で作成する
            self.save()
        except json.JSONDecodeError:
            # 不正な形式の場合はデフォルト値が使用されるため、何もしない
            pass

    def reset_to_defaults(self):
        """設定を初期値に戻す"""
        self.app.warning_threshold_var.set("80")
        self.app.interval_var.set("1")
        self.app.topmost_var.set(False)
        self.app.start_minimized_var.set(False)
        self.app.shortcut_var.set("")
        self.app.exclusion_list = []
        self.app.flash_color_var.set("lightblue")
        self.app.warning_color_var.set("tomato")
        self.app.cleaner_logic.exclusion_list = []
        
        # 設定反映
        self.app.toggle_topmost()
        self.app.setup_shortcut()
        self.app.update_flash_style()
        self.app.update_warning_style()
        
        self.save()

    def save(self):
        """
        現在の設定をconfig.jsonに保存する
        """
        config_data = {
            "warning_threshold": self.app.warning_threshold_var.get(),
            "auto_free_interval": self.app.interval_var.get(),
            "topmost": self.app.topmost_var.get(),
            "start_minimized": self.app.start_minimized_var.get(),
            "shortcut_key": self.app.shortcut_var.get(),
            "exclusion_list": self.app.exclusion_list,
            "flash_color": self.app.flash_color_var.get(),
            "warning_color": self.app.warning_color_var.get()
        }
        with open(self.config_file, "w") as f:
            json.dump(config_data, f, indent=4)