# Phase 1：基礎量化數據層與技術面指標擴充 — 技術指標庫擴充規格書

**模組**：技術面純函式指標庫（`backend/indicators/`）與 AI 診股報告技術面 Context 擴充
**版本**：v2.0（v1.0 為草案，範圍與現況嚴重脫節，本版整份重寫，見 §0）
**日期**：2026-08-28
**狀態**：需求規格 — 待審核。本文件只定義需求與驗收條件，**不含程式開發**
**對應既有模組**：
[indicators/moving_average.py](../../backend/indicators/moving_average.py)、
[indicators/stochastic.py](../../backend/indicators/stochastic.py)、
[indicators/chip.py](../../backend/indicators/chip.py)、
[services/chip_provider.py](../../backend/services/chip_provider.py)（`ScanContext`）、
[services/fetcher.py](../../backend/services/fetcher.py)（TWSE 爬蟲）、
[services/us_fetcher.py](../../backend/services/us_fetcher.py)（yfinance 爬蟲）、
[services/stock_service.py](../../backend/services/stock_service.py)、
[strategies/conditions_tech.py](../../backend/strategies/conditions_tech.py)、
[strategies/filters.py](../../backend/strategies/filters.py)、
[ai/summary.py](../../backend/ai/summary.py)、
[scripts/verify_kd.py](../../backend/scripts/verify_kd.py)（既有驗證慣例前例）

**參考文件**
- [AI 技術分析報告 系統開發規格書](AI技術分析規劃.md)（以下簡稱《AI 報告規格》）——`quant_summary` 結構、`ai/summary.py` 鐵則的母體文件
- [Phase2-籌碼面與基本面量化擴充.md](Phase2-籌碼面與基本面量化擴充.md)——同一輪「v1.0 對照現況重寫」的前例，本文件的 §0、§2 沿用其寫法
- [Phase3-產業鏈知識圖譜與輪動模型.md](Phase3-產業鏈知識圖譜與輪動模型.md) §2.0——該文件已指出本文件 v1.0 與現行架構不符（`TWSEProvider`／`YahooProvider`／Parquet 落地），本版即為該落差的修正
- [KD指標 設計規格書]（`strategies/conditions_tech.py`、`indicators/stochastic.py` 註解引用）——本文件 §4、§6 的整合深度沿用其「純函式 → ScanContext → condition → 前端副圖」四層落地模式

---

## 0. 改版說明：為什麼整份重寫

v1.0 的草案設想的是「從零打造」一條量化數據管線——抽象基底類別 `BaseProvider` 與具體的
`TWSEProvider`／`YahooProvider`、兩段式落地目錄（`data/raw/` JSON 緩衝 → `data/curated/` Parquet
欄位式儲存）、`pandas` DataFrame in/out 的指標函式、以及 `pytest` 單元測試框架。但實際比對現有
程式碼後發現：**OHLCV 資料管線與六成以上的指標庫早就做完了**，只是模組名稱、儲存形態與測試慣例
與 v1.0 的設想不同，沿用 v1.0 字面重寫只會生出一份「要求重做已完成功能、且引入專案目前不存在
的技術棧（Parquet、pytest）」的錯誤規格。

因此 v2.0 做了三件事：

1. **§2 現況盤點**：把 v1.0 四大項逐一核對現況，標明「已完成」「部分完成」與對應程式碼位置。
2. **重新定位本文件的範圍**：v1.0 標題「基礎量化與技術面」在現況下唯一站得住腳、且未被任何其他
   指標檔案認領的缺口，是——**MACD、RSI、布林通道、ATR 這四項動能／震盪／波動指標，全專案（前後端）
   目前完全沒有實作**。本文件的交付內容就是把這四項指標補進既有的純函式指標庫，並視需要串進
   AI 診股報告的 Context（比照《AI 報告規格》既有模式）。
