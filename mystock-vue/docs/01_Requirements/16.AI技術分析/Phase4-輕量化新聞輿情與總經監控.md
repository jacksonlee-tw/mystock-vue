# Phase 4：輕量化新聞輿情與總經監控 需求規格書

```text
Phase 4: 輕量化新聞輿情與總經監控 (Semantic Assist & Macro Monitoring)
   │ (Cnyes/Yahoo/PTT/FRED 爬蟲 + 來源白名單 + 分層情緒評分 + 大盤總經全域鎖)
```

| 項目 | 內容 |
| --- | --- |
| 模組 | 輕量化新聞輿情與總經監控 |
| 對應既有模組 | `strategies/`（新增條件類型）、`services/`（新增新聞與總經管線）、`notify/`（沿用推播）、`db/migration/`（新增資料表） |
| 版本 | v3.0（P5 通知整合已實作，`ALERT_SIGNAL` 附上促成訊號的新聞與情緒分數，見 §0.1） |
| 狀態 | **部分已開發**：P0～P5 已實作並 commit，P1／P2／P3 已對真實本機 Postgres 完整端對端驗證；Spike-0（中文情緒模型選型）已完成並**定案**——LLM 與人工一致率 87.0%，使用者拍板直接採用 LLM、不開發本地模型，`NEWS_SENTIMENT_ENGINE` 預設值已改為 `"llm"`（§15.3-1、ADR-P4-08）。`sentiment_filter`／`macro_filter` 已可透過 `gates:` 欄位真正發揮閘門效果並已在 `momentum_with_news_confirmation` 策略上實際啟用（v2.8／v2.9）；`ALERT_SIGNAL` 推播已附上促成訊號的新聞標題與情緒分數（v3.0，見 §0.1）。**P6～P7（前端、排程）尚未開發**，見 §15.2 現況與計畫。 |

---

## 0. 修訂紀錄與決策（ADR）

### 0.1 v3.0 變更摘要

依 §15.2 的分階段計畫，實作 **P5（通知整合）**：

- `repositories/news_repository.py`：新增 `get_top_news()`——近 N 天內方向性最強（`|sentiment_score|` 最大）的前 3 則非重複已評分新聞，供推播訊息附上標題與來源。
- `strategies/scanner.py`：候選警示新增 `sentiment_5d` 欄位——只有這條策略的 `gates` 真的包含 `sentiment_filter` 時才附上該筆訊號當下的 5 日加權情緒分數，其餘策略一律 `None`（`strategy_has_sentiment_gate` 判斷，一個策略只算一次，不逐筆重算）。
- `notify/intake.py`：`publish_alert_signals()` 的 `ALERT_SIGNAL` payload 新增 `sentiment_5d`／`top_news` 兩個欄位；只有 `sentiment_5d` 非 `None`（代表情緒真的影響了這筆警示是否放行）且為台股時，才呼叫 `_fetch_top_news()` 查一次新聞（不是每筆台股警示都查），失敗一律靜默回傳空陣列（鐵則 R7 的精神延伸）。查詢窗口用日曆天數粗略近似（`_TOP_NEWS_LOOKBACK_DAYS = 7`），不重建交易日曆——展示用途，不是評分計算。
- `notify/events.py`：`TEMPLATE_CONTEXT_SPEC[ALERT_SIGNAL]` 新增這兩個變數說明（供管理介面「變數說明」顯示）；`SAMPLE_PAYLOADS[ALERT_SIGNAL]` 範例改用 `momentum_with_news_confirmation`，讓範本預覽功能能展示新欄位。
- `notify/templates/alert_signal.{email,slack,telegram}.j2`：三份樣板皆加上 `{% if top_news %}` 選擇性區塊（比照既有 `{% if details %}`／`{% if suggested_action %}` 寫法），email 版列出全部標題與來源，slack／telegram 版只顯示第一則＋則數。冪等鍵 `_key_alert_signal`（`notify/events.py`）完全未改動，不受影響。

**驗證**：

- 三份本地 `.j2` 樣板直接渲染測試（`_render_file()`，不經 DB）：含情緒資料時正確顯示新聞區塊；不含時（一般技術面策略）正確完全省略、無殘留空白列；`top_news` 有 2 則以上時「等N則」後綴正確顯示。過程中抓到並修正一個真實排版 bug——slack／telegram 樣板的 `{% endif %}` 緊接在 `{% if top_news|length > 1 %}...{% endif %}` 後面換行，`trim_blocks=True` 會把這個換行吃掉，導致新聞行跟下一行「▸ 查看圖表」黏在一起；補一個 `{{ "" }}` 讓換行改成跟在 `{{ }}` 表達式後面即修正（`trim_blocks` 只對 `{% %}` 區塊標籤生效，不影響 `{{ }}` 運算式標籤）。
- **發現並處理一個真實環境落差**：資料庫裡已有 3 筆 `ALERT_SIGNAL` 範本（email/slack/telegram），內容與修改前的原始 `.j2` 檔案位元組完全相同（`render()` 的三層回退機制第一層優先讀 DB 範本，本地 `.j2` 檔案是第二層備援）——這代表光改 `.j2` 檔案，正式環境不會生效。核對後（email／telegram 兩筆的 `created_at` 精確到毫秒完全相同，判斷是程式化初始化留下的未編輯副本，非管理者手動客製化），與使用者確認後用 `NotifyRepository.upsert_template()` 一併更新這 3 筆 DB 範本內容，使其與新版 `.j2` 檔案一致。
- **真實觸發一次 `publish_alert_signals()`**（用 2330 台積電的真實新聞資料）：確認 `notify_event.payload` 正確帶有 `sentiment_5d`／`top_news`（3 則真實新聞標題與連結）；DB 範本更新前，組出的 `notify_message.body` 沒有新聞區塊（證實了上一點的落差）；DB 範本更新後重新觸發，`notify_message.body` 正確顯示「📰 情緒分數 0.55：〈熱門股〉光罩爆量周漲23.7% 創兩個月來新高（cnyes）等3則」。測試用的事件與訊息事後已從 `notify_event`／`notify_message` 清除，不留測試噪音。
- 重新觸發一次 `scan_market('tw')` 確認未影響既有 24 條策略與 `momentum_with_news_confirmation` 的既有執行路徑（迴歸通過）。

### 0.2 v2.9 變更摘要

依使用者要求「幫我在 strategies.yaml 加一條真的會用到 sentiment_filter／macro_filter 的策略並啟用」：

- `strategy_config/strategies.yaml`：新增並啟用 **`momentum_with_news_confirmation`**（動能突破與利多共振）——`conditions:` 為主觸發 `price_cross`（站上季線 MA60），`gates:` 為
  `sentiment_filter`（`min_score: 0.5`、`max_buzz_percentile: 0.85`，沿用 §6.3 範例的門檻值）與 `macro_filter`（`market_trend: "above_20ma"`），`filters:` 沿用既有 `volume_confirm`
  加分不擋。`markets: ["tw"]`（`sentiment_filter` 僅支援台股，§1.3）。這是本文件第一條真實引用這兩個 condition 的上線策略。
- `strategies/scanner.py`：`_SUGGESTED_ACTION_TEMPLATES` 新增 `("momentum_with_news_confirmation", "bullish")` 建議操作文案，比照既有策略的既有慣例。

**驗證**：

