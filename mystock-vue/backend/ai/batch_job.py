"""
ai/batch_job.py
Phase5-三層式 AI 決策引擎與戰情室.md FR-5.3：監控清單批次產生。由
services/scheduler.py::_scan_after_fetch() 排在既有 fetch→scan 鏈之後串行呼叫（Q4 決議）。

批次沒有瀏覽器可產生 K 線圖截圖，改用 AIProvider.extract_structured()（純文字結構化輸出，
Phase3 產業鏈萃取已在用同一方法，見 BATCH_SYSTEM_PROMPT），trigger_type="batch" 走獨立配額
（AI_BATCH_DAILY_QUOTA，§8），與手動點擊互不排擠（guard.resolve_report_slot()）。

單檔任何失敗都只記原因、絕不中斷整批（NFR-3／AC-P5-08）；批次配額用盡時，該檔與後續所有未處理
標的一併記為 skipped，不得靜默跳過（AC-P5-07）。逐檔依序執行（不併發）：避免同時撞 Provider
限流，且 guard.py 的佔位機制本就假設同一時間一個標的一個呼叫（比照 industry_chain 排程 job）。
"""
from __future__ import annotations
import logging
from datetime import date
from typing import Any, Optional

from ai import config as ai_config
from ai import guard
from ai.cost import estimate_cost
from ai.errors import (
    AIAnalysisInProgressException, AIProviderMisconfiguredException, AIQuotaExceededException,
)
from ai.prompt import BATCH_SYSTEM_PROMPT, build_user_prompt
from ai.providers import get_provider
from ai.recorder import AIRecorder
from ai.rule_alignment import compute_alignment
from ai.schema import LLMAnalysisReport, from_llm_report
from ai.summary import build_quant_summary
from db.session import get_async_session

logger = logging.getLogger("mystock-backend")

VIEW_ID = "war_room_batch"


async def get_eligible_symbols(market: str) -> tuple[list[str], list[str]]:
    """監控清單扣除 ETF 排除（Q2 決議）後的批次候選名單。回傳 (eligible, etf_excluded)。

    抽成獨立函式供 `run_watchlist_batch()` 與 `api/v1/endpoints/ai_batch.py` 的費用預估
    端點共用——預估必須看到跟實際執行完全相同的候選清單，兩處各自算一份容易對不上。"""
    from services.tracking_service import get_crawl_enabled_symbols
    symbols = await get_crawl_enabled_symbols(market)

    if market != "tw" or not ai_config.get_batch_exclude_etf():
        return symbols, []

    from repositories.stock_repository import StockRepository
    from strategies.scanner import is_chip_excluded

    rows = await StockRepository().list_symbols(market_type=market)
    security_type_map = {r["symbol"]: r.get("security_type") for r in rows}
    keep, excluded = [], []
    for s in symbols:
        (excluded if is_chip_excluded(s, security_type_map.get(s)) else keep).append(s)
    return keep, excluded


