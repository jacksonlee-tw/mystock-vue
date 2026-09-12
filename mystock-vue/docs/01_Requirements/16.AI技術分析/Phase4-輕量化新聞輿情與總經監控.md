# Phase 4：輕量化新聞輿情與總經監控 需求規格書

```text
Phase 4: 輕量化新聞輿情與總經監控 (Semantic Assist & Macro Monitoring)
   │ (Cnyes/Yahoo/PTT/FRED 爬蟲 + 來源白名單 + 分層情緒評分 + 大盤總經全域鎖)
```

| 項目 | 內容 |
| --- | --- |
| 模組 | 輕量化新聞輿情與總經監控 |
| 對應既有模組 | `strategies/`（新增條件類型）、`services/`（新增新聞與總經管線）、`notify/`（沿用推播）、`db/migration/`（新增資料表） |
| 版本 | v2.1（新增 §15 現況評估與分階段實作計畫） |
| 狀態 | 需求規格 — 待審核，**尚未開發**（2026-09-13 已逐項核對現行程式碼確認：本文件所有規劃項目在 backend／frontend 皆零實作，見 §15.1） |

---

## 0. 修訂紀錄與決策（ADR）

### 0.1 v2.1 變更摘要

新增 §15「現況評估與分階段實作計畫」：逐項核對現行程式碼確認本文件規劃的全部項目（三張新表、`news_fetcher.py`／`macro_fetcher.py`、`news_sources.yaml`、`conditions_sentiment.py`／`conditions_macro.py`、`ScanContext` 新欄位、`api/v1/endpoints/news.py`／`macro.py`、scheduler 排程、notify 樣板、前端元件）**目前零實作**，並將本文件已定案的技術決策轉譯為可執行的分階段交付計畫（WBS），標出文件本身三處已過期／寫錯的檔案路徑（§15.1）、需要人為先做實驗或拍板的風險點（§15.3），以及文件未講清楚、留給實作者自行決定的落差點（§15.4）。**本次僅新增 §15，不變更 §1～§14 任何 FR／ADR／驗收條件的需求本身。**

### 0.2 v2.0 優化重點

v1.0 僅列出「要做哪些功能」，實作時會撞到三個問題：新聞來源開越多雜訊越大、同一則消息被多家轉載重複計分、LLM 逐則評分的成本無上限。v2.0 針對這三點補上機制，並補齊 v1.0 完全沒有處理的 **Point-in-time 對齊**（新聞與總經數據的「可見時點」與交易日不是同一條時間軸）。

### 0.3 決策紀錄

| 編號 | 決策 | 理由 |
| --- | --- | --- |
| ADR-P4-01 | 新聞／社群來源以 `strategy_config/news_sources.yaml` 白名單驅動，可逐一 `enabled` 開關並設定 `weight`，不寫死於程式碼 | 使用者需能隨時關閉雜訊來源；沿用 `strategies.yaml`「改設定不需改程式」的既有慣例 |
| ADR-P4-02 | 入庫前做三層去重（URL → 正規化標題雜湊 → 近似標題），重複者保留權重最高的來源，其餘標記 `is_duplicate` 但不刪除 | Yahoo 股市大量轉載鉅亨網內容，不去重會讓同一則利多被重複計分；保留列而非刪除，方便回頭稽核降噪是否過當 |
| ADR-P4-03 | 情緒評分採分層成本控管：預設本地模型批次評分全部標題，LLM 僅在指定閘門觸發時介入；LLM 配額**獨立於** `AI_DAILY_QUOTA` | 新聞評分是「每日數百則標題」的量級，與「每檔每日一份技術分析報告」的成本模型完全不同，共用計數器會把報告額度排擠掉 |
| ADR-P4-04 | 新聞／PTT／總經資料採兩段式落地：先寫 JSON 緩衝檔，再入 PostgreSQL | 外部來源不可重放（新聞列表 API 只給最近 N 則，過期就抓不回來），DB 短暫不可用時不能漏接 |
| ADR-P4-05 | 新聞與總經數據一律以「可見時點」對齊交易日，不以發布內容所屬期間對齊 | 比照 `strategies/conditions_fund.py` 對 MOPS 月營收的 look-ahead bias 處理，避免用盤後才出現的新聞去判斷當日訊號 |
| ADR-P4-06 | `sentiment_filter`／`macro_filter` 實作為 **condition**，不是 `strategies/filters.py` 的 filter | `filters.py` 明訂濾網只加分、永不擋訊號；情緒與總經是會決定訊號成立與否的閘門，語意上屬 condition |
| ADR-P4-07 | 三張新表直接以 PostgreSQL 為唯一儲存，不參與 `DATA_SOURCE` 的 JSON／PG 雙軌切換 | 比照 `ai_analysis_report` 的既有決策（ADR-AI-14）；雙軌是為 OHLCV 設計，新資料類別不值得再做一套 |

---

## 1. 範圍與設計前提

### 1.1 核心目標

引進「消息面」與「總體經濟面」作為技術／籌碼／基本面之外的第四道濾網：對個股新聞與社群討論做輕量化情緒量化，並以大盤與總經環境作為策略引擎的進場總開關，為既有選股與風控邏輯提供**輔助確認層**，不取代任何既有量化訊號。

### 1.2 交付內容

- 依白名單設定串接鉅亨網（Cnyes）個股新聞、Yahoo 股市重大訊息與 PTT Stock 板討論度，經三層去重後存入 `stock_news` / `stock_discussion_buzz`。
- 串接 FRED 總經指標與美元指數（DXY），存入 `macro_indicators`；大盤位階（20MA／60MA）沿用既有 `services/index_service.py` 的指數資料，不重建管線。
- 分層情緒評分引擎：輸出 `sentiment_score`（-1.0～+1.0）與 `sentiment_label`（BULLISH／BEARISH／NEUTRAL），並彙整為個股 5 日情緒動能與 Buzz Surge 指標。
- 於 `strategy_config/strategies.yaml` 新增 `sentiment_filter`／`macro_filter` 兩種 condition，串進既有掃描器、去重與通知平台。