- `load_strategy_config()` 對真實 YAML 檔案載入這條新策略，`conditions`／`gates`／`filters` 三個欄位皆正確解析，且未觸發 §6.4 的任何一條誤用警示（`conditions` 非純閘門型、`gates` 非空且 `conditions` 也非空）。
- 真實觸發一次 `scan_market('tw')`：確認 `needs_sentiment`／`needs_macro` 因這條新策略正確轉為 `True`，`get_macro_flags('tw')` 正確算出 `{"tw_above_20ma": true, "tw_above_60ma": true}`；掃描 1394 檔、本次未產生新警示（抽樣 300 檔確認當下沒有任何個股在最新可用交易日出現「站上季線」的主觸發，屬於盤面現況、非程式問題）。
- **完整端對端合成情境驗證**（用這條策略真實載入的 `gates` 設定，手動構造一組「昨日收在季線下、今日收在季線上」的價格序列讓主觸發真的成立）：確認①情緒與大盤都過關時整筆放行；②情緒不過關（`sentiment_5d = -0.9 < min_score 0.5`）整筆擋掉；③大盤不過關（`tw_above_20ma = False`）整筆擋掉——證明 v2.8 的 AND 閘門機制搭配這條真實策略設定完全如預期運作。

### 0.3 v2.8 變更摘要

依使用者要求「補上 scanner.py 的 AND 機制，讓 P4 真正發揮作用」，解決 v2.7 交付時記錄的
架構限制（§0.4 v2.7 摘要）：

- `strategies/config_loader.py`：`StrategyDef` 新增 `gates: List[dict]` 欄位（YAML 對應
  新的 `gates:` key），語意上屬於 condition（會決定訊號成立與否），跟只加分不擋的
  `filters` 完全不同角色，型別沿用既有 `CONDITION_REGISTRY`，不另立一套註冊表。§6.4
  警示檢核擴充為兩條：①`conditions` 只掛閘門型（沿用 v2.7 既有檢核，補充成「應改放 gates」
  的提示）；②`gates` 有設定但 `conditions` 是空的（新增，這種設定 gates 永遠不會被評估到，
  整條策略形同沒作用）。
- `strategies/scanner.py`：新增 `_evaluate_gates(gates, ctx, idx, symbol) -> bool`——主觸發
  condition 產生候選警示後，在寫入 `raw_candidates` 之前，逐一評估 `strategy.gates` 裡的
  每個型別（借用既有 `CONDITION_REGISTRY`，跟一般 condition 用同一套 `spec.func(ctx, idx,
  params)` 呼叫介面），全部通過（回傳非空）才放行；任一 gate 未通過（含型別未註冊、
  `min_bars`／`requires` 不滿足、評估拋例外）一律 **fail-closed**（視為不通過），不是
  「這個 gate 不適用、略過」。沒有 gates 的策略（現有 24 條）呼叫
  `_evaluate_gates([], ...)` 直接回傳 `True`，行為完全不變。`needs_sentiment`／
  `needs_macro` 判斷也一併擴充為同時掃 `conditions` 與 `gates`（`gates` 欄位是本次新增，
  v2.7 時還不存在這個欄位；新增後若只掃 `conditions` 會漏掉正確用法放在 `gates` 裡的
  情境，一併處理）。警示紀錄新增 `gates_passed` 欄位（記錄哪些型別放行了這筆警示，供稽核追溯，比照既有
  `filters_passed` 的呈現方式）。
- `strategies/conditions_sentiment.py`／`conditions_macro.py`：檔頭與函式 docstring
  更新，移除 v2.7 記錄的「目前技術上等同獨立 condition」限制說明，改為「掛進 `gates:`
  才會真的發揮閘門效果」的正確用法說明。

**驗證**：`_evaluate_gates()` 用 9 組合成情境直接測試（無 gates 預設放行、單一 gate 通過／
不通過、`macro_filter` 兩種 `market_trend` 各自通過／不通過、兩個 gates AND 語意——其中一個
不過則整體不過／兩個都過才整體過、型別未註冊 fail-closed、格式錯誤 fail-closed、
`macro_flags` 為空 fail-closed），全數通過。YAML 解析路徑用暫存設定檔驗證三種情境
（`conditions` 誤掛閘門型、`gates` 設定但 `conditions` 空、正確用法同時有兩者），
兩條警示邏輯與正確用法不觸發警示皆核對正確（暫存檔案，未寫入真實
`strategy_config/strategies.yaml`）。`condition_types_in_use` 掃描邏輯以合成
`StrategyDef` 驗證能正確從 `gates` 撈出型別。**實際重新觸發一次 `scan_market('tw')`**
確認掃描檔數（1394 檔）與既有 24 條策略行為完全不變（迴歸通過，這些策略皆無 `gates`，
`_evaluate_gates([], ...)` 每次都直接放行）。本次未在 `strategy_config/strategies.yaml`
新增任何引用 `sentiment_filter`／`macro_filter` 的真實策略，機制已可用、範例策略留給
使用者之後決定是否要新增。

### 0.4 v2.7 變更摘要

依 §15.2 的分階段計畫，實作 **P4（ScanContext 擴充＋兩個新 condition）**：

- `services/chip_provider.py`：`ScanContext` 新增 `sentiment_5d`／`news_count`／`buzz_percentile`
  （逐日平行序列，比照既有 `revenue_yoy` 寫法：一個 symbol 只查一次歷史，不逐日查詢）與
  `macro_flags`（`Dict[str, bool]`，掃描層級常數，不是逐日序列）四個欄位；`get_bars()`
  新增 `with_sentiment`／`macro_flags` 兩個參數（比照既有 `with_valuation` 的按需計算分工，
  未啟用時三個序列維持空 list、`macro_flags` 維持空 dict，零額外查詢成本）。
- `strategies/scanner.py`：在 `for symbol in all_scan_symbols:` 迴圈**之前**先掃過所有已載入
  策略的 `conditions` 型別，判斷是否有策略掛 `sentiment_filter`／`macro_filter`；只有掛了
  `macro_filter` 才呼叫一次 `get_macro_flags(market)`（AC-P4-06「全市場一次」），結果原封不動
  注入該次掃描的每一次 `get_bars()` 呼叫。
- `strategies/conditions_sentiment.py`、`strategies/conditions_macro.py`（新增）：
  `sentiment_filter`／`macro_filter` 兩個 condition 函式，比照 `conditions_pick.py` 的
  `_eval_*` 私有函式慣例（判斷邏輯與 `@condition` 註冊薄殼分離，方便未來被複合 condition
  重用）；`strategies/__init__.py` 補兩行 import 觸發自我註冊。
- `strategies/config_loader.py`：新增 §6.4「只掛閘門型 condition 需在啟動日誌警示」的檢核，
  併入既有 YAML 載入批次（不另立檢查函式，比照規格書 §15.4 對此落差點的既有建議）。
- `services/macro_analytics.py`：新增 `get_macro_flags(market)`，組裝
  `f"{market}_above_20ma"`／`f"{market}_above_60ma"` 兩個布林旗標（§5.2 提到的「總經指標
  同向轉緊」原文未給出具體判定門檻，刻意不猜一個數字，留給未來有明確規則時再補）。
- `repositories/news_repository.py`：`get_recent_scores()` 加回 `effective_trade_date`
  欄位（原本只給「as of 今天」單一數值用，P4 逐日序列需要知道每筆分數屬於哪一天）；新增
  `get_buzz_percentile_series()`（讀 P1 寫入時已算好的 `percentile_rank`，不重算）。
- `indicators/news_time.py`：新增 `sentiment_5d_series()` 純函式，用 `trading_dates` 自身的
  索引往前數 N 筆當作「近 N 個交易日」視窗（不是額外查交易日曆），對齊 `ScanContext.dates`。

