# Phase 2：籌碼面與基本面量化擴充 — 實作計畫

**上游文件**：[Phase2-籌碼面與基本面量化擴充.md](Phase2-籌碼面與基本面量化擴充.md)（v2.1，需求規格，已依 2026-08-30 上線的程式碼核對為完工狀態）
**性質**：本文件是需求文件 v2.0（上游文件現已更新為 v2.1，內容為完工核對，需求本身未變）的實作落地計畫，
記錄開工前的資料現況確認結果與具體改動點，供之後回顧「當初為什麼這樣做」。

## Context

`Phase2-籌碼面與基本面量化擴充.md`（v2.0）要求把已經每天在寫入 Postgres 的
`daily_valuation`（PE／PB／殖利率／市值／市值排名）與 `monthly_revenue`（YoY／MoM）資料，貫通到個股頁
KPI 卡、新增的估值／營收趨勢圖分頁、以及 AI 診股報告的量化摘要——目前這些資料進得去資料庫，卻沒有任何
使用者看得到的地方讀得到（個股頁四張估值卡恆為「—」，點下去還會跳回 K 線圖）。

開工前依文件 §9 Q-1 的要求，已對 Postgres 現況做了抽樣查詢確認：

- `pe_ratio`／`pb_ratio`／`dividend_yield`：最新交易日 1081 檔中約 870 檔有值（≈80%），符合文件預期。
- `market_cap`／`mcap_rank`：**目前 0% 有值**——`services/valuation_fetcher.py` 明確寫死 `None`
  （註解：「市值後續可由行情價格 × 股本計算或來源補充」），這條爬蟲從未真正算過市值。
- 已與使用者確認：**仍照文件規格把管線整條接上**（FR-1 市值卡、FR-5 市值排名），只是接上後因資料源頭
  是 0% 覆蓋率、兩張卡目前會顯示「—」——這符合 ADR-P2-02「缺值即缺席」的既有約定，不是壞掉，只是在等
  未來有人補市值爬蟲。AC-3／AC-15 因此目前無法用真實數字驗證，會誠實記錄，並建議把這條資料缺口登記到
  《選股功能及爬蟲》。

另外開工前確認也發現：`scripts/verify_indicators.py`／`verify_kd.py` 預期 `get_stock_chart_payload()`
回傳 `macd`／`rsi`／`bollinger`／`atr`／`kd`／`moving_averages` 欄位，但當時線上這個函式**並不會**產生
這些欄位（已用真實 API 呼叫確認）。

> **後續追查結果（2026-08-29，已修復）**：這不是「文件超前於實作」，而是一次**程式碼回歸**——
> commit `27a7f96`「左邊menu功能tree調整」把 34 個檔案連同大量後端核心一起換成舊版，Phase 1 的
> 指標組裝（`_build_kd_payload()`／`_build_recursive_indicator_payloads()`／
> `_build_bollinger_and_levels_payload()`）整段被刪除。完整落差清單與修復內容見
> [回歸修復紀錄.md](回歸修復紀錄.md)。修復後 `scripts/verify_indicators.py` 已可完整通過
> （含 AC-P1-4／5／6 真實標的檢查），AI 量化摘要也恢復 `ma`／`kd`／`macd`／`rsi`／`bollinger`／
> `atr`／`range` 七個區塊。

## 整體策略

依文件 §1.2 既有元件表與 §4 資料流圖，資料組裝的核心落點是 `services/stock_service.py` 的
`get_stock_chart_payload()`——它目前完全沒有估值／營收欄位。採用的組裝方式：

**在聚合之前，把估值／營收欄位併入每日原始記錄**，讓既有的 `aggregate_stock_data()`（日/週/月聚合）與
`latest_summary` 組裝自動帶到這些欄位，不必新開一條資料流、也不必為週期聚合另寫邏輯。這比直接呼叫
`ChipDataProvider.get_bars()`（它只做日線，無法對齊週/月聚合後的日期軸）更適合這個消費端。