### 1.3 既有系統前提（重用什麼、不重建什麼）

實作前先盤點既有模組，避免重工，也避免與既有慣例衝突：

- **大盤位階不重算**：加權指數／S&P 500 的每日收盤與均線基礎資料，`services/index_service.py`（`GET /api/v1/indices/overview`）已可取得。總經模組只在既有指數資料上疊加「是否站上 20MA」的判斷。
- **匯率不重建**：USD/JPY/CNY 兌台幣已有 `services/exchange_rate_fetcher.py` + `GET /api/v1/exchange-rates/latest`。本階段只新增既有管線沒有的美元指數（DXY）與 FRED 系列。
- **設定檔路徑**：`backend/` 底下**沒有** `config/` 目錄，只有 `config.py` 模組，新建 `config/` 會撞名（`strategies.yaml` 當初就是因此改放 `strategy_config/`）。新設定檔一律放 `backend/strategy_config/`。
- **`data/raw/` 目前不存在**：實際落地結構是 `backend/data/{tw,us}/<symbol>.json` 與 `backend/data/_alerts/`（非個股資料以 `_` 前綴目錄存放）。Phase 1／Phase 2 規劃文件提到的 `data/raw/` 尚未落地，本階段比照 `_alerts` 的實際慣例使用 `backend/data/_news/`，不另立 `data/raw/`。
- **LLM Provider 可重用、配額不可共用**：`ai/providers.py` 的 `PROVIDER_REGISTRY`（Claude／Gemini）抽象可直接沿用，但 `ai/guard.py` 的 `AI_DAILY_QUOTA` 計數器不可共用（ADR-P4-03）。
- **通知不建新管線**：Email／Slack／Telegram 三通道與 Jinja2 樣板機制（`notify/`）已完成，情緒／總經訊號比照 `ALERT_SIGNAL`／`ALERT_DIGEST` 事件掛上 `notify/dispatcher.py`。**專案沒有 LINE 通道**，規劃文件不應假設其存在。
- **市場範圍**：新聞、情緒、PTT 討論度來源皆為台股專屬內容，本階段**僅支援 TW**（比照 `conditions_chip.py`／`conditions_fund.py` 以 `ctx.market == "tw"` 把關的慣例）；總經全域鎖涵蓋 TW（加權指數）與 US（S&P 500）。

### 1.4 不在本文件範圍

- 盤中即時串流情緒更新（僅批次評分，不做 WebSocket／輪詢推送）。
- 台股以外的新聞來源（Bloomberg、Reuters 等），US 個股本階段沒有新聞／情緒資料。
- PTT 以外的社群平台（Dcard、Threads、X 等）。
- 新聞全文抓取、全文 RAG 與事件抽取（本階段只處理標題）。
- 情緒與總經訊號的獨立回測框架（樣本累積足夠後另立階段，做法可比照 Phase 3「跟漲勝率矩陣」）。
- `macro_filter` 的非布林分級輸出（「降低每筆部位上限」的量化分級）；本階段只落地「限制進場」的布林式全域鎖。

---

## 2. 設定檔驅動的來源白名單（ADR-P4-01）

新增 `backend/strategy_config/news_sources.yaml`，與 `strategies.yaml` 同目錄、同慣例（每次讀取時重新解析，改設定不需重啟）：

```yaml
# backend/strategy_config/news_sources.yaml
defaults:
  dedup_window_hours: 48      # 近似標題比對的回溯範圍
  dedup_hamming_max: 3        # SimHash 漢明距離門檻，越小越嚴格
  sentiment_window_days: 5    # 情緒動能計算的交易日數

sources:
  - id: "cnyes"
    name: "鉅亨網台股新聞"
    kind: "news"
    enabled: true
    weight: 1.2               # 情緒加權平均的來源權重
    endpoint: "https://api.cnyes.com/media/api/v1/newslist/category/tw_stock_news"
    rate_limit_seconds: [3, 5]  # 隨機延遲區間，比照 fetcher.py 節流慣例

  - id: "yahoo_stock"
    name: "Yahoo 股市重大訊息"
    kind: "news"
    enabled: false            # 預設關閉：與鉅亨網轉載重疊度高，需要冷門股覆蓋率時再開
    weight: 1.0

  - id: "ptt_stock"
    name: "PTT Stock 板"
    kind: "buzz"              # 只計討論量，不進情緒評分
    enabled: true
    weight: 0.8
```

規格要點：

- `enabled: false` 的來源**完全不抓取**，且既有資料在情緒計算時一併排除（不是只停止新增），使用者關掉來源後當天就能看到降噪效果。
- `weight` 用於 5 日情緒加權平均（見 §4.3），不影響去重優先序以外的其他行為。
- `kind` 區分 `news`（進情緒評分）與 `buzz`（只計討論量），避免把社群發文當新聞評分。
- 設定檔解析失敗時（YAML 語法錯誤）記錄錯誤並沿用上一次成功載入的設定，不讓排程整個中斷。

---

## 3. 新聞資料管線（News Pipeline）

### 3.1 抓取與輕量化

- 封裝於 `services/news_fetcher.py`，比照 `services/fetcher.py` 的 `fetch_status` 單例（排程與手動觸發共用同一個 in-flight guard，執行中不重複觸發）與節流設計。
- 僅擷取 `title`、`news_url`、`published_at`、`symbol`、`industry`，**不抓內文與 HTML**，降低儲存與後續評分的輸入成本。
- 新聞與 PTT 皆非官方開放資料，須遵守目標站點的存取條款與頻率限制，採隨機延遲與失敗重試上限，不併發高頻爬取。

### 3.2 兩段式落地（ADR-P4-04）

1. 第一階段寫入 JSON 緩衝檔 `backend/data/_news/raw/{source_id}/{YYYYMMDD}.json`（目錄命名比照既有 `data/_alerts/`）。
2. 第二階段解析緩衝檔寫入 PostgreSQL `stock_news`。第二階段失敗可依緩衝檔重跑，不需重新爬取。

