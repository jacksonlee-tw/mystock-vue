"""爬蟲模組（fetcher.py / us_fetcher.py）呼叫的雙寫入口。

統一在此處理 PostgreSQL 暫時不可用時的容錯：只記錄警告，絕不讓 JSON 主流程失敗（見設計文件第 4.1 節）。
"""
import logging
from datetime import date as date_cls
from datetime import datetime
from typing import Optional

logger = logging.getLogger("mystock-backend")


def dual_write_daily_data(symbol: str, market_type: str, dated_records: dict,
                           security_type: Optional[str] = None) -> None:
    """`security_type`：僅供指數呼叫端（services/index_fetcher.py）標記 `'index'` 用，讓
    symbols 表能區分指數與個股（大盤指數功能規劃書 ADR-I3）。個股爬蟲不傳，維持原行為
    （FK-ensure 只補 symbol/market_type，不動 security_type，避免蓋掉代碼主檔同步的分類）。"""
    if not dated_records:
        return
    try:
        from db.mapping import record_to_daily_row
        from repositories.stock_repository import StockRepository, _BackgroundSessionFactory

        rows = [
            record_to_daily_row(symbol, market_type, date_key, record)
            for date_key, record in dated_records.items()
        ]
        StockRepository(session_factory=_BackgroundSessionFactory()).upsert_daily_data_sync(
            rows, security_type=security_type
        )
    except Exception as e:
        logger.warning(f"PostgreSQL 雙寫失敗 ({market_type}/{symbol}): {e}")


def dual_write_symbol_industry(rows: list) -> None:
    """個股產業標籤雙寫（大盤指數功能規劃書 §8.2）。rows: [{"symbol","market_type",
    "industry_code","industry_name"}, ...]。同樣容錯：Postgres 失敗只記警告，
    JSON（services/industry_fetcher.py 的 save_industries_json）才是主要儲存。"""
    if not rows:
        return
    try:
        from repositories.stock_repository import StockRepository, _BackgroundSessionFactory

        StockRepository(session_factory=_BackgroundSessionFactory()).upsert_symbol_industry_sync(rows)
    except Exception as e:
        logger.warning(f"個股產業標籤 PostgreSQL 雙寫失敗: {e}")


def dual_write_no_trading_days(market_type: str, dates, source: str = "probed") -> None:
    """把爬蟲探測到的非交易日寫入 market_no_trading_days（見 phase3_5 設計文件第 3.5 節）。"""
    if not dates:
        return
    try:
        from repositories.stock_repository import StockRepository, _BackgroundSessionFactory

        parsed = {date_cls.fromisoformat(d) if isinstance(d, str) else d for d in dates}
        StockRepository(session_factory=_BackgroundSessionFactory()).add_no_trading_days_sync(
            market_type, parsed, source=source
        )
    except Exception as e:
        logger.warning(f"market_no_trading_days 寫入失敗 ({market_type}): {e}")


def log_crawler_run(
    market_type: str,
    trigger_type: str,
    started_at: datetime,
    status: str,
    symbols_success: int = 0,
    symbols_failed: int = 0,
    error_message: Optional[str] = None,
) -> None:
    try:
        from repositories.stock_repository import StockRepository, _BackgroundSessionFactory

        StockRepository(session_factory=_BackgroundSessionFactory()).log_crawler_run_sync(
            market_type=market_type,
            trigger_type=trigger_type,
            started_at=started_at,
            finished_at=datetime.now(),
            status=status,
            symbols_success=symbols_success,
            symbols_failed=symbols_failed,
            error_message=error_message,
        )
    except Exception as e:
        logger.warning(f"crawler_logs 寫入失敗 ({market_type}): {e}")