async def run_watchlist_batch(market: str, symbols: Optional[list[str]] = None) -> dict[str, Any]:
    """對 market 監控清單批次產生 AI 報告。回傳彙總結果供排程 log 與呼叫端判斷是否需要推播。

    symbols：戰情室多選標的、手動觸發時由呼叫端指定（見 api/v1/endpoints/ai_batch.py 的
    /batch/trigger）。這是使用者從監控清單裡明確勾選出來的子集合，因此略過 get_eligible_symbols()
    的 ETF 排除規則——排除規則的用意是自動批次不要「順便」碰到 ETF，使用者自己勾選就是明確
    的例外意圖（既有的個股頁「可在個股頁手動點擊產生」說明本就允許這個例外，多選只是同一件事
    的另一個入口）。未帶 symbols（None）則維持原本「整份監控清單」的既有行為。"""
    if not ai_config.is_enabled() or not ai_config.get_batch_enabled():
        return {"market": market, "skipped_all": True, "reason": "BATCH_DISABLED"}

    if symbols is not None:
        target_symbols: list[str] = symbols
        skipped: list[dict] = []
    else:
        target_symbols, etf_excluded = await get_eligible_symbols(market)
        skipped = [{"symbol": s, "reason": "ETF_EXCLUDED"} for s in etf_excluded]

    provider_code = ai_config.get_batch_provider()
    model = ai_config.get_batch_model()

    produced: list[str] = []
    cached: list[str] = []
    changed: list[dict] = []  # FR-5.4 推播摘要素材：翻多／翻空／觸價
    quota_exhausted = False
    abort_reason: Optional[str] = None

    for symbol in target_symbols:
        # 已知後續必然全部失敗的情況（批次配額用盡、Provider 設定錯誤）不再逐檔重試，
        # 但每一檔仍留下明確的原因，不得靜默跳過（AC-P5-07）
        if abort_reason:
            skipped.append({"symbol": symbol, "reason": abort_reason})
            continue
        try:
            outcome = await _run_one(symbol, market, provider_code, model)
        except AIQuotaExceededException:
            quota_exhausted = True
            abort_reason = "BATCH_QUOTA_EXCEEDED"
            skipped.append({"symbol": symbol, "reason": abort_reason})
            continue
        except AIProviderMisconfiguredException as e:
            # 金鑰未設定／無效是設定層的確定性錯誤：對第 2 檔到第 65 檔的結果完全相同。
            # 繼續跑只會多產生 64 筆一模一樣的失敗紀錄與 64 列 failed 報告，對使用者毫無資訊量
            # （批次預設 provider/model 與手動預設可各自設定，兩邊金鑰不同步時很容易踩到）。
            abort_reason = "PROVIDER_MISCONFIGURED"
            logger.warning(f"[AI批次] {market} Provider 設定錯誤，中止本輪批次（其餘標的一併標示原因）: {e}")
            skipped.append({"symbol": symbol, "reason": abort_reason})
            continue
        except AIAnalysisInProgressException:
            skipped.append({"symbol": symbol, "reason": "IN_PROGRESS"})
            continue
        except Exception as e:
            logger.warning(f"[AI批次] {market}/{symbol} 產生失敗（已略過，不中斷整批）: {e}")
            skipped.append({"symbol": symbol, "reason": "ERROR"})
            continue

        status = outcome["status"]
        if status == "no_data":
            skipped.append({"symbol": symbol, "reason": "NO_CHART_DATA"})
        elif status == "cached":
            cached.append(symbol)
        else:
            produced.append(symbol)
            # 獨立的 try：報告此時已經產生並落地（也已經計費），重大變化偵測純粹是推播摘要的
            # 素材。讓它的失敗（例如查歷史 verdict 時資料庫短暫不可用）把整批剩下的標的一起
            # 帶走，是拿「加分項」去換「主線」，明確違反 AC-P5-08／NFR-3。
            try:
                change_reason = await _detect_change(symbol, market, provider_code, model, outcome)
            except Exception as e:
                logger.warning(f"[AI批次] {market}/{symbol} 重大變化偵測失敗（報告已產生，僅略過推播判斷）: {e}")
                change_reason = None
            if change_reason:
                changed.append({**outcome, "symbol": symbol, "reason": change_reason})

    result = {
        "market": market, "produced": produced, "cached": cached,
        "skipped": skipped, "quota_exhausted": quota_exhausted,
        "aborted_reason": abort_reason if abort_reason != "BATCH_QUOTA_EXCEEDED" else None,
    }
    logger.info(f"[AI批次] {market} 完成：產生 {len(produced)}、快取 {len(cached)}、略過 {len(skipped)}")

    if changed:
        try:
            await _publish_digest(market, changed)
        except Exception as e:
            logger.warning(f"[AI批次] {market} 推播摘要發佈失敗（已靜默）: {e}")

    return result