3. **修正與現行架構不符的技術假設**：純函式指標的既有慣例是 `List[Optional[float]]`（見
   `moving_average.py`／`stochastic.py`），不是 `pandas.DataFrame`；資料落地是「JSON 為唯一事實
   來源 + 盡力而為 dual-write 到 Postgres」，沒有 Parquet 層；驗證慣例是一次性交叉比對腳本（見
   `scripts/verify_kd.py`），專案目前**沒有 `pytest`**（`requirements.txt` 未列出，`CLAUDE.md`
   明載「無後端測試套件」）。v2.0 不再假設這些不存在的技術棧。

---

## 1. 目的與範圍

### 1.1 目的

把技術面純函式指標庫從「趨勢＋隨機指標」（MA／BIAS／KD）補齊到「趨勢＋動能＋波動＋量能」四大類，
讓 AI 診股報告與（未來視需要）策略引擎能取得比現行更完整的技術面數據，同時**不新建**任何一條與
`indicators/` 既有慣例不同的資料路徑——沿用同一套「純函式、`List[Optional[float]]`、無副作用、
與前端算法對齊」的既有設計原則（見 CLAUDE.md「策略/警示引擎」一節）。

### 1.2 交付範圍

1. 四個新純函式指標模組（或併入既有檔案）：**MACD**、**RSI**、**布林通道（Bollinger Bands）**、
   **ATR**（§3）。
2. 兩個「正式化」既有 ad-hoc 邏輯的指標函式：**近 N 日支撐／壓力**（現行 `ai/summary.py` 有
   inline 版本，無 N 可調、無法在指標庫外重用）、**爆量偵測**（現行已有 `filters.volume_confirm`，
   本文件僅評估是否需要一個回傳倍數本身而非布林值的指標版本，供 AI Context 顯示用，見 §3.5）。
3. 將以上指標接入 `ai/summary.py` 的 `build_quant_summary()`，作為 `quant_summary` 的新增區塊
   （比照《AI 報告規格》既有的「缺值即省略、不得臆測」慣例，見 §4.2）。
4. 撰寫與 `scripts/verify_kd.py` 同等級的一次性驗證腳本，交叉比對已知數值與邊界案例（§5），
   **不引入 pytest**（見 ADR-P1-03）。

### 1.3 不在本文件範圍

| 項目 | 原因 | 責任文件／現況 |
|---|---|---|
| OHLCV 爬蟲重寫（`TWSEProvider`／`YahooProvider` 抽象層） | 已完成，且現行 `fetcher.py`／`us_fetcher.py` 具體模組運作良好，改抽象類別無實質效益 | `services/fetcher.py`、`services/us_fetcher.py`（見 §2） |
| 兩段式 `data/raw/` JSON → `data/curated/` Parquet 落地 | 現行架構是 JSON 為唯一事實來源 + dual-write Postgres，無 Parquet 層；新增一層儲存格式會製造第三份資料來源，違反「唯一事實來源」原則 | 見 ADR-P1-01 |
| MA／BIAS／均線多空排列 | 已完成 | `indicators/moving_average.py`、`strategies/conditions_tech.py` 的 `alignment` |
| KD 隨機指標 | 已完成（含台股慣例遞迴平滑、暖身期、鈍化判定，規格遠超 v1.0 原始描述） | `indicators/stochastic.py`、`strategies/conditions_tech.py` 的 `kd_cross` |
| 爆量濾網（成交量 ≥ 均量 × 倍數） | 已完成 | `strategies/filters.volume_confirm`（見 §2、§3.5） |
| `pytest` 測試框架導入 | 專案目前無任何測試框架，是否要為此單獨引入超出本文件範圍的決定 | 見 ADR-P1-03 |
| MACD／RSI 是否要做成策略 `condition`（比照 `kd_cross`）與前端副圖切換（比照 KD 副圖） | 屬於「用不用」的整合深度問題，不是「算不算得出來」的指標需求，列為 P1/P2 待決，見 §7、§9 | 見 ADR-P1-04 |

### 1.4 市場範圍

本文件全部指標**同時適用 TW／US**——與 v1.0 一致，且與現行 MA／BIAS／KD 的既有慣例相同：
輸入只需要 OHLCV 序列，不依賴台股專屬的籌碼／基本面資料（不同於 Phase 2 的估值／營收僅
TW 適用）。`ai/summary.py` 的 Context 組裝中，這批指標**不受**既有 `market == "tw"` 分支限制。