**⚠️ 重要架構限制（開工前已與使用者確認，本次刻意不處理）**：`strategies/scanner.py` 目前
的 condition 評估迴圈**沒有「多個 condition AND 在一起才算一次訊號」的機制**——`conditions:`
清單裡每一項各自獨立評估、各自獨立產生候選警示（OR 關係）。核對現有 24 條策略設定檔，
目前一條都沒有掛超過 1 個 condition，證實這條 AND 語意路徑從未被使用過。這代表 §6.3 YAML
範例裡「`price_cross` 主觸發 + `sentiment_filter`／`macro_filter` 閘門」這種組合，**掛上去
不會真的擋掉主觸發訊號**，只會變成兩個獨立發自己警示的條件類型。真正要發揮「閘門」效果，
需要先擴充 scanner.py（例如新增策略層級的 `gates:` 欄位，或比照 `conditions_pick.py` 的
`stock_pick_resonance` 用 `_eval_*` 私有函式做 AND 組合、另外設計一個複合 condition）——
規劃為未來待辦，不在本次 P4 範圍內。本次依使用者指示**只交付 condition 骨架，不在
`strategy_config/strategies.yaml` 新增任何範例策略**，避免在閘門機制不完整的狀態下讓真實
策略上線、產生誤導性的警示。

**驗證**：直接呼叫 `get_bars(with_sentiment=True, macro_flags=...)` 對真實本機 Postgres 資料
（symbol 2330）驗證——`macro_flags` 正確算出 `{"tw_above_20ma": true, "tw_above_60ma": true}`；
`sentiment_5d`／`news_count`／`buzz_percentile` 皆為 `None`／`0`，**這是正確的 point-in-time
行為**，不是 bug：本機 OHLCV 資料最新僅到 2026-09-10，而真實已評分新聞的 `effective_trade_date`
是 2026-09-14（尚未有對應的價格交易日），兩者本來就不該對得上，證明沒有把未來新聞洩漏回過去
的價格交易日。`with_sentiment=False`（未指定）時三個序列與 `macro_flags` 正確維持空值，
零查詢。另外**實際觸發一次 `scan_market('tw')`**（經使用者同意，寫入 `data/_alerts/`）——
掃描 1394 檔、新增 22 筆真實警示（`rsi_overbought_reversal`／`ma_alignment` 等既有策略），
確認本次改動未影響既有 24 條策略的既有執行路徑（迴歸驗證通過）；§6.4 閘門警示檢核邏輯另以
三組合成情境（只掛閘門／掛閘門+主觸發／只掛主觸發）驗證判斷正確。

### 0.5 v2.6 變更摘要

補測先前因「本機無可連線 Postgres」標記為未實測的 P1／P2／P3 寫入路徑——使用者提供 FRED API 金鑰後，
發現本機其實已有一個這個專案自己 `docker-compose.yml` 建的 `mystock_db` 容器在跑，只是卡在 flyway
V20（比 V23 舊 3 版，V21/V22 是另一並行 session 的季度財報功能）。徵求使用者同意後執行
`docker compose up -d` 補跑 migration 至 V23，取得真正可寫入的 Postgres，逐一觸發 P1/P2/P3 的
真實流程（`run_news_fetch()`／`score_pending_news()`／`run_macro_fetch()`），**過程中發現並修正
3 個先前從未被真實 DB 寫入路徑觸發過、因此從未被抓到的真實 bug**：

1. **`indicators/news_time.py` `simhash()`**：預設產生 64-bit 無號雜湊值，但 `stock_news.simhash`
   欄位是 Postgres 有號 `BIGINT`（範圍 -2⁶³～2⁶³-1）——約一半的雜湊值會落在 2⁶³～2⁶⁴-1 之間，
   寫入時直接觸發 `asyncpg.exceptions.DataError`（實測撞到：`9298988751881561404 (value out
   of int64 range)`）。修正：`bits` 參數預設值由 64 改為 63，雜湊空間仍綽綽有餘，不需要改
   schema 或另外做二補數轉換。
2. **`repositories/news_repository.py` `find_recent_candidates_for_dedup()`**：`(:exclude_id
   IS NULL OR id != :exclude_id)` 這種寫法 asyncpg 無法推斷參數型別，一律拋
   `AmbiguousParameterError`（不限 `exclude_id` 是否為 `None`，帶實際整數值一樣炸——這是
   L3 去重比對唯一會被觸發到的路徑，先前完全沒被驗證過）。修正：改用
   `CAST(:exclude_id AS BIGINT)` 顯式轉型（`:exclude_id::bigint` 簡寫語法在 SQLAlchemy
   `text()` 底下會把整個綁定參數解析壞掉，實測也撞過，改採 `CAST(...)` 語法）。
3. **`services/macro_fetcher.py` `fetch_fred_series()`**：`realtime_start`／`realtime_end`
   未指定時 FRED API 預設兩者皆為「今天」，搭配 `output_type=4`（Initial Release Only）會把
   即時窗口收窄成「只限今天發布的版本」，99% 情況下直接 400（`No vintage dates exist`）；
   而 `realtime_start` 若設成「開站至今」（`1776-07-04`）則對日頻數列（`DGS10`／`DXY`）的
   vintage 數量會超過 FRED JSON 輸出格式上限（2000 筆）也是 400。修正：`realtime_start`
   設成跟 `observation_start` 同一天、`realtime_end` 固定寫死 FRED 官方文件明列的哨兵值
   `"9999-12-31"`（不能填 `date.today()`——本機時區 UTC+8 比 FRED 伺服器時區早換日，會被
   判定「晚於伺服器的今天」而 400）。

**驗證結果**：`run_news_fetch()` 真實抓取 101 則 cnyes 新聞全數寫入（`simhash` 皆落在合法範圍）；
`score_pending_news()` 真實呼叫 Gemini 對 101 則批次評分、4 批全數成功（`ai_llm_execution` 記錄
成本 $0.02）；`run_macro_fetch()` 真實抓取 FRED 5 個指標共 579 筆寫入，`indicator_date`／
`release_date` 分欄正確（例如 CPI 公布落後所屬月份 40～43 天，符合 ADR-P4-05 point-in-time
對齊的設計預期）；`GET /api/v1/macro/indicators`、`GET /api/v1/news/{symbol}/sentiment-summary`、
`GET /api/v1/news/{symbol}` 三個讀取端點皆對這批真實資料回應正確。至此 P1／P2／P3 的 Postgres
寫入路徑不再是「未實測」狀態。

### 0.6 v2.5 變更摘要

依 §15.2 的分階段計畫，實作 **P3（總經／大盤環境管線）**：

- `services/macro_fetcher.py`（新增）：`run_macro_fetch()` 抓取 5 個總經指標——`FEDFUNDS`／
  `NFP`（FRED 官方 series `PAYEMS`）／`CPI`（`CPIAUCSL`）／`US10Y`（`DGS10`）／`DXY`（`DTWEXBGS`，
  見下方 **ADR-P4-09**）。呼叫 FRED API 時指定 `output_type=4`（"Initial Release Only"），
  依 ALFRED 官方文件其 `realtime_start` 即為資料首次公布日，直接寫入 `release_date`，滿足
  ADR-P4-05 的 point-in-time 對齊要求，不需另外呼叫 release-calendar 端點比對。兩段式落地
  （ADR-P4-04）：原始回應先落地 `data/_macro/raw/{indicator_code}/*.json`。單一數列失敗不中止
  整輪（比照 P1 三來源互相獨立的精神）。
- `services/macro_analytics.py`（新增）：`get_market_regime(market)`（§5.2）——大盤指數
  20MA／60MA 位階，直接重用 `services/stock_service.py` 既有聚合函式與
  `indicators/moving_average.py` 的 `sma()`，不重建指數管線、不重寫均線演算法（§1.3「大盤位階
  不重算」）。`macro_flags` 實際掛進 `ScanContext` 屬 P4 範疇，本模組只提供 P4 會呼叫的底層
  查詢函式。
