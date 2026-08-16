"""端點探測腳本（選股功能與爬蟲 規格書 §3.2、§14 P0-1、§15）。

用途：
- 實測 TWSE / TPEx 端點（回傳筆數、欄位名、當日可用性、日期參數支援）
- 驗證 K (BWIBBU_d) / L (TPEx 估值) / M (TWSE 月營收) / N (TPEx 月營收) 的回傳結構
"""
import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("probe_market_sources")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def probe_twse_quotes(date_str: str) -> dict:
    """A: TWSE 每日收盤行情 (MI_INDEX)"""
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date_str}&type=ALLBUT0999&response=json"
    logger.info(f"Probing TWSE quotes: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return {"status": "http_error", "code": r.status_code}
        data = r.json()
        stat = data.get("stat", "")
        # Look for table9 (or tables with title containing 每日收盤行情)
        tables = data.get("tables", [])
        quote_table = None
        for t in tables:
            title = t.get("title", "")
            if "每日收盤行情" in title or "價格資訊" in title or len(t.get("data", [])) > 500:
                quote_table = t
                break
        if not quote_table and "data9" in data:
            quote_table = {"fields": data.get("fields9", []), "data": data.get("data9", [])}
        
        row_count = len(quote_table.get("data", [])) if quote_table else 0
        fields = quote_table.get("fields", []) if quote_table else []
        sample = quote_table.get("data", [])[0] if row_count > 0 else None
        return {
            "stat": stat,
            "row_count": row_count,
            "fields": fields,
            "sample_row": sample,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def probe_twse_chips(date_str: str) -> dict:
    """B: TWSE 三大法人 (T86) + C: 融資融券 (MI_MARGN)"""
    t86_url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALL&response=json"
    margn_url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date_str}&selectType=ALL&response=json"
    result = {}
    try:
        r = requests.get(t86_url, headers=HEADERS, timeout=15)
        t86_data = r.json() if r.status_code == 200 else {}
        result["t86"] = {
            "stat": t86_data.get("stat"),
            "row_count": len(t86_data.get("data", [])),
            "fields": t86_data.get("fields", []),
            "sample_row": t86_data.get("data", [])[0] if t86_data.get("data") else None
        }
    except Exception as e:
        result["t86"] = {"error": str(e)}
        
    try:
        r = requests.get(margn_url, headers=HEADERS, timeout=15)
        margn_data = r.json() if r.status_code == 200 else {}
        tables = margn_data.get("tables", [])
        m_table = tables[0] if tables else None
        result["margn"] = {
            "stat": margn_data.get("stat"),
            "row_count": len(m_table.get("data", [])) if m_table else len(margn_data.get("data", [])),
            "fields": m_table.get("fields", []) if m_table else margn_data.get("fields", []),
            "sample_row": (m_table.get("data", []) if m_table else margn_data.get("data", []))[0] if (m_table and m_table.get("data")) or margn_data.get("data") else None
        }
    except Exception as e:
        result["margn"] = {"error": str(e)}
    return result


def probe_twse_valuation(date_str: str) -> dict:
    """J/K: TWSE 個股本益比、殖利率、股價淨值比 (BWIBBU_ALL 快照 vs BWIBBU_d 指定日期)"""
    snapshot_url = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
    historical_url = f"https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={date_str}&selectType=ALL&response=json"
    result = {}
    
    try:
        r = requests.get(snapshot_url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            arr = r.json()
            result["snapshot_BWIBBU_ALL"] = {
                "status": "ok",
                "row_count": len(arr),
                "sample": arr[0] if arr else None
            }
        else:
            result["snapshot_BWIBBU_ALL"] = {"status": "http_error", "code": r.status_code}
    except Exception as e:
        result["snapshot_BWIBBU_ALL"] = {"status": "error", "error": str(e)}
        
    try:
        r = requests.get(historical_url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            result["historical_BWIBBU_d"] = {
                "stat": data.get("stat"),
                "row_count": len(data.get("data", [])),
                "fields": data.get("fields", []),
                "sample_row": data.get("data", [])[0] if data.get("data") else None
            }
        else:
            result["historical_BWIBBU_d"] = {"status": "http_error", "code": r.status_code}
    except Exception as e:
        result["historical_BWIBBU_d"] = {"status": "error", "error": str(e)}
        
    return result


def probe_twse_monthly_revenue() -> dict:
    """M: TWSE 上市每月營業收入彙總 (t187ap05_L)"""
    url = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return {
                "status": "ok",
                "row_count": len(data),
                "sample": data[0] if data else None
            }
        return {"status": "http_error", "code": r.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Probe market sources")
    parser.add_argument("--date", type=str, default="", help="Trade date in YYYYMMDD format (default: latest weekday)")
    args = parser.parse_args()
    
    if not args.date:
        # Get latest weekday
        d = datetime.now()
        if d.weekday() == 5: # Sat
            d -= timedelta(days=1)
        elif d.weekday() == 6: # Sun
            d -= timedelta(days=2)
        date_str = d.strftime("%Y%m%d")
    else:
        date_str = args.date.replace("-", "")
        
    logger.info(f"=== Starting Probe for Trade Date {date_str} ===")
    
    quotes = probe_twse_quotes(date_str)
    logger.info(f"TWSE Quotes: {json.dumps(quotes, ensure_ascii=False, indent=2)}")
    
    chips = probe_twse_chips(date_str)
    logger.info(f"TWSE Chips: {json.dumps(chips, ensure_ascii=False, indent=2)}")
    
    val = probe_twse_valuation(date_str)
    logger.info(f"TWSE Valuation: {json.dumps(val, ensure_ascii=False, indent=2)}")
    
    rev = probe_twse_monthly_revenue()
    logger.info(f"TWSE Monthly Revenue: {json.dumps(rev, ensure_ascii=False, indent=2)}")
    
    logger.info("=== Probe Complete ===")


if __name__ == "__main__":
    main()