### 1.5 前置依賴

無阻塞性前置依賴——OHLCV 歷史資料（JSON 與 Postgres 雙軌）在 TW／US 皆已完整累積，本文件的
指標函式可直接對現有資料開發與驗證，不需要等待任何爬蟲或資料表新增。

---

## 2. 現況盤點：v1.0 四大項 vs 實際狀態

| v1.0 項目 | 現況 | 依據 |
|---|---|---|
| 一、基礎工程與資料目錄重構（`requirements.txt` 鎖版、兩段式落地、`fetch_range`／`display_range` 解耦） | 🟡 部分完成且路徑不同：`requirements.txt` 已鎖版但**無 `pyarrow`／`pytest`**；儲存是 JSON 源頭 + dual-write Postgres，**無 Parquet 層**；`fetch_range`／`display_range` 解耦**已用不同機制達成**——`get_stock_chart_payload(period, months)` 的 `months` 是前端顯示範圍，內部另以 `MAX_HISTORY_MONTHS` 撈 `full_records` 供指標計算，兩者本來就已分離 | `requirements.txt`；`services/stock_service.py` `get_stock_chart_payload()` |
| 二、抽象資料層與 OHLCV 爬蟲（`BaseProvider`／`TWSEProvider`／`TPEXProvider`／`YahooProvider`、Parquet 增量保存） | ✅ 功能已完成，**但不是 v1.0 描述的形態**：無抽象基底類別，是 `services/fetcher.py`（TWSE，含民國年轉換、千分位清理、3.5~5.5 秒隨機節流、指數退避重試）與 `services/us_fetcher.py`（yfinance）兩支具體模組；落地為 `data/{tw,us}/<symbol>.json`，dual-write 到 Postgres（`db/dual_write.py`），無 Parquet | `services/fetcher.py`、`services/us_fetcher.py`、`db/dual_write.py`；CLAUDE.md「雙資料來源」一節 |
| 三、純函式技術指標庫（趨勢／動能／通道／量能四類） | 🟡 趨勢與隨機類已完成，**動能與波動類完全空白**：MA5/10/20/60/120/240、均線多空排列、BIAS ✅；KD（含台股遞迴平滑）✅；MACD ❌；RSI ❌；布林通道 ❌；ATR ❌；量能爆量偵測✅（做成濾網而非獨立指標）；支撐/壓力 🟡（`ai/summary.py` 有 inline 版本，非可重用的指標函式） | `indicators/moving_average.py`、`indicators/stochastic.py`、`strategies/filters.py`（`volume_confirm`）、`ai/summary.py`（`range`／`volume_ma5`／`volume_ratio`）；全專案（含前端）搜尋 `MACD`／`RSI`／`Bollinger`／`ATR` 均無結果 |
| 四、品質保證與單元測試（`pytest.fixture`、`test_indicators.py`） | ❌ 未採用 `pytest`——專案目前**沒有任何測試框架**（`requirements.txt` 未列 `pytest`，CLAUDE.md 明載「無後端測試套件」）；既有驗證慣例是**一次性交叉比對腳本**：`scripts/verify_kd.py`（獨立參考實作比對 + 邊界案例斷言）、`scripts/compare_data_sources.py`（JSON vs Postgres 一致性） | `scripts/verify_kd.py`、`scripts/compare_data_sources.py`；CLAUDE.md「Commands」章節 |

**結論**：本文件唯一站得住腳、且無人認領的缺口，是 §3 要處理的「MACD／RSI／布林通道／ATR
四項指標的純函式實作」，以及 §3.5 對支撐/壓力的正式化評估。其餘 v1.0 項目要嘛已完成（形態不同
但功能等價），要嘛是與現行技術棧不符的多餘假設（Parquet、pytest、抽象基底類別）。

---

## 3. 核心設計：新增指標規格

沿用 `indicators/moving_average.py`／`indicators/stochastic.py` 的既有慣例（見 ADR-P1-02）：

