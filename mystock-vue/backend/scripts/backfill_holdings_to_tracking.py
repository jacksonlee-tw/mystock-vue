"""一次性回填腳本：把「既有交易紀錄」涵蓋的股票補進追蹤清單，見
docs/15.追蹤個股清單優化/追蹤與觀察名單整合_規劃書.md §12（ADR-08、ADR-09）。

背景
----
ADR-08 讓 `POST /api/v1/transactions`（新增交易）之後自動 upsert 進 `portfolio_watchlist`，
但這是「寫入時」才生效的即時掛勾，對 ADR-08 上線前就已經存在的舊交易不會回溯生效（見 R-08-2）。
本腳本掃描 `portfolio_transaction` 目前所有 distinct `(market, symbol)`，逐筆呼叫與 ADR-08
相同語意的 `tracking_service.upsert_from_holding()`：已在清單中的項目不覆寫既有目標價／
tag／追蹤原因，不在清單中的新增為純追蹤（`target_price=NULL`, `source='holding'`）。

冪等：以 (market, symbol) 唯一鍵 upsert，可重複執行。

用法
----
    python scripts/backfill_holdings_to_tracking.py             # 實際寫入
    python scripts/backfill_holdings_to_tracking.py --dry-run    # 只列出將被回填的股票，不寫入
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import dispose_engine, get_async_session
from repositories.portfolio_repository import PortfolioRepository
from services import tracking_service


async def _distinct_holding_symbols() -> list[tuple[str, str, str]]:
    """回傳目前有交易紀錄的 distinct (market, symbol, name)；name 取該 symbol 最新一筆交易的名稱。"""
    async with get_async_session() as session:
        transactions = await PortfolioRepository(session).list_transactions()

    seen: dict[tuple[str, str], str] = {}
    for t in transactions:
        seen[(t["market"], t["symbol"])] = t["name"]  # 後面的（較新的）覆蓋前面的，取最新名稱
    return [(market, symbol, name) for (market, symbol), name in seen.items()]


async def main(dry_run: bool) -> None:
    try:
        holdings = await _distinct_holding_symbols()
        if not holdings:
            print("目前沒有任何交易紀錄，無需回填")
            return

        existing_by_market: dict[str, set[str]] = {}
        for market, symbol, name in holdings:
            if market not in existing_by_market:
                existing_by_market[market] = {row["symbol"] for row in await tracking_service.list_items(market)}

        to_add = [
            (market, symbol, name) for market, symbol, name in holdings
            if symbol not in existing_by_market.get(market, set())
        ]
        already_tracked = len(holdings) - len(to_add)

        print(f"交易紀錄涵蓋 {len(holdings)} 檔股票，其中 {already_tracked} 檔已在追蹤清單中，{len(to_add)} 檔尚未追蹤：")
        for market, symbol, name in to_add:
            print(f"  [{market}] {symbol} {name}")

        if dry_run:
            print("[DRY-RUN] 未寫入")
            return

        for market, symbol, name in to_add:
            await tracking_service.upsert_from_holding(market, symbol, name)
        print(f"已回填 {len(to_add)} 檔股票進追蹤清單（is_crawl_enabled=true, source='holding'）")
    finally:
        await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="只顯示將回填的股票，不寫入")
    args = parser.parse_args()

    asyncio.run(main(args.dry_run))