### 3.3 三層去重與降噪（ADR-P4-02）

v1.0 只有 URL 唯一鍵，攔不住跨來源轉載。改為三層，由便宜到昂貴：

| 層級 | 機制 | 攔截對象 |
| --- | --- | --- |
| L1 | 唯一索引 `(symbol, news_url)` + `ON CONFLICT DO NOTHING` | 同一來源重複抓取 |
| L2 | 唯一索引 `(symbol, title_hash, effective_trade_date)`，`title_hash = sha256(正規化標題)` | 跨來源逐字轉載 |
| L3 | SimHash（64-bit）+ 漢明距離 ≤ `dedup_hamming_max`，比對範圍限縮在**同一 symbol 近 `dedup_window_hours` 小時** | 改寫標題的近似重複 |

- 標題正規化規則：全形轉半形、去除來源前綴標記（如「〈財經〉」「快訊」「盤中速報」）、移除空白與標點、統一大小寫。
- L3 命中時，保留 `news_sources.yaml` 中 `weight` 最高的那一則為代表列（`is_duplicate = false`），其餘標記 `is_duplicate = true`；情緒計算只讀 `is_duplicate = false` 的列。
- **不採用 v1.0 提案的「`similarity_hash` 欄位 + 相似度 90%」寫法**：一般雜湊只能做完全相等比對，無法表達 90% 相似度，欄位與判斷條件互相矛盾。若不想自建 SimHash，替代方案是啟用 PostgreSQL `pg_trgm` 擴充以 `similarity()` 比對——但目前 `db/migration/` 從未啟用任何 extension，且 trigram 對中文標題的鑑別度需先實測，故列為備案而非預設。

### 3.4 Point-in-time 對齊：`effective_trade_date`（ADR-P4-05）

新聞的 `published_at` 是掛鐘時間，交易訊號的判斷單位是交易日，兩者不能直接相等：

- 台股收盤 13:30，當日 20:00 發布的新聞若計入 `trade_date = T`，掃描 T 日訊號時就會用到「當時還不存在的資訊」，形成 look-ahead bias。
- 規則：`published_at` ≤ 當日 13:30 → `effective_trade_date = T`；晚於 13:30 或落在非交易日 → 順延至**下一個交易日**。交易日曆沿用既有 `market_no_trading_days` 資料。
- 此欄位為 §4.3 情緒動能與 `sentiment_filter` 的唯一時間依據，`published_at` 僅供前端顯示。

處理方式與 `strategies/conditions_fund.py` 對 MOPS 月營收的做法一致（該檔案已明文處理「營收公告日與交易日曆是兩套獨立時間軸」）。

---

## 4. 情緒量化引擎（Sentiment Engine）

### 4.1 分層評分與成本控管（ADR-P4-03）

| 層 | 引擎 | 觸發時機 | 成本 |
| --- | --- | --- | --- |
| L1（預設） | 本地輕量模型批次評分 | 每則 `is_duplicate = false` 的新聞標題 | 免費，僅耗 CPU |
| L2（加強） | LLM（沿用 `ai/providers.py` 的 Claude／Gemini 抽象） | 僅在閘門成立時 | 計費，受獨立配額上限管控 |

L2 閘門條件（三者皆需成立，避免無上限呼叫）：

1. 該標的當日 5 日情緒分數落在極端區間（`|score| ≥ 0.8`），或當日 Buzz Surge ≥ 設定倍數；且
2. 該標的在追蹤清單／持股庫存內（不對全市場開放）；且
3. 當日 LLM 呼叫數未達 `NEWS_LLM_DAILY_QUOTA`。

L2 呼叫一律**批次送出**（一次請求帶多則標題、回傳 JSON 陣列），不逐則呼叫，降低 per-request overhead。呼叫紀錄比照既有 `ai_llm_execution` 表的粒度記錄成本（可沿用該表，以 `symbol` 為空、另立 `prompt_version` 區分用途，避免再建一張成本表）。

### 4.2 中文模型選型風險（需在開發前先驗證）

v1.0 直接指名 FinBERT，但 **FinBERT 是以英文財經語料訓練的**，對繁體中文新聞標題不可直接套用。開發前需先做選型驗證：

- 候選：中文金融領域微調模型、通用中文情感分類模型 + 財經語料微調，或直接以 LLM 少量樣本標註後蒸餾。
- 驗收方式：人工標註 200～300 則台股新聞標題作為基準集，比較候選模型與 LLM 的一致率，達標才進入 L1 預設；未達標則暫時以「L2 LLM + 更嚴格閘門」上線，不硬推低品質的本地模型。
- 部署成本需一併評估：把 transformer 模型載入 FastAPI 容器會顯著增加映像大小與記憶體佔用，需決定是「常駐 API 程序內」或「排程批次程序獨立執行」——建議後者，避免拖累既有 API 反應時間。

### 4.3 個股情緒動能與 Buzz Surge

以 `effective_trade_date` 為時間軸，於每日新聞評分完成後計算並落地（前後端共用同一份結果，不各算一套）：

- **5 日加權情緒分數**：對近 5 個交易日、`is_duplicate = false` 的新聞取來源權重加權平均
  `sentiment_5d = Σ(weight_source × score_i) / Σ(weight_source)`
- **Buzz Surge（新聞曝光倍數）**：`當日新聞則數 / 近 20 交易日平均則數`
- **背離標記**：結合既有 `ScanContext` 的價格序列，標記「利多鈍化」（情緒 ≥ 門檻但股價未漲）與「利空不跌」（情緒 ≤ 門檻但股價未跌），作為訊號的補充註記，不單獨成為訊號。

### 4.4 PTT 散戶熱度（反向指標）

- 抓取 PTT Stock 板每日各標的討論篇數，落地至 `stock_discussion_buzz`。
- 過熱判定採**該檔個股自身近 250 交易日分佈的分位數**，不用絕對篇數門檻——不同市值標的的日常討論量差好幾個量級，「單日 50 篇」對台積電是冷清、對中小型股是異常，絕對值沒有跨股可比性。
- `percentile_rank ≥ 0.95` 標記為散戶過熱，供 `sentiment_filter` 的 `max_buzz_percentile` 參數排除。

