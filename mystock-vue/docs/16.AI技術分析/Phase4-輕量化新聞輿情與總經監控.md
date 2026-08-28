Phase 4: 輕量化新聞輿情與總經監控 (Semantic Assist)
   │ (Cnyes/PTT/FRED 爬蟲 + LLM 情緒評分 + 大盤總經濾網)

# Phase 4：輕量化新聞輿情與總經監控（語義輔助・第四階段）功能需求文件

## 核心目標

引進「消息面」與「總體經濟面」作為技術／籌碼／基本面之外的第四道濾網：對個股新聞與社群討論做輕量化 NLP／LLM 情緒量化，並以大盤與總經環境作為策略引擎的進場總開關，為既有選股與風控邏輯提供輔助確認層，不取代任何既有量化訊號。

## 交付內容（總覽）

- 串接鉅亨網（Cnyes）個股新聞 API、Yahoo 股市重大訊息與 PTT Stock 板討論度，落地存入 `stock_news` / `stock_discussion_buzz`。
- 串接 FRED 總經指標與美元指數（DXY），落地存入 `macro_indicators`；大盤位階（20MA／60MA）沿用既有 `services/index_service.py` 運算，不重算。
- 利用輕量化 LLM 或 FinBERT 對新聞標題做結構化情緒評分（Bullish／Bearish／Neutral），並彙整成個股 5 日情緒動能指標。
- 於 `strategy_config/strategies.yaml` 新增 `sentiment_filter`／`macro_filter` 兩種 condition 類型，串進既有策略引擎與通知平台。

## 範圍界定：與既有模組的關係

新增功能前先盤點會用到、以及會被取代的既有模組，避免重工：

- **大盤位階不重算**：加權指數／S&P 500 的 20MA、60MA 位階與漲跌幅，`GET /api/v1/indices/overview`（`services/index_service.py`）已可取得每日收盤與均線基礎資料，總經過濾模組只需在既有指數資料上疊加「是否站上 20MA」的判斷，不重建一套指數抓取管線。
- **匯率不重建**：USD/JPY/CNY 兌台幣已有 `services/exchange_rate_fetcher.py` + `GET /api/v1/exchange-rates/latest`。本階段只新增既有管線沒有的美元指數（DXY）與 FRED 系列總經數據（利率政策、非農就業、CPI、美國 10 年期公債殖利率）。
- **LLM 呼叫另立配額，不共用既有 AI 額度**：`ai/providers.py` 的 `PROVIDER_REGISTRY`（Claude／Gemini）抽象與 `ai/guard.py` 的 `AI_DAILY_QUOTA` 是為「每檔個股每交易日一份技術分析報告」設計的成本模型；新聞情緒評分是「每日數十~數百則標題的批次分類」，呼叫頻率與單價完全不同量級。可沿用 provider 抽象呼叫 LLM，但必須設計獨立的每日配額與成本紀錄，不可共用 `AI_DAILY_QUOTA` 計數器，避免把技術分析報告額度排擠掉。優先評估 FinBERT 等本地輕量模型作為預設，LLM 僅作為 fallback 或標題語意較模糊時的加強判斷。
- **condition 與 filter 是兩種不同機制，不可混用**：`strategies/filters.py` 明文規定濾網（`volume_confirm`／`candlestick_confirm`）只做加分（計入 `signal_strength`），核心訊號一定會產生、絕不被濾網擋下。而「情緒分數未達門檻」「大盤空頭排列時限制進場」屬於**會擋掉訊號成立與否**的判斷，因此必須實作成新的 **condition 類型**（`sentiment_filter`、`macro_filter`），比照 `conditions_tech.py`／`conditions_chip.py`／`conditions_fund.py` 的慣例各自新增 `conditions_sentiment.py`／`conditions_macro.py`，簽章維持 `(ctx, idx, params) -> list[dict] | None`，並在 `strategies/__init__.py` 補上匯入以觸發 `@condition` 自動註冊。命名雖沿用原始構想中的 `sentiment_filter`／`macro_filter`，語意上屬於 condition，非 `filters` 模組的 filter。
- **通知直接掛既有平台，不建新推播管線**：Slack／Telegram／Email 三個通道與樣板機制（`notify/`）已完成（見 `db/migration/V13__Add_slack_channel.sql` 與 `notify/templates/alert_signal.*.j2`）。情緒／總經訊號比照既有 `alert_signal`／`alert_digest` 事件掛上 `notify/dispatcher.py`，不另建推播管道。
- **市場範圍**：新聞、情緒評分、PTT 討論度資料來源（鉅亨網、Yahoo 股市、PTT）皆為台股專屬內容，本階段**僅支援 TW**（比照 `conditions_chip.py`／`conditions_fund.py` 以 `ctx.market == "tw"` 把關的慣例）；總經環境過濾器則涵蓋 TW（加權指數）與 US（S&P 500）雙市場，兩邊各自的 20MA 位階透過 `markets/tw.py`／`markets/us.py` 既有的市場抽象取得。
- **資料源不參與 `DATA_SOURCE` 切換**：`stock_news`／`stock_discussion_buzz`／`macro_indicators` 是全新資料類別，OHLCV 既有的「JSON／PostgreSQL 雙軌可切換＋dual-write」機制（`services/stock_service.load_stock_data()`、`db/dual_write.py`）是針對股價資料設計的，本階段資料比照 `ai_analysis_report` 的既有決策（ADR-AI-14：不受 `DATA_SOURCE` 影響），**直接以 PostgreSQL 為唯一儲存**，JSON 僅作為爬蟲的中繼緩衝檔，不提供 JSON 模式的正式讀取路徑。此為刻意的範圍限縮，之後若要支援 JSON-only 部署另行評估。

