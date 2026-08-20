"""每日匯率爬蟲：抓 USD/JPY/CNY 對 TWD 的每日參考匯率，寫入 exchange_rate 表。

來源沿革：原規劃抓台灣銀行牌告匯率（rate.bot.com.tw/xrt/flcsv/0/day），但該端點對一般伺服器環境的
自動化請求一律回傳需要執行 JS 才能過關的 bot-challenge 頁面（HTTP 200，但 body 是
"Challenge Validation" 頁面，不是 CSV）——這不是能靠調整 User-Agent／header 解決的簡易過濾，
而是專門阻擋自動化請求的機制，因此這裡不嘗試繞過，改用 fawazahmed0/currency-api
（https://github.com/fawazahmed0/exchange-api）：免金鑰、無需授權、透過 jsDelivr CDN（主）／
Cloudflare Pages（備援）提供每日更新的市場參考匯率，兩個來源都失敗才視為本次抓取失敗。

要注意這不是台灣銀行牌告匯率，而是單一市場參考匯率，沒有現金/即期、買入/賣出的區分（銀行報價
通常會有買賣價差）。若之後找到台銀官方且未受阻擋的資料源，可以在保留同一張表 schema（單一 rate
欄位）的前提下切換，或依需要擴充回買入/賣出兩欄。見
docs/8.個人投資記帳功能/個人投資記帳功能_design.md 補充章節。

沒有進度條需求（單次 HTTP 請求，秒級完成）；抓取＋upsert 全部包在 try/except，失敗只記 log、回傳
{"success": False, ...}，絕不拋例外——不管是排程、啟動時的背景任務、還是手動觸發，都不能因為這個
次要功能失敗而卡住主流程。

**兩個進入點，依呼叫端「目前是否在 event loop 上」挑一個，不可混用**（db/session.py 的
_engine/_session_factory 是行程全域共用，asyncpg 連線繫結在建立時所在的 event loop——這裡曾經真的
炸過："Future ... attached to a different loop"，起因是 main.py 啟動時 fetch_exchange_rates_startup()
原本透過 run_async() 另外開一個新 event loop，跟同一時間 run_startup_backfill() 在主 loop 上建立的
全域 engine 互踩）：

- `fetch_exchange_rates_async()`：呼叫端本身已經在跑 event loop 時用（main.py 啟動背景任務、
  api/v1/endpoints/exchange_rates.py 的 API handler）——直接 await，DB 操作沿用呼叫端當下的主 loop。
- `fetch_exchange_rates_now()`：呼叫端不在任何 event loop 上時用（services/scheduler.py 的
  _scheduled_tw()，跑在 APScheduler 的 ThreadPoolExecutor 執行緒裡）——比照
  repositories/stock_repository.py 的 run_async()，獨立開一個 asyncio.run()，結束後釋放連線池。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import requests

logger = logging.getLogger("mystock-backend")

TARGET_CURRENCIES = ("USD", "JPY", "CNY")
SOURCE_NAME = "fawazahmed0-currency-api"

# {version} 是 "latest" 或 "YYYY-MM-DD"；{base} 是幣別小寫代碼。先試 jsDelivr，失敗再試 pages.dev 備援。
_URL_TEMPLATES = (
    "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{version}/v1/currencies/{base}.json",
    "https://{version}.currency-api.pages.dev/v1/currencies/{base}.json",
)
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MyStockPortfolio/1.0)"}


def _fetch_currency_json(base: str, version: str = "latest") -> Optional[dict]:
    """base 為幣別小寫代碼（如 "usd"），回傳該來源的原始 JSON（含 date 與各目標幣別匯率）；
    兩個來源都失敗回傳 None 並記 log。"""
    last_error: Optional[Exception] = None
    for template in _URL_TEMPLATES:
        url = template.format(version=version, base=base)
        try:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001 — 任何來源層級的失敗都要能容錯換下一個來源
            last_error = exc
            continue
    logger.warning(f"[匯率] {base.upper()} 兩個來源皆請求失敗，略過該幣別: {last_error}")
    return None


def fetch_currency_rates(version: str = "latest") -> list[dict[str, Any]]:
    """回傳 [{currency, rate_date, rate, source}, ...]，只含成功解析到 TWD 匯率的幣別；
    單一幣別失敗只記 log 並跳過，不影響其他幣別。"""
    out: list[dict[str, Any]] = []
    for currency in TARGET_CURRENCIES:
        base = currency.lower()
        data = _fetch_currency_json(base, version)
        if not data:
            continue

        # 回應形如 {"date": "2026-08-20", "usd": {"twd": 31.94..., ...其他上百種幣別}}，
        # 目標匯率巢狀在 base 幣別代碼底下，不是最外層。
        rate_raw = (data.get(base) or {}).get("twd")
        date_str = data.get("date")
        if rate_raw is None or not date_str:
            logger.warning(f"[匯率] {currency} 回應內容缺少 twd 或 date 欄位，略過該幣別")
            continue
        try:
            rate = Decimal(str(rate_raw))
        except InvalidOperation:
            logger.warning(f"[匯率] {currency} 匯率數值解析失敗（{rate_raw!r}），略過該幣別")
            continue
        try:
            rate_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            rate_date = date.today()

        out.append({"currency": currency, "rate_date": rate_date, "rate": rate, "source": SOURCE_NAME})

    if not out:
        logger.warning(f"[匯率] {TARGET_CURRENCIES} 全部幣別都取不到資料，略過本次抓取")
    return out


async def _upsert_async(rows: list[dict[str, Any]]) -> int:
    from db.session import get_async_session
    from repositories.exchange_rate_repository import ExchangeRateRepository

    async with get_async_session() as session:
        count = await ExchangeRateRepository(session).upsert_many(rows)
        await session.commit()
        return count


def _result_dict(rows: list[dict[str, Any]], count: int) -> dict[str, Any]:
    return {
        "success": True,
        "data": {"updated": count, "currencies": [r["currency"] for r in rows], "rate_date": max(r["rate_date"] for r in rows).isoformat()},
        "error": None,
    }


async def fetch_exchange_rates_async(trigger_type: str = "manual") -> dict[str, Any]:
    """給呼叫端本身已經在 event loop 上跑的情境用（見上方模組說明）：main.py 啟動背景任務、
    api/v1/endpoints/exchange_rates.py 的 API handler 都呼叫這個，用 await 直接串接，
    DB 寫入沿用呼叫端當下的主 loop，不額外開新的 event loop。"""
    try:
        rows = await asyncio.to_thread(fetch_currency_rates)  # 純網路 I/O，丟執行緒池避免卡住 event loop
        if not rows:
            return {"success": False, "data": None, "error": "無法取得匯率資料（來源可能暫時無回應，詳見後端 log）"}

        count = await _upsert_async(rows)
        logger.info(f"[匯率] {trigger_type} 觸發抓取完成，已更新 {count} 筆（{[r['currency'] for r in rows]}）")
        return _result_dict(rows, count)
    except Exception as exc:
        logger.warning(f"[匯率] {trigger_type} 觸發抓取失敗: {exc}")
        return {"success": False, "data": None, "error": str(exc)}


def fetch_exchange_rates_now(trigger_type: str = "scheduled") -> dict[str, Any]:
    """給呼叫端不在任何 event loop 上的情境用（見上方模組說明）：services/scheduler.py 的
    _scheduled_tw()，跑在 APScheduler 的 ThreadPoolExecutor 執行緒裡，比照
    repositories/stock_repository.py 的 run_async()：獨立開一個 asyncio.run()，結束後釋放連線池
    （asyncpg 連線繫結建立時所在的 event loop，見 db/session.py dispose_engine() 的說明）。"""
    from repositories.stock_repository import run_async

    try:
        rows = fetch_currency_rates()
        if not rows:
            return {"success": False, "data": None, "error": "無法取得匯率資料（來源可能暫時無回應，詳見後端 log）"}

        count = run_async(_upsert_async(rows))
        logger.info(f"[匯率] {trigger_type} 觸發抓取完成，已更新 {count} 筆（{[r['currency'] for r in rows]}）")
        return _result_dict(rows, count)
    except Exception as exc:
        logger.warning(f"[匯率] {trigger_type} 觸發抓取失敗: {exc}")
        return {"success": False, "data": None, "error": str(exc)}


async def fetch_exchange_rates_startup() -> None:
    """main.py lifespan 的背景任務：啟動時自動抓一次，失敗不得擋住服務啟動。用 async 版本
    （fetch_exchange_rates_async），不能用 fetch_exchange_rates_now()／run_async()——這個函式本身
    是被 asyncio.create_task() 排進主 event loop 執行的，若內部再開一個新的 asyncio.run()，
    會跟同一時間點主 loop 上其他 DB 操作（例如 run_startup_backfill()）搶用行程全域共用的
    db/session.py engine，導致 asyncpg 連線跨 loop 使用而炸掉。"""
    try:
        result = await fetch_exchange_rates_async("startup")
        if not result["success"]:
            logger.warning(f"[匯率] 啟動時自動抓取未成功：{result['error']}")
    except Exception as exc:
        logger.warning(f"[匯率] 啟動時自動抓取發生例外（已略過）: {exc}")
