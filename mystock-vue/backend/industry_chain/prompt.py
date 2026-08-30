"""
industry_chain/prompt.py
LLM 知識萃取的 System／User Prompt 組裝（見
docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §4.7.3）。

比照 ai/prompt.py 的既有慣例：常數＋純函式，不包 class。Prompt 內不得出現任何硬編碼的
策略門檻——門檻屬於 industry_chain_config/industry_chains.yaml 或 .env 的管轄範圍。
"""
from industry_chain.config import ChainDef

SYSTEM_PROMPT = """你是一位熟悉台灣股市與全球科技產業鏈的專業產業研究員。
你的任務是依據我提供的【產業鏈名稱】與【下游龍頭標的】，建構符合台股現況的上下游供應鏈關聯。

【萃取規範】
1. 僅限台股上市／上櫃公司，且必須同時提供 4 碼股票代號與公司簡稱。
2. relation_tier：1 = 下游龍頭的直接供應商；2 = 供應商的上一層供應商。只輸出這兩層。
3. component_type：精要標示該上游提供的具體零組件或服務（如「散熱模組」「CCL 銅箔基板」）。
4. 排除該業務營收佔比極低、或已退出該供應鏈的公司。
5. evidence：用一句話說明你認定這條關係的依據。

【最重要的一條】
你只需要輸出你有把握的關係。寧可少列，不要猜。
- 不確定股票代號的公司，直接不要列出——列一筆代號錯誤的關係，比漏掉一筆關係傷害大得多。
- 若某個環節你想不出明確的台股上市櫃供應商，把該環節寫進 notes 說明，不要用相近的公司填充。
- 你的知識有時間截止點；若你對某條關係的近況沒有把握，降低該筆的 confidence 或直接略過。

請把 chain_id 原樣填回你收到的值，不要自行更改或創造新的 chain_id。"""


def build_user_prompt(chain: ChainDef, leader_names: dict[str, str]) -> str:
    """`leader_names`：{symbol: name}，用來把 downstream_leaders 展開成「名稱(代號)」。"""
    leaders_text = "、".join(f"{leader_names.get(s, s)}({s})" for s in chain.downstream_leaders)
    parts = [
        f"請建構【{chain.name}（chain_id: {chain.chain_id}）】的上下游供應鏈關聯。",
        f"下游龍頭基準標的：{leaders_text}",
        "請找出它們在台股中的 Tier 1 與 Tier 2 上游供應商。",
    ]
    if chain.extraction_hint:
        parts.append(chain.extraction_hint)
    return "\n".join(parts)


# ── §4.7.7 兩段式 grounded 萃取：Stage A「研究」的 Prompt ─────────
# 刻意跟上面的萃取 Prompt 分開：這一段**不**要求輸出任何結構化欄位，只要研究文字＋
# 檢索工具自己帶回的引用來源；混用會踩到 ADR-IC-17 提到的相容性風險。
RESEARCH_SYSTEM_PROMPT = """你是一位熟悉台灣股市與全球科技產業鏈的專業產業研究員，
可以使用網路搜尋工具查找最新公開資訊。

你的任務是針對我提供的產業鏈與下游龍頭標的，研究「近期」的供應鏈變動：
1. 有沒有新加入的上游供應商？
2. 有沒有已退出或被替換掉的既有供應商？
3. 既有供應商的供貨份額有沒有明顯變化？

【重要規範】
- 只根據搜尋結果回答，不要用你自己的訓練記憶杜撰任何公司名稱或關係。
- 找不到近期異動的環節，直接說「查無近期異動」，不要硬湊內容。
- 用條列的敘述文字回答即可，不需要任何特定格式或結構化欄位——這只是後續萃取步驟的參考資料，
  不是最終輸出。"""


def build_research_user_prompt(chain: ChainDef, leader_names: dict[str, str], lookback_months: int) -> str:
    leaders_text = "、".join(f"{leader_names.get(s, s)}({s})" for s in chain.downstream_leaders)
    return (
        f"請研究【{chain.name}】的供應鏈，近 {lookback_months} 個月內，"
        f"下游龍頭 {leaders_text} 的上游供應商有哪些新進、退出、或份額明顯變動？"
    )