`ChipDataProvider`（`services/chip_provider.py`，供 `/compare` 與策略引擎使用）與 `stock_service.py` 走
兩條各自獨立的組裝路徑，兩者都只讀 `market_repository.preload_market_data()`，不新增任何 SQL
（ADR-P2-01）——這個「同一份底層查詢、兩處各自組裝」的重複型態在現有程式碼裡本來就存在（`/compare` 用
`chip_provider`，個股頁用 `stock_service`），本次不改變這個既有分工。

## 後端變更

### 1. `services/stock_service.py`（FR-1／FR-2／FR-5 核心）

新增一個私有 helper（例如 `_attach_valuation_and_revenue(raw_data, stock_id, months)`），在
`get_stock_chart_payload()` 呼叫 `aggregate_stock_data()` 之前執行，僅當 `market == "tw" and kind ==
"stock"` 時才跑（美股與指數不受影響）：

- **估值**：僅當 `get_data_source() == "postgres"` 才查（ADR-P2-02，JSON 模式明確降級為缺席）。
  呼叫 `MarketRepository().preload_market_data([stock_id], cutoff_date, today, market="tw")`（沿用
  `fundamentals.py::compare_stocks()` 已驗證的呼叫方式，`cutoff_date` 用檔案內既有的 `months_ago(months)`
  helper 算），包在 try/except 裡，任何失敗都退回空字典（不得讓 K 線／籌碼等既有區塊跟著壞掉）。
  `market_cap` 在此處就近做元→億元換算（ADR-P2-06，除以 1e8，換算放後端）。
- **月營收**：優先用同一次 `preload_market_data()` 回傳的 `revenue` 區塊；查無資料（Postgres 不可用、
  或該檔不在批次結果中）時退回 `services/mops_fetcher.load_stock_revenue()` 讀逐檔 JSON——完全比照
  `chip_provider.py` 第 153-159 行已有的雙來源判斷式，不另創新邏輯。用
  `indicators/fundamental.py::latest_visible_month()` 逐日計算「當天已公開的最新月份」（ADR-P2-03，
  不得直接取當月或最新一筆），只在游標到達的日期 ≥ 該月可見日時才把 `yoy_percent`／`mom_percent` 寫入。
- 把算出的 `pe_ratio`／`pb_ratio`／`dividend_yield`／`market_cap`／`mcap_rank`／`revenue_yoy`／
  `revenue_mom`／`revenue_visible_month` 直接寫回 `raw_data[date_str]`（原地補欄位；`load_stock_json()`
  每次都是重新讀檔產生新 dict，Postgres 路徑也是每次新建 dict，原地寫入不會污染其他呼叫端或快取）。

**`aggregate_stock_data()` 的必要修改**：新增一組欄位分類（例如 `NULLABLE_END_FIELDS`），涵蓋上述
8 個新欄位，套用「取群組內最後一筆非 None 值，若群組內全缺則整欄位回傳 `None`」的邏輯——**不能沿用既有
`END_FIELDS` 的寫法**，因為那組欄位缺值時預設回傳 `0`（`margin_balance`/`short_balance` 語意上 0 是合法
值），而估值／營收欄位的 0 已在資料庫層被定義為「不存在」（NULL），照抄 `END_FIELDS` 會讓某週/月完全缺
估值資料時卡片顯示「0」而非「—」，直接違反 CLAUDE.md「不得顯示 0 代替缺值」鐵則。`period="daily"` 分支
本來就是逐筆直接帶過，不需要另外處理，新欄位補進 `raw_data` 後會自動出現在每筆 daily 記錄裡。

**`get_stock_chart_payload()` 最終組裝**：
- `latest_summary` 新增這 8 個鍵（直接讀 `latest.get(...)`，缺值時保持 `None`／不塞入，前端
  `formatMetricValue()` 遇 `undefined`/`null` 已經會顯示「—」，不需要額外處理）。
- 新增兩個頂層區塊，供 FR-3 圖表分頁使用，形狀比照既有 `institutional`/`margin`：
  `payload["valuation"] = {"pe_ratio": [...], "pb_ratio": [...], "dividend_yield": [...]}`、
  `payload["revenue"] = {"yoy": [...], "mom": [...], "visible_month": [...]}`（各為對齊 `dates` 的陣列，
  缺值為 `None`，前端 ECharts `connectNulls: false` 會自動斷線留白，符合 ADR-SP-08／FR-3 缺值規則）。

