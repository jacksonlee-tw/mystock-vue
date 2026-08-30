"""
industry_chain/decouple_job.py
FR-9／FR-20：產業鏈動態脫鉤監控（見 docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md
§4.2、§4.6）。

跟 lead_lag_job.py 的 CCF 快取是兩件不同的事：那裡是「掃描 1~30 天找最佳延遲」，這裡是
「最近 N 天（預設 60）report 的單一相關係數是否低於門檻」——固定 lag=0，不做延遲掃描。
只寫 activity_log 事件，不改動／刪除 industry_chain_edges（AC-IC-6：脫鉤是觀察結果，不代表
關聯不存在）。
"""
from __future__ import annotations
import logging

from scipy.stats import pearsonr

from db.session import get_async_session
from industry_chain import config as ic_config
from industry_chain.lead_lag_job import price_series
from indicators.lead_lag import align_series, daily_returns
from repositories.activity_log_repository import ActivityLogRepository
from repositories.industry_chain_repository import IndustryChainRepository

logger = logging.getLogger("mystock-backend")

VIEW_ID = "industry_chain_decouple"


async def _check_edge_decoupling(edge: dict, threshold: float, window_days: int) -> dict | None:
    """回傳 `{"correlation": r, "sample_size": n}`（相關係數低於門檻，判定脫鉤）；
    資料不足或未低於門檻回傳 None。"""
    up_dates, up_closes = await price_series(edge["upstream_symbol"], edge["upstream_market"])
    down_dates, down_closes = await price_series(edge["downstream_symbol"], edge["downstream_market"])
    common_dates, aligned_up, aligned_down = align_series(up_dates, up_closes, down_dates, down_closes)
    if len(common_dates) < window_days + 1:
        return None  # 資料不足以覆蓋整個檢查窗口，不判定（避免用不足窗口的資料誤判脫鉤）

    recent_up = daily_returns(aligned_up[-(window_days + 1):])
    recent_down = daily_returns(aligned_down[-(window_days + 1):])
    if len(recent_up) < 3:
        return None

    try:
        r, _p = pearsonr(recent_up, recent_down)
    except Exception:
        return None

    if abs(r) >= threshold:
        return None
    return {"correlation": round(float(r), 4), "sample_size": len(recent_up)}


async def check_all_decoupling(chain_id: str | None = None) -> dict:
    """FR-20 排程主體：對每條 active 邊檢查是否脫鉤，低於門檻即記一筆 activity_log。
    單一邊計算失敗不影響其餘邊（比照 lead_lag_job.py 的既有容錯慣例）。"""
    defaults = ic_config.get_defaults()
    threshold = defaults["decouple_threshold"]
    window_days = defaults["decouple_check_window_days"]

    async with get_async_session() as session:
        repo = IndustryChainRepository(session)
        log_repo = ActivityLogRepository(session)
        edges = await repo.list_edges(chain_id=chain_id, is_active=True)

        processed = decoupled = failed = 0
        for edge in edges:
            processed += 1
            try:
                result = await _check_edge_decoupling(edge, threshold, window_days)
            except Exception as e:
                failed += 1
                logger.warning(f"[產業鏈] 脫鉤檢查失敗 {edge['upstream_symbol']}->{edge['downstream_symbol']}: {e}")
                continue
            if result is None:
                continue
            decoupled += 1
            await log_repo.log(
                "IC_DECOUPLE_DETECTED", view_id=VIEW_ID, success=True, rel_id=edge["id"],
                detail=f"{edge['chain_id']}: {edge['upstream_symbol']}->{edge['downstream_symbol']}",
                comments=f"近 {window_days} 日相關係數 {result['correlation']}（門檻 {threshold}），樣本數 {result['sample_size']}",
            )
            logger.info(f"[產業鏈] 脫鉤：{edge['upstream_symbol']}->{edge['downstream_symbol']} r={result['correlation']}")

        await session.commit()

    result = {"processed": processed, "decoupled": decoupled, "failed": failed}
    logger.info(f"[產業鏈] 脫鉤監控完成: {result}")
    return result