- 型別一律 `Series = List[Optional[float]]`，**不使用 `pandas.DataFrame`**。
- 純函式、無副作用、不做 I/O；輸入序列與輸出序列等長，資料不足或缺值的位置一律 `None`，
  不得補零或臆測（比照 `stochastic.py` 的 `_clean()`／暖身期慣例）。
- 0 值語意：比照全專案既有慣例，OHLC 為 `0` 視為當天缺值（`services/fetcher.py` 抓取失敗時
  的已知行為，見 CLAUDE.md「爬蟲」一節），指標函式的輸入清理需與 `stochastic._clean()` 一致。

### 3.1 MACD

| 項目 | 規格 |
|---|---|
| 檔案 | `indicators/macd.py`（新增，比照一指標一檔的既有慣例：`moving_average.py`／`stochastic.py`） |
| 函式 | `macd(closes: Series, fast_period=12, slow_period=26, signal_period=9) -> Tuple[Series, Series, Series]`，回傳 `(dif, macd_line, histogram)` |
| 計算式 | `EMA_fast = EMA(closes, fast_period)`；`EMA_slow = EMA(closes, slow_period)`；`DIF = EMA_fast - EMA_slow`；`MACD(信號線) = EMA(DIF, signal_period)`；`Histogram = DIF - MACD` |
| 需一併新增 | `ema(values: Series, period: int) -> Series`——現行 `moving_average.py` **只有 `sma()`，沒有 `ema()`**，MACD／未來任何 EMA 系指標都需要這個基礎函式，建議加進 `moving_average.py`（同檔）而非 `macd.py`（避免以後 EMA 需求分散在多個檔案） |
| 缺值規則 | 序列前段不足以完成 `slow_period` 根 EMA 暖身的位置一律 `None`；輸入含 `None` 的位置比照 `sma()` 的視窗處理，中斷 EMA 遞迴需重新起算（需在 §5 驗證腳本明確覆蓋此邊界案例） |
| 對齊需求 | 若後續要接前端圖表（§9 待決），需與 `frontend/src/utils/movingAverage.js` 比照 CLAUDE.md 既有的「前後端算法對齊」要求，新增對應 `ema()`／`macd()` JS 實作 |

### 3.2 RSI（相對強弱指標）

| 項目 | 規格 |
|---|---|
| 檔案 | `indicators/rsi.py`（新增） |
| 函式 | `rsi(closes: Series, period: int) -> Series`；呼叫端各自帶入 `6`、`14` 取得兩組序列 |
| 計算式 | Wilder's smoothing：以「漲幅平均」/「跌幅平均」的 `1/period` 遞迴平滑計算 `RS`，`RSI = 100 - 100/(1+RS)`（比照 `stochastic.py` 的遞迴平滑風格，而非簡單移動平均版 RSI，避免與台股看盤軟體常見演算法對不起來——同一顧慮见 `stochastic.py` 檔頭 ADR-KD-01） |
| 超買／超賣門檻 | v1.0 原文寫 `>80` 超買／`<20` 超賣——**明顯比業界慣用的 70/30 更嚴格**，本文件不擅自更改數字，但門檻應設計為**呼叫端參數**而非寫死常數（比照既有 `bias` condition 的 `overbought_threshold`／`oversold_threshold` 慣例），若日後要做成 condition 或寫進 Prompt，門檻取自 `strategy_config/strategies.yaml` 或 `ai/config.py`，不得在指標函式內部硬編碼 |
| 缺值規則 | 同 MACD：暖身期不足、輸入缺值時的處理需在驗證腳本明確覆蓋 |

### 3.3 布林通道（Bollinger Bands）