### 2. `services/chip_provider.py`（FR-5，`ScanContext.valuation`）

`val_series` dict 新增 `"market_cap"` 與 `"mcap_rank"` 兩個 key，從 `val_lookup.get(d_str, {})` 取值填入
（第 172-178 行附近，`preload_market_data()` 早就查回這兩欄，只是組裝時被丟棄，ADR-P2-04）。
`market_cap` 在此處同樣要做元→億元換算，維持與 `stock_service.py` 的單位一致。這條路徑影響
`/compare` 與任何讀 `ctx.valuation` 的策略條件；兩者現有程式碼一律用 `.get(key, ...)` 取值，新增 key 對
既有讀取安全（已確認 `strategies/conditions_pick.py`、`api/v1/endpoints/fundamentals.py` 皆是如此）。

### 3. `markets/tw.py`（FR-1／FR-2／FR-5）

- `market_cap` 這個既有 `Metric` 的 `unit` 由 `"元"` 改為 `"億元"`。
- 新增三個 `Metric`：`revenue_yoy`（`label="營收年增率"`, `unit="%"`, `frequency="monthly"`,
  `tile=True`, `panel="fundamental"`）、`revenue_mom`（同上，`label="營收月增率"`）、`mcap_rank`
  （`label="市值排名"`, `unit="名"`, `frequency="daily"`, `tile=True`, `panel="valuation"`）。
- `meta.panels` 由 `["institutional", "margin", "valuation", "table"]` 追加 `"fundamental"`。

### 4. `ai/config.py`（FR-4，比照 ADR-AI-12 既有的 `_env_int` 慣例）

新增兩個 getter：`get_recent_alerts_lookback_days()`（env `AI_RECENT_ALERTS_DAYS`，預設 10）、
`get_recent_alerts_limit()`（env `AI_RECENT_ALERTS_LIMIT`，預設 5）。

### 5. `ai/summary.py`（FR-4）

`build_quant_summary()` 內、`market == "tw"` 的既有籌碼區塊旁新增三個區塊（`_clean()`／`_round()`／
「整個鍵省略」慣例照抄既有寫法）：
- `summary["valuation"]`：`pe_ratio`／`pb_ratio`／`dividend_yield`，來源 `latest.get(...)`（就是
  FR-1 補進 `latest_summary` 的欄位，不重新查詢——符合 ADR-P2-05「只讀 `get_stock_chart_payload()`」）。
- `summary["revenue"]`：`yoy_percent`／`mom_percent`／`visible_month`，分別來自
  `latest.get("revenue_yoy")`／`latest.get("revenue_mom")`／`latest.get("revenue_visible_month")`。
- `summary["market_position"]`：`market_cap`／`mcap_rank`，來自 `latest.get(...)`。

`market == "tw"` 判斷式外（TW／US 皆可）新增 `recent_alerts`（選用區塊）：呼叫
`repositories.alert_repository.query_alerts(market=market, symbol=symbol, days=get_recent_alerts_lookback_days())`
（同步函式可直接呼叫），取前 `get_recent_alerts_limit()` 筆（該函式已依日期新到舊排序），只取
`strategy_id`／`direction`／`trade_date`／`signal_strength` 四個欄位（不送 `details`，避免洩漏策略門檻值
——符合既有「Prompt 不得出現硬編碼門檻」原則）。整段包 try/except，失敗只記警告、視為無訊號，不中止整份
報告組裝。

### 6. `ai/prompt.py`（FR-4）

- `_LABELS` 新增：`pe_ratio`／`pb_ratio`／`dividend_yield`／`yoy_percent`／`mom_percent`／
  `market_cap`／`mcap_rank` 的中文標籤。
- `build_user_prompt()` 依序新增 `valuation`／`revenue`／`market_position` 三個 `_format_block()` 呼叫
  （缺值區塊自動因為字典為空被略過，不會出現空標題），以及一段 `recent_alerts` 的客製化格式化（是
  list of dict，不能直接套 `_format_block()`；逐筆列出日期／策略／方向／強度）。