- `api/v1/endpoints/macro.py`（新增）：`POST /trigger`、`GET /status`、`GET /indicators`、
  `GET /indicators/{indicator_code}`、`GET /market-regime/{market}` 五個端點；`/indicators*`
  一律只回傳 `release_date <= 今天` 的最新值（ADR-P4-05）。
- **ADR-P4-09**（新增，§0.12 決策表）：解決規格書 §15.4 原本標注「DXY 的具體資料來源未指定」的
  落差——官方 ICE DXY 期貨指數不是 FRED 免費數列，改用 FRED 自家發布的 Nominal Broad
  U.S. Dollar Index（series `DTWEXBGS`）作為免費替代，對外仍稱 `indicator_code = "DXY"`。
- **驗證**：`fetch_fred_series()` 的 JSON 解析邏輯用符合官方文件格式的合成回應驗證（含 FRED
  缺值標記 `"."`、缺 `value`／`realtime_start` 欄位等邊界案例）——過程中抓到並修正一個真實
  bug：原本用 `obs["value"]` 存取，缺鍵時拋 `KeyError` 未被既有的 `(TypeError, ValueError)`
  捕捉，改用 `obs.get("value")`。`get_market_regime()` 已對本機真實 TWII／GSPC 本地 JSON 資料
  端對端驗證（非合成資料），算出的 20MA/60MA／`above_ma20`/`above_ma60`/漲跌幅數字皆核對正確。
  FastAPI 路由掛載無衝突（`/openapi.json` 核對 5 個 `/macro` 端點皆正確掛載）。**FRED API 本身
  未實測**（本機無 `FRED_API_KEY`，需使用者自行申請—免費即時核發—填入 `.env` 後以
  `POST /macro/trigger` 補測）；Postgres 寫入路徑同樣未實測（`DATA_SOURCE=json`，與 P1／P2
  同一侷限）。

### 0.7 v2.4 變更摘要

依 §15.2 的分階段計畫，實作 **P2（情緒評分引擎）**——ADR-P4-08 定案後範圍已簡化為「全部標題一律走
LLM 批次評分」，不存在文件原訂的 L1 本地模型／L2 閘門分流：

- `services/news_sentiment.py`（新增）：`score_pending_news()` 批次評分主流程，呼叫骨架比照
  `industry_chain/extractor.py`（佔位寫入 pending 執行紀錄 → 呼叫 LLM → 依成功/失敗收尾
  `ai_llm_execution`），配額比照 `NEWS_LLM_DAILY_QUOTA`、`view_id="news_sentiment"`，
  單一批次失敗不中止整輪。系統提示已內建 Spike-0 人工覆核發現的偏誤修正（§15.3-1「設計啟示」：
  中立類別應偏保守判準，不因出現正面數字/關鍵字就直接判多）。
- `services/news_analytics.py`（新增）：`get_sentiment_5d()`／`get_buzz_surge()`（§4.3），組裝
  `NewsRepository` 取回的資料與 `indicators/news_time.py` 的純函式，前後端共用同一份計算結果。
- `indicators/news_time.py`：新增 `recent_trading_dates()`／`weighted_sentiment_avg()`／
  `buzz_surge_ratio()`／`divergence_flag()` 四個純函式（皆為新增，不改動既有函式）。
  `divergence_flag()`（§4.3 利多鈍化／利空不跌）只實作判斷邏輯本身，實際掛進 `ScanContext`
  屬於 P4 範疇（見 §15.2 P4 列），本次不提前綁定 `strategies/scanner.py`。
- `repositories/news_repository.py`：新增 `list_unscored()`／`update_sentiment()`／
  `get_recent_scores()`／`get_news_count_by_dates()`；順手修正 `get_buzz_history()` 一處過期
  docstring（原文提及 `indicators/chip.py` 的 `rolling_percentile()`，P1 實際採用的是
  `indicators/news_time.py` 的 `percentile_rank_of()`，見該函式 docstring 說明兩者互為逆運算）。
- `api/v1/endpoints/news.py`：新增 `POST /sentiment/trigger`、`GET /sentiment/status`、
  `GET /{symbol}/sentiment-summary` 三個端點。
- **本次未實作**（範圍外或依賴 P2 以外階段）：`macro_flags`／`sentiment_5d`／`buzz_surge` 掛進
  `ScanContext` 與 `strategies/conditions_sentiment.py`（屬 P4）、`sentiment_filter` 的
  Prompt／後處理層級的「數字增長但無方向性語境詞則傾向中立」規則化（§15.3-1 提及的設計啟示已
  以系統提示文字形式落實，但未做額外的後處理層規則引擎）。
- **驗證侷限**：本機無可連線 Postgres（`DATA_SOURCE=json`），`score_pending_news()` 與
  `sentiment-summary` 端點的 DB 讀寫路徑本次**未實測**，僅驗證：模組匯入、FastAPI 路由掛載
  無衝突（`/openapi.json` 核對 7 個 `/news` 端點皆正確掛載）、四個純函式的單元斷言（含
  `recent_trading_dates()` 與台股週末排除、`weighted_sentiment_avg()` 加權平均、
  `buzz_surge_ratio()` 除以近 20 交易日均值、`divergence_flag()` 四種情境）皆通過。
  需之後啟動 `docker compose up -d` 後補測 `POST /sentiment/trigger` 與 `sentiment-summary`。

### 0.8 v2.3 變更摘要

Spike-0 定案：使用者依 v2.2 記錄的 87.0% 一致率結果，拍板「直接定案」採用 LLM 作為情緒評分引擎，
不再另外測試／開發本地輕量模型。新增 **ADR-P4-08**（§0.12 決策表）記錄此決定；§4.1 分層評分表下方
補充說明「L1 本地／L2 LLM 升級」的兩層分工不採用，全部標題一律走 LLM 批次評分；§15.3-1 標記為
**已結案**。程式碼同步更新：`config.py` 的 `DEFAULT_NEWS_SENTIMENT_ENGINE` 由 `"local"` 改為
`"llm"`，`.env.example` 的 `NEWS_SENTIMENT_ENGINE` 預設值同步更新（尚未 commit 到 P2 的其餘實作，
本次只調整預設值常數，P2 情緒評分引擎本身仍未開發）。

### 0.9 v2.2 變更摘要

依 §15.2 的分階段計畫，實際完成並 commit（`3a96bda`）**P0（骨架與設定）與 P1（新聞資料管線）**：
`db/migration/V23__Create_news_and_macro_tables.sql`（三張新表）、`strategy_config/news_sources.yaml`、
`services/news_config.py`（熱重載 loader）、`indicators/news_time.py`（point-in-time 對齊／標題正規化／
SHA-256／SimHash／漢明距離／百分位排名）、`repositories/news_repository.py`、`services/news_dedup.py`、
`services/news_fetcher.py`（cnyes 抓取已對真實 API 端到端驗證；PTT Stock 板討論量抓取邏輯已對真實頁面
結構驗證）、`api/v1/endpoints/news.py`（4 個端點，已掛載）、`config.py`／`.env.example` 新增設定項、
`repositories/stock_repository.py` 新增 `list_symbols_sync()`／`get_no_trading_days_sync()`。
**Postgres 寫入路徑本次未實測**（本機無可連線的 Postgres，`DATA_SOURCE=json`），需之後啟動
`docker compose up -d` 後補測 `POST /news/trigger`。

同時完成 **Spike-0 第一輪**（中文情緒模型選型驗證）：抓取 300 則真實 cnyes 新聞標題，人工逐則標註多空／
中立，並用既有 `ai/providers`（Gemini）批次產出 LLM 參考標籤對照，整體一致率 **87.0%**，詳見 §15.3-1。
本次**只驗證了 LLM vs 人工**，本地輕量模型 vs 人工的比對仍待進行。

