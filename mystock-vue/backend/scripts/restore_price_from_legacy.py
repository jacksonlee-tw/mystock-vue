"""一次性修復腳本：從 migration 前的舊資料檔補回被 0 覆蓋的行情。

背景
----
`services/fetcher.py` 舊版在抓不到 STOCK_DAY 行情時，會把 開/高/低/收 填成
字面 0.0 後寫入檔案（`pd.isna(0.0)` 為 False，所以躲過了既有的過濾），把
`data/tw/*.json` 中原本正確的價格覆蓋掉。法人與融資融券資料未受影響。

migration 時 `scripts/migrate_data_layout.py` 只複製、沒有刪除舊檔，因此
`data/*.json` 仍保有覆蓋發生前的正確價格，可直接拿來還原。

用法
----
    python scripts/restore_price_from_legacy.py --dry-run   # 只檢視不寫入
    python scripts/restore_price_from_legacy.py             # 實際寫入

只會修改「價格為 0 或缺漏」的日期，其餘欄位一律不動。
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATA_DIR
from markets.tw import FIELD_MAP
from services.fetcher import load_stock_json, stock_json_path, _normalize_keys

# 需要從舊檔還原的價格欄位（以英文 key 表示）
PRICE_KEYS = ["open", "high", "low", "close", "volume", "amount", "trades"]


def load_legacy(stock_id: str) -> dict:
    """讀取 migration 前的舊檔，並把中文 key 正規化成英文。"""
    path = os.path.join(DATA_DIR, f"{stock_id}.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {date_key: _normalize_keys(record) for date_key, record in raw.items()}


def restore_stock(stock_id: str, dry_run: bool) -> dict:
    current = load_stock_json(stock_id, market="tw")
    if not current:
        return {"status": "no_current_data", "fixed": 0}

    damaged = sorted(d for d in current if not current[d].get("close"))
    if not damaged:
        return {"status": "healthy", "fixed": 0}

    legacy = load_legacy(stock_id)
    if not legacy:
        return {"status": "no_legacy_backup", "fixed": 0, "damaged": len(damaged)}

    fixed_dates = []
    unrecoverable = []

    for date_key in damaged:
        source = legacy.get(date_key)
        if not source or not source.get("close"):
            unrecoverable.append(date_key)
            continue

        record = current[date_key]
        for key in PRICE_KEYS:
            if source.get(key) is not None:
                record[key] = source[key]

        # 估算買賣超金額當初是用 close=0 算出來的，要跟著重算
        total_lots = record.get("institutional_total")
        if total_lots is not None:
            record["institutional_amount_est"] = round(total_lots * record["close"] / 10, 2)

        fixed_dates.append(date_key)

    if fixed_dates and not dry_run:
        # 順便把殘留的中文 key 一併正規化，避免同筆記錄中英文並存
        cleaned = {k: _normalize_keys(v) for k, v in sorted(current.items())}
        with open(stock_json_path(stock_id, "tw"), "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)

    return {
        "status": "fixed",
        "fixed": len(fixed_dates),
        "damaged": len(damaged),
        "range": (fixed_dates[0], fixed_dates[-1]) if fixed_dates else None,
        "unrecoverable": unrecoverable,
    }


def main():
    parser = argparse.ArgumentParser(description="從舊資料檔還原被 0 覆蓋的行情")
    parser.add_argument("--dry-run", action="store_true", help="只顯示將修改的內容，不寫入檔案")
    parser.add_argument("stocks", nargs="*", help="指定股票代號；省略則掃描 data/tw/ 下全部檔案")
    args = parser.parse_args()

    tw_dir = os.path.join(DATA_DIR, "tw")
    codes = args.stocks or sorted(
        f[:-5] for f in os.listdir(tw_dir)
        if f.endswith(".json") and not f.startswith("_")
    )

    if args.dry_run:
        print("=== DRY RUN（不會寫入任何檔案）===\n")

    total_fixed = 0
    for code in codes:
        result = restore_stock(code, args.dry_run)
        status = result["status"]

        if status == "healthy":
            print(f"[--] {code:<8} 資料完好，無需修復")
        elif status == "no_current_data":
            print(f"[--] {code:<8} 尚無資料檔")
        elif status == "no_legacy_backup":
            print(f"[!] {code:<8} 有 {result['damaged']} 天缺價，但找不到舊備份 → 請改用 UI 的「重新抓取」")
        else:
            rng = result["range"]
            print(f"[OK] {code:<8} 修復 {result['fixed']}/{result['damaged']} 天  ({rng[0]} ~ {rng[1]})")
            if result["unrecoverable"]:
                print(f"       其中 {len(result['unrecoverable'])} 天舊備份也沒有，需重新抓取")
            total_fixed += result["fixed"]

    print(f"\n合計修復 {total_fixed} 筆" + ("（dry-run，未實際寫入）" if args.dry_run else ""))


if __name__ == "__main__":
    main()