---

## 5. 總體經濟與大盤環境（Macro & Market Filter）

### 5.1 FRED 資料管線與釋出時點對齊

- 封裝於 `services/macro_fetcher.py`，串接 FRED API 抓取：聯邦資金利率、非農就業、CPI、美國 10 年期公債殖利率；另抓美元指數（DXY）。統一落地 `macro_indicators`。
- **`indicator_date`（資料所屬期間）與 `release_date`（官方公布日）必須分開兩欄**（ADR-P4-05）：CPI、非農等月頻數據的公布日落後所屬月份數週，若只存 `indicator_date` 並以之對齊交易日，等於在資料尚未公布前就拿來判斷，是與月營收完全相同的 look-ahead bias。`macro_filter` 只讀 `release_date ≤ trade_date` 的紀錄。
- 台股與美股的每日指數收盤資料沿用既有 `index_service.py`，本管線不重抓指數。

### 5.2 大盤環境全域鎖（Global Market Filter）

- 在既有指數資料上計算 20MA／60MA 位階與單日跌幅，實作為 `macro_filter` condition。
- 觸發「限制進場」的條件（YAML 可調）：大盤跌破 20MA、或呈空頭排列、或總經指標同向轉緊（例如 10 年期殖利率短期急升）。條件成立時，掛載此 condition 的策略當日不成立訊號。
- **全域鎖是「每個市場每個交易日一組值」，不是每檔個股各算一次**：掃描器會對數千檔個股跑迴圈，若在 condition 內部逐檔載入指數資料等於重複載入數千次。設計上須在單次掃描開始時計算一次並注入，供該次掃描的所有標的共用。

---

## 6. 策略引擎整合

### 6.1 condition 與 filter 的分工（ADR-P4-06）

`strategies/filters.py` 的檔案註解已明訂：「濾網只做加分——計入 `signal_strength` 的通過項目，不會擋掉核心策略本身已觸發的訊號」。而「情緒未達門檻不進場」「大盤空頭時不進場」是**會決定訊號成立與否**的閘門，因此必須實作為 condition：

- 新增 `strategies/conditions_sentiment.py`、`strategies/conditions_macro.py`，比照 `conditions_tech.py`／`conditions_chip.py`／`conditions_fund.py` 的慣例，函式簽章維持 `(ctx: ScanContext, idx: int, params: dict) -> list[dict] | None`。
- 以 `@condition(type=...)` 裝飾器自動註冊，並在 `strategies/__init__.py` 補上兩行 import（匯入即註冊，漏掉就找不到條件函式）。
- 型別名稱沿用 `sentiment_filter`／`macro_filter`（語意上是 condition，與 `filters` 模組無關，此點於文件與程式註解中明示以免誤解）。

### 6.2 `ScanContext` 擴充

condition 只能讀 `ctx`，**不得自行發請求或讀檔**（此為專案既有鐵則：條件函式只讀 `ctx.ma`／`ctx.bias`，不重算指標）。因此需在 `services/chip_provider.py` 的 `ScanContext` 新增與 `dates` 等長的平行序列，比照既有 `revenue_yoy`／`revenue_visible_month` 的做法：

| 新增欄位 | 型別 | 說明 |
| --- | --- | --- |
| `sentiment_5d` | `List[Optional[float]]` | 逐交易日的 5 日加權情緒分數 |
| `news_count` | `List[Optional[int]]` | 逐交易日的有效新聞則數（去重後） |
| `buzz_percentile` | `List[Optional[float]]` | 逐交易日的 PTT 討論量分位數 |
| `macro_flags` | `Dict[str, bool]` | 該次掃描的市場層級旗標（單次掃描共用，非逐日序列） |

`ChipDataProvider.get_bars()` 需在載入 K 線的同一次呼叫中一併補上這些序列，避免掃描器對每檔個股額外多發查詢。

### 6.3 YAML 擴充範例

```yaml
# backend/strategy_config/strategies.yaml 擴充範例
strategies:
  - id: "momentum_with_news_confirmation"
    name: "動能突破與利多共振"
    category: "trend_sentiment"
    enabled: true
    markets: ["tw"]              # sentiment_filter 僅支援 TW；跨市場需拆成兩個策略
    conditions:
      - type: "price_cross"      # 主觸發：技術面突破
        target: "close"
        ma_periods: [60]
        directions: ["cross_above"]
      - type: "sentiment_filter" # 閘門：不在利空下追高
        min_score: 0.5
        max_buzz_percentile: 0.85
      - type: "macro_filter"     # 閘門：大盤環境保護
        market_trend: "above_20ma"
    filters:
      - type: "volume_confirm"   # 加分：不影響訊號成立
        params: { multiple: 1.5 }
```

### 6.4 閘門型 condition 的使用限制

`sentiment_filter` / `macro_filter` 屬於**持續性狀態**（大盤站上月線可能連續成立數十天），不是轉折事件。若某策略只掛閘門型 condition 而無主觸發條件，會每個交易日都成立、天天推播。規格要求：

- 兩者不得作為策略的唯一 condition，設定檔載入時應檢核並在啟動日誌警示。
- 訊號去重仍沿用既有 `strategies/cooldown.py`（`ALERT_COOLDOWN_DAYS`，依 `(symbol, strategy, direction)`），不另建一套。

---

## 7. 資料庫設計（PostgreSQL）

新增 Flyway 遷移檔（版本號以合併當下 `backend/db/migration/` 最新序號為準，例如 `V17__Create_news_and_macro_tables.sql`；**不得修改任何已套用的 `V*` 檔案**）。