| 項目 | 規格 |
|---|---|
| 檔案 | `indicators/bollinger.py`（新增） |
| 函式 | `bollinger_bands(closes: Series, period=20, num_std=2.0) -> Tuple[Series, Series, Series]`，回傳 `(upper, middle, lower)` |
| 計算式 | `middle = SMA(closes, period)`（**可直接重用 `moving_average.sma()`，不得重算**——若呼叫端已有 `ctx.ma[20]`，中軌應直接取用而非在此函式內部重跑一次 `sma()`，避免同一份資料算兩次、也避免浮點結果因兩條路徑而出現細微不一致）；`std = 母體標準差(近 period 天收盤價)`；`upper = middle + num_std*std`；`lower = middle - num_std*std` |
| 帶寬 | 另外提供 `bandwidth = (upper - lower) / middle`（供未來「均線糾結」類判斷使用，語意與既有 `squeeze_breakout` condition 的糾結概念相關但不重複——`squeeze_breakout` 看的是均線本身糾結，此處是通道寬窄，兩者是不同指標，不合併） |
| 缺值規則 | 沿用 `sma()` 的視窗完整性規則：視窗內任一天缺值，該點 `None` |

### 3.4 ATR（真實波動區間）

| 項目 | 規格 |
|---|---|
| 檔案 | `indicators/atr.py`（新增） |
| 函式 | `atr(highs: Series, lows: Series, closes: Series, period=14) -> Series` |
| 計算式 | `TR_t = max(High_t - Low_t, |High_t - Close_{t-1}|, |Low_t - Close_{t-1}|)`；`ATR = TR` 的 Wilder `1/period` 遞迴平滑（首值以 `period` 天 TR 簡單平均做種子，比照 `stochastic.py` 的 `seed` 暖身設計） |
| 用途範圍 | v1.0 定位「作為後續波動度與停損位階參考」——本階段**只交付計算函式本身**，不預先決定要不要接進《AI 報告規格》既有的 `stop_loss` 欄位運算（那是 `ai/schema.py`／LLM 產出的欄位，非規則式計算，接入與否留待 §9 開放問題） |
| 缺值規則 | 需要 `Close_{t-1}`，序列第一天必為 `None`；高低收任一為 `0`（缺值慣例）視為當天無法計算 TR，遞迴狀態處理比照 `stochastic.py`「缺值不重置遞迴」的既有決策 |

### 3.5 支撐／壓力與爆量偵測：正式化評估

| 項目 | 現況 | 本文件決定 |
|---|---|---|
| 近 N 日波段高低點（支撐/壓力） | `ai/summary.py` 第 124~133 行有 inline 版本：固定抓 `records`（AI 報告顯示視窗）內的最高/最低，**視窗天數等於呼叫端傳入的月份範圍，不是 v1.0 要的固定 20/60 日，也不是可從外部呼叫的函式** | **新增** `indicators/levels.py` 的 `rolling_high_low(highs, lows, window) -> Tuple[Series, Series]`，讓 20 日、60 日兩組視窗各自可調用；`ai/summary.py` 既有 inline 邏輯改呼叫此函式（見 §4.1），不重複維護兩份邏輯 |
| 爆量偵測（成交量 ≥ 均量 1.5～2 倍） | `strategies/filters.volume_confirm` 已完整實作，回傳布林值（是否達倍數），供訊號強度加分用 | **不新增**判斷邏輯；若 AI Context 需要顯示「當前是均量的幾倍」這個**數值**（而非濾網的布林結果），比照 `ai/summary.py` 既有 `volume_ratio` 欄位即可，**已經存在**，不需新指標函式，本文件不重複造輪子 |

---

## 4. 與既有系統的整合點

### 4.1 `ai/summary.py`：`quant_summary` 新增區塊

比照《AI 報告規格》與 Phase 2 既有的擴充模式——新增鍵值、缺值即省略、不動對外七個結構化輸出
欄位：

| 區塊鍵 | 欄位 | 型別 | 市場 |
|---|---|---|---|
| `macd` | `dif`／`macd`／`histogram`（皆取當日值） | number | TW／US |
| `rsi` | `rsi_6`／`rsi_14` | number | TW／US |
| `bollinger` | `upper`／`middle`／`lower`（`middle` 直接取用既有 `ma_block["ma20"]`，不重算） | number | TW／US |
| `atr` | `atr_14` | number | TW／US |
| `range`（既有鍵改為指標函式驅動） | `resistance_20d`／`support_20d`／`resistance_60d`／`support_60d`，取代現行單一視窗的 `high`／`low` | number | TW／US |

