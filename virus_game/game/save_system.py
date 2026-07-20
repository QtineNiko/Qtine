import json
import os


class SaveSystem:
    def __init__(self, save_dir="saves"):
        self.save_dir = save_dir
        self.save_file = os.path.join(save_dir, "savegame.json")
        self._ensure_dir()
    
    def _ensure_dir(self):
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
    
    def save(self, data):
        try:
            with open(self.save_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Save error: {e}")
            return False
    
    def load(self):
        try:
            if not os.path.exists(self.save_file):
                return None
            with open(self.save_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Load error: {e}")
            return None
    
    def has_save(self):
        return os.path.exists(self.save_file)
    
    def delete_save(self):
        if os.path.exists(self.save_file):
            os.remove(self.save_file)
            return True
        return False