### 7.1 `stock_news`（新聞與情緒）

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `id` | BIGSERIAL PK | |
| `symbol` / `market_type` | VARCHAR | 比照既有表以 `market_type` 命名 |
| `source` | VARCHAR(20) | 對應 `news_sources.yaml` 的 `id` |
| `title` | TEXT | 標題原文 |
| `news_url` | TEXT | |
| `published_at` | TIMESTAMP | 原始發布時間，僅供顯示 |
| `effective_trade_date` | DATE | Point-in-time 對齊後的交易日（§3.4），所有計算的時間依據 |
| `title_hash` | CHAR(64) | 正規化標題 SHA-256，L2 去重用 |
| `simhash` | BIGINT | 64-bit SimHash，L3 近似去重用 |
| `is_duplicate` | BOOLEAN | L3 判定為重複；情緒計算排除 |
| `duplicate_of_id` | BIGINT | 指向保留的代表列 |
| `sentiment_score` | NUMERIC(4,3) | -1.000 ～ 1.000 |
| `sentiment_label` | VARCHAR(10) | BULLISH / BEARISH / NEUTRAL |
| `sentiment_engine` | VARCHAR(20) | 標記由 L1 本地模型或 L2 LLM 產生，供品質稽核 |
| `extra_meta` | JSONB | 作者、標籤等擴充欄位（比照 `activity_log.detail`／`ai_analysis_report.quant_summary` 的 JSONB 慣例） |
| `created_at` | TIMESTAMP | |

索引：唯一 `(symbol, news_url)`、唯一 `(symbol, title_hash, effective_trade_date)`、查詢用 `(market_type, symbol, effective_trade_date DESC)`、去重掃描用 `(symbol, published_at DESC)`。

### 7.2 `stock_discussion_buzz`（社群討論度）

`symbol`、`market_type`、`trade_date`、`source`、`post_count`、`percentile_rank`、`created_at`；唯一鍵 `(source, symbol, trade_date)`。

### 7.3 `macro_indicators`（總經時序）

`indicator_code`（如 `DXY`、`US10Y`、`CPI`、`NFP`）、`indicator_date`（所屬期間）、`release_date`（公布日，§5.1）、`value`、`source`、`fetched_at`；唯一鍵 `(indicator_code, indicator_date)`，另建 `(indicator_code, release_date DESC)` 供 Point-in-time 查詢。

---

## 8. API 設計

回應信封沿用專案慣例 `{"success": bool, "data": ..., "message"?: ..., "error"?: {"code","message"}}`；個股不存在時拋 `core.exceptions.SymbolNotFoundException`，由 `main.py` 全域 handler 轉 404。新增 `api/v1/endpoints/news.py`、`api/v1/endpoints/macro.py` 兩個市場無關的 `APIRouter`，掛載於 `main.py`。

| 端點 | 說明 |
| --- | --- |
| `GET /api/v1/news/{symbol}` | 分頁查詢個股新聞與情緒評分。分頁參數比照 `stocks.py`／`investment_notes.py` 採 `page`／`page_size`；預設隱藏 `is_duplicate = true`，可加 `include_duplicates=true` 稽核 |
| `GET /api/v1/news/sources` | 回傳 `news_sources.yaml` 目前的來源與啟用狀態，供前端顯示「目前納入哪些來源」 |
| `POST /api/v1/news/trigger` | 手動觸發抓取（背景執行），比照 `fundamentals.py` 的 trigger／status 成對慣例 |
| `GET /api/v1/news/status` | 抓取任務進度與日誌 |
| `GET /api/v1/macro/summary` | 一次回傳大盤位階（TW／US）＋ 總經指標現值與趨勢，前端不需分別呼叫兩套 API |

---

## 9. 排程整合

沿用 `services/scheduler.py` 的 `AsyncIOScheduler` 與「抓取完成後鏈式觸發下一步」的既有慣例（現行 `_scan_after_fetch` 即為此模式），全部使用 `Asia/Taipei` 時區：

| 工作 | 時間 | 說明 |
| --- | --- | --- |
| 新聞抓取（盤後） | 交易日 14:40 | 接在 TW 14:30 抓取之後 |
| 新聞抓取（夜間） | 每日 21:00 | 收攏盤後發布的新聞，歸入次一交易日 |
| 情緒評分 | 新聞抓取完成後鏈式觸發 | 不另設固定時間，避免與抓取搶時序 |
| PTT 討論量 | 每日 23:30 | 收整當日發文數 |
| FRED／DXY | 每日 08:00 | 美國前一交易日資料已釋出 |
| 新聞資料清理 | 每日 04:10 | 比照既有 `_notify_purge_logs`（04:00）的清理時段 |

---

## 10. 通知整合

- 情緒／總經訊號沿用既有 `ALERT_SIGNAL`／`ALERT_DIGEST` 事件與 `notify/dispatcher.py`，不建新推播管線。
- **推播訊息附上促成訊號的新聞標題與來源**：於 `ALERT_SIGNAL` 的 `payload` 增加 `top_news`（標題、來源、連結）與 `sentiment_5d` 欄位，並在 `notify/templates/alert_signal.{email,slack,telegram}.j2` 三份樣板加上對應區塊（樣板已有 `{% if details %}` 的選擇性區塊寫法可比照）。
- 冪等鍵不受影響：`notify/events.py` 的 `_key_alert_signal` 由 `(market, stock_id, strategy_id, direction, trade_date)` 組成，新增 payload 欄位不會改變去重行為。
- 若需與技術訊號不同的文案，再新增 `sentiment_alert.*.j2` 三份樣板；三個通道必須同時提供，缺一會退回 `__default__.txt.j2`。

---

## 11. 前端（Vue 戰情室）

- **個股新聞卡片**：列出標題、來源、發布時間與情緒 Tag。
  **配色須注意**：本專案的硬性慣例是**紅漲綠跌（台美股統一，不因市場切換）**，因此情緒 Tag 若採紅綠色系，必須是**利多＝紅、利空＝綠、中性＝灰**。常見的「綠色利多／紅色利空」西方慣例在本專案是反的，會與同頁面的漲跌幅色彩互相矛盾。若要避免混淆，替代方案是情緒 Tag 改用非紅綠色系（如琥珀／靛藍）並加上文字標籤。
