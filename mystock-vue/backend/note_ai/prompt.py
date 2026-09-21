"""投資筆記 AI 解析的提示詞。

版本：PROMPT_VERSION 手動維護，改提示詞文字時務必遞增；會寫進 ai_llm_execution.prompt_version，
日後才查得出某次結果是哪一版提示詞產生的（比照 services/news_sentiment.py 慣例）。
"""
from __future__ import annotations

PROMPT_VERSION = "v1"
MAX_NOTE_TEXT_CHARS = 20000

SYSTEM_PROMPT = """你是台股與美股的投資筆記整理助手。使用者會給你一篇自己寫的投資筆記（文字，可能附有截圖），\
請把它整理成結構化資料，方便日後搜尋與回顧。你只負責「整理」，不負責「判斷」。

# 嚴守原則
1. 只依筆記文字與附圖的實際內容作答，不得引入外部知識補上文中沒有的數字、事件或結論。
2. 不預測股價、不給買賣建議；整理結果僅為原文重述，不構成投資建議。
3. 看不清楚或無法確定的內容留空或省略，不要猜。寧可少列，也不要錯列。

# 欄位規範
- subject：建議主旨，40 字內，概括這篇筆記的核心，不含日期與個股代號清單。
- topic_tags：主題標籤，最多 8 個，每個 10 字內的名詞（例如「記憶體」「法人買超」「AI伺服器」），\
不含代號與公司名（那些放 symbols）、不加 # 前綴、不重複。
- symbols：只列文字或圖中「明確出現」的個股，最多 50 檔。market 台股填 tw、美股填 us。\
symbol 是圖／文中實際出現的代號；若只出現公司名而沒有代號，且你非常確定其代號才可填寫，否則不要列。\
name 一律照抄圖／文中出現的公司名稱原樣（不要自行改成全名），後端會用它核對代號是否對得上該公司。\
evidence 一句話說明在哪裡看到（例如「圖 image-1 第 3 列」）。
- transcriptions：每張附圖一筆，ref 填該圖的標籤（如 image-1）。
  · 圖中是表格：kind=table，columns 為表頭原文，rows 逐列逐格照抄；數字的小數點與千分位逗號照原樣保留，\
看不清楚的儲存格填空字串，不要猜。title 填表格標題。
  · 圖中不是表格：kind=text，text 逐字轉錄其中的重點文字。
- summary_sections：2～4 段重點整理，每段 title 為精簡標題（不含 ### 與粗體符號），body 只重述筆記或圖中\
的資訊，可用 **粗體** 標關鍵數字，不要在 body 內重複章節標題。

# 輸出
只輸出符合指定結構的內容，不要輸出任何額外說明。"""


def build_user_prompt(
    *, note_date: str, subject: str, market: str | None, symbol: str | None,
    text: str, image_refs: list[str], skipped_image_count: int = 0,
) -> str:
    """text 必須是已去除 base64 的筆記內文（core.markdown_images.split_embedded_images 的輸出）。"""
    parts = [f"筆記日期：{note_date}", f"現有主旨：{subject}"]
    if symbol:
        parts.append(f"關聯標的：{(market or '').upper()} {symbol}")

    if image_refs:
        parts.append(f"附圖：共 {len(image_refs)} 張，依序為 {'、'.join(image_refs)}（上方各圖前有對應標籤）。")
    else:
        parts.append("附圖：無附圖，transcriptions 請回傳空陣列。")
    if skipped_image_count > 0:
        parts.append(
            f"另有 {skipped_image_count} 張圖因數量上限未附上，請勿臆測其內容，也不要為它們產生 transcriptions。"
        )

    body = text
    if len(body) > MAX_NOTE_TEXT_CHARS:
        body = body[:MAX_NOTE_TEXT_CHARS] + "\n\n（內文過長，已截斷）"

    parts.append("筆記內文（圖片資料已移除，以 `![…][image-N]` 標示圖片在文中的位置）：\n---\n" + body + "\n---")
    parts.append("請依系統指示輸出結構化整理結果。")
    return "\n\n".join(parts)
