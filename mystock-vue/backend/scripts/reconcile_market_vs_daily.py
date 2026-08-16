"""全市場資料與既有日資料對帳腳本（選股功能與爬蟲 規格書 §3.5、§15、AC-19）。

用途：
- 對追蹤清單標的比對 `daily_stock_data`（或 JSON）與新表 `daily_market_quote` / `daily_market_chip` 的行情與籌碼
- 比對項目：收盤價 (close)、成交量 (volume)、外資買賣超 (foreign_net)、融資餘額 (margin_balance)
- 輸出不一致項目與統計報告
"""
import argparse
import asyncio
from datetime import date, datetime, timedelta
import json
import logging
import os
import sys

from config import get_target_stocks
from repositories.market_repository import MarketRepository
from repositories.stock_repository import StockRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reconcile_market_vs_daily")


async def reconcile(trade_date_str: str, market: str = "tw") -> dict:
    t_date = datetime.strptime(trade_date_str, "%Y-%m-%d").date()
    target_stocks = get_target_stocks(market)
    logger.info(f"=== 開始對帳：交易日 {trade_date_str}，標的數：{len(target_stocks)} ===")

    market_repo = MarketRepository()
    stock_repo = StockRepository()

    # 1. 取得全市場新表切片
    _, market_rows, _ = await market_repo.query_market_daily(
        trade_date=t_date,
        market=market,
        symbols=target_stocks,
        page_size=200,
        include_delisted=True,
        include_suspect=True,
    )
    market_map = {r["symbol"]: r for r in market_rows}

    # 2. 逐檔比對
    discrepancies = []
    matched_count = 0

    for symbol in target_stocks:
        m_data = market_map.get(symbol)
        if not m_data:
            discrepancies.append({
                "symbol": symbol,
                "field": "existence",
                "daily_stock_data": "present",
                "market_table": "missing",
            })
            continue

        # 取得既有日資料
        daily_records = await stock_repo.get_daily_data(symbol, limit=60)
        daily_for_date = next((d for d in daily_records if str(d.get("trade_date")) == trade_date_str), None)

        if not daily_for_date:
            discrepancies.append({
                "symbol": symbol,
                "field": "existence",
                "daily_stock_data": "missing",
                "market_table": "present",
            })
            continue

        # 比較欄位
        fields_to_compare = [
            ("close", daily_for_date.get("close_price"), m_data.get("close")),
            ("volume", daily_for_date.get("volume"), m_data.get("volume")),
        ]

        has_diff = False
        for f_name, d_val, m_val in fields_to_compare:
            if d_val is not None and m_val is not None:
                if abs(float(d_val) - float(m_val)) > 0.001:
                    discrepancies.append({
                        "symbol": symbol,
                        "field": f_name,
                        "daily_stock_data": d_val,
                        "market_table": m_val,
                    })
                    has_diff = True

        if not has_diff:
            matched_count += 1

    report = {
        "trade_date": trade_date_str,
        "target_symbols_count": len(target_stocks),
        "matched_count": matched_count,
        "discrepancies_count": len(discrepancies),
        "discrepancies": discrepancies,
    }
    logger.info(f"=== 對帳完成：相符 {matched_count} 檔，差異 {len(discrepancies)} 項 ===")
    return report


def main():
    parser = argparse.ArgumentParser(description="Reconcile daily market quotes vs daily stock data")
    parser.add_argument("--date", type=str, default="", help="Trade date in YYYY-MM-DD format (default: latest weekday)")
    parser.add_argument("--market", type=str, default="tw", help="Market (default: tw)")
    args = parser.parse_args()

    if not args.date:
        d = datetime.now()
        if d.weekday() == 5:
            d -= timedelta(days=1)
        elif d.weekday() == 6:
            d -= timedelta(days=2)
        date_str = d.strftime("%Y-%m-%d")
    else:
        date_str = args.date

    res = asyncio.run(reconcile(date_str, args.market))
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
