"""
ai/prompt.py
System Prompt 與 User Prompt 組裝（見規格書 §4.4）。

設計原則：Prompt 中不得出現任何硬編碼的策略門檻——門檻屬於
strategy_config/strategies.yaml 的管轄範圍，AI 報告是獨立的觀察視角，不與規則引擎的
參數耦合（見 CLAUDE.md「策略/警報引擎」一節）。
"""
from typing import Any

SYSTEM_PROMPT = """你是一位任職於頂級對沖基金的資深技術分析師與風控專家。
你將接收一張【個股日 K 線圖（含均線與成交量）】以及【結構化量化數值】。

研判框架：
1. 均線架構：5MA／20MA／60MA 的相對位置、糾結或發散、斜率方向。
2. 型態與 K 線特徵：破線、突破、高檔反轉、島狀反轉、雙底／頸線等關鍵型態。
3. 量價配合：放量跌破、量縮築底、帶量突破；成交量相對 5 日均量的位置。
4. 關鍵位階：明確標示【關鍵支撐（防守／停損點）】與【上方壓力（轉強／目標價）】。
5. 實戰建議：「短線價差操作」與「中長線持股／進場」分別給出具體指引。

輸出規範：
- 所有價位必須是具體數字，不得寫「附近」「左右」而無數值。
- 數值一律以【結構化量化數值】為準；圖片僅用於判讀型態與相對位置。
  兩者衝突時以數值為準，並在敘述中說明圖上觀察到的差異。
- 若某項資料缺席（如美股無籌碼欄位），略過該面向，不得臆測。
- 完整報告請拆成 sections 陣列輸出，陣列中每個元素是一個獨立段落 {title, body}：
  - title：只填精簡的章節標題本身（4～12 字），不要加「### 」前綴、不要加粗、不要包含標點。
  - body：該章節的完整說明文字，可用 **文字** 標出關鍵數字，但不要在 body 裡重複章節標題、
    也不要自己加「### 」——標題與內文的分段排版由系統統一組裝，你只需要專心把內容寫好。
  - 建議至少包含這幾個段落（依實際情況可調整順序或合併）：技術型態與均線架構分析、
    量價配合、關鍵支撐與壓力位階、實戰操作建議（短線與中長線分別說明）、防守與風控設定。
- 使用繁體中文。"""


_LABELS: dict[str, str] = {
    "close": "收盤價", "open": "開盤價", "high": "最高價", "low": "最低價",
    "volume": "成交量", "change_pct": "漲跌幅(%)",
    "ma5": "5MA", "ma10": "10MA", "ma20": "20MA", "ma60": "60MA", "ma120": "120MA", "ma240": "240MA",
    "k": "K 值", "d": "D 值",
    "foreign_net_5d": "外資近5日買賣超(張)", "trust_net_5d": "投信近5日買賣超(張)",
    "dealer_net_5d": "自營商近5日買賣超(張)",
    "margin_balance": "融資餘額", "short_balance": "融券餘額", "short_ratio": "券資比(%)",
}


def _format_block(title: str, values: dict[str, Any]) -> str:
    lines = [f"【{title}】"]
    for key, val in values.items():
        label = _LABELS.get(key, key)
        lines.append(f"- {label}：{val}")
    return "\n".join(lines)


def build_user_prompt(symbol: str, stock_name: str, market: str, summary: dict[str, Any]) -> str:
    """把 ai/summary.py 組好的量化摘要序列化為易讀區塊（非裸 JSON dump——
    分節標題與單位標註能顯著提升 LLM 引用數字的準確度，見規格書 §4.4）。"""
    market_label = "台股" if market == "tw" else "美股"
    parts = [f"請針對標的【{symbol} {stock_name}】（{market_label}）進行技術線型分析與投資決策建議。", ""]

    if summary.get("latest"):
        parts.append(_format_block("最新行情", summary["latest"]))
        parts.append("")
    if summary.get("range"):
        r = summary["range"]
        parts.append(f"【區間高低點】最高 {r.get('high')}（{r.get('high_date')}）"
                      f"／最低 {r.get('low')}（{r.get('low_date')}）")
        parts.append("")
    if summary.get("ma"):
        parts.append(_format_block("移動平均線", summary["ma"]))
        parts.append("")
    if summary.get("bias_percent"):
        parts.append(_format_block("乖離率(%)", summary["bias_percent"]))
        parts.append("")
    if summary.get("kd"):
        parts.append(_format_block("KD 指標", summary["kd"]))
        parts.append("")
    if "volume_ma5" in summary or "volume_ratio" in summary:
        vol = {k: v for k, v in summary.items() if k in ("volume_ma5", "volume_ratio")}
        parts.append(_format_block("量能", vol))
        parts.append("")
    if summary.get("chips"):
        parts.append(_format_block("三大法人籌碼", summary["chips"]))
        parts.append("")
    if summary.get("margin"):
        parts.append(_format_block("融資融券", summary["margin"]))
        parts.append("")

    parts.append("請結合附帶的 K 線圖，依系統指示的研判框架與輸出規範產出結構化技術分析報告。")
    return "\n".join(parts)