## 一、財經新聞輕量化資料管線 (News Pipeline)

- **鉅亨網（Anue Cnyes）API 爬蟲模組**：實作個股與類股新聞爬蟲（端點：`https://api.cnyes.com/media/api/v1/newslist/category/tw_stock_news`），封裝於 `services/news_fetcher.py`，比照 `services/fetcher.py` 的 `fetch_status` 單例與節流設計（隨機延遲，避免高頻打 API 被封鎖）。
- **輕量化欄位過濾**：僅擷取 `title`、`news_url`、`published_at`、`symbol` 與 `industry`，避開肥大內文與 HTML 廣告雜訊；不落地全文，降低儲存與後續 LLM 輸入成本。
- **兩段式 ELT 儲存與去重入庫**：第一階段於 `data/raw/news/` 落地原始 JSON 緩衝檔（例如 `1101_20260820_news.json`），比照 Phase 1／Phase 2 既有的兩段式落地慣例；第二階段寫入 PostgreSQL `stock_news` 資料表，以 `(symbol, news_url)` 唯一鍵搭配 `ON CONFLICT DO NOTHING` 避免重複資料堆積。
- **Yahoo 股市重大訊息擴充串接**：封裝 Yahoo 股市即時重大訊息與焦點新聞，補足冷門中小型股在鉅亨網覆蓋率不足的缺口，寫入同一張 `stock_news`（以 `source` 欄位區分來源）。
- **爬蟲節流與條款遵循**：新聞與 PTT 來源皆非官方資料，須留意目標網站的存取條款與頻率限制，沿用 Phase 1 `TWSEProvider` 的節流設計原則（隨機延遲、失敗重試上限），不可高頻併發爬取。

## 二、NLP / LLM 輿情多空情緒量化引擎 (Sentiment Analysis Engine)

