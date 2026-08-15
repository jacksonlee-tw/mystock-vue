"""大盤指數歷史資料一次性初始化腳本（見 docs/10.加權指數/大盤指數功能規劃書.md 第 3.3 節 Phase 1）。

可重複執行（底層 run_index_fetch_process 以 dict.update() 合併既有資料，同日期覆蓋、不重複累加）。
用法：
    python scripts/init_index_history.py                       # 全部指數，預設 INDEX_HISTORY_YEARS（.env，預設 5）年
    python scripts/init_index_history.py --years 3              # 回補近 3 年
    python scripts/init_index_history.py --market us             # 只回補美股指數
    python scripts/init_index_history.py --codes TWII,SOX        # 只回補指定代號
    python scripts/init_index_history.py --mode repair            # 忽略既有資料，完整區間重抓
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import get_index_history_years
from services.fetcher import fetch_status
from services.index_fetcher import run_index_fetch_process


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--years", type=int, default=None, help="回補年數（預設讀 .env 的 INDEX_HISTORY_YEARS）")
    parser.add_argument("--market", default=None, help="只回補指定市場：tw 或 us（預設全部）")
    parser.add_argument("--codes", default=None, help="只回補指定代號，逗號分隔，例如 TWII,SOX")
    parser.add_argument("--mode", default="incremental", choices=["incremental", "repair"],
                         help="incremental=只補缺口（預設）；repair=忽略既有資料完整重抓")
    args = parser.parse_args()

    years = args.years or get_index_history_years()
    months = years * 12
    codes = [c.strip() for c in args.codes.split(",") if c.strip()] if args.codes else None

    snapshot = fetch_status.get_snapshot()
    if snapshot["is_running"]:
        print("已有抓取任務執行中，請稍後再試。")
        sys.exit(1)

    print(f"開始回補指數歷史資料：market={args.market or '全部'}, codes={codes or '全部'}, "
          f"years={years}, mode={args.mode}")

    result = run_index_fetch_process(
        market=args.market, codes=codes, months=months, mode=args.mode, trigger_type="manual",
    )

    print(f"完成。成功: {result['success']}")
    if result["skipped"]:
        print(f"略過（無新資料或尚未支援自動回補歷史）: {result['skipped']}")
    if result["failed"]:
        print(f"失敗: {result['failed']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