P2（情緒評分引擎）／P3（總經管線）／P4（策略引擎整合）／P5（通知）／P6（前端）／P7（排程串接）
**維持未開發**，§15.2 WBS 內容不變。

### 0.10 v2.1 變更摘要

新增 §15「現況評估與分階段實作計畫」：逐項核對現行程式碼確認本文件規劃的全部項目（三張新表、`news_fetcher.py`／`macro_fetcher.py`、`news_sources.yaml`、`conditions_sentiment.py`／`conditions_macro.py`、`ScanContext` 新欄位、`api/v1/endpoints/news.py`／`macro.py`、scheduler 排程、notify 樣板、前端元件）**目前零實作**（此結論已於 v2.2 部分推翻，P0／P1 已完成，見 §0.9），並將本文件已定案的技術決策轉譯為可執行的分階段交付計畫（WBS），標出文件本身三處已過期／寫錯的檔案路徑（§15.1）、需要人為先做實驗或拍板的風險點（§15.3），以及文件未講清楚、留給實作者自行決定的落差點（§15.4）。**本次僅新增 §15，不變更 §1～§14 任何 FR／ADR／驗收條件的需求本身。**

### 0.11 v2.0 優化重點

v1.0 僅列出「要做哪些功能」，實作時會撞到三個問題：新聞來源開越多雜訊越大、同一則消息被多家轉載重複計分、LLM 逐則評分的成本無上限。v2.0 針對這三點補上機制，並補齊 v1.0 完全沒有處理的 **Point-in-time 對齊**（新聞與總經數據的「可見時點」與交易日不是同一條時間軸）。

### 0.12 決策紀錄

| 編號 | 決策 | 理由 |
| --- | --- | --- |
| ADR-P4-01 | 新聞／社群來源以 `strategy_config/news_sources.yaml` 白名單驅動，可逐一 `enabled` 開關並設定 `weight`，不寫死於程式碼 | 使用者需能隨時關閉雜訊來源；沿用 `strategies.yaml`「改設定不需改程式」的既有慣例 |
| ADR-P4-02 | 入庫前做三層去重（URL → 正規化標題雜湊 → 近似標題），重複者保留權重最高的來源，其餘標記 `is_duplicate` 但不刪除 | Yahoo 股市大量轉載鉅亨網內容，不去重會讓同一則利多被重複計分；保留列而非刪除，方便回頭稽核降噪是否過當 |
| ADR-P4-03 | 情緒評分採分層成本控管：預設本地模型批次評分全部標題，LLM 僅在指定閘門觸發時介入；LLM 配額**獨立於** `AI_DAILY_QUOTA` | 新聞評分是「每日數百則標題」的量級，與「每檔每日一份技術分析報告」的成本模型完全不同，共用計數器會把報告額度排擠掉 |
| ADR-P4-04 | 新聞／PTT／總經資料採兩段式落地：先寫 JSON 緩衝檔，再入 PostgreSQL | 外部來源不可重放（新聞列表 API 只給最近 N 則，過期就抓不回來），DB 短暫不可用時不能漏接 |
| ADR-P4-05 | 新聞與總經數據一律以「可見時點」對齊交易日，不以發布內容所屬期間對齊 | 比照 `strategies/conditions_fund.py` 對 MOPS 月營收的 look-ahead bias 處理，避免用盤後才出現的新聞去判斷當日訊號 |
| ADR-P4-06 | `sentiment_filter`／`macro_filter` 實作為 **condition**，不是 `strategies/filters.py` 的 filter | `filters.py` 明訂濾網只加分、永不擋訊號；情緒與總經是會決定訊號成立與否的閘門，語意上屬 condition |
| ADR-P4-07 | 三張新表直接以 PostgreSQL 為唯一儲存，不參與 `DATA_SOURCE` 的 JSON／PG 雙軌切換 | 比照 `ai_analysis_report` 的既有決策（ADR-AI-14）；雙軌是為 OHLCV 設計，新資料類別不值得再做一套 |
| **ADR-P4-08**（v2.3 新增） | Spike-0 驗證結果（300 則真實標題人工標註 vs LLM 一致率 87.0%，見 §15.3-1）出爐後，使用者拍板**直接定案採用 LLM，不再另外測試／開發 §4.2 原訂的本地輕量模型**。`NEWS_SENTIMENT_ENGINE` 預設值改為 `"llm"`；§4.1 原訂的 L1（本地免費）／L2（LLM 限量升級）兩層分工**不採用**，全部標題一律走 LLM 批次評分 | 87% 一致率已達文件建議的 ≥80% 門檻，且中文情緒模型選型／訓練／部署（常駐 vs 排程批次）的額外工程量，相對於直接用已驗證堪用的 LLM 批次評分，效益不成比例；LLM 批次呼叫（比照 Spike-0 實測：25 則/批，日新聞量落在個位數批次）本身成本可控，`NEWS_LLM_DAILY_QUOTA` 已能限制上限，不需要再靠「本地免費 + 極端案例才升級」的分層設計省成本 |
| **ADR-P4-09**（v2.5 新增） | §5.1「另抓美元指數（DXY）」改用 FRED 官方發布的 Nominal Broad U.S. Dollar Index（series `DTWEXBGS`）作為免費替代來源，`macro_indicators.indicator_code` 對外仍稱 `"DXY"`，不暴露底層 series_id 差異 | 官方 ICE DXY 期貨指數並非 FRED 免費數列（需付費／授權資料商），`DTWEXBGS` 是 FRED 官方文件明列的美元強弱免費替代指標，日頻更新、2006 年後資料完整，不需另外整合第二個付費資料源或改用 yfinance 爬取指數期貨報價（後者穩定度與 ToS 風險比 FRED 自家 API 更高，且會讓「統一走 FRED 管線」的設計前提破功）；解決規格書 §15.4 原本標注的落差點 |

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

L2 呼叫一律**批次送出**（一次請求帶多則標題、回傳 JSON 陣列），不逐則呼叫，降低 per-request overhead。呼叫紀錄比照既有 `ai_llm_execution` 表的粒度記錄成本（可沿用該表，以 `symbol` 為空、另立 `prompt_version` 區分用途，避免再建一套成本表）。

> **v2.3 更新（ADR-P4-08）**：Spike-0 已於 2026-09-13 定案**不開發 L1 本地模型**，本節原訂的兩層分工（L1 本地免費批次 + L2 LLM 限量升級）**不採用**——實作時**全部標題一律走 LLM 批次評分**，不存在「先本地跑一輪、極端案例才升級 LLM」這道分流。上表與「L2 閘門條件」三點原文保留供歷史對照，但**閘門條件不再是「是否呼叫 LLM」的判準**（因為現在唯一的引擎就是 LLM），僅第 3 點「`NEWS_LLM_DAILY_QUOTA`」的配額管控概念仍然適用（改為限制「當日批次評分呼叫數」，而非「當日 L2 升級呼叫數」）。理由與影響見 §15.3-1、ADR-P4-08。

### 4.2 中文模型選型風險（Spike-0 已完成，見 §15.3-1）

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

> **v2.5 更新（ADR-P4-09）**：官方 ICE DXY 期貨指數不是 FRED 免費數列，`services/macro_fetcher.py`
> 實際改用 FRED 自家發布的 Nominal Broad U.S. Dollar Index（series `DTWEXBGS`）作為免費替代，
> `macro_indicators.indicator_code` 對外仍稱 `"DXY"`，不暴露底層 series_id 差異。另外，
> `indicator_date`／`release_date` 分欄的實作方式是呼叫 FRED API 時指定 `output_type=4`
> （"Initial Release Only"）：依 ALFRED 官方文件，這個輸出格式的 `realtime_start` 欄位就是
> 「資料第一次對外公布的日期」，直接拿來當 `release_date`，比原訂「查 release-calendar 端點再
> 比對配對」更簡單也更準確（不受後續修訂版本干擾）。理由與影響見 §0.6、§0.12 ADR-P4-09。

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