- **新聞標題情緒評分（Sentiment Scoring）**：對每日新聞標題做結構化情緒分析（本地 FinBERT 優先，LLM 作 fallback，見前述配額說明），輸出 `sentiment_score`（`-1.0` 至 `+1.0`）與 `sentiment_label`（`BULLISH` 利多 ／`BEARISH` 利空／`NEUTRAL` 中性），寫回 `stock_news` 對應列。
- **個股 5 日情緒動能指標（Sentiment Momentum）**：計算個股近 5 日新聞情緒加權平均分與新聞曝光量暴增倍數（Buzz Surge），標記「利多鈍化（股價不漲）」或「利空不跌（籌碼沉澱）」等量價與消息面背離特徵，供 `sentiment_filter` condition 與戰情室 UI 共用同一份計算結果（避免前後端各算一套）。
- **社群散戶熱度監控（PTT Stock 板爬蟲擴充）**：抓取 PTT Stock 板每日熱門討論代碼與發文篇數，計算散戶討論度過熱指標（當討論量進入歷史前 5% 分位數時，作為潛在反轉或短線過熱濾網），落地至 `stock_discussion_buzz`（`symbol`、`trade_date`、`post_count`、`percentile_rank`），兩段式 ELT 落地方式與新聞管線一致。

## 三、總體經濟與大盤環境過濾模組 (Macro & Market Filter)

- **FRED / 官方總經資料管線**：串接美國聯準會 FRED API（利率政策、非農就業、CPI、美國 10 年期公債殖利率），封裝於 `services/macro_fetcher.py`；需在 `backend/.env` 新增 `FRED_API_KEY` 等設定項目。
- **美元指數（DXY）**：與既有 `exchange_rate_fetcher.py`（USD/JPY/CNY 兌台幣）互補，新增美元指數本身的抓取，統一落地至 `macro_indicators`（`indicator_code`、`indicator_date`、`value`、`source`，唯一鍵 `(indicator_code, indicator_date)`）。
- **大盤環境全域鎖（Global Market Filter）**：在既有 `index_service.py` 的加權指數／S&P 500 收盤資料上，計算 20MA、60MA 位階與單日跌幅，實作為 `macro_filter` condition（見上一節「condition 與 filter」的分工說明）：當大盤處於空頭排列或流動性收緊（總經指標同向轉緊）時，令掛載此 condition 的策略當日不成立訊號，等同「限制進場」；是否要支援「降低每筆部位上限」這類非布林值的分級輸出，留待與 `strategies/registry.py` 的 condition 回傳格式（目前為 `list[dict] | None`，非數值分級）對齊後再評估，本階段先落地布林式全域鎖。

## 四、設定檔驅動之訊息與總經策略整合

策略設定檔實際路徑為 `backend/strategy_config/strategies.yaml`（`config/strategies.yaml` 會與既有 `config.py` 模組撞名，專案既有慣例已改放此處，見該檔案開頭註解），擴充範例：

```yaml
# backend/strategy_config/strategies.yaml 擴充範例
strategies:
  - id: "momentum_with_news_confirmation"
    name: "動能突破與利多共振"
    category: "trend_sentiment"
    enabled: true
    markets: ["tw"]  # sentiment_filter 僅支援 TW，同一策略若要跨市場需拆分 condition
    conditions:
      - type: "price_cross"
        target: "close"
        ma_periods: [60]
        directions: ["cross_above"]
      - type: "sentiment_filter"
        min_score: 0.6            # 近 5 日情緒分數需為利多
        max_buzz_percentile: 0.90 # 排除散戶討論極度過熱者
      - type: "macro_filter"
        market_trend: "above_20ma" # 大盤（依 strategy 所屬市場）需在月線之上
    filters:
      - type: "volume_confirm"
        params: { multiple: 1.5 }
```

`sentiment_filter`／`macro_filter` 與既有 `price_cross`／`ma_cross` 等 condition 一樣，只是「讀哪份資料」不同（前者讀 `ctx` 新增的情緒與總經欄位，需在 `services/chip_provider.py` 的 `ScanContext` 補上對應欄位，後者讀既有指數資料），掃描流程、去重（`strategies/cooldown.py`）與訊號寫入（`repositories/alert_repository.py`）皆沿用既有機制，不新建掃描器。