- `SYSTEM_PROMPT` 研判框架新增兩點（基本面與估值檢核、市場資金定位），輸出規範追加一條「近期策略訊號
  僅供佐證，不得複述訊號當結論」。
- `ai/config.py::get_prompt_version()` 預設值由 `"v4"` 比照既有慣例升級為 `"v5"`，並更新其註解說明新增
  的研判框架點。**AI 對外契約（七個結構化輸出欄位）不變**（ADR-P2-05／AC-14），這只是 metadata 版本號。

### 7. `docs/16.AI技術分析/AI技術分析規劃.md`

依既有版本紀錄慣例，補一列 v3.5，說明 Phase 2 已完成基本面／估值貫通。

## 前端變更

### 8. `frontend/src/views/StockDashboard.vue`

- `isSignedMetric()`（560-564 行附近）加入 `metric.key.includes('revenue_yoy') ||
  metric.key.includes('revenue_mom')` 判斷，讓這兩個指標顯示正負號並套用紅漲綠跌色（FR-2 明確要求）。
- `revenue_yoy` 卡片副標顯示 `latest_summary.revenue_visible_month`（比照既有 `institutional_total`
  副標「外資 +1,234」的寫法，template 209-214 行附近再加一個 `v-else-if`）。
- `setActiveChart()`（476-487 行）補上對照：`pe_ratio`／`pb_ratio`／`dividend_yield`／`market_cap`／
  `mcap_rank` → `widgetId = 'valuation'`；`revenue_yoy`／`revenue_mom` → `widgetId = 'revenue'`
  （market_cap／mcap_rank 目前沒有專屬趨勢圖，導去估值分頁至少不會落回 K 線圖重現 G-2）。
- KPI 卡片矩陣本身（`v-for="metric in chartData.metrics"`）不需改動——新指標會自動渲染、自動帶
  `!m-0`，這正是 G-1 附帶說明強調的「投入小、可見度高」之處，也是 CLAUDE.md 硬規則 2 已經處理好的地方。

### 9. `frontend/src/components/StockCharts.vue` ＋ `frontend/src/views/ChartDetailView.vue`

兩處各自維護一份圖表定義是既有慣例（元件內註解已言明），本次一併補齊：

- `StockCharts.vue` 的 `widgetDefinitions`（154 行起）新增
  `{ id: 'valuation', title: '估值走勢（PE／PB／殖利率）', icon: 'pi-chart-line', route: 'valuation', panel: 'valuation' }`
  與 `{ id: 'revenue', title: '月營收 YoY／MoM', icon: 'pi-percentage', route: 'revenue', panel: 'fundamental' }`；
  `getOption(id)`（284 行起）新增對應 case；新增 `valuationOption`／`revenueOption` 兩個 computed。
  - 估值圖：PE／PB／殖利率三線共圖、雙 Y 軸（PE/PB 一軸「倍」，殖利率一軸「%」），
    `connectNulls: false`（缺值斷線留白，ADR-SP-08／FR-3 缺值規則）。
  - 營收圖：YoY／MoM 雙線，`markLine` 在 `yAxis: 0` 處畫一條虛線標示零軸（FR-3「零軸需明顯標示」）。
    不做逐點紅綠著色——文件只要求「零軸標示」，紅漲綠跌鐵則本次僅套用在既有的 KPI 卡數值與方向指標，
    不強加到這條可正可負來回擺動的趨勢線上（同一條線紅綠交錯不易讀，也非文件要求）。
- `ChartDetailView.vue` 的 `stockChartTabs`（218-225 行）比照新增兩個分頁項目，`currentChartOption`
  的 `switch`（559 行起）新增對應 `case 'valuation'` / `case 'revenue'`，重用同一份 option 邏輯（各自
  獨立一份程式碼是現有慣例，不抽共用元件）。

### 10. `frontend/src/utils/chartExplanations.js`

