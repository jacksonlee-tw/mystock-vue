"""個股產業標籤一次性初始化腳本（見 docs/10.加權指數/大盤指數功能規劃書.md §8.2）。

可重複執行（idempotent：JSON 用 dict.update() 合併，Postgres 用 ON CONFLICT DO UPDATE）。
用法：
    python scripts/init_industries.py               # 台股全市場 + 目前追蹤的美股清單
    python scripts/init_industries.py --market tw     # 只更新台股
    python scripts/init_industries.py --market us     # 只更新美股（僅限目前追蹤清單，見
                                                        # services/industry_fetcher.py 的說明：
                                                        # 美股沒有 TWSE 那種全市場一次性 API）
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import get_target_stocks
from services.industry_fetcher import sync_tw_industries, sync_us_industries


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--market", default=None, choices=["tw", "us"], help="只更新指定市場（預設兩者都跑）")
    args = parser.parse_args()

    if args.market in (None, "tw"):
        count = sync_tw_industries()
        print(f"台股產業標籤已更新 {count} 檔")

    if args.market in (None, "us"):
        symbols = get_target_stocks(market="us")
        count = sync_us_industries(symbols)
        print(f"美股產業標籤已更新 {count} / {len(symbols)} 檔（僅限目前追蹤清單）")


if __name__ == "__main__":
    main()
