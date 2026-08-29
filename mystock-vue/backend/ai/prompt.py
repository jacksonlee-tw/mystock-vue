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
6. 動能與波動檢核：MACD 柱狀圖與 DIF／訊號線的交叉是否支持當前趨勢方向、RSI 所處位階、
   布林通道收斂或開口擴大所反映的波動狀態、ATR 反映的單日波動幅度。
   任一數值缺席時（如新上市個股尚未累積足夠交易日）略過該面向，不得臆測。
7. 基本面與估值檢核：本益比／股價淨值比／殖利率所處的合理與偏貴／偏便宜區間、月營收年增率／月增率
   所反映的營運動能是否與價格走勢相符（例如股價上漲但營收衰退屬於背離，須特別指出）。
   任一數值缺席時（如美股無此類欄位、該股尚無月營收資料）略過該面向，不得臆測。
8. 市場資金定位：市值與市值排名所反映的籌碼流動性與法人／指數化資金偏好程度，作為評估操作策略
   （如波段持有 vs 短線價差）的參考背景之一。缺席時略過，不得臆測。

輸出規範：
- 所有價位必須是具體數字，不得寫「附近」「左右」而無數值。
- 數值一律以【結構化量化數值】為準；圖片僅用於判讀型態與相對位置。
  兩者衝突時以數值為準，並在敘述中說明圖上觀察到的差異。
- 若某項資料缺席（如美股無籌碼欄位），略過該面向，不得臆測。
- 近期策略訊號（如提供）僅供佐證研判方向，不得直接複述訊號內容當成結論——訊號是規則引擎的獨立
  觀察，你的研判必須基於自己對量化數值與圖片的分析。
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
    "dif": "DIF", "signal": "訊號線(Signal)", "histogram": "柱狀圖(Histogram)",
    "rsi_6": "RSI(6)", "rsi_14": "RSI(14)",
    "upper": "布林上軌", "middle": "布林中軌", "lower": "布林下軌", "bandwidth": "布林帶寬",
    "atr_14": "ATR(14)",
    "foreign_net_5d": "外資近5日買賣超(張)", "trust_net_5d": "投信近5日買賣超(張)",
    "dealer_net_5d": "自營商近5日買賣超(張)",
    "margin_balance": "融資餘額", "short_balance": "融券餘額", "short_ratio": "券資比(%)",
    # Phase2-籌碼面與基本面量化擴充 設計文件 FR-4：估值／營收／市場定位
    "pe_ratio": "本益比(倍)", "pb_ratio": "股價淨值比(倍)", "dividend_yield": "殖利率(%)",
    "yoy_percent": "營收年增率(%)", "mom_percent": "營收月增率(%)", "visible_month": "資料月份",
    "market_cap": "市值(億元)", "mcap_rank": "市值排名",
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
        lines = ["【區間高低點與位階】"]
        if r.get("high") is not None:
            lines.append(f"- 本次顯示區間最高 {r.get('high')}（{r.get('high_date')}）"
                          f"／最低 {r.get('low')}（{r.get('low_date')}）")
        for window in (20, 60):
            resistance_key, support_key = f"resistance_{window}d", f"support_{window}d"
            if resistance_key in r or support_key in r:
                lines.append(f"- 近{window}日壓力 {r.get(resistance_key)}／支撐 {r.get(support_key)}")
        parts.append("\n".join(lines))
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
    if summary.get("macd"):
        parts.append(_format_block("MACD", summary["macd"]))
        parts.append("")
    if summary.get("rsi"):
        parts.append(_format_block("RSI", summary["rsi"]))
        parts.append("")
    if summary.get("bollinger"):
        parts.append(_format_block("布林通道", summary["bollinger"]))
        parts.append("")
    if summary.get("atr"):
        parts.append(_format_block("ATR 波動幅度", summary["atr"]))
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
    if summary.get("valuation"):
        parts.append(_format_block("估值", summary["valuation"]))
        parts.append("")
    if summary.get("revenue"):
        parts.append(_format_block("月營收動能", summary["revenue"]))
        parts.append("")
    if summary.get("market_position"):
        parts.append(_format_block("市場資金定位", summary["market_position"]))
        parts.append("")
    if summary.get("recent_alerts"):
        lines = ["【近期策略訊號（僅供佐證，非結論）】"]
        for a in summary["recent_alerts"]:
            lines.append(
                f"- {a.get('trade_date')}：{a.get('strategy_id')}"
                f"（方向：{a.get('direction')}，強度：{a.get('signal_strength')}）"
            )
        parts.append("\n".join(lines))
        parts.append("")

    parts.append("請結合附帶的 K 線圖，依系統指示的研判框架與輸出規範產出結構化技術分析報告。")
    return "\n".join(parts)
