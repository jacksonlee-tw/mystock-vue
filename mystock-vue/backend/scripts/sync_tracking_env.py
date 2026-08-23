"""手動修復追蹤清單 `.env` 與 DB（`portfolio_watchlist`）不同步的情況，見
docs/14.追蹤個股清單優化/追蹤與觀察名單整合_規劃書.md §4.3、§8（P2）。

正常情況下兩邊應該恆為一致：`services/tracking_service.py` 每次清單異動都會在 DB commit 成功後
重寫 `.env` 鏡像。會不一致通常是因為：
  - Postgres 一度連不上，`/api/v1/stocks/tracked` 相容層退回直接寫 `.env`，之後沒有清單操作
    觸發重新鏡像；
  - 有人手動編輯了 `backend/.env` 的 STOCK_CODES/US_STOCK_CODES；
  - 尚未執行過 `scripts/migrate_tracking_list.py`（DB 裡還沒有 .env 既有代碼對應的列）。

main.py 的 lifespan 啟動時只會對帳並印警告，不會自動修改（避免啟動時偷改使用者設定）；
發現不一致時用本腳本指定要「以哪一邊為準」修復。

用法
----
    python scripts/sync_tracking_env.py --market tw --from db        # 以 DB 為準覆寫 .env 鏡像
    python scripts/sync_tracking_env.py --market tw --from env       # 以 .env 為準，把缺少的代碼補進 DB
    python scripts/sync_tracking_env.py --market tw --from db --dry-run
    python scripts/sync_tracking_env.py --market us --from env
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import dispose_engine
from services.tracking_service import diff_env_vs_db, sync_env_mirror


async def sync_from_db(market: str, dry_run: bool) -> None:
    """以 DB 的 is_crawl_enabled=TRUE 代號為準，覆寫 .env 鏡像。"""
    diff = await diff_env_vs_db(market)
    if not diff["checked"]:
        print(f"[{market}] 無法連線資料庫，略過")
        return
    if diff["in_sync"]:
        print(f"[{market}] 已同步，無需修復")
        return

    print(f"[{market}] 將以 DB 為準覆寫 .env：")
    if diff["only_in_db"]:
        print(f"  新增進 .env：{diff['only_in_db']}")
    if diff["only_in_env"]:
        print(f"  從 .env 移除（DB 中沒有或未啟用抓取）：{diff['only_in_env']}")
    if dry_run:
        print(f"[{market}] [DRY-RUN] 未寫入")
        return
    await sync_env_mirror(market)
    print(f"[{market}] 已完成")


async def sync_from_env(market: str, dry_run: bool) -> None:
    """以 .env 的代號為準，把缺少的代碼補進 DB（等同單市場版的 migrate_tracking_list.py，
    可重複執行，冪等）。"""
    from scripts.migrate_tracking_list import migrate_market  # 複用同一套合流邏輯，不重寫一份

    report = await migrate_market(market, dry_run)
    print(f"[{market}] 從 .env 補進 DB：")
    if report["promoted_to_crawl"]:
        print(f"  原本暫停抓取、改為納入抓取：{report['promoted_to_crawl']}")
    if report["added_from_env"]:
        print(f"  新增為「純追蹤」清單列：{report['added_from_env']}")
    if not report["promoted_to_crawl"] and not report["added_from_env"]:
        print("  已同步，無需修復")
    if dry_run:
        print(f"[{market}] [DRY-RUN] 未寫入")


async def main(market: str, source: str, dry_run: bool) -> None:
    try:
        if source == "db":
            await sync_from_db(market, dry_run)
        else:
            await sync_from_env(market, dry_run)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--market", choices=["tw", "us"], required=True, help="要修復的市場")
    parser.add_argument("--from", dest="source", choices=["db", "env"], required=True, help="以哪一邊的資料為準")
    parser.add_argument("--dry-run", action="store_true", help="只顯示差異，不寫入")
    args = parser.parse_args()

    asyncio.run(main(args.market, args.source, args.dry_run))