> **v2.7 更新（P4 實作發現的架構限制）**：本節與 §6.3 假設 `sentiment_filter`／`macro_filter`
> 可以跟主觸發 condition（如 `price_cross`）以 **AND** 關係掛在同一個策略下、互相把關。
> 實作時對照 `strategies/scanner.py` 的實際評估迴圈才發現：**目前的掃描器完全沒有「多個
> condition AND 在一起才算一次訊號」的機制**——`conditions:` 清單裡每一項是各自獨立評估、
> 各自獨立產生候選警示（OR 關係，各自用自己的 `direction` 去重）。核對現有 24 條策略設定檔，
> 目前一條都沒有掛超過 1 個 condition，證實這條 AND 語意路徑從未被使用過。這代表本節與
> §6.3 描述的「情緒/大盤不過關就擋掉主觸發」效果**目前技術上尚未成立**——`sentiment_filter`／
> `macro_filter` 已依本節規格實作（`strategies/conditions_sentiment.py`／
> `conditions_macro.py`），但掛在任何策略上目前都只會變成獨立發自己警示的條件類型，
> 不會真的擋掉其他 condition。真正要做到「閘門」效果，需要先擴充 `scanner.py`（例如新增
> 策略層級的 `gates:` 欄位，或比照 `conditions_pick.py` 的 `stock_pick_resonance` 用
> `_eval_*` 私有函式做 AND 組合、另外設計一個複合 condition），規劃為後續待辦，本次 P4
> 刻意不處理（開工前已與使用者確認），也因此本次未在 `strategy_config/strategies.yaml`
> 新增任何引用這兩個 condition 的範例策略，避免在閘門機制不完整的狀態下讓真實策略上線、
> 產生誤導性的警示。理由與影響見 §0.4、§15.2 P4 列。
>
> **v2.8 更新（此限制已解決）**：依使用者要求「補上 scanner.py 的 AND 機制」，
> `StrategyDef` 新增 `gates:` 欄位，`strategies/scanner.py` 新增 `_evaluate_gates()`——
> 主觸發 condition 產生候選警示後，先檢查 `strategy.gates` 是否全數通過才真的放行。
> `sentiment_filter`／`macro_filter` 現在**掛進 `gates:` 才會真的發揮閘門效果**（掛在
> `conditions:` 仍是獨立 condition，行為與 v2.7 相同）。現有 24 條策略皆無 `gates`，
> 呼叫 `_evaluate_gates([], ...)` 直接放行，行為完全不變（已重新觸發 `scan_market('tw')`
> 迴歸驗證）。理由與影響見 §0.3。

### 6.2 `ScanContext` 擴充（✅ 已實作，見 §0.4）

condition 只能讀 `ctx`，**不得自行發請求或讀檔**（此為專案既有鐵則：條件函式只讀 `ctx.ma`／`ctx.bias`，不重算指標）。因此需在 `services/chip_provider.py` 的 `ScanContext` 新增與 `dates` 等長的平行序列，比照既有 `revenue_yoy`／`revenue_visible_month` 的做法：

| 新增欄位 | 型別 | 說明 |
| --- | --- | --- |
| `sentiment_5d` | `List[Optional[float]]` | 逐交易日的 5 日加權情緒分數 |
| `news_count` | `List[Optional[int]]` | 逐交易日的有效新聞則數（去重後） |
| `buzz_percentile` | `List[Optional[float]]` | 逐交易日的 PTT 討論量分位數 |
| `macro_flags` | `Dict[str, bool]` | 該次掃描的市場層級旗標（單次掃描共用，非逐日序列） |

`ChipDataProvider.get_bars()` 需在載入 K 線的同一次呼叫中一併補上這些序列，避免掃描器對每檔個股額外多發查詢。

### 6.3 YAML 擴充範例

> **v2.8 更新**：原始範例把 `sentiment_filter`／`macro_filter` 放進 `conditions:`，
> 那是 v2.7 交付時尚未解決 AND 閘門機制前的示意寫法——照抄會變成兩個獨立發自己警示的
> 條件類型，不會真的擋掉 `price_cross`。§6.1 v2.8 更新後正確寫法是放進新增的 `gates:`
> 欄位，下方範例已更新為正確用法。

```yaml
# backend/strategy_config/strategies.yaml 擴充範例
strategies:
  - id: "momentum_with_news_confirmation"
    name: "動能突破與利多共振"
    category: "trend_sentiment"
    enabled: true
    markets: ["tw"]              # sentiment_filter 僅支援 TW；跨市場需拆成兩個策略
    conditions:
      - type: "price_cross"      # 主觸發：技術面突破，獨立產生警示
        target: "close"
        ma_periods: [60]
        directions: ["cross_above"]
    gates:                       # 閘門：全部通過，上面的主觸發才會真的放行（v2.8 新增機制）
      - type: "sentiment_filter" # 不在利空下追高
        min_score: 0.5
        max_buzz_percentile: 0.85
      - type: "macro_filter"     # 大盤環境保護
        market_trend: "above_20ma"
    filters:
      - type: "volume_confirm"   # 加分：不影響訊號成立
        params: { multiple: 1.5 }
```

### 6.4 閘門型 condition 的使用限制（✅ 已實作，見 §0.3）

`sentiment_filter` / `macro_filter` 屬於**持續性狀態**（大盤站上月線可能連續成立數十天），不是轉折事件。若某策略只掛閘門型 condition 而無主觸發條件，會每個交易日都成立、天天推播。規格要求：

- 兩者不得作為策略的唯一 condition，設定檔載入時應檢核並在啟動日誌警示。
- 訊號去重仍沿用既有 `strategies/cooldown.py`（`ALERT_COOLDOWN_DAYS`，依 `(symbol, strategy, direction)`），不另建一套。

> **v2.8 更新**：本節原文假設的「唯一 condition」情境，在 v2.8 新增 `gates:` 欄位後
> 分成兩種需要檢核的誤用：①仍把 `sentiment_filter`／`macro_filter` 放進 `conditions:`
> 而沒有其他主觸發（沿用本節原檢核，補充「應改放 gates」的提示）；②正確放進 `gates:`，
> 但 `conditions:` 是空的（新增檢核——`gates` 只在 `conditions` 觸發時才會被評估，
> 沒有主觸發時這些 `gates` 永遠不會被檢查，整條策略形同沒作用）。兩條檢核都已併入
> `strategies/config_loader.py` 既有 YAML 載入批次，見 §0.3。

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

## 10. 通知整合（✅ 已實作，見 §0.1）

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

## 15. 現況評估與分階段實作計畫（v2.1 新增，v3.0 更新實作進度，2026-09-13）

本節不改變 §1～§14 的任何需求，只回答兩件事：**現在做到哪裡了**、**接下來怎麼分階段做**。方法是逐項核對現行程式碼，不是讀規格猜測。

### 15.0 現況評估結論（v3.0 更新）

**v2.1 原文**（僅供歷史對照）：全文對照後確認本文件規劃的每一項產出全部零實作，狀態與文件自報一致。

**v2.2 現況**（僅供歷史對照）：P0（骨架與設定）與 P1（新聞資料管線）已實作並 commit（`3a96bda`）——`V23__Create_news_and_macro_tables.sql`（三張新表）、`services/news_fetcher.py`（cnyes 抓取已對真實 API 端到端驗證、PTT Stock 板討論量抓取已對真實頁面結構驗證）、`services/news_config.py`、`services/news_dedup.py`、`indicators/news_time.py`、`repositories/news_repository.py`、`api/v1/endpoints/news.py`（4 個端點已掛載）均已落地，細節見 §0.9。