**缺值規則**：沿用既有 `_clean()`（0/None 一律省略），暖身期不足的指標（如上市未滿 26+9 天的
新股，MACD 訊號線無法計算）整段鍵省略，不得以 `null` 或近似值頂替。

### 4.2 Prompt 影響

`ai/prompt.py` 的 System Prompt 研判框架新增一點（沿用《AI 報告規格》既有分節風格）：

```text
8. 動能與波動檢核：MACD 柱狀圖與 DIF/MACD 交叉是否支持當前趨勢、RSI 是否處於超買/超賣、
   布林通道是否收窄或開口擴大、ATR 反映的波動度是否適合當前操作策略；任一數值缺席時略過，
   不得臆測。
```

User Prompt 新增對應分節，缺值區塊整段不輸出（沿用既有「不出現空標題」慣例）。

### 4.3 是否接入策略引擎與前端圖表（本階段刻意不預先決定）

KD 指標的既有落地路徑是「純函式 → `ScanContext` → `conditions_tech.py` 的 `kd_cross` →
`strategies.yaml` 可設定策略 → 前端副圖切換」四層全套。MACD／RSI 若要做到同等整合深度，需要：

- `services/chip_provider.py` 的 `ScanContext` 新增對應欄位（比照 `ctx.kd`）。
- `strategies/conditions_tech.py` 新增 `macd_cross`／`rsi_overbought_oversold` condition。
- 前端新增副圖切換（比照 `ChartDetailView.vue`／`StockCharts.vue` 既有的 KD 副圖開關樣式，
  `KD_VISIBLE_STORAGE_KEY` 一類的 localStorage 慣例）。

**本文件不預先假設答案**——§3 的指標函式與 §4.1 的 AI Context 整合是可以獨立交付的最小範圍
（P0，見 §7），策略 condition 與前端圖表是否要做、做到什麼程度，列為 §9 待決問題，避免本文件
把「算得出指標」與「要不要因此新增兩個 UI/策略功能面」綁成同一個交付項目。

---

## 5. 品質保證與驗證慣例

專案沒有 `pytest`，比照 `scripts/verify_kd.py` 的既有模式（見 ADR-P1-03）：

| 項目 | 規格 |
|---|---|
| 腳本 | `scripts/verify_indicators.py`（新增，涵蓋 MACD／RSI／布林通道／ATR 四項；可仿 `verify_kd.py` 拆成多支或合一支，以維護方便為準） |
| 驗證方式 | 對每個指標寫一份**與 `indicators/` 正式實作不共用程式碼**的獨立參考算法（例如用不同的遞迴/迴圈寫法重算一次 EMA/RSI/ATR），交叉比對數值在容許誤差內一致 |
| 邊界案例 | 至少涵蓋：序列長度小於暖身期、輸入含 `None`／`0`（缺值）、連續同值（如連續漲跌停）、EMA 遞迴中斷後是否正確延續（比照 `stochastic.py`「缺值不重置遞迴」的既有決策，需明確驗證 MACD/RSI 是否採同一原則或改用視窗中斷重算，並在程式註解與本文件 §9 記錄選擇） |
| 真實資料一致性 | 對至少 1 檔 TW、1 檔 US 標的的歷史區間執行，肉眼／已知看盤軟體數值比對合理性（比照 `verify_kd.py` 對真實標的的月份區間檢查） |
| 通過標準 | 全部檢查印出 `PASS` 才算完成，比照 `verify_kd.py` 既有輸出格式 |

---

## 6. 決議事項（ADR）

