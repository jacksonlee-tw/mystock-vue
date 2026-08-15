"""一次性歷史資料匯入腳本：將 backend/data/**/*.json 匯入 PostgreSQL（設計文件 Phase 2）。

可重複執行（idempotent，靠 (symbol, trade_date) 的 Unique Index 做 Upsert）。
用法： python scripts/import_json_to_postgres.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import DATA_DIR
from db.mapping import record_to_daily_row
from repositories.stock_repository import StockRepository

_MARKET_DIRS = ("tw", "us")


def _iter_symbol_files():
    """列出所有股票 JSON 檔，回傳 (symbol, market_type, file_path)。

    根目錄下若已有同代號的市場子目錄檔案，代表是 migrate_data_layout.py 搬遷後留下的舊檔，略過以免
    用較舊的資料覆蓋掉子目錄裡較新的資料。
    """
    migrated_symbols = set()
    for market in _MARKET_DIRS:
        market_dir = os.path.join(DATA_DIR, market)
        if not os.path.isdir(market_dir):
            continue
        for filename in sorted(os.listdir(market_dir)):
            if filename.startswith("_") or not filename.endswith(".json"):
                continue
            symbol = filename[:-5]
            migrated_symbols.add(symbol)
            yield symbol, market, os.path.join(market_dir, filename)

    for filename in sorted(os.listdir(DATA_DIR)):
        if filename.startswith("_") or not filename.endswith(".json"):
            continue
        symbol = filename[:-5]
        if symbol in migrated_symbols:
            print(f"[skip] {filename} 已有市場子目錄版本，略過根目錄舊檔")
            continue
        yield symbol, "tw", os.path.join(DATA_DIR, filename)


async def import_all() -> None:
    repo = StockRepository()
    total_files = 0
    total_rows = 0

    for symbol, market_type, path in _iter_symbol_files():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[error] 讀取 {path} 失敗: {e}")
            continue

        if not data:
            continue

        # 最新一天常常只由 backfill_daily_quotes() 純行情補上，不帶 name 欄位（見
        # services/stock_service.py 的 discover_available_stocks() 同一段註解）；若直接取
        # 最後一筆，name 會是 None，upsert_symbol() 的 ON CONFLICT DO UPDATE 又是整欄覆蓋，
        # 會把 symbols 表裡原本正確的名稱洗成空值。改為往前找最近一筆真的有 name 的記錄。
        sorted_dates = sorted(data.keys())
        name = next((data[d].get("name") for d in reversed(sorted_dates) if data[d].get("name")), None)
        await repo.upsert_symbol(symbol=symbol, market_type=market_type, name=name)

        rows = [
            record_to_daily_row(symbol, market_type, date_key, record) for date_key, record in data.items()
        ]
        await repo.upsert_daily_data(rows)

        total_files += 1
        total_rows += len(rows)
        print(f"[ok] {market_type}/{symbol}: 匯入 {len(rows)} 筆")

    print(f"完成：共處理 {total_files} 檔標的，{total_rows} 筆每日資料。")


if __name__ == "__main__":
    asyncio.run(import_all())