**v2.4 現況**（僅供歷史對照）：P2（情緒評分引擎）已實作，細節見 §0.7。

**v2.5 現況**（僅供歷史對照）：P3（總經／大盤環境管線）已實作，細節見 §0.6。

**v2.6 現況**（僅供歷史對照）：使用者提供 FRED API 金鑰後，發現本機其實已有可連線的 `mystock_db`，補跑 migration 至 V23 後，**P1／P2／P3 的 Postgres 寫入路徑已全部真實端對端驗證**，過程中發現並修正 3 個真實 bug，細節見 §0.5。

**v2.7 現況**（僅供歷史對照）：P4（`ScanContext` 擴充＋`sentiment_filter`／`macro_filter` 兩個新 condition）已實作，細節見 §0.4。當時記錄的「⚠️ 重要限制」（這兩個 condition 技術上等同獨立 condition，scanner.py 未支援 AND 組合）已於 v2.8 解決。

**v2.8 現況**（僅供歷史對照）：依使用者要求「補上 scanner.py 的 AND 機制，讓 P4 真正發揮作用」，新增 `gates:` 欄位與 `_evaluate_gates()`，`sentiment_filter`／`macro_filter` 現在掛進 `gates:` 就能真正發揮閘門效果，細節見 §0.3。現有 24 條策略無 `gates`，行為完全不變（已迴歸驗證）。當時仍未在 `strategies.yaml` 新增任何引用它們的真實策略——此點已於 v2.9 補上。

**v2.9 現況**（僅供歷史對照）：依使用者要求「幫我在 strategies.yaml 加一條真的會用到 sentiment_filter／macro_filter 的策略並啟用」，新增並啟用 `momentum_with_news_confirmation`，細節見 §0.2。已用這條策略真實載入的 `gates` 設定完成端對端合成情境驗證（主觸發成立時，情緒/大盤任一不過關皆正確整筆擋掉）。

**v3.0 現況**：P5（通知整合）已實作——`ALERT_SIGNAL` payload 新增 `sentiment_5d`／`top_news`，三份樣板（email/slack/telegram）加上選擇性新聞區塊，細節見 §0.1。已對真實新聞資料端對端驗證，過程中發現並處理一個環境落差：資料庫已有 3 筆與程式碼同步的 `ALERT_SIGNAL` 範本會覆蓋本地 `.j2` 檔案，經確認後一併更新。

**尚未實作**：`services/scheduler.py` 的新聞/總經排程、任何前端新聞或總經 UI——對應 §15.2 的 P6～P7。

Spike-0（中文情緒模型選型驗證）已完成並定案：LLM 與人工一致率 87.0%，詳見 §15.3-1。

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
| **P2** 情緒評分引擎（✅ 已實作，見 §0.7；Postgres 寫入路徑已於 v2.6 端對端驗證，見 §0.5） | ~~依 Spike-0 結論實作 L1／L2~~——ADR-P4-08 定案後簡化為全部標題一律 LLM 批次評分：`services/news_sentiment.py` 沿用 `ai/providers/__init__.py` 的 `PROVIDER_REGISTRY`，配額與成本記錄照抄 `industry_chain/extractor.py`（見 §15.1 附註）；`services/news_analytics.py` 提供 `sentiment_5d`／Buzz Surge 查詢；`indicators/news_time.py` 新增 `divergence_flag()` 判斷邏輯（掛進 `ScanContext` 留給 P4）。~~PTT 過熱分位數直接複用 `indicators/chip.py` 既有的 `rolling_percentile()`~~——**此描述於 P1 階段已修正**：實際採用 `indicators/news_time.py` 新增的 `percentile_rank_of()`，因為 `rolling_percentile()` 算的是相反方向的問題（見該函式 docstring），且 P1 已完成落地，不在 P2 範圍內 | Spike-0 結論、P1 | 對照 Spike-0 基準集算一致率回歸；配額用完驗證 AC-P4-07；已對真實 Gemini 呼叫＋Postgres 寫入端對端驗證（101 則真實新聞全數評分成功，見 §0.5） | **主要工程量，且高度依賴 Spike-0 是否順利**（已完成） |
| **P3** 總經／大盤環境管線（✅ 已實作，見 §0.6；Postgres 寫入路徑已於 v2.6 端對端驗證，見 §0.5）（可與 P1/P2 並行） | `services/macro_fetcher.py`（FRED 5 指標＋DXY，`indicator_date`/`release_date` 分欄，`output_type=4` 取代「查 release-calendar 再比對」）、`api/v1/endpoints/macro.py`、`services/macro_analytics.py` 的 20MA/60MA 位階讀既有 `index_service.py`／`stock_service.py`（不重建指數管線）。DXY 來源見新增 **ADR-P4-09**（FRED `DTWEXBGS` 免費替代 ICE DXY） | P0 | 查表確認兩欄位分離；用歷史 CPI/非農公布日構造案例驗證 AC-P4-04；已對真實 FRED API＋Postgres 寫入端對端驗證（5 指標共 579 筆，見 §0.5） | 中（FRED API 本身簡單，複雜度在 release_date 對齊與 DXY 來源選定，已解決）（已完成） |
| **P4** ScanContext 擴充＋兩個新 condition（整合階段）（✅ 已實作，見 §0.4；AND 閘門機制已於 v2.8 補上，見 §0.3） | `chip_provider.py` 的 `ScanContext`（`@dataclass`）新增四欄位，逐日 append 邏輯仿 `revenue_yoy` 寫法；`macro_flags` 已在 `strategies/scanner.py` 的 `for symbol in all_scan_symbols:` 迴圈之前算一次、注入每次 `get_bars()` 呼叫（AC-P4-06「全市場一次」）；`conditions_sentiment.py`／`conditions_macro.py`＋`strategies/__init__.py` 補 import；「只掛閘門型 condition 需警示」的檢核已併入 `strategies/config_loader.py` 既有 YAML 載入批次。~~**⚠️ 重要限制**：scanner.py 沒有 AND 組合機制~~——**此限制已於 v2.8 解決**：新增 `StrategyDef.gates` 欄位與 `strategies/scanner.py` 的 `_evaluate_gates()`，`sentiment_filter`／`macro_filter` 掛進 `gates:` 即可真正擋掉主觸發訊號，現有 24 條策略無 `gates` 故行為不變。**v2.9 更新**：已在 `strategies.yaml` 新增並啟用 `momentum_with_news_confirmation`，第一條真實引用這兩個 condition 的上線策略，見 §0.2 | P1、P2、P3 全部 | AC-P4-05（對照既有 filter 行為差異，已可驗證：`_evaluate_gates()` 用 9 組合成情境驗證 AND 語意正確）；AC-P4-06（斷言計算次數==掃描次數，已驗證：`get_macro_flags()` 於迴圈外呼叫一次，結果原封不動注入）；已對真實 Postgres 資料驗證 point-in-time 對齊正確，並兩度觸發 `scan_market('tw')`（P4、v2.8 各一次）確認未影響既有 24 條策略（迴歸通過） | 中，程式量不大但正確性要求高（look-ahead bias、單次計算共用）（已完成，含 AND 閘門機制） |
| **P5** 通知整合（✅ 已實作，見 §0.1） | `notify/events.py` 的 `ALERT_SIGNAL` payload 加 `top_news`/`sentiment_5d`（確認不影響 `_key_alert_signal()` 冪等鍵）；三通道樣板加選擇性區塊 | P4 | 手動觸發一次帶新聞資料的訊號，核對三通道渲染與去重鍵不變；已對真實新聞資料端對端驗證，並發現、處理一個資料庫範本覆蓋本地檔案的環境落差 | 小 |
| **P6** 前端 | `service/newsApi.js`／`macroApi.js`（`import { apiClient } from '@/service/stockApi'`）；個股新聞卡片仿 `StockAlertsPanel.vue`＋`AlertTimeline.vue`（情緒 Tag 沿用 `marketColors.js` 紅漲綠跌，**不看 `useMarket.js` 死欄位 `up_down_convention`**）；總經儀表板區塊加在 **`HeatmapDashboard.vue`**（見 §15.1-1），Sparkline 抄 `HeatmapDashboard.vue` 既有 `getSparklineOption()` 改中性單色 | P1、P3（不依賴 P4/P5，可先用假資料開發 UI） | AC-P4-08/09，建議用 `/run` 實際跑起來截圖驗證（純視覺回歸容易漏審） | 中 |
| **P7** 排程串接與資料保留清理 | `scheduler.py` 新增 §9 六個排程項（新聞抓取／情緒評分鏈式觸發／PTT／FRED-DXY／清理）；保留政策比照既有 `purge_old_logs` | P1～P4 全部 | 先手動觸發 `POST /news/trigger` 跑順鏈式流程，再掛 cron（排程本身難重現問題，不建議用排程除錯） | 小 |

