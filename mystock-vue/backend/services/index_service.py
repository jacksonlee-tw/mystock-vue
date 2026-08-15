"""大盤指數讀取／聚合服務（見 docs/10.加權指數/大盤指數功能規劃書.md 第九節、ADR-I1/I2）。

刻意保持精簡：所有聚合與均線計算 100% 重用 services/stock_service.py 既有函式
（aggregate_stock_data / get_stock_chart_payload），本檔案只負責「指數專屬的中繼資料組裝」
（定義檔清單、首頁總覽卡片）。寫入／抓取邏輯在 services/index_fetcher.py。

`get_index_overview()` 的欄位命名刻意對齊 get_heatmap_data()（stock_id / stock_name /
latest_close / start_date / end_date / sparkline…），讓前端「全市場個股動態熱力圖」可以把
指數當成第三個分類（指數／ETF／一般個股），直接重用同一份卡片樣板渲染，不需要另外寫一套
欄位轉換或卡片元件（大盤指數功能規劃書 P-1「不另建平行系統」）。
"""
import logging
from typing import Any, Dict, List, Optional

from markets.tw_industries import TWSE_INDUSTRY_MAP, sector_code
from services.index_fetcher import IndexDefinition, get_index_definition, get_index_definitions
from services.stock_service import aggregate_stock_data, load_stock_data

logger = logging.getLogger("mystock-backend")

# 首頁／熱力圖 Sparkline 點數：與 get_heatmap_data() 的既有慣例一致（近 10 筆）。
# P1 尚無盤中資料管線（規劃書 ADR-I8），這是近 10 個交易週期的收盤，不是「當日走勢」。
SPARKLINE_POINTS = 10


def _base_entry(d: IndexDefinition) -> Dict[str, Any]:
    return {
        "stock_id": d.code,
        "stock_name": d.name,
        "short_name": d.short_name,
        "market": d.market,
        "display_order": d.display_order,
        "is_index": True,
    }


async def discover_available_indices(market: Optional[str] = None) -> List[Dict[str, Any]]:
    """指數清單（GET /api/v1/indices）：定義檔中繼資料 + 目前資料涵蓋範圍。"""
    result = []
    for d in get_index_definitions(market):
        data = await load_stock_data(d.code, d.market, kind="index")
        dates = sorted(data.keys()) if data else []
        entry = _base_entry(d)
        entry.update({
            "source": d.source,
            "start_date": dates[0] if dates else None,
            "end_date": dates[-1] if dates else None,
            "total_records": len(dates),
        })
        result.append(entry)
    return result


async def get_index_overview(market: Optional[str] = None, period: str = "daily") -> List[Dict[str, Any]]:
    """首頁／熱力圖大盤概況（GET /api/v1/indices/overview）：一次回傳最新報價、漲跌與
    Sparkline，避免前端對 N 檔指數各發一次請求（規劃書 AC-IDX-09）。`period` 對齊熱力圖既有的
    日／週／月切換（stock_service.get_heatmap_data 的 period 語意）。

    沒有資料的指數（尚未抓取／抓取失敗）仍會回傳一筆 has_data=false 的紀錄，而不是整筆省略，
    讓呼叫端（例如熱力圖分類清單）可以自行決定要顯示佔位卡片還是過濾掉，不用另外查一次
    /api/v1/indices 才知道「這檔指數存在但沒資料」跟「這檔指數根本沒被定義」的差別。
    """
    overview = []
    for d in get_index_definitions(market):
        entry = _base_entry(d)
        try:
            raw = await load_stock_data(d.code, d.market, kind="index")
            aggregated = aggregate_stock_data(raw, period=period, months=6) if raw else []

            if not aggregated:
                entry["has_data"] = False
                overview.append(entry)
                continue

            latest = aggregated[-1]
            close = latest.get("close") or 0
            if len(aggregated) >= 2:
                prev_close = aggregated[-2].get("close") or 0
            else:
                prev_close = latest.get("open") or close

            change = close - prev_close
            change_percent = (change / prev_close * 100) if prev_close else 0
            sparkline_records = aggregated[-SPARKLINE_POINTS:]

            entry.update({
                "has_data": True,
                "latest_date": latest.get("date"),
                "open": latest.get("open", 0),
                "high": latest.get("high", 0),
                "low": latest.get("low", 0),
                "latest_close": close,
                "prev_close": prev_close,
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "start_date": sparkline_records[0].get("date", "") if sparkline_records else "",
                "end_date": sparkline_records[-1].get("date", "") if sparkline_records else "",
                "sparkline": [r.get("close", 0) for r in sparkline_records],
            })
            overview.append(entry)
        except Exception as e:
            logger.warning(f"[指數] {d.code} overview 組裝失敗: {e}")
            entry["has_data"] = False
            overview.append(entry)

    return overview


