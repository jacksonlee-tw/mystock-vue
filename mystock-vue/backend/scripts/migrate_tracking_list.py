"""一次性合流腳本：把 .env 的追蹤股票號碼（STOCK_CODES/US_STOCK_CODES）與既有觀察名單
（portfolio_watchlist）合流成單一清單（見
docs/14.追蹤個股清單優化/追蹤與觀察名單整合_規劃書.md §7.1）。

做法
----
1. 既有 portfolio_watchlist 的每一列，一律把 is_crawl_enabled 設為 TRUE（原本的觀察名單股票
   從此也會被每日爬蟲抓取，這正是解決「觀察名單沒有 K 線」問題所需的副作用，見規劃書 P2 問題）。
   只動這一個欄位，不覆寫使用者已填的 target_price／note／tag。
2. .env 的每個代碼，若尚未存在於 portfolio_watchlist，才新增一列（is_crawl_enabled=TRUE，
   source='env_import'，name 盡量從 symbols 主檔補、查不到則用代碼本身，added_date 取該股既有
   資料最早交易日、查不到則用今天）。已存在的代碼只確保 is_crawl_enabled=TRUE（步驟 1 已處理），
   不會覆寫既有欄位。
3. 依步驟 1＋2 的最終集合重寫 .env 鏡像。

冪等：以 (market, symbol) 唯一鍵判斷存在與否，重複執行結果相同。

用法
----
    python scripts/migrate_tracking_list.py --dry-run          # 只看差異報告，不寫入
    python scripts/migrate_tracking_list.py                    # 實際寫入
    python scripts/migrate_tracking_list.py --market us        # 只處理單一市場
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_target_stocks, save_target_stocks
from db.session import get_async_session, dispose_engine
from repositories.portfolio_repository import PortfolioRepository
from repositories.stock_repository import StockRepository


async def migrate_market(market: str, dry_run: bool) -> dict:
    env_codes = get_target_stocks(market=market)
    stock_repo = StockRepository()

    async with get_async_session() as session:
        repo = PortfolioRepository(session)
        existing_rows = await repo.list_watchlist(market)
        existing_by_symbol = {r["symbol"]: r for r in existing_rows}

        # ── 步驟 1：既有清單列一律確保 is_crawl_enabled=TRUE ──────────────
        promoted = [r["symbol"] for r in existing_rows if not r["is_crawl_enabled"]]
        if not dry_run:
            for r in existing_rows:
                if not r["is_crawl_enabled"]:
                    await repo.update_watchlist(r["id"], {"is_crawl_enabled": True})

        # ── 步驟 2：.env 代碼中尚未存在於清單者，新增為「純追蹤」列 ────────
        missing_codes = [c for c in env_codes if c not in existing_by_symbol]
        name_map: dict[str, str] = {}
        coverage_map: dict[str, dict] = {}
        if missing_codes:
            symbol_rows = await stock_repo.get_symbols(missing_codes, market)
            name_map = {row["symbol"]: row["name"] for row in symbol_rows if row.get("name")}
            coverage_map = await stock_repo.get_coverage_summary(missing_codes, market)

        added: list[str] = []
        if not dry_run:
            for code in missing_codes:
                payload = {
                    "market": market, "symbol": code,
                    "name": name_map.get(code, code),
                    "is_crawl_enabled": True, "source": "env_import",
                }
                start_date = coverage_map.get(code, {}).get("start_date")
                if start_date:
                    from datetime import date as _date
                    payload["added_date"] = _date.fromisoformat(start_date)
                await repo.upsert_watchlist(payload)
                added.append(code)
        else:
            added = missing_codes

        if not dry_run:
            await session.commit()

    # ── 步驟 3：重寫 .env 鏡像 ────────────────────────────────────────
    final_codes = sorted(set(env_codes) | set(existing_by_symbol.keys()))
    if not dry_run:
        save_target_stocks(final_codes, market=market)

    return {
        "market": market,
        "env_codes_before": len(env_codes),
        "watchlist_rows_before": len(existing_rows),
        "promoted_to_crawl": promoted,
        "added_from_env": added,
        "env_codes_after": len(final_codes),
    }


async def main(markets: list[str], dry_run: bool) -> None:
    print(f"{'[DRY-RUN] ' if dry_run else ''}追蹤與觀察名單合流遷移\n" + "=" * 60)
    try:
        for market in markets:
            report = await migrate_market(market, dry_run)
            print(f"\n市場：{market}")
            print(f"  遷移前 .env 追蹤代碼數：{report['env_codes_before']}")
            print(f"  遷移前清單列數（觀察名單）：{report['watchlist_rows_before']}")
            print(f"  原本暫停抓取、本次改為納入抓取的代碼數：{len(report['promoted_to_crawl'])}"
                  + (f" {report['promoted_to_crawl']}" if report["promoted_to_crawl"] else ""))
            print(f"  從 .env 新增為「純追蹤」清單列：{len(report['added_from_env'])} 檔"
                  + (f" {report['added_from_env']}" if report["added_from_env"] else ""))
            print(f"  遷移後 .env 追蹤代碼數：{report['env_codes_after']}"
                  f"（{'預估' if dry_run else '實際'}）")
        if dry_run:
            print("\n[DRY-RUN] 未寫入任何資料，重新執行不加 --dry-run 以實際套用。")
        else:
            print("\n完成。可執行 GET /api/v1/watchlist 或前端「追蹤與觀察名單」頁確認結果。")
    finally:
        await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="只顯示差異報告，不寫入")
    parser.add_argument("--market", choices=["tw", "us"], default=None, help="只處理單一市場，預設兩者皆處理")
    args = parser.parse_args()

    target_markets = [args.market] if args.market else ["tw", "us"]
    asyncio.run(main(target_markets, args.dry_run))