- **來源開關可視性**：卡片區塊需顯示「目前納入 N 個來源」並可連結至來源設定說明，讓使用者知道看到的新聞量是被白名單過濾過的結果。
- **總經儀表板**：於 `HomeDashboard.vue` 新增區塊，顯示大盤 20MA 多空燈號、10 年期公債殖利率與 DXY 的 Sparkline（Sparkline 資料格式可比照 `indices/overview` 既有回傳結構）。
- **兩條硬性規則必須遵守**（見專案 `CLAUDE.md`）：
  1. 圖表期間／區間切換時不得整頁 reload 導致捲動位置跳回頂端——刷新期間保留舊內容並以覆蓋層顯示 spinner，只有首次無資料時才顯示整頁載入狀態。
  2. 同列 KPI／指標卡片高度必須一致——grid 版面的卡片需補 `!m-0` 以中和 `_utils.scss` 的 legacy `margin-bottom`，比照 `StockDashboard.vue` 現行作法。

---

## 12. 設定項目（`backend/.env`）

```bash
# --- Phase 4 新聞輿情與總經監控 ---
NEWS_FETCH_ENABLED=true
NEWS_SENTIMENT_ENGINE=local          # local | llm | hybrid
NEWS_LLM_DAILY_QUOTA=50              # 獨立於 AI_DAILY_QUOTA（ADR-P4-03）
NEWS_LLM_PROVIDER=gemini             # 沿用 ai/providers.py 的 provider 代碼
NEWS_RETENTION_MONTHS=12             # 新聞保留月數，逾期由清理排程刪除
FRED_API_KEY=                        # 機敏資訊，不進版控，比照既有 .env 慣例
MACRO_FETCH_ENABLED=true
```

`.env.example` 需同步新增這些項目（含註解），維持既有「複製 `.env.example` 即可啟動」的前提。

---

## 13. 資料保留

新聞是每日數百列的持續成長資料，與既有的每日一列 OHLCV 不同量級，需明確保留政策（比照 `ai_analysis_report` 規格書 §5.10 對保留策略的處理）：

- `stock_news` 保留 `NEWS_RETENTION_MONTHS` 個月，逾期刪除；每日情緒動能彙總值另存不刪，避免歷史回溯時整段空白。
- `stock_discussion_buzz`、`macro_indicators` 為每日／每月一列的小量時序，不設刪除。
- 清理由排程執行（§9），實作比照 `notify` 既有的 `purge_old_logs`。

---

## 14. 驗收條件（AC）

| 編號 | 驗收條件 |
| --- | --- |
| AC-P4-01 | 將 `news_sources.yaml` 中某來源設為 `enabled: false` 後，重新抓取不再產生該來源新聞，且情緒計算排除其歷史資料，全程不需改動程式碼或重啟服務 |
| AC-P4-02 | 同一則新聞由兩個來源轉載時，`stock_news` 僅有一列 `is_duplicate = false`，且保留的是 `weight` 較高的來源 |
| AC-P4-03 | 台股當日 20:00 發布的新聞，其 `effective_trade_date` 為次一交易日，且不影響當日已產生的訊號 |
| AC-P4-04 | 月頻總經指標（CPI／非農）在 `release_date` 之前不被 `macro_filter` 讀取 |
| AC-P4-05 | 掛載 `sentiment_filter` 的策略在情緒未達門檻時不產生訊號；而 `volume_confirm` 等既有 filter 不通過時訊號仍然產生（只是強度較低）——兩者行為差異可在掃描結果中驗證 |
| AC-P4-06 | 全市場掃描時，指數／總經資料每次掃描只載入一次，不隨標的數量線性成長 |
| AC-P4-07 | LLM 情緒評分呼叫數達 `NEWS_LLM_DAILY_QUOTA` 後停止呼叫並記錄，且 `AI_DAILY_QUOTA`（技術分析報告）額度不受影響 |
| AC-P4-08 | 新聞卡片的情緒 Tag 配色與同頁面漲跌幅配色方向一致，不出現「紅色代表利空、同頁紅色代表上漲」的矛盾 |
| AC-P4-09 | 個股頁切換圖表期間時捲動位置不跳回頂端；新增的總經卡片與同列既有卡片高度一致 |

---

## 15. 現況評估與分階段實作計畫（v2.1 新增，2026-09-13）

本節不改變 §1～§14 的任何需求，只回答兩件事：**現在做到哪裡了**、**接下來怎麼分階段做**。方法是逐項核對現行程式碼，不是讀規格猜測。

### 15.0 現況評估結論

全文對照 `backend/`／`frontend/` 後確認：本文件規劃的每一項產出——三張新表（`stock_news`／`stock_discussion_buzz`／`macro_indicators`）、`services/news_fetcher.py`、`services/macro_fetcher.py`、`strategy_config/news_sources.yaml`、`strategies/conditions_sentiment.py`／`conditions_macro.py`、`ScanContext` 的 `sentiment_5d`／`news_count`／`buzz_percentile`／`macro_flags` 欄位、`api/v1/endpoints/news.py`／`macro.py`、`services/scheduler.py` 的新聞/總經排程、`notify/` 的新聞相關樣板、任何前端新聞或總經 UI——**全部零實作**。目前最新 Flyway 遷移是 `V22__Create_quarterly_financials.sql`，本文件新增的遷移須從 **V23** 起算（§7 原文寫「例如 V17」已過期）。這與文件頂部自報的「尚未開發」狀態一致，不像 Phase 2／3／5 文件曾出現「狀態欄位過期、程式碼早已超前」的落差。

### 15.1 轉譯前必須先修正的文件錯誤（避免施工者照抄文件字面出錯）

