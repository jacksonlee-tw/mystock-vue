"""全市場代碼／名稱主檔一次性初始化腳本（見 services/symbol_master_fetcher.py）。

台股來源：TWSE／TPEx ISIN 編碼網頁。美股來源：SEC EDGAR 官方代碼清單。
可重複執行（idempotent：Postgres 用 ON CONFLICT DO UPDATE）。純 Postgres，沒有 JSON 落地，
執行前請確認 backend/.env 的 POSTGRES_* 設定正確且資料庫可連線。

用法：
    python scripts/init_symbol_master.py               # 台股 + 美股都跑
    python scripts/init_symbol_master.py --market tw    # 只更新台股
    python scripts/init_symbol_master.py --market us    # 只更新美股
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.symbol_master_fetcher import sync_tw_symbol_master, sync_us_symbol_master


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--market", default=None, choices=["tw", "us"], help="只更新指定市場（預設兩者都跑）")
    args = parser.parse_args()

    if args.market in (None, "tw"):
        count = await sync_tw_symbol_master()
        print(f"台股全市場代碼主檔已更新 {count} 檔")

    if args.market in (None, "us"):
        count = await sync_us_symbol_master()
        print(f"美股全市場代碼主檔已更新 {count} 檔")


if __name__ == "__main__":
    asyncio.run(main())