**建議執行順序**：Spike-0（越早做越好，與 P0 並行）→ P0 → P1 與 P3 並行 → P2 → P4（收斂整合點，必須排在 P1/P2/P3 之後）→ P5 → P6（可與 P4/P5 部分並行，先用假資料開發 UI 骨架）→ P7（收尾）。

### 15.3 需要人為決策、無法單靠寫程式解決的風險點

1. **§4.2 中文情緒模型選型驗證（Spike-0，已於 2026-09-13 完成並定案，✅ 已結案）**：從 cnyes 即時抓取 300 則真實台股新聞標題，由使用者人工逐則標註多空／中立，並用既有 `ai/providers`（Gemini `gemini-3.6-flash`，經 `extract_structured()`）批次產出 LLM 參考標籤做對照。結果：
   - **整體一致率 87.0%（261/300）**，達文件建議的 ≥80% 門檻。
   - 混淆矩陣顯示 LLM 對「看多」（recall 95.6%／precision 92.0%）與「看空」（recall 88.2%）判斷相當準，但**「中立」類別明顯偏弱**（recall 僅 50.9%）：55 則人工判定中立的標題中，LLM 把 27 則誤判成有方向性（18 則誤判看多、9 則誤判看空）。人工複核誤判樣本後歸納出系統性傾向：**LLM 只要看到具體正面數字或字眼（營收年增、訂單、認證）就傾向直接判多，即使人工認為那只是中性的事實揭露**（例如「TPCA：全球載板產值增3成」人工判中立、LLM 判看多；「大立光8月營收年減16%」人工判中立、LLM 判看空）——這不是隨機誤差，是 LLM 對「多空方向性」的判準比人工寬鬆。
   - **使用者已於 2026-09-13 拍板「用這 87% 直接定案」**：**不再另外測試／開發本地輕量模型**，直接採用 LLM 作為唯一情緒評分引擎（見新增 **ADR-P4-08**、§4.1 更新、§0.8 v2.3 摘要）。§4.1 原訂「L1 本地免費批次＋L2 LLM 限量升級」的兩層分工**不採用**，全部標題一律走 LLM 批次評分；`NEWS_SENTIMENT_ENGINE` 程式預設值已改為 `"llm"`（`config.py`、`.env.example`，2026-09-13 commit）。
   - **設計啟示（仍然適用，未因定案而失效）**：鑑於「中立」類別誤判率高，`sentiment_filter` 的中立判斷應偏保守——寧可漏判也不要把中性新聞誤判成有方向性訊號，避免產生假訊號；P2 實作時應留意這點，必要時可在 Prompt 或後處理補一道「數字增長但無方向性語境詞則傾向中立」的規則。
   - 完整標註結果、混淆矩陣、全部誤判案例見對話紀錄（`spike0_report.txt`，未隨文件留存，如需重新產生可重跑同一套流程：cnyes 抓取 → Artifact 人工標註工具 → `read_db` 拉回比對）。
2. **PTT／Cnyes／Yahoo 爬蟲的 ToS／穩定度風險**：§3.1 僅寫「須遵守目標站點的存取條款」，未給明確驗收標準。PTT 網頁版有 18 歲同意頁與偶發改版，屬營運風險；Cnyes／Yahoo 若無官方開放條款，長期存取有 IP 封鎖或法遵疑慮——這是業務層級的風險接受決策，不是工程師能單方面決定的事，建議在 P1 動工前由你明確拍板「接受此風險上線」或「先確認/改用官方付費 API」。工程上能做的只有把三個來源做成互相獨立、單一來源失效不影響其他（`news_sources.yaml` 的 `enabled` 開關已是這個設計的一部分）。
3. **三層去重（尤其 L3 SimHash）對中文標題的實際效果未經實測**：文件自己承認「trigram 對中文標題的鑑別度需先實測」，`dedup_hamming_max: 3` 只是預設值。建議 P1 上線後留一週觀察期，用真實跨來源轉載樣本人工抽查「有沒有漏判」與「有沒有誤判」，再回頭調整門檻，不能假設一次寫對。

### 15.4 文件未講清楚、留給實作者自行決定的落差點

- ~~**`macro_flags` 的計算/注入位置未指名檔案**~~——**此落差點已解決**：`services/scanner.py` 已在 `for symbol in all_scan_symbols:` 迴圈之前呼叫 `services/macro_analytics.get_macro_flags()` 一次，結果原封不動注入每次 `get_bars()`（見 §0.4 v2.7 摘要）。
- ~~**L3 SimHash 工具函式該放哪個檔案未指定**~~——**此落差點已解決**：P1 已獨立成 `services/news_dedup.py`（而非併入 `news_fetcher.py`），去重邏輯供評分 job 複用來排除 `is_duplicate` 列，不與抓取器耦合。
- ~~**「策略只掛閘門型 condition 需在啟動日誌警示」的實作位置未指定**（§6.4）~~——**此落差點已解決**：已併入 `strategies/config_loader.py` 既有 YAML 載入批次，不另立檢查函式（見 §0.4 v2.7 摘要，v2.8 再擴充一條「gates 設定但 conditions 空」的檢核，見 §0.3）。
- ~~**DXY 的具體資料來源未指定**（§5.1）~~——**此落差點已由 ADR-P4-09 解決**：改用 FRED 官方發布的 `DTWEXBGS`（Nominal Broad U.S. Dollar Index）作為免費替代來源，`indicator_code` 對外仍稱 `"DXY"`。
- ~~**L2 閘門條件二「追蹤清單／持股庫存」對應哪張表未指名**（§4.1）~~——**此落差點因 ADR-P4-08 已不存在**：定案全部標題一律走 LLM 批次評分後，不再有「僅追蹤清單／持股標的才升級 LLM」這道閘門，`services/news_sentiment.py` 的 `list_unscored()` 對全市場候選一視同仁，不需要查 `watchlist`／`portfolio` 表。

### 15.5 Critical Files（供 P0 開工時快速定位）

`backend/services/chip_provider.py`（ScanContext）、`backend/strategies/scanner.py`（掃描迴圈與 macro_flags 注入點）、`backend/strategies/__init__.py`（condition 模組註冊）、`backend/services/news_fetcher.py`（待新增）、`backend/strategy_config/news_sources.yaml`（待新增）、`backend/db/migration/V23__Create_news_and_macro_tables.sql`（待新增）、`backend/industry_chain/extractor.py`（LLM 配額/成本記錄範本）、`frontend/src/views/HeatmapDashboard.vue`（總經儀表板實際掛載處）。