| # | 文件原文 | 問題 | 修正 |
| --- | --- | --- | --- |
| 1 | §11：「於 `HomeDashboard.vue` 新增總經儀表板區塊」 | `HomeDashboard.vue` 是**遺留死碼**——已核對 `frontend/src/router/index.js`，完全沒有任何路由掛載它；內容是假資料 `newsList`/`todoList`，還留著除錯用 `console.log` | 總經儀表板區塊應加在 **`frontend/src/views/HeatmapDashboard.vue`**——這才是真正掛在 `/` 路由（`name: 'heatmap-dashboard'`）的首頁 |
| 2 | §6.4：暗示 `ALERT_COOLDOWN_DAYS` 在 `strategies/cooldown.py` | 已核對 `backend/config.py`：常數是 `DEFAULT_ALERT_COOLDOWN_DAYS`、讀取函式是 `get_alert_cooldown_days()`，都在 `config.py`；`strategies/cooldown.py` 只有兩個純函式 `cooldown_key()`／`is_active()`，沒有任何天數常數 | 去重邏輯是「`cooldown.py` 的鍵與判斷函式」＋「`config.py` 的天數設定」兩個檔案協作，文件與後續程式註解需並列兩個檔名，不能只提一個 |
| 3 | §7：「例如 `V17__Create_news_and_macro_tables.sql`」 | `V17` 已被 `V17__Relax_investment_note_symbol_pair_check.sql` 占用；目前最新是 `V22__Create_quarterly_financials.sql` | 實際命名為 **`V23__Create_news_and_macro_tables.sql`**，且動工前需重新 `ls db/migration/` 確認當下最新序號（期間可能有其他分支併入新遷移） |

**額外可具體化之處**：§4.1「呼叫紀錄比照既有 `ai_llm_execution` 表的粒度記錄成本」——已找到比文件描述更具體的現成範本：`backend/industry_chain/extractor.py`（約 117～201 行）就是同一模式的實作先例（配額檢查直接 `SELECT COUNT(*) FROM ai_llm_execution WHERE ...`、寫入時 `report_id=None`／`symbol=None`／獨立 `prompt_version`；`ai_llm_execution.report_id` 已核對 `V14__Create_ai_analysis_tables.sql` 為可 NULL 外鍵）。`NEWS_LLM_DAILY_QUOTA` 的配額檢查與寫入建議直接照抄這段程式碼的結構，不需重新設計。

### 15.2 分階段交付計畫（WBS）

| 階段 | 範圍 | 前置依賴 | 獨立驗證方式 | 工作量感覺 |
| --- | --- | --- | --- | --- |
| **Spike-0**（可與 P0 並行，建議最早啟動） | 中文情緒模型選型驗證（§4.2）：人工標註 200～300 則台股新聞標題，比較候選模型與 LLM 的一致率，決定 `NEWS_SENTIMENT_ENGINE` 預設值與 L1 部署形態（常駐 vs 排程批次） | 無（可先用臨時腳本抓樣本，不需等 P1 完工） | 與人工標註基準集的一致率（門檻數字待訂，見 §15.3-1） | **需要先做實驗才能繼續，非單純寫程式**；結果回頭決定 P2 範圍 |
| **P0** 骨架與設定 | `db/migration/V23__Create_news_and_macro_tables.sql`（三表+索引，§7 照抄）、`strategy_config/news_sources.yaml`（§2 照抄）、`.env`/`.env.example` 新增 §12 六個變數、`config.py` 新增對應 getter（比照 `get_alert_cooldown_days()` 模式）、YAML loader（重新解析不需重啟、解析失敗沿用舊設定——需先讀 `strategies/config_loader.py` 確認能否共用同一套快取/重載機制） | 無 | `flyway migrate` 後查表結構；改 `enabled` 值驗證熱重載；刻意寫壞 YAML 驗證 fallback | 小 |
| **P1** 新聞資料管線 | `services/news_fetcher.py`（cnyes/yahoo_stock/ptt_stock，比照 `fetcher.py` 的 `fetch_status` 單例＋節流）、兩段式落地（`data/_news/raw/{source_id}/{YYYYMMDD}.json` → `stock_news`）、三層去重（L1/L2 為 SQL 唯一索引；L3 SimHash 需新增獨立工具函式，建議 `services/news_dedup.py`）、`effective_trade_date` 計算（比照 `indicators/fundamental.py` 的 `latest_visible_month()` 寫法，建議新增 `indicators/news_time.py`）、`api/v1/endpoints/news.py` 四個端點 | P0 | 情緒評分完全不做也能驗證 AC-P4-01/02/03（`sentiment_score` 允許 NULL） | **主要工程量**（三來源穩定度＋三層去重＋point-in-time 對齊） |
| **P2** 情緒評分引擎 | 依 Spike-0 結論實作 L1／L2；L2 沿用 `ai/providers/__init__.py` 的 `PROVIDER_REGISTRY`；配額與成本記錄直接照抄 `industry_chain/extractor.py`（見 §15.1 附註）；`sentiment_5d`／Buzz Surge／背離標記彙總 job；PTT 過熱分位數直接複用 `indicators/chip.py` 既有的 `rolling_percentile()`（換 `value_fn`、`window=250`，不重寫演算法） | Spike-0 結論、P1 | 對照 Spike-0 基準集算一致率回歸；配額用完驗證 AC-P4-07 | **主要工程量，且高度依賴 Spike-0 是否順利** |
| **P3** 總經／大盤環境管線（可與 P1/P2 並行） | `services/macro_fetcher.py`（FRED + DXY，`indicator_date`/`release_date` 分欄）、`api/v1/endpoints/macro.py`、20MA/60MA 位階讀既有 `index_service.py`（不重建指數管線） | P0 | 查表確認兩欄位分離；用歷史 CPI/非農公布日構造案例驗證 AC-P4-04 | 中（FRED API 本身簡單，複雜度在 release_date 對齊與 DXY 來源選定） |
| **P4** ScanContext 擴充＋兩個新 condition（整合階段） | `chip_provider.py` 的 `ScanContext`（`@dataclass`）新增四欄位，逐日 append 邏輯仿 `revenue_yoy` 寫法；**`macro_flags` 需在 `strategies/scanner.py` 的 `for symbol in all_scan_symbols:` 迴圈之前算一次、注入每次 `get_bars()` 呼叫**（不能塞進逐日迴圈，這是滿足 AC-P4-06「全市場一次」的關鍵，文件沒點名具體檔案/行號，已在此補上）；`conditions_sentiment.py`／`conditions_macro.py`＋`strategies/__init__.py` 補 import；「只掛閘門型 condition 需警示」的檢核（建議併入 `strategies/config_loader.py` 既有 YAML schema 驗證） | P1、P2、P3 全部 | AC-P4-05（對照既有 filter 行為差異）；AC-P4-06（斷言計算次數==掃描次數） | 中，程式量不大但正確性要求高（look-ahead bias、單次計算共用） |
| **P5** 通知整合 | `notify/events.py` 的 `ALERT_SIGNAL` payload 加 `top_news`/`sentiment_5d`（確認不影響 `_key_alert_signal()` 冪等鍵）；三通道樣板加選擇性區塊 | P4 | 手動觸發一次帶新聞資料的訊號，核對三通道渲染與去重鍵不變 | 小 |
| **P6** 前端 | `service/newsApi.js`／`macroApi.js`（`import { apiClient } from '@/service/stockApi'`）；個股新聞卡片仿 `StockAlertsPanel.vue`＋`AlertTimeline.vue`（情緒 Tag 沿用 `marketColors.js` 紅漲綠跌，**不看 `useMarket.js` 死欄位 `up_down_convention`**）；總經儀表板區塊加在 **`HeatmapDashboard.vue`**（見 §15.1-1），Sparkline 抄 `HeatmapDashboard.vue` 既有 `getSparklineOption()` 改中性單色 | P1、P3（不依賴 P4/P5，可先用假資料開發 UI） | AC-P4-08/09，建議用 `/run` 實際跑起來截圖驗證（純視覺回歸容易漏審） | 中 |
| **P7** 排程串接與資料保留清理 | `scheduler.py` 新增 §9 六個排程項（新聞抓取／情緒評分鏈式觸發／PTT／FRED-DXY／清理）；保留政策比照既有 `purge_old_logs` | P1～P4 全部 | 先手動觸發 `POST /news/trigger` 跑順鏈式流程，再掛 cron（排程本身難重現問題，不建議用排程除錯） | 小 |