新增 `valuation` 與 `revenue` 兩個說明區塊（`definition`／`purpose`／`howToRead` 三段式，比照既有其他
圖表的寫法與白話程度）。

## 驗收（對照文件 §7 AC-1～AC-16）

- AC-1／AC-2／AC-4／AC-5／AC-6／AC-7／AC-8／AC-9／AC-10／AC-11／AC-12／AC-13／AC-14：用現有 Postgres
  資料（DATA_SOURCE=postgres）實測台積電等 3 檔台股 + 1 檔美股，比對 KPI 卡數值、圖表斷線、AI 報告
  `quant_summary` 內容與既有 7 個結構化輸出欄位是否不變。
- AC-3／AC-15：**目前資料源頭 0% 覆蓋，無法用真實數字驗證**——會改為驗證「代碼路徑正確、缺值時顯示
  「—」而非 0、K 線等既有區塊不受影響」，並在完成後的報告中明確記錄這個資料缺口，建議另案登記到
  《選股功能及爬蟲》觸發市值爬蟲的後續工作。
- AC-16（既有回歸）：`fundamental_revenue_decline`、三個籌碼型態警示、六個均線策略、KD 相關策略跑一次
  掃描，確認觸發結果與改動前一致（`chip_provider.py` 的改動只新增 dict key，不影響既有欄位數值）。
- 手動檢查 CLAUDE.md 兩條硬規則：切換到估值／營收分頁不跳回頁首；新增 KPI 卡與同列卡片等高。
- 額外檢查 DATA_SOURCE=json 模式（目前 `.env` 的預設值）：確認估值卡優雅降級為「—」，K 線／均線／KD／
  三大法人／融資融券完全正常，不因新增邏輯報錯（ADR-P2-02，這是本地預設環境會天天碰到的路徑，必測）。

## 事後複查（2026-09-01）

Phase 2 已於 2026-08-30 完成並上線（commit `8d56dd8`）。本次獨立重新核對本文件記錄的各項改動與現行程式碼
是否仍一致，結果如下：

- **FR-1／FR-2／FR-3／FR-4／FR-5 的後端與前端改動**：逐項核對 `stock_service.py`／`markets/tw.py`／
  `chip_provider.py`／`ai/summary.py`／`ai/prompt.py`／`ai/config.py`／`StockDashboard.vue`／
  `StockCharts.vue`／`ChartDetailView.vue`／`chartExplanations.js`，內容與本文件記錄的改動點**一致**，
  未發現落差（完整比對表見上游文件新增的 §0.2）。
- **`market_cap`／`mcap_rank` 0% 覆蓋率**（本文件 Context 一節記錄的開工前現況）：重新讀取
  `services/valuation_fetcher.py` 確認 `fetch_twse_valuation()`／`fetch_twse_valuation_snapshot()`
  **仍然**把這兩欄寫死為 `None`，程式碼邏輯與本文件記錄的開工前狀態相同、未見任何後續補接市值來源的改動；
  獨立交叉比對 [AI技術分析規劃.md](AI技術分析規劃.md) v3.6 版本紀錄（2026-08-29）也記著同一件事，三份文件
  在這一點上互相一致。**本次無法連線真實 Postgres，因此無法重新驗證「目前實際覆蓋率是否仍為 0%」這個數字
  本身**——只確認了「造成 0% 的程式碼路徑沒有被改過」，兩者不可混為一談。AC-3／AC-15 的驗收狀態維持本文件
  原記錄不變。
- **FR-3 的 `StockCharts.vue`／`ChartDetailView.vue` 改動說明**（本文件「前端變更」第 9 節）：核對後確認本
  文件此處描述（`widgetDefinitions`／`getOption()`／`stockChartTabs`／`currentChartOption` 的 switch-case
  機制）**準確**；倒是上游規格文件 FR-3 原句「`chart-data` 支援 `chartType=valuation｜revenue`」對後端機制
  的描述不夠精確（該端點實際沒有 `chartType` 查詢參數，是固定回傳完整 payload 由前端選擇渲染），已在上游
  文件 §0.2 一併修正，本文件的描述不受影響、無需修改。
