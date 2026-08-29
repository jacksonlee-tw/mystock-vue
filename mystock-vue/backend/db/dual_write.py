"""爬蟲模組（fetcher.py / us_fetcher.py）呼叫的雙寫入口。

統一在此處理 PostgreSQL 暫時不可用時的容錯：只記錄警告，絕不讓 JSON 主流程失敗（見設計文件第 4.1 節）。
"""
import logging
from datetime import date as date_cls
from datetime import datetime
from typing import Optional

logger = logging.getLogger("mystock-backend")


def dual_write_symbol_industry(records: list[dict]) -> None:
    if not records:
        return
    try:
        from repositories.market_repository import (
            MarketRepository,
            _BackgroundSessionFactory,
            run_async,
        )

        repository = MarketRepository(session_factory=_BackgroundSessionFactory())
        run_async(repository.upsert_symbol_industries(records))
    except Exception as e:
        logger.warning(f"symbol_industry 寫入失敗: {e}")


def dual_write_daily_data(
    symbol: str,
    market_type: str,
    dated_records: dict,
    security_type: Optional[str] = None,
) -> None:
    if not dated_records:
        return
    try:
        from db.mapping import record_to_daily_row
        from repositories.stock_repository import StockRepository

        rows = [
            record_to_daily_row(symbol, market_type, date_key, record)
            for date_key, record in dated_records.items()
        ]
        repository = StockRepository()
        if security_type:
            repository.upsert_symbol_sync(symbol, market_type, security_type=security_type)
        repository.upsert_daily_data_sync(rows)
    except Exception as e:
        logger.warning(f"PostgreSQL 雙寫失敗 ({market_type}/{symbol}): {e}")


def dual_write_no_trading_days(market_type: str, dates) -> None:
    """把爬蟲探測到的非交易日寫入 market_no_trading_days（見 phase3_5 設計文件第 3.5 節）。"""
    if not dates:
        return
    try:
        from repositories.stock_repository import StockRepository

        parsed = {date_cls.fromisoformat(d) if isinstance(d, str) else d for d in dates}
        StockRepository().add_no_trading_days_sync(market_type, parsed)
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
        from repositories.stock_repository import StockRepository

        StockRepository().log_crawler_run_sync(
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