async def _run_one(symbol: str, market: str, provider_code: str, model: str) -> dict[str, Any]:
    """單一標的的批次產生流程。回傳 {"status": "produced"|"cached"|"no_data", ...報告欄位}。"""
    qs = await build_quant_summary(symbol, market, "daily", 3)
    if qs is None:
        return {"status": "no_data"}

    async with get_async_session() as session:
        decision = await guard.resolve_report_slot(
            session, symbol=symbol, market=market, trade_date=qs.trade_date,
            provider=provider_code, model=model, stock_name=qs.stock_name,
            chart_period="daily", chart_months=3,
            chart_start_date=qs.chart_start_date, chart_end_date=qs.chart_end_date,
            trigger_type="batch",
        )
        recorder = AIRecorder(session)

        if decision.outcome == "cached":
            await recorder.log_cached(view_id=VIEW_ID, report_id=decision.report["id"])
            await session.commit()
            return {"status": "cached"}

        execution_id = await recorder.start_execution(
            report_id=decision.report_id, provider=provider_code, model=model,
            symbol=symbol, market=market, trade_date=qs.trade_date,
            attempt_no=decision.attempt_no, prompt_version=ai_config.get_prompt_version(),
            request_meta={
                "max_tokens": ai_config.get_extraction_max_output_tokens(),
                "mode": "batch_text_only",
            },
            is_dry_run=decision.forced, view_id=VIEW_ID,
        )
        await session.commit()
        report_id = decision.report_id

    provider_impl = get_provider(provider_code)
    # with_chart=False：批次沒有圖片可送，結尾的收斂指示必須跟著改，否則會要求模型
    # 「結合附帶的 K 線圖」——一張根本不存在的圖（見 ai/prompt.py build_user_prompt()）。
    user_prompt = build_user_prompt(symbol, qs.stock_name, market, qs.summary, with_chart=False)

    try:
        result = await provider_impl.extract_structured(
            BATCH_SYSTEM_PROMPT, user_prompt, LLMAnalysisReport, model=model,
        )
    except Exception as exc:
        async with get_async_session() as fail_session:
            await AIRecorder(fail_session).record_failure(
                execution_id=execution_id, report_id=report_id, view_id=VIEW_ID,
                error_code=type(exc).__name__, error_message=str(exc),
            )
            await fail_session.commit()
        raise

    if result.data is None:
        async with get_async_session() as fail_session:
            await AIRecorder(fail_session).record_failure(
                execution_id=execution_id, report_id=report_id, view_id=VIEW_ID,
                error_code="AI_BATCH_NO_PARSED_OUTPUT", error_message="LLM 回應無法解析為結構化輸出",
            )
            await fail_session.commit()
        raise RuntimeError(f"{symbol}：LLM 回應無法解析為結構化輸出")

    report = from_llm_report(result.data)
    est_cost = estimate_cost(result.model, result.input_tokens, result.output_tokens)
    rule_signal_alignment = compute_alignment(report.verdict, qs.summary.get("recent_alerts"), qs.trade_date)
    report_data = {
        "provider": provider_code, "model": result.model,
        "verdict": report.verdict, "headline": report.headline,
        "support_levels": [lvl.model_dump() for lvl in report.support_levels],
        "resistance_levels": [lvl.model_dump() for lvl in report.resistance_levels],
        "stop_loss": report.stop_loss, "target_price": report.target_price,
        "rule_signal_alignment": rule_signal_alignment,
        "report_markdown": report.report_markdown, "confidence": report.confidence,
        "quant_summary": qs.summary, "truncated": result.truncated,
    }
    async with get_async_session() as session2:
        await AIRecorder(session2).record_success(
            execution_id=execution_id, report_id=report_id, view_id=VIEW_ID,
            stop_reason=result.stop_reason, response_meta=result.response_meta,
            provider_request_id=result.provider_request_id,
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
            cache_read_tokens=None, cache_write_tokens=None,  # extract_structured() 無此資料（無圖片呼叫）
            image_bytes=None, estimated_cost_usd=est_cost,
            elapsed_ms=result.response_meta.get("elapsed_ms"),
            report_data=report_data,
        )
        await session2.commit()

    return {
        "status": "produced",
        "stock_name": qs.stock_name,
        "verdict": report.verdict,
        "target_price": report.target_price,
        "stop_loss": report.stop_loss,
        "close": (qs.summary.get("latest") or {}).get("close"),
        "trade_date": qs.trade_date,
    }


