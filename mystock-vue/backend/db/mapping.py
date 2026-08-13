"""JSON 落地格式 ⇄ daily_stock_data 資料列的雙向轉換。

`record_to_daily_row()`（JSON → 資料列）供爬蟲雙寫（db/dual_write.py）與一次性匯入腳本
（scripts/import_json_to_postgres.py）共用；`daily_row_to_record()`（資料列 → JSON 形狀）供
Phase 3 讀取路徑（services/stock_service.py 的 load_stock_data()）還原成下游聚合邏輯需要的形狀。
兩個方向的映射並排維護在同一個檔案，避免加欄位時只改到一邊（見設計文件第 4.1 節風險）。
"""
from decimal import Decimal
from datetime import date
from typing import Optional, Union

_INSTITUTIONAL_MAP = {
    "foreign_buy_sell": "foreign_net_buy",
    "trust_buy_sell": "investment_trust_net_buy",
    "dealer_buy_sell": "dealer_net_buy",
    "institutional_total": "total_net_buy",
    "institutional_amount_est": "estimated_net_buy_amount",
}
_REVERSE_INSTITUTIONAL_MAP = {db_key: json_key for json_key, db_key in _INSTITUTIONAL_MAP.items()}

_MARGIN_MAP = {
    "融資買進(張)": "margin_purchase",
    "融資賣出(張)": "margin_sale",
    "融資現金償還(張)": "margin_cash_repayment",
    "融資前日餘額(張)": "margin_prev_balance",
    "margin_balance": "margin_balance",
    "融券買進(張)": "short_purchase",
    "融券賣出(張)": "short_sale",
    "融券現券償還(張)": "short_cash_repayment",
    "融券前日餘額(張)": "short_prev_balance",
    "short_balance": "short_balance",
    "資券互抵(張)": "margin_short_offset",
}
# 反向還原只需要英文鍵：中文鍵的融資/融券明細欄位下游聚合邏輯與前端都沒有使用（見設計文件第 2.4 節）
_MARGIN_REVERSE_FIELDS = ("margin_balance", "short_balance")


def _build_market_specific_data(record: dict, market_type: str) -> Optional[dict]:
    if market_type == "tw":
        institutional = {v: record[k] for k, v in _INSTITUTIONAL_MAP.items() if record.get(k) is not None}
        margin = {v: record[k] for k, v in _MARGIN_MAP.items() if record.get(k) is not None}

        result = {}
        if institutional:
            result["institutional_investors"] = institutional
        if margin:
            result["margin_trading"] = margin
        return result or None

    if market_type == "us":
        # Short Interest／機構持股是美股確實存在的資料，本來就該儲存；
        # 只有台股專屬的法人買賣超/融資融券在美股才是「這個市場不存在此概念」而回 NULL（見設計文件第 2.7 節）。
        short_interest = {}
        if record.get("short_interest") is not None:
            short_interest["shares_short"] = record["short_interest"]
        if record.get("short_ratio") is not None:
            short_interest["short_ratio"] = record["short_ratio"]

        institutional = {}
        if record.get("institutional_holders") is not None:
            institutional["shares_held"] = record["institutional_holders"]

        result = {}
        if short_interest:
            result["short_interest"] = short_interest
        if institutional:
            result["institutional"] = institutional
        return result or None

    return None  # 其他市場：尚無籌碼資料概念，維持 NULL（見設計文件第 3.1 節）


def record_to_daily_row(symbol: str, market_type: str, trade_date: Union[str, date], record: dict) -> dict:
    """把單一日期的 JSON record 轉成 daily_stock_data upsert 用的欄位字典。"""
    if isinstance(trade_date, str):
        trade_date = date.fromisoformat(trade_date)

    return {
        "symbol": symbol,
        "market_type": market_type,
        "trade_date": trade_date,
        "open_price": record.get("open"),
        "high_price": record.get("high"),
        "low_price": record.get("low"),
        "close_price": record.get("close"),
        "volume": record.get("volume"),
        "turnover": record.get("amount"),
        "transaction_count": record.get("trades"),
        "market_specific_data": _build_market_specific_data(record, market_type),
    }


def daily_row_to_record(row: dict) -> dict:
    """把 daily_stock_data 資料列還原成與 JSON 相同形狀的 record。

    下游 aggregate_stock_data() 完全依賴這個形狀，因此必須處理三件事（見設計文件第 2.4 節）：
    1. 型別還原：Decimal → float，否則與 float 混算會拋 TypeError 或影響精度。
    2. JSONB 攤平：market_specific_data 的巢狀結構攤回頂層英文鍵。
    3. None 不可補 0：欄位不存在時直接不產生該鍵，而不是補 0，避免前端表格出現假資料。
    """

    def _num(value):
        return float(value) if isinstance(value, Decimal) else value

    record: dict = {}
    for json_key, db_key in (
        ("open", "open_price"),
        ("high", "high_price"),
        ("low", "low_price"),
        ("close", "close_price"),
        ("volume", "volume"),
        ("amount", "turnover"),
        ("trades", "transaction_count"),
    ):
        value = row.get(db_key)
        if value is not None:
            record[json_key] = _num(value)

    market_specific = row.get("market_specific_data") or {}

    institutional = market_specific.get("institutional_investors") or {}
    for db_key, json_key in _REVERSE_INSTITUTIONAL_MAP.items():
        if institutional.get(db_key) is not None:
            record[json_key] = _num(institutional[db_key])

    margin = market_specific.get("margin_trading") or {}
    for key in _MARGIN_REVERSE_FIELDS:
        if margin.get(key) is not None:
            record[key] = margin[key]

    short_interest = market_specific.get("short_interest") or {}
    if short_interest.get("shares_short") is not None:
        record["short_interest"] = short_interest["shares_short"]
    if short_interest.get("short_ratio") is not None:
        record["short_ratio"] = _num(short_interest["short_ratio"])

    institutional_holders = market_specific.get("institutional") or {}
    if institutional_holders.get("shares_held") is not None:
        record["institutional_holders"] = institutional_holders["shares_held"]

    return record
