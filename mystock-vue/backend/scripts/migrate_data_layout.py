import os
import json
import shutil
import sys

# 將 backend 目錄加入 sys.path 以便 import config 和 markets
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from markets.tw import FIELD_MAP

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, "data")
TW_DIR = os.path.join(DATA_DIR, "tw")

def migrate():
    if not os.path.exists(DATA_DIR):
        print("Data directory does not exist.")
        return

    os.makedirs(TW_DIR, exist_ok=True)
    
    files = [f for f in os.listdir(DATA_DIR) if f.endswith(".json") and not f.startswith("_")]
    
    migrated_count = 0
    for filename in files:
        old_path = os.path.join(DATA_DIR, filename)
        new_path = os.path.join(TW_DIR, filename)
        
        try:
            with open(old_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            new_data = {}
            for date_key, record in data.items():
                new_record = {}
                for k, v in record.items():
                    # 特殊處理：日期、股票代號等基本欄位通常保留或統一
                    if k in FIELD_MAP:
                        new_record[FIELD_MAP[k]] = v
                    elif k in ["日期", "股票代號"]:
                        new_record[k] = v # 這些通常不需要存，但如果有的話保留。或改為 date, symbol
                    else:
                        # 其他未定義在 FIELD_MAP 的爛位，先保留中文，
                        # 但我們的目標是統一為英文。這邊可以簡單加上對應：
                        new_record[k] = v
                        
                # 確保收盤價等欄位為數字，並加入必要的新欄位
                new_data[date_key] = new_record
                
            with open(new_path, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, ensure_ascii=False, indent=2)
                
            migrated_count += 1
            print(f"Migrated {filename} to tw/{filename}")
            
            # Optional: 刪除舊檔案
            # os.remove(old_path)
            
        except Exception as e:
            print(f"Failed to migrate {filename}: {e}")
            
    print(f"Successfully migrated {migrated_count} files.")

if __name__ == "__main__":
    migrate()