| 編號 | 決策 | 理由 |
|---|---|---|
| **ADR-P1-01** | 不採用 `BaseProvider`／`TWSEProvider`／`YahooProvider` 抽象基底類別，也不新增 `data/curated/` Parquet 層 | 現行 `fetcher.py`／`us_fetcher.py` 具體模組已穩定運作多時，抽象化沒有新增市場的迫切需求（`markets/` 已是既有的多市場抽象點）；Parquet 會製造 JSON／Postgres 之外的第三份資料來源，違反「唯一事實來源」原則 |
| **ADR-P1-02** | 新指標一律 `List[Optional[float]]` 純函式，不使用 `pandas.DataFrame` | 比照 `moving_average.py`／`stochastic.py` 既有慣例；`ScanContext` 本身也是以 list 為基礎的資料結構，DataFrame in/out 會需要額外轉換層，且與既有程式碼風格不一致 |
| **ADR-P1-03** | 驗證方式採一次性交叉比對腳本（`scripts/verify_indicators.py`），不引入 `pytest` | 專案目前無任何測試框架，`scripts/verify_kd.py` 是唯一先例且運作良好；引入 `pytest` 屬於「新增專案級測試基礎設施」的決定，超出本文件「補齊指標庫」的範圍，若日後要導入應是獨立決定，不隨本文件夾帶 |
| **ADR-P1-04** | MACD／RSI 是否比照 KD 做成策略 `condition` 與前端副圖切換，本階段不預先決定 | 指標計算與其下游整合（策略引擎、圖表 UI）是可分離的兩件事；先交付 P0（純函式 + AI Context），觀察是否有實際需求後再決定是否比照 KD 的四層整合深度，避免範圍蔓延 |
| **ADR-P1-05** | 布林通道中軌直接重用既有 `ctx.ma[20]`／`ma_block["ma20"]`，不在新函式內部重算 SMA | 避免同一份資料算兩次；與《AI 報告規格》「不得自行重算已算好的序列」既有鐵則一致 |

---

## 7. 分階段交付

| 階段 | 內容 | 前置條件 |
|---|---|---|
| **P0** | `indicators/macd.py`（含新增 `moving_average.ema()`）、`indicators/rsi.py`、`indicators/bollinger.py`、`indicators/atr.py`、`indicators/levels.py`（§3.5 支撐/壓力正式化）；`ai/summary.py` 新增對應 `quant_summary` 區塊（§4.1）；`ai/prompt.py` 新增第 8 點（§4.2）；`scripts/verify_indicators.py`（§5） | 無 |
| **P1** | 視 §9 Q1 決議，評估是否新增 `macd_cross`／`rsi_overbought_oversold` condition 並接入 `strategies.yaml` | P0 穩定運行 |
| **P2** | 視 §9 Q2 決議，評估是否於前端新增 MACD／RSI 副圖切換（比照 KD 既有 UI 樣式） | P1（若 P1 決議要做 condition，通常前端顯示的需求會隨之出現） |

---

## 8. 驗收條件

| # | 條件 |
|---|---|
| AC-1 | `scripts/verify_indicators.py` 全部檢查印出 `PASS`，涵蓋 MACD／RSI／布林通道／ATR 的正常值與 §5 列出的所有邊界案例 |
| AC-2 | 任選 3 檔 TW、3 檔 US 有足夠歷史（≥ 60 個交易日）的標的，`quant_summary` 新增區塊（`macd`／`rsi`／`bollinger`／`atr`）數值與獨立參考實作一致 |
| AC-3 | 任選 1 檔上市未滿 35 個交易日的新股，`quant_summary` 不含尚無法計算的指標鍵（不得為 `0` 或 `null`） |
| AC-4 | 布林通道中軌數值與同一日期的 `quant_summary.ma.ma20` 完全相等（驗證確實共用同一份 SMA，未重算） |
| AC-5 | 既有回歸：關閉本次新增區塊後產生的報告（`verdict`／支撐壓力／停損等 7 個對外欄位）與改動前逐筆相同 |
| AC-6 | `range` 區塊改用 `rolling_high_low()` 後，`resistance_20d`／`support_20d` 數值與「近 20 個交易日高低點」手動核對一致；`resistance_60d`／`support_60d` 同理 |

---

## 9. 開放問題