async def get_index_chart_data(code: str, period: str = "daily", months: int = 3,
                                market: str = "tw") -> Dict[str, Any]:
    """指數圖表資料（GET /api/v1/indices/{code}/chart-data）。

    回應結構刻意對齊 get_stock_chart_payload() 既有的個股回應形狀（規劃書 §9：
    「回應結構與 /stocks/{id}/chart-data 對齊，讓前端可共用 StockCharts.vue」），
    因此直接重用該函式、只是把 kind 切成 'index'，不重新實作一份聚合邏輯。

    `meta.panels` 只給 ['index']：P1 爬蟲只抓得到 OHLCV + 成交量值（見 services/index_fetcher.py），
    還沒有三大法人／融資融券等籌碼資料，所以重用 StockCharts.vue 時只會顯示「K 線圖」與「成交金額」
    頁籤（panel='always'／'index'），不會顯示個股才有的三大法人／融資融券頁籤（P-4「誠實標示資料
    缺口」，避免顯示一整排全是 0 的假資料）。Phase 3 補上大盤籌碼資料後，這裡再補對應 panels。
    """
    from services.stock_service import get_stock_chart_payload
    payload = await get_stock_chart_payload(code, period=period, months=months, market=market, kind="index")
    if "error" not in payload:
        definition = get_index_definition(code)
        payload["meta"] = {
            "code": "index",
            "label": definition.short_name if definition else code,
            "panels": ["index"],
        }
        payload["metrics"] = []
    return payload


async def build_rebased_series(items: List[Dict[str, str]], period: str = "daily",
                                months: int = 12) -> Dict[str, Any]:
    """多標的 Rebase=100 比較（大盤指數功能規劃書 FR-IDX-06「多指數疊圖比較」／
    FR-IDX-50「個股 vs 大盤」共用同一核心邏輯，差別只在 items 裡 kind 混不混 'stock'）。

    每個 item 需要 {"code", "market", "kind"（'stock'|'index'）, "label"}。

    交易日對齊採「聯集 + 前值延續（forward-fill）」而非交集（規劃書 §4.5）：台美交易日本來就不同
    （國定假日、夏令時間），用交集會讓兩地比較掉一堆資料點；缺漏日沿用該標的最近一個有效收盤價，
    數值不變代表當天無新資訊，而不是憑空填 0 或掐斷線段。
    """
    per_symbol_closes: Dict[str, Dict[str, float]] = {}
    labels: Dict[str, str] = {}

    for item in items:
        code, market, kind = item["code"], item["market"], item.get("kind", "index")
        raw = await load_stock_data(code, market, kind=kind)
        aggregated = aggregate_stock_data(raw, period=period, months=months) if raw else []
        closes = {r["date"]: r["close"] for r in aggregated if r.get("close")}
        per_symbol_closes[code] = closes
        labels[code] = item.get("label") or code

    all_dates: List[str] = sorted({d for closes in per_symbol_closes.values() for d in closes})

    series: Dict[str, List[Optional[float]]] = {}
    for code, closes in per_symbol_closes.items():
        base = None
        last_value = None
        rebased: List[Optional[float]] = []
        for d in all_dates:
            if d in closes:
                last_value = closes[d]
            if base is None and last_value is not None:
                base = last_value
            rebased.append(round(last_value / base * 100, 3) if (last_value is not None and base) else None)
        series[code] = rebased

    return {"dates": all_dates, "labels": labels, "series": series}


async def get_sector_overview() -> List[Dict[str, Any]]:
    """台股類股指數當日表現排行／輪動熱力圖資料（FR-IDX-30/31，規劃書 §8.1）。

    資料型狀刻意對齊 get_index_overview()（stock_id/stock_name/latest_close/change_percent…），
    讓 SectorRotationView.vue 可以重用同一套卡片渲染邏輯。類股指數只有收盤價（見
    services/index_fetcher.py 的 fetch_and_store_sector_snapshot() 說明），因此沒有
    open/high/low 可顯示。依 change_percent 由大到小排序，直接對應「資金流向排行」的用途。
    """
    overview = []
    for industry_code, meta in TWSE_INDUSTRY_MAP.items():
        if not meta.get("index_name"):
            continue  # 存託憑證等沒有對應類股指數的分類，略過

        code = sector_code(industry_code)
        entry = {
            "stock_id": code,
            "stock_name": meta["name"],
            "market": "tw",
            "industry_code": industry_code,
            "is_index": True,
            "is_sector": True,
        }
        try:
            raw = await load_stock_data(code, "tw", kind="index")
            aggregated = aggregate_stock_data(raw, period="daily", months=6) if raw else []

            if not aggregated:
                entry["has_data"] = False
                overview.append(entry)
                continue

            latest = aggregated[-1]
            close = latest.get("close") or 0
            prev_close = (aggregated[-2].get("close") or 0) if len(aggregated) >= 2 else close
            change = close - prev_close
            change_percent = (change / prev_close * 100) if prev_close else 0
            sparkline_records = aggregated[-SPARKLINE_POINTS:]

            entry.update({
                "has_data": True,
                "latest_date": latest.get("date"),
                "latest_close": close,
                "prev_close": prev_close,
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "start_date": sparkline_records[0].get("date", "") if sparkline_records else "",
                "end_date": sparkline_records[-1].get("date", "") if sparkline_records else "",
                "sparkline": [r.get("close", 0) for r in sparkline_records],
            })
            overview.append(entry)
        except Exception as e:
            logger.warning(f"[指數] 類股 {code} overview 組裝失敗: {e}")
            entry["has_data"] = False
            overview.append(entry)

    overview.sort(key=lambda e: e.get("change_percent") if e.get("has_data") else -999, reverse=True)
    return overview