**建議執行順序**：Spike-0（越早做越好，與 P0 並行）→ P0 → P1 與 P3 並行 → P2 → P4（收斂整合點，必須排在 P1/P2/P3 之後）→ P5 → P6（可與 P4/P5 部分並行，先用假資料開發 UI 骨架）→ P7（收尾）。

### 15.3 需要人為決策、無法單靠寫程式解決的風險點

1. **§4.2 中文情緒模型選型驗證缺一致率門檻數字**：文件已承認 FinBERT 不適用，但沒給「一致率要達到多少才算通過」的具體門檻——這是需要使用者/架構師在 Spike-0 開工前先拍板的數字（例如「與 LLM 標註結果一致率 ≥ 80%」），否則 Spike-0 沒有明確的 Definition of Done，容易陷入無限調參，且此結果會回頭改變 P2 範圍與部署形態（常駐 API 內 vs 獨立排程批次程序）。
2. **PTT／Cnyes／Yahoo 爬蟲的 ToS／穩定度風險**：§3.1 僅寫「須遵守目標站點的存取條款」，未給明確驗收標準。PTT 網頁版有 18 歲同意頁與偶發改版，屬營運風險；Cnyes／Yahoo 若無官方開放條款，長期存取有 IP 封鎖或法遵疑慮——這是業務層級的風險接受決策，不是工程師能單方面決定的事，建議在 P1 動工前由你明確拍板「接受此風險上線」或「先確認/改用官方付費 API」。工程上能做的只有把三個來源做成互相獨立、單一來源失效不影響其他（`news_sources.yaml` 的 `enabled` 開關已是這個設計的一部分）。
3. **三層去重（尤其 L3 SimHash）對中文標題的實際效果未經實測**：文件自己承認「trigram 對中文標題的鑑別度需先實測」，`dedup_hamming_max: 3` 只是預設值。建議 P1 上線後留一週觀察期，用真實跨來源轉載樣本人工抽查「有沒有漏判」與「有沒有誤判」，再回頭調整門檻，不能假設一次寫對。

### 15.4 文件未講清楚、留給實作者自行決定的落差點

- **`macro_flags` 的計算/注入位置未指名檔案**：已在 §15.2 P4 具體標出是 `strategies/scanner.py` 的 `for symbol in all_scan_symbols:` 迴圈之前，文件只講了原則（單次掃描共用一份），沒點名這個位置。
- **L3 SimHash 工具函式該放哪個檔案未指定**：建議獨立成 `services/news_dedup.py`（而非併入 `news_fetcher.py`），因為去重邏輯未來可能被評分 job 複用來排除 `is_duplicate` 列，放進抓取器檔案會造成不必要耦合。
- **「策略只掛閘門型 condition 需在啟動日誌警示」的實作位置未指定**（§6.4）：建議併入 `strategies/config_loader.py` 既有 YAML schema 驗證批次，不另立檢查函式。
- **DXY 的具體資料來源未指定**（§5.1）：只寫「串接美元指數（DXY）」，沒說是哪個 FRED series ID 或替代來源，需在 P3 開工前先確認，否則 `macro_fetcher.py` 無法真的動手寫。
- **L2 閘門條件二「追蹤清單／持股庫存」對應哪張表未指名**（§4.1）：推測是 `watchlist`／`portfolio` 相關表，但需在 P2 開工前明確指名具體查詢來源，避免評分 job 各自猜測出兩套不一致的清單定義。

### 15.5 Critical Files（供 P0 開工時快速定位）

`backend/services/chip_provider.py`（ScanContext）、`backend/strategies/scanner.py`（掃描迴圈與 macro_flags 注入點）、`backend/strategies/__init__.py`（condition 模組註冊）、`backend/services/news_fetcher.py`（待新增）、`backend/strategy_config/news_sources.yaml`（待新增）、`backend/db/migration/V23__Create_news_and_macro_tables.sql`（待新增）、`backend/industry_chain/extractor.py`（LLM 配額/成本記錄範本）、`frontend/src/views/HeatmapDashboard.vue`（總經儀表板實際掛載處）。