async def _detect_change(
    symbol: str, market: str, provider_code: str, model: str, outcome: dict[str, Any],
) -> Optional[str]:
    """FR-5.4：判斷這次批次產生的報告是否構成「重大變化」——翻多／翻空／觸及停損／觸及目標價。
    只拿「這次批次自己剛產生的報告」跟「上一則歷史報告」比，不回頭比對 cached／skipped 的標的
    （cached 代表今天稍早已有手動報告，其變化在產生當下即由手動路徑各自處理）。

    觸價方向：停損是下檔防守，收盤「跌到或跌破」才算觸及（close <= stop_loss）；目標價是上檔
    滿足點，收盤「漲到或漲過」才算觸及（close >= target_price）。任一值為 None（LLM 依規範
    留空）就整條判斷略過，不得拿 None 去比大小、也不得當成 0 而誤判成觸價。"""
    close = outcome.get("close")
    stop_loss = outcome.get("stop_loss")
    target_price = outcome.get("target_price")
    if close is not None and stop_loss is not None and close <= stop_loss:
        return "觸及停損價"
    if close is not None and target_price is not None and close >= target_price:
        return "觸及目標價"

    from repositories.ai_report_repository import AIReportRepository

    # before_date 用「這份報告自己的交易日」而不是 date.today()：遇到假日補跑、或最新交易日
    # 落在今天之前（美股時差、連假後首次排程）時，date.today() 會把剛剛才寫進去的這一筆
    # 一起算成「前一則」，prev_verdict 永遠等於當前 verdict，翻多／翻空就再也不會被偵測到。
    before_date = outcome.get("trade_date") or date.today()
    async with get_async_session() as session:
        prev_verdict = await AIReportRepository(session).get_previous_verdict(
            symbol, market, provider_code, model, before_date,
        )
    verdict = outcome.get("verdict")
    if prev_verdict and prev_verdict != verdict:
        if verdict == "bullish":
            return "轉為偏多"
        if verdict == "bearish":
            return "轉為偏空"
    return None


async def _publish_digest(market: str, changed: list[dict]) -> None:
    """組一則聚合摘要事件（非整篇報告），直接呼叫 notify.intake.publish()——這裡是批次自己已經
    算好的聚合事件，不需要像 ALERT_DIGEST 先展開路由再等待訊息停放（notify/digest.py 的
    digest_pending 機制是「先確定端點再產生內容」的反向流程，本情境不適用，見 §4.4 說明）。"""
    from datetime import datetime, timezone

    from notify import config as notify_config
    from notify.events import Event, EventType, Severity
    from notify.intake import publish
    from db.session import get_async_session as _get_session

    if not notify_config.is_enabled():
        return

    digest_date = datetime.now().strftime("%Y-%m-%d")
    # rstrip("/")：沿用 notify/composer.py、notify/binding.py 對 PUBLIC_BASE_URL 的既有處理，
    # 設定值帶結尾斜線時才不會組出 http://host//war-room
    war_room_url = f"{notify_config.get_public_base_url().rstrip('/')}/war-room?market={market}"
    payload = {
        "market": market,
        "digest_date": digest_date,
        "total_count": len(changed),
        "items": [
            {
                "symbol": c["symbol"], "stock_name": c.get("stock_name", ""),
                "verdict": c.get("verdict"), "target_price": c.get("target_price"),
                "stop_loss": c.get("stop_loss"), "reason": c.get("reason"),
            }
            for c in changed
        ],
        "war_room_url": war_room_url,
        "seq": 0,
    }
    event = Event(
        event_type=EventType.AI_VERDICT_DIGEST,
        severity=Severity.INFO,
        source="ai_batch",
        occurred_at=datetime.now(timezone.utc),
        payload=payload,
        source_event_key=f"ai_digest:{market}:{digest_date}:0",
    )
    async with _get_session() as session:
        await publish(event, session)
        await session.commit()
