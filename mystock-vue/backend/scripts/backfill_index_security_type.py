"""一次性修復腳本：把 PostgreSQL `symbols` 表裡已經寫入的指數／類股指數代碼標記
`security_type='index'`（大盤指數功能規劃書 ADR-I3）。

背景
----
`services/index_fetcher.py` 透過 `db/dual_write.py` 的 `dual_write_daily_data()` 把大盤／類股指數
寫進 `daily_stock_data`；`StockRepository.upsert_daily_data()` 為滿足外鍵，會順手在 `symbols` 表
FK-ensure 建一筆對應列。這個 FK-ensure 修復前只帶 `symbol`/`market_type`，沒有標記
`security_type='index'`，導致 `get_symbol_summaries()`（餵給 `/api/v1/stocks` 個股清單／切換股票
下拉選單）把這些指數當成個股一併回傳（例如台股類股輪動監控寫入的 `TWSE_S15`、`TWSE_S31`…）。

程式碼已修好「之後」的寫入（dual_write_daily_data 現在會帶 security_type="index"），
但本機／既有環境 Postgres 裡「之前」已經寫壞的列不會自動變好，需要跑這支腳本補標記一次。
冪等（用 upsert_symbol 的 ON CONFLICT DO UPDATE，重跑安全）。

用法
----
    python scripts/backfill_index_security_type.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from markets.tw_industries import TWSE_INDUSTRY_MAP, sector_code
from repositories.stock_repository import StockRepository
from services.index_fetcher import load_index_definitions


async def backfill() -> None:
    repo = StockRepository()
    count = 0

    for industry_code, meta in TWSE_INDUSTRY_MAP.items():
        if not meta.get("index_name"):
            continue
        code = sector_code(industry_code)
        await repo.upsert_symbol(symbol=code, market_type="tw", name=meta["name"], security_type="index")
        print(f"[ok] {code} ({meta['name']}) -> security_type=index")
        count += 1

    for d in load_index_definitions():
        await repo.upsert_symbol(symbol=d.code, market_type=d.market, name=d.name, security_type="index")
        print(f"[ok] {d.code} ({d.name}) -> security_type=index")
        count += 1

    print(f"完成，共標記 {count} 筆指數代碼。")


if __name__ == "__main__":
    asyncio.run(backfill())