| # | 問題 | 影響 | 建議 |
|---|---|---|---|
| Q1 | MACD／RSI 是否要做成策略 `condition`（比照 `kd_cross`），串進 `strategies.yaml` 與通知平台？ | 決定是否需要 §4.3 的 `ScanContext` 擴充與 `conditions_tech.py` 新增函式 | 建議 P0 上線、AI 報告觀察一段時間後再決定，避免一次擴大兩個交付面（同 ADR-P1-04） |
| Q2 | 前端是否需要 MACD／RSI 副圖切換（比照 KD 既有 UI）？ | 決定 §7 P2 是否啟動，及是否需要 `frontend/src/utils/` 新增對應 JS 實作以維持前後端算法對齊 | 待 Q1 決議「要做 condition」後再評估，純 AI Context 用途不需要圖表 |
| Q3 | RSI 超買/超賣門檻沿用 v1.0 的 80/20，還是改為業界慣用的 70/30？ | 影響 Prompt 措辭與（若做 condition）預設參數 | 門檻本身設計為參數（見 §3.2），不影響本階段開發；數字選擇建議使用者決定後寫入 `ai/config.py` 或 `strategies.yaml` 預設值，本文件不擅自認定 |
| Q4 | ATR 是否要接入《AI 報告規格》既有的 `stop_loss` 欄位計算（例如 `close - 2×ATR` 一類的規則式停損建議）？ | 若要做，`ai/summary.py` 或 `ai/schema.py` 需要新的規則式運算層，可能與現行「`stop_loss` 完全由 LLM 產出」的既有設計衝突，需先確認是否要引入規則式與 LLM 併存的雙軌停損 | 本階段不做，ATR 先以純數值形式併入 Context 供 LLM 參考（比照現行技術面數值皆為「佐證」而非「直接決策」的既有定位） |

---

## 10. 風險與限制

1. **EMA／RSI 的遞迴狀態處理需與既有指標一致，否則產生兩套「缺值後如何延續」的規則**：`stochastic.py`
   已有明確決策（缺值不重置遞迴狀態），MACD／RSI 若各自決定不同的處理方式，會讓「同一份資料、不同
   指標對缺值的反應不一致」，增加使用者與後續維護者的認知負擔——本文件要求 §5 驗證腳本明確覆蓋此
   案例並記錄最終選擇（見 §9 相關討論可併入該記錄，不另開新章節）。
2. **暖身期造成新股資料在多個指標同時缺席**：MACD 需要約 35 天（26+9）、RSI/ATR 需要 14~15 天，
   上市未滿一個月的新股在 `quant_summary` 中會有大片指標鍵缺席，需在 §4.2 Prompt 措辭中明確處理，
   避免 LLM 因「看不到常見指標」誤判為異常。
3. **不新增套件依賴**：本文件四項指標的計算（EMA 遞迴、標準差、TR）皆可用純 Python 完成，不需要
   `numpy`／`pandas`（現行 `pandas` 已在 `requirements.txt` 但指標層刻意不使用，見 ADR-P1-02），
   不引入任何新套件。

---

## 11. 影響範圍（僅供日後開發估算，本文件不動任何檔案）

| 檔案 | 預期異動 |
|---|---|
| `backend/indicators/moving_average.py` | 新增：`ema()` |
| `backend/indicators/macd.py` | 新增 |
| `backend/indicators/rsi.py` | 新增 |
| `backend/indicators/bollinger.py` | 新增 |
| `backend/indicators/atr.py` | 新增 |
| `backend/indicators/levels.py` | 新增：`rolling_high_low()`（§3.5） |
| `backend/ai/summary.py` | 新增 `macd`／`rsi`／`bollinger`／`atr` 區塊；`range` 區塊改呼叫 `rolling_high_low()` |
| `backend/ai/prompt.py` | System Prompt 新增第 8 點；User Prompt 新增對應分節 |
| `backend/scripts/verify_indicators.py` | 新增 |
| **P1（視 Q1 決議）** | `services/chip_provider.py`（`ScanContext` 擴充）、`strategies/conditions_tech.py`（新增 condition）、`strategy_config/strategies.yaml`（設定範例） |
| **P2（視 Q2 決議）** | `frontend/src/utils/`（EMA/MACD/RSI 對齊實作）、`ChartDetailView.vue`／`StockCharts.vue`（副圖切換） |
| **不需異動** | `services/fetcher.py`／`services/us_fetcher.py`（OHLCV 管線已完成，本文件不改動）、`db/dual_write.py`、`indicators/stochastic.py`／`chip.py`（既有指標不變） |