## 五、資料庫與後端 API

- **PostgreSQL 新表**：`stock_news`（新聞列表與情緒評分）、`stock_discussion_buzz`（PTT 討論度）、`macro_indicators`（FRED／DXY 等總經時序）。比照既有 Flyway 慣例新增遷移檔（例如 `V17__Create_stock_news_and_macro_tables.sql`，實際版本號以合併當下 `backend/db/migration/` 最新序號為準，不得覆寫已套用過的 `V*` 檔案）。
- **FastAPI 路由**（回應信封沿用專案慣例 `{"success": bool, "data": ..., "message"?: ..., "error"?: {"code","message"}}`，個股不存在時比照既有端點拋 `SymbolNotFoundException`）：
  - `GET /api/v1/news/{symbol}`：分頁查詢個股近期新聞清單與情緒評分，分頁參數比照 `stocks.py`／`investment_notes.py` 既有慣例採 `page`／`page_size`。
  - `GET /api/v1/macro/summary`：整合既有 `index_service.py` 算出的大盤位階（TW／US）與新增的 `macro_indicators`（利率、CPI、DXY 等）於同一份回應，前端不須分別呼叫兩套 API。
  - 新增端點掛在 `main.py`，比照既有 `api/v1/endpoints/*.py` 一檔一個市場無關的 `APIRouter` 慣例（新檔 `api/v1/endpoints/news.py`、`api/v1/endpoints/macro.py`）。
- **通知整合**：情緒或總經訊號觸發時，複用既有 `notify/dispatcher.py` 與 `alert_signal`／`alert_digest` 樣板（`notify/templates/*.j2`）發送，不另建推播邏輯；如需獨立文案，新增 `sentiment_alert.*.j2` 樣板即可。

## 六、Vue 戰情室可視化

- **個股即時新聞卡片**：列出重點新聞標題、來源與發布時間，以綠／紅 Tag 視覺化標記多空情緒；配色沿用專案既有「紅漲綠跌」慣例（台美股統一採同一套漲跌色，不因市場切換色彩，見專案 CLAUDE.md），情緒標籤色與漲跌色分開設計，避免使用者誤讀成價格漲跌。
- **總經與大盤儀表板**：呈現大盤多空燈號（依 `macro_filter` 的判斷結果）、公債殖利率與匯率波動折線圖，整合進現有 `HomeDashboard.vue` / `HeatmapDashboard.vue` 所在的戰情室頁面群，或視元件複雜度另立 `views/news/` 子路由，沿用既有 `router/index.js` 的 `:market` 參數與 `useMarket()` 慣例。
- 新增卡片／圖表元件遵守專案兩條硬性規則：K 線圖等圖表切換時不可整頁 reload 導致捲動位置歸零，同列 KPI／指標卡片高度必須一致（見專案 CLAUDE.md「Hard rules」章節，新元件套用 grid 版面時比照 `StockDashboard.vue` 現有作法補上 `!m-0`）。

## 七、本階段不包含（Out of Scope）

- 盤中即時串流情緒更新（僅日終批次評分，不做 WebSocket／輪詢式即時推送）。
- 台股以外的新聞來源（Bloomberg、Reuters 等國際財經媒體），US 個股本階段沒有新聞／情緒資料。
- PTT 以外的社群平台（Dcard、Threads、X 等）。
- 情緒與總經訊號的獨立歷史回測框架（勝率驗證留待訊號累積足夠樣本後另立 Phase 評估，做法可比照 Phase 3「跟漲勝率矩陣」的量化方式）。
- 選擇權／期貨市場的總經避險訊號。
- `macro_filter` 的非布林分級輸出（「降低部位上限」的量化分級）；本階段僅落地「限制進場」的布林式全域鎖。
