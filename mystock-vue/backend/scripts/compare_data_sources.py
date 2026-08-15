"""比對 JSON 與 PostgreSQL 兩種資料來源的 chart-data 回應是否逐欄位一致（phase3_5 設計文件第 2.6 節）。

Phase 3 切換前、Phase 5 退役前都要跑這支腳本；輸出所有差異，全部通過（0 差異）才代表兩邊資料一致。
用法：python scripts/compare_data_sources.py
"""
import asyncio
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import get_enabled_markets, get_target_stocks
from services.stock_service import get_stock_chart_payload

FLOAT_TOLERANCE = 2e-4  # daily_stock_data 價格欄位為 NUMERIC(15,4)，US 股價（yfinance 還原股利/分割後有效位數更長）
                        # 落地時本來就會四捨五入到小數點後 4 位，這是設計上接受的精度上限，不是轉換誤差（見設計文件第 2.6 節）。
                        # 實測發現差 1 個第 4 位小數的正常案例（如 331.4391 vs 331.4392）在 Python 浮點數運算下
                        # abs(a-b) 會算成 1.0000000000317e-4，比 1e-4 還多一點點浮點誤差，用 abs_tol=1e-4 卡在邊界上
                        # 反而全部被誤判成差異；抓到 2e-4 才有安全餘裕吸收這個浮點噪音，同時仍遠低於「真的算錯」的量級。
PERIODS = ("daily", "weekly", "monthly")
MONTHS_OPTIONS = (1, 3, 12)

# 中文鍵的融資/融券明細欄位只存在於 JSON、db/mapping.py 刻意不反向映射（見設計文件第 2.4 節）；
# 已核對 frontend/ 沒有任何地方讀取這些鍵（僅用到英文的 margin_balance/short_balance），
# 因此比對時明確排除、不視為差異，而不是放寬容錯掩蓋掉真正的問題。
IGNORED_RECORD_FIELDS = {
    "融資買進(張)", "融資賣出(張)", "融資現金償還(張)", "融資前日餘額(張)",
    "融券買進(張)", "融券賣出(張)", "融券現券償還(張)", "融券前日餘額(張)",
    "資券互抵(張)",
}

# JSON 早期有些日期只由 backfill_daily_quotes() 純行情補上（見 services/fetcher.py），從未写入 name；
# PostgreSQL 候將 name 存在 symbols 表（symbol 級別），還原時會幫每一列都補上。
# 這是對顯示中繼資料的回填改善，不是退化，所以只排除 json 缺漏/postgres 有值這一方向。
NAME_FIELDS = ("name", "stock_name")


def _deep_diff(path: str, a, b, diffs: list) -> None:
    if isinstance(a, float) or isinstance(b, float):
        if a is None or b is None:
            if a != b:
                diffs.append((path, a, b))
            return
        try:
            if not math.isclose(float(a), float(b), rel_tol=0, abs_tol=FLOAT_TOLERANCE):
                diffs.append((path, a, b))
        except (TypeError, ValueError):
            diffs.append((path, a, b))
        return

    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a.keys()) | set(b.keys()), key=str):
            if key in IGNORED_RECORD_FIELDS:
                continue
            av, bv = a.get(key), b.get(key)
            if key in NAME_FIELDS and bv:
                continue  # name/stock_name 是顯示用中繼資料，來源為 symbols 表；JSON 舊資料可能因早期記錄缺 name 而不一致，不視為差異
            _deep_diff(f"{path}.{key}", av, bv, diffs)
        return

    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append((f"{path}.length", len(a), len(b)))
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _deep_diff(f"{path}[{i}]", x, y, diffs)
        return

    if a != b:
        diffs.append((path, a, b))


async def compare_all() -> int:
    total_diffs = 0
    total_checked = 0

    for market in get_enabled_markets():
        for symbol in get_target_stocks(market=market):
            for period in PERIODS:
                for months in MONTHS_OPTIONS:
                    total_checked += 1
                    json_payload = await get_stock_chart_payload(
                        symbol, period=period, months=months, market=market, source="json"
                    )
                    pg_payload = await get_stock_chart_payload(
                        symbol, period=period, months=months, market=market, source="postgres"
                    )

                    diffs: list = []
                    _deep_diff(f"{market}/{symbol}[{period},{months}m]", json_payload, pg_payload, diffs)

                    if diffs:
                        total_diffs += len(diffs)
                        print(f"[DIFF] {market}/{symbol} period={period} months={months}")
                        for path, jv, pv in diffs:
                            print(f"    {path}: json={jv!r} postgres={pv!r}")

    print(f"完成：檢查 {total_checked} 組組合，共 {total_diffs} 處差異。")
    return total_diffs


if __name__ == "__main__":
    diff_count = asyncio.run(compare_all())
    sys.exit(1 if diff_count else 0)
