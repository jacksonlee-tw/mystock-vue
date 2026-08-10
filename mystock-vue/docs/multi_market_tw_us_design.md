# 系統設計規劃：台股／美股雙市場切換 (Multi-Market TW / US Design)

這份文件說明如何在**不改變現有架構**（每檔股票一個 JSON 檔 → FastAPI 聚合 → Vue + ECharts 繪圖）的前提下，
加入「台股 / 美股」市場切換能力，並將 `GOOGL`、`NVDA`、`SPCX`、`TSLA` 納入初期追蹤標的。

**本文件整併兩份來源**：

1. 後端資料管線與 API 契約設計（本文件原始內容）。
2. [`docs/ui-redesign-prototype.html`](./ui-redesign-prototype.html) —「MyStock 介面優化雛形」，
   可切換市場的互動雛形，內含設計註解、指標支援矩陣與落地順序建議。
   本文件第 3、8 節的介面決策以該雛形為準；雛形是視覺與互動的權威來源，本文件是工程落地的權威來源。

> **標的先行確認：`SPCX` 需要重新確認。**
> SpaceX 為未公開發行公司、沒有股票代號；`SPCX` 曾是 Tuttle 發行的 SPAC 主題 ETF 代號，目前已清算下市，
> 資料源大機率抓不到報價。本文件仍將 `SPCX` 列入設定清單，但第 10 節設計了「代號驗證」機制會把它標記為
> `unresolved` 並在管理頁顯示警示，不會讓整批抓取失敗。若原意是太空／航太概念股，常見替代為
> `SPCE`（Virgin Galactic）或 `ARKX`（ARK 太空探索 ETF）——確認後改一個 `.env` 字串即可。

---

## 1. 設計目標與原則

| 目標 | 說明 |
| :--- | :--- |
| 架構一致 | 沿用 `data/{symbol}.json` 檔案儲存、`FetchStatusManager` 進度回報、`chart-data` 圖表載荷格式，不引入資料庫 |
| 市場可插拔 | 新增市場＝新增一個 adapter 檔 + 一組指標設定，不必修改既有台股邏輯與 API 路由 |
| 誠實呈現能力差異 | 不支援的指標**一律不渲染**，而非渲染成空白或 0——空白格會被讀成「這檔沒有法人買賣超」，而不是「這個市場沒有這種資料」 |
| 頻率畫進介面 | 每個指標標示更新頻率（<kbd>雙週</kbd><kbd>季</kbd>），把「這個數字多久更新一次」直接畫出來，比事後解釋為什麼線是平的有效 |
| 顯示層資料驅動 | 幣別、單位（張／股）、漲跌配色、指標組成、分頁組成全部由設定與後端 metadata 決定，前端不寫死 |
| 色彩承載資訊 | 強調色（brass）只用於互動與品牌，紅／綠專屬漲跌與買賣超正負，其餘一律灰階 |
| 狀態即網址 | 市場、代號、週期、範圍、分頁全部進 URL，可重整、可分享、可回上一頁 |
| 向後相容 | 既有 `.env` 的 `STOCK_CODES`、既有 `data/*.json`、既有前端網址全部繼續可用（舊網址 301 導向新格式） |

---

## 2. 現況盤點

### 2.1 綁死台股的位置

| 位置 | 台股專屬之處 |
| :--- | :--- |
| `backend/config.py` | `STOCK_CODES` 單一清單，無市場概念 |
| `backend/services/fetcher.py` | 全檔為 TWSE 專用（`STOCK_DAY` / `T86` / `MI_MARGN`、民國年轉換、3 秒節流、`_no_trading_days.json`） |
| `backend/services/stock_service.py` | `SUM_FIELDS` / `END_FIELDS` 直接列出「融資餘額(張)」等中文欄位；`券資比(%)` 計算 |
| `backend/data/*.json` | 平坦目錄，無市場分層 |
| `stocks.py` API | 所有端點皆無 `market` 參數 |
| `HeatmapDashboard.vue` | `getPriceColorClass()` 寫死 `text-red-500` 漲 / `text-emerald-500` 跌；sparkline 寫死 `#ef4444` |
| `StockDashboard.vue` | KPI 盤五格中三格是台股獨有；表格 13 欄有 8 欄是台股籌碼；單位寫死「張」「萬元」「$」 |
| `StockCharts.vue`、`ChartDetailView.vue` | 分頁固定為「法人籌碼 / 信用交易」，六種 chartType 有五種是台股籌碼 |
| `chartExplanations.js` | 六段說明全為台股籌碼制度 |

### 2.2 雛形「先做（不需後端配合）」清單的完成度

雛形列出的五項前端整理，**多數已在前一輪重構完成**，盤點如下，避免重複規劃：

| 雛形項目 | 狀態 | 位置 |
| :--- | :--- | :--- |
| 切股改用 `[` `]`，方向鍵歸還頁面捲動 | ✅ 已完成 | `AppTopbar.vue:68` |
| period／range 寫回 URL query | ✅ 已完成 | `StockDashboard.vue:405-413` |
| 移除頁內第二個個股下拉；追蹤管理搬到 `/stocks` | ✅ 已完成 | `StockDashboard.vue` 身分列 |
| `alert/confirm` 換成 Toast／Dialog | ✅ 已完成 | `useToast` / `useConfirm` |
| 日期區間只出現一次 | ✅ 已完成 | `StockCharts.vue:4-8` |
| 抽出 `--up`／`--down`，清掉 `text-red-500`／`text-emerald-500` | ⚠️ **半套** | `marketColors.js` 已建立但 `HeatmapDashboard.vue:168-206` 完全繞過它 |
| 色彩配額（刪掉六色裝飾色） | ❌ 未做 | `StockCharts.vue` / `ChartDetailView.vue` 仍有 6 種裝飾色 |
| `tab` 寫回 URL query | ❌ 未做 | `StockCharts.vue` 的 `activeTab` 是純 ref |
| Ctrl K 全域搜尋取代頂部 `select` | ❌ 未做 | `AppTopbar.vue:173` 仍是原生 `select` |

**已就緒可直接接上的部分**：`utils/marketColors.js` 已有 `tw`（紅漲綠跌）/ `us`（綠漲紅跌）雙配色，
`StockDashboard.vue`、`ChartDetailView.vue`、`StockCharts.vue` 都已有 `market` computed 與 `market` prop，
只是目前恆為 `'tw'`——**後端一旦回傳 `market` 欄位，K 線與 KPI 配色會自動切換**。

---

## 3. 三層設計骨幹

整套雙市場能力由三個互相獨立的層次組成，可以分開實作、分開驗收：

```
① Market Adapter  ── 我從哪裡抓、抓到什麼欄位          （後端 · 資料管線）
② Metric Registry ── 這個市場有哪些指標、更新頻率多快   （後端 · 設定驅動）
③ Display Contract ─ 這些指標長什麼樣、用什麼顏色和單位 （前端 · 資料驅動渲染）
```

### 3.1 ① Market Adapter（`backend/markets/`）

```
backend/markets/
├── __init__.py          # MARKETS 註冊表、resolve_market()、get_adapter()
├── base.py              # MarketAdapter 介面 + MarketMeta dataclass
├── tw.py                # 現有 TWSE 邏輯搬入（STOCK_DAY / T86 / MI_MARGN）
└── us.py                # 新增：yfinance 來源
```

```python
class MarketAdapter(Protocol):
    code: str                      # 'tw' | 'us'
    meta: MarketMeta               # 幣別、單位、交易所、時區、收盤時間
    metrics: list[Metric]          # 見 3.2

    def normalize_symbol(self, raw: str) -> str: ...
    def validate_symbols(self, symbols: list[str]) -> dict[str, SymbolInfo]: ...
    # 回傳 {date_key: {欄位: 值}} 的巢狀 dict，與現有 JSON 格式完全一致
    def fetch(self, symbols: list[str], months: int, progress) -> dict[str, dict]: ...
    def session_state(self, now: datetime) -> str:   # 'pre' | 'open' | 'post' | 'closed'
        ...
```

`MarketMeta` 內容：

| 欄位 | TW | US |
| :--- | :--- | :--- |
| `label` | 台股 | 美股 |
| `exchange` | `TWSE` | `NASDAQ` / `NYSE`（逐檔） |
| `currency` / `currency_symbol` | `TWD` / `NT$` | `USD` / `$` |
| `price_decimals` | 2 | 2 |
| `lot_size` / `volume_unit_label` | 1000 / `張` | 1 / `股` |
| `amount_unit_label` | `萬元` | `百萬美元` |
| `timezone` | `Asia/Taipei` | `America/New_York` |
| `sessions` | `09:00–13:30` | `04:00–09:30 pre` / `09:30–16:00` / `16:00–20:00 post` |
| `symbol_pattern` | `^\d{4,6}[A-Z]?$` | `^[A-Z][A-Z.\-]{0,5}$` |
| `price_adjusted` | `false`（TWSE 原始價，未還原權值） | `true`（yfinance auto_adjust，已還原分割與配息） |
| `up_down_convention` | 紅漲綠跌 | 綠漲紅跌 |

> **已知不對稱（需在 UI 標註）**：台股 JSON 存未還原價，美股存還原價，
> 否則 NVDA 2024 年 10:1 分割會讓 K 線出現斷崖。美股 K 線標題旁顯示「已還原權值」小標。

### 3.2 ② Metric Registry（取代硬編碼的 KPI 與分頁）

雛形的核心主張：**指標盤與分頁組成不該寫死在元件裡，而該由 registry 決定**。
每個指標宣告自己屬於哪個市場、更新頻率多快、要不要進指標盤、歸屬哪個分頁：

```python
@dataclass(frozen=True)
class Metric:
    key: str              # 'institutional_total'
    label: str            # '三大法人合計'
    unit: str | None      # '張'
    frequency: Frequency  # daily | biweekly | quarterly | realtime
    markets: list[str]    # ['tw']
    source: str           # 'T86'
    tile: bool            # 是否進指標盤（最多 5 格）
    panel: str | None     # 'institutional' | 'margin' | 'short' | 'holders' | None
    tone: str | None      # 'signed' 代表要依正負套 --up/--down
```

**指標支援矩陣**（對應雛形〈指標支援矩陣〉章節）：

| 指標 | 台股 | 美股 | 更新頻率 | 加入美股後的處理 |
| :--- | :---: | :---: | :--- | :--- |
| OHLC ／ 成交量 | ✓ | ✓ | 每日 | 共用主圖 |
| 三大法人買賣超 | ✓ | — | 每日 | 美股不渲染此分頁 |
| 估算買賣超金額 | ✓ | — | 每日 | 同上 |
| 融資 ／ 融券餘額 | ✓ | — | 每日 | 同上 |
| 券資比 | ✓ | — | 每日 | 同上 |
| Short Interest ／ % of float | — | ✓ | **雙週** | 美股專屬分頁，標記資料延遲 |
| Days to Cover | — | ✓ | **雙週** | 同上 |
| 13F 機構持股 | — | ✓ | **每季** | 季度長條圖，非時間序列 |
| 盤前 ／ 盤後價 | — | ✓ | **即時** | 身分列狀態徽章（見 6.4 的可行性但書） |

`frequency` 不是註解而是渲染指令：
非 `daily` 的指標在指標盤標籤旁顯示 <kbd>雙週</kbd> / <kbd>季</kbd> 徽章，
其時間序列以**階梯線（step line）**而非平滑折線繪製——線在兩次結算之間維持水平是資料本質，不是圖畫壞了。

### 3.3 ③ Display Contract

前端從後端拿到三樣東西就足以完整渲染，不需要任何 `if (market === 'tw')`：

* `meta` — 幣別符號、單位、交易所、時區、`price_adjusted`
* `metrics` — 這檔股票有哪些指標（含 `frequency`、`tone`、`panel` 歸屬）
* 資料本身 — 不支援的指標**鍵不存在或為 `null`**，絕不補零

---

## 4. 資料層設計

### 4.1 目錄分層與相容

```
backend/data/
├── tw/
│   ├── 2330.json
│   └── _no_trading_days.json
├── us/
│   ├── GOOGL.json
│   ├── NVDA.json
│   └── TSLA.json
└── _symbols.json            # 代號 → 市場／交易所／證券類型 的權威索引
```

* **一次性搬移**：`backend/scripts/migrate_data_layout.py` 把現有 `data/*.json` 移到 `data/tw/`，
  並產生 `_symbols.json`。腳本需 idempotent（重跑不出錯）。
* **讀取相容**：`stock_json_path(symbol, market)` 先找 `data/{market}/{symbol}.json`，
  找不到再退回舊路徑 `data/{symbol}.json`，確保搬移前後都能跑。

### 4.2 `_symbols.json` 索引

`exchange` 與 `security_type` 是雛形身分列徽章（`TWSE · ETF`、`NASDAQ · 普通股`）的資料來源：

```json
{
  "0050": { "market": "tw", "name": "元大台灣50", "exchange": "TWSE",   "security_type": "ETF" },
  "2330": { "market": "tw", "name": "台積電",      "exchange": "TWSE",   "security_type": "普通股" },
  "NVDA": { "market": "us", "name": "NVIDIA Corporation", "exchange": "NASDAQ", "security_type": "普通股" },
  "SPCX": { "market": "us", "name": null, "status": "unresolved", "checked_at": "2026-08-09" }
}
```

> **生命週期**：`_symbols.json` 在 MySQL 上線前作為標的索引的 source of truth；
> 資料庫導入後由 `symbols` 表取代，屆時此檔案可作為初始化種子或移除。

### 4.3 市場判定 `resolve_market(symbol, hint=None)`

判定順序：**URL／API 明示的 market → `_symbols.json` 索引 → `symbol_pattern` 正則推斷 → 預設 `tw`**。
新網址格式（見 8.3）一律明示 market，正則推斷只用於處理舊網址與 API 相容呼叫。

### 4.4 JSON 欄位統一改用英文鍵名

台股與美股的日線 JSON **統一使用英文鍵名**，消除「美股資料用中文鍵」的反直覺問題，
也為未來擴充第三市場（港股、日股等）奠定基礎。

**標準鍵名定義**：

```json
{
  "2026-08-08": {
    "name": "NVIDIA Corporation",
    "open": 182.5, "high": 185.2, "low": 181.0, "close": 184.3,
    "volume": 152340000,
    "amount": 28076000000
  }
}
```

台股 JSON 除上述共用鍵外，另含台股專屬欄位：

```json
{
  "2026-08-08": {
    "name": "台積電",
    "open": 1050.0, "high": 1065.0, "low": 1045.0, "close": 1060.0,
    "volume": 25478000, "amount": 2698000000, "trades": 48592,
    "foreign_buy_sell": 3200, "trust_buy_sell": 850, "dealer_buy_sell": -120,
    "institutional_total": 3930, "institutional_amount_est": 8195,
    "margin_balance": 12450, "short_balance": 320
  }
}
```

**欄位映射（Field Mapping）**：每個 Market Adapter 提供 `field_map` 將資料源的原始欄位名對應到標準鍵名。
台股 adapter 的 `field_map` 負責將 TWSE 回傳的中文欄位（如 `"收盤價"` → `"close"`）轉換為標準鍵名，
轉換在 `fetch()` 寫入 JSON 時一次完成：

```python
# markets/tw.py
FIELD_MAP = {
    "股票名稱": "name", "開盤價": "open", "最高價": "high",
    "最低價": "low", "收盤價": "close",
    "成交股數(股)": "volume", "成交金額(元)": "amount", "成交筆數(筆)": "trades",
    "外資買賣超(張)": "foreign_buy_sell", "投信買賣超(張)": "trust_buy_sell",
    "自營商買賣超(張)": "dealer_buy_sell", "合計買賣超(張)": "institutional_total",
    "估算買賣超金額(萬元)": "institutional_amount_est",
    "融資餘額(張)": "margin_balance", "融券餘額(張)": "short_balance",
}
```

**現有聚合器的改寫**：`stock_service.py` 的 `SUM_FIELDS`、`END_FIELDS` 等常數改用英文鍵名。
由於改動集中在常數定義，聚合邏輯（`.get(f, 0)`）本身無須變動。

**遷移**：Phase 1 的 `migrate_data_layout.py` 在搬移 `data/*.json` → `data/tw/` 的同時，
一併將既有 JSON 的中文鍵名轉換為英文鍵名。腳本保持 idempotent（已是英文鍵的檔案跳過）。

> 低頻資料（Short Interest、13F）**不塞進日線 JSON**，另存
> `data/us/_short_interest/{symbol}.json`、`data/us/_holders/{symbol}.json`，
> 各自帶 `settlement_date` / `quarter` 與 `fetched_at`，避免把雙週／季資料偽裝成日資料。

---

## 5. 設定層 (`.env` 與 `config.py`)

```ini
# 台股追蹤代號（沿用舊變數名，向後相容）
STOCK_CODES=0050,2330,2317,006208,1101,1760
# 美股追蹤代號
US_STOCK_CODES=GOOGL,NVDA,SPCX,TSLA
MONTHS_RANGE=3
# 啟用的市場（Feature Flag，可隨時移除 us 以關閉美股功能）
ENABLED_MARKETS=tw,us
```

```python
MARKET_ENV_KEYS = {"tw": "STOCK_CODES", "us": "US_STOCK_CODES"}
DEFAULT_STOCKS = {"tw": ["0050", "2330", "006208", "2317"],
                  "us": ["GOOGL", "NVDA", "SPCX", "TSLA"]}

def get_enabled_markets() -> list[str]:
    """回傳啟用的市場清單，可透過 .env 隨時開關。"""
    return os.getenv("ENABLED_MARKETS", "tw").split(",")

def get_target_stocks(market: str | None = None) -> list[str] | dict[str, list[str]]: ...
def save_target_stocks(stocks: list[str], market: str) -> None: ...
```

不帶參數時回傳 `{"tw": [...], "us": [...]}`；帶 `market` 時回傳該市場清單。
呼叫端只有 4 處（`stocks.py`、`fetch.py`、`fetcher.py`、`stock_service.py`），改動可控。

**Feature Flag 機制**：`ENABLED_MARKETS` 控制前端 `GET /markets` 只回傳啟用的市場。
如果美股上線後出現問題，只要將 `.env` 改為 `ENABLED_MARKETS=tw` 並重啟，
即可立即關閉美股功能而不影響台股，無需回滾程式碼。

---

## 6. 美股資料源選型

雛形把四類美股指標畫在同一張圖上，但它們的取得成本差距很大，**必須分開評估**：

### 6.1 OHLCV（每日）— yfinance ✅ 低成本

| 方案 | 免費額度 | 優缺點 |
| :--- | :--- | :--- |
| **yfinance（建議）** | 無金鑰、無硬性額度 | 一次呼叫批次抓 4 檔 3 個月，秒級完成；非官方 API，偶有中斷 |
| Alpha Vantage | 25 次/日 | 需金鑰；抓 4 檔 + 補歷史很快用完 |
| Finnhub | 60 次/分 | 需金鑰；免費方案不含完整歷史日線 |
| Stooq CSV | 無 | 極簡但無公司名稱、無成交值 |

```python
df = yf.download(symbols, period=f"{months}mo", interval="1d",
                 group_by="ticker", auto_adjust=True, threads=True)
```

> 美股**不需要** `_no_trading_days.json`——yfinance 只回傳實際交易日；
> 台股那套「探測非交易日並快取」是為了避開 TWSE 的空回應，美股沒有這個問題。

### 6.2 Short Interest ／ Days to Cover（雙週）— ⚠️ 分兩段做

`yfinance` 的 `Ticker.info` 只給**當期快照**（`sharesShort`、`shortRatio`、`shortPercentOfFloat`），
**沒有歷史序列**。而雛形的「空方部位」分頁畫的是 63 天的階梯線，需要歷史。因此拆成兩段：

* **6.2a 指標盤方塊（快照）** — yfinance `info`，成本近乎為零，可與 OHLCV 同批完成。
  這已足以支撐雛形指標盤中的 `Short Interest` 與 `Days to Cover` 兩格（含 <kbd>雙週</kbd> 徽章）。
* **6.2b 空方部位分頁（歷史階梯線）** — 需 FINRA 統一短額報告或 Nasdaq 的 per-symbol 短額 API，
  兩者皆為免費但需另寫解析與回補邏輯。**只有一個資料點時不要開這個分頁**，
  否則會出現一條只有單點的「時間序列」。

### 6.3 13F 機構持股（每季）— ⚠️ 分兩段做

`yfinance` 的 `Ticker.major_holders` 提供 `heldPercentInstitutions` 單一百分比快照，
`institutional_holders` 提供當期前十大持有人表格，**都不是雛形畫的 5 季長條圖**。

* **6.3a 指標盤方塊（快照）** — yfinance，成本低，含 <kbd>季</kbd> 徽章。
* **6.3b 機構持股分頁（5 季長條圖）** — 需自行從 SEC EDGAR 逐季彙總 13F，或接付費源。
  這是**獨立且不小的工程**，不應綁進雙市場切換的交付範圍。

### 6.4 盤前／盤後價（即時）— ⚠️ 架構外的東西

雛形身分列的狀態徽章寫「盤後 · 紐約 16:00 ET」，矩陣把盤前／盤後價標為「即時」。
但目前整套系統是**每日批次寫 JSON**，沒有任何即時報價路徑。因此拆解為：

* **可以做（Phase 1 就做）**：狀態徽章本身。`session_state(now)` 純粹用
  `zoneinfo` 依市場時區與交易時段計算「盤前／盤中／盤後／收盤」，**不需要任何行情資料**。
* **不在本次範圍**：盤前／盤後的實際價格。需要新增即時報價通道（WebSocket 或短輪詢），
  與現行批次架構是兩件事，建議另立提案。

---

## 7. 後端 API 契約

### 7.1 新增端點

**`GET /api/v1/markets`** — 市場切換器與 metric registry 的資料來源：

```json
{ "success": true, "data": [
  { "code": "tw", "label": "台股", "exchange": "TWSE",
    "currency": "TWD", "currency_symbol": "NT$", "lot_size": 1000,
    "volume_unit_label": "張", "price_adjusted": false,
    "session_state": "closed", "timezone": "Asia/Taipei",
    "panels": ["institutional", "margin", "table"],
    "tracked_count": 6 },
  { "code": "us", "label": "美股", "exchange": "NASDAQ",
    "currency": "USD", "currency_symbol": "$", "lot_size": 1,
    "volume_unit_label": "股", "price_adjusted": true,
    "session_state": "post", "timezone": "America/New_York",
    "panels": ["short", "holders", "table"],
    "tracked_count": 4 }
]}
```

**`GET /api/v1/search?q=&limit=10`** — Ctrl K 全域搜尋（雛形〈單一切換入口〉）：
跨市場、代號與名稱模糊比對，回傳**依市場分組**的結果，每筆含 `market` / `symbol` / `name` / `exchange`。
第一階段可純用 `_symbols.json` 做記憶體內比對，不需要外部搜尋服務。

| 參數 | 預設 | 說明 |
| :--- | :--- | :--- |
| `q` | （必填） | 搜尋關鍵字，長度 < 1 時回空陣列 |
| `limit` | `10` | 每組（台股／美股）最多回傳筆數，上限 `50` |
| `market` | `all` | 限制搜尋範圍，可為 `tw`、`us` 或 `all` |

### 7.2 既有端點加上 `market` 參數（全部 optional，缺省行為不變）

| 端點 | 變更 |
| :--- | :--- |
| `GET /stocks` | `?market=tw\|us\|all`（預設 `all`），回傳項目加 `market` / `exchange` / `security_type` / `currency` / `lot_size` |
| `GET /stocks/tracked` | `?market=`；不帶時回傳 `{"tw": [...], "us": [...]}` |
| `POST /stocks/tracked` | body 加 `market`（缺省用 `resolve_market()` 推斷） |
| `DELETE /stocks/tracked/{id}` | `?market=` |
| `GET /stocks/heatmap` | `?market=`（預設 `all`）；回傳項目加 `market` |
| `GET /stocks/{id}/chart-data` | `?market=`；載荷新增 `market` / `meta` / `metrics` 三個頂層欄位 |
| `GET /stocks/{id}` | 同上 |
| `POST /fetch/trigger` | body 加 `market`；不帶時依 `stocks` 逐檔 `resolve_market()` 分組派工 |

### 7.3 `chart-data` 載荷擴充（不刪不改任何既有欄位）

```jsonc
{
  "stock_id": "NVDA", "stock_name": "NVIDIA Corporation",
  "market": "us",                                   // ← marketColors.js 已在等這個欄位
  "meta": { "exchange": "NASDAQ", "security_type": "普通股",
            "currency_symbol": "$", "volume_unit_label": "股",
            "lot_size": 1, "price_adjusted": true,
            "timezone": "America/New_York", "session_state": "post" },
  "metrics": [                                      // ← 驅動指標盤與分頁，取代前端硬編碼
    { "key": "close",          "label": "Close",          "unit": null,       "frequency": "daily",     "tile": true, "tone": "signed" },
    { "key": "volume",         "label": "成交量",          "unit": "M",        "frequency": "daily",     "tile": true },
    { "key": "short_interest", "label": "Short Interest", "unit": "% float",  "frequency": "biweekly",  "tile": true, "panel": "short" },
    { "key": "days_to_cover",  "label": "Days to Cover",  "unit": "天",       "frequency": "biweekly",  "tile": true, "panel": "short" },
    { "key": "inst_held",      "label": "13F 機構持股",    "unit": "%",        "frequency": "quarterly", "tile": true, "panel": "holders" }
  ],
  "period": "daily", "months": 3,
  "dates": [...], "kline": [...],
  "volume": { "shares": [...], "amount": [...] },   // ← 新增，兩個市場都有
  "latest_summary": { ... },
  "institutional": null,                            // 美股為 null（不是補 0）
  "margin": null,
  "records": [...]
}
```

**關鍵約定**：不支援的能力回傳 `null` 而非零陣列。前端以 `metrics` 決定渲染、以 `null` 做防呆，
兩層保護避免畫出一整排 0 的假圖。Code review 需檢查是否有 `|| []` 把 `null` 洗成空陣列後畫出空圖。

### 7.4 抓取任務併發

`FetchStatusManager` 目前是單例、單一全域鎖。雙市場後維持單一鎖（**一次只跑一個抓取任務**），
但快照加上 `market` 欄位，讓前端能顯示「正在同步：美股」。
台股抓取需數分鐘、美股僅數秒；若之後要平行化，再把 `fetch_status` 改為 `dict[market, FetchStatusManager]`
並讓 `/fetch/status` 回傳彙總——第一階段不做，避免前端輪詢邏輯同步改寫。

### 7.5 錯誤回應契約

所有 API 端點採用統一的錯誤回應格式，前端依 `error.code` 決定呈現方式：

```json
{
  "success": false,
  "error": {
    "code": "SYMBOL_NOT_FOUND",
    "message": "找不到代號 XYZZ 的股票資料",
    "details": { "symbol": "XYZZ", "market": "us" }
  }
}
```

**錯誤碼定義**：

| HTTP | `error.code` | 觸發情境 | 前端處理 |
| :--- | :--- | :--- | :--- |
| 404 | `SYMBOL_NOT_FOUND` | 請求的代號不存在 | 顯示「找不到此代號」提示卡片，附搜尋連結 |
| 404 | `MARKET_NOT_FOUND` | 請求的市場代碼無效 | 導向首頁 |
| 400 | `INVALID_MARKET_INDICATOR` | 請求了該市場不支援的指標或分頁 | 顯示「此市場不提供此分析」並提供返回連結 |
| 409 | `FETCH_IN_PROGRESS` | 觸發抓取時已有任務進行中 | Toast 提示「同步進行中，請稍候」 |
| 422 | `SYMBOL_UNRESOLVED` | 代號存在但資料源無法驗證（如 SPCX） | 管理頁顯示警示徽章 |
| 502 | `UPSTREAM_ERROR` | yfinance / TWSE 等外部來源回應異常 | Toast 提示「資料源暫時無法連線」，顯示最後快取資料 |
| 500 | `INTERNAL_ERROR` | 伺服器未預期錯誤 | 通用錯誤頁 |

**前端錯誤狀態元件**：各頁面的錯誤呈現由共用元件 `components/ErrorState.vue` 統一處理，
接收 `error` 物件後依 `code` 渲染對應的圖示、文字與操作按鈕（重試／返回／搜尋），
避免各頁面各自實作不一致的錯誤畫面。

---

## 8. 前端設計

### 8.1 設計 token 與色彩配額

雛形定義了完整的淺／深色 token 組（brass 強調色 + 灰階 + 紅綠語意色），與 repo 現有的
`_common-brass.scss` 同一方向。落地重點是**色彩配額規則**：

| 用途 | 允許的顏色 |
| :--- | :--- |
| 品牌、互動、焦點、選中態 | `--accent`（brass）／`--accent-2` |
| 漲跌、買賣超正負 | `--up` / `--down`（依市場交換） |
| 其他所有圖表、圖示、邊框、標籤 | 灰階（`--ink-2`、`--ink-3`、`--line`） |

這條規則直接刪掉 `StockCharts.vue` / `ChartDetailView.vue` 現有的六種裝飾色
（`#ec4899`、`#06b6d4`、`#f97316`、`#8b5cf6`、`#3b82f6`、`#f59e0b`）與四顆彩色圓球圖示。

> **三大法人的四色堆疊怎麼辦？** 雛形的做法是主視圖只畫**合計買賣超的發散長條圖**
> （依正負套 `--up`／`--down`），外資／投信／自營商的拆解留在明細表格。
> 這樣既守住色彩配額，也讓「今天法人是買是賣」一眼可讀。

### 8.2 `--up` / `--down`：CSS 變數為單一真相

雛形用的是 CSS 變數 + 屬性選擇器，比目前純 JS 的 `marketColors.js` 覆蓋面更廣（表格、邊框、徽章都吃得到）：

```css
[data-market="tw"] { --up: var(--red);   --down: var(--green); }
[data-market="us"] { --up: var(--green); --down: var(--red);   }
```

**建議兩者併用**：CSS 變數是單一真相，`marketColors.js` 改寫為
`getUpDownColor(el)` → 用 `getComputedStyle(el).getPropertyValue('--up')` 讀值供 ECharts 使用
（雛形的 `css('--up')` helper 就是這個做法）。好處是主題切換、市場切換、
未來的「使用者自訂漲跌配色」三者都只需要改 CSS 變數，ECharts 自動跟上。

`data-market` 屬性掛在 `AppLayout.vue` 的根容器上，由全域市場狀態驅動。
由於**同一時間只顯示單一市場**（見 8.6），不需要在個別卡片上分別掛 `data-market`，
整個頁面共用同一組 `--up` / `--down` 即可。

### 8.3 路由：市場成為路徑的一部分

採用雛形的網址設計（**此處推翻本文件初版「維持 `/stock/:id`」的做法**——
明示優於推斷，且 `tab` 也該進網址）：

```
/stock/:market/:symbol?period=daily&range=3m&tab=institutional
```

* 舊網址 `/stock/2330` 由路由守衛 `resolve_market()` 補上市場後 **301 導向** `/stock/tw/2330`。
* `/stock/:market/:symbol/chart/:chartType` 同步調整。
* 使用者若輸入該市場不支援的 `chartType` 或 `tab`（例如 `/stock/us/NVDA?tab=margin`），
  顯示「此市場不提供此分析」並提供返回連結，而非空白圖表。

### 8.4 全域市場狀態 `composables/useMarket.js`

仿 `useCrawlerStatus.js` 的模組級單例：

```js
const currentMarket = ref(localStorage.getItem('mystock.market') || 'tw');
const markets = ref([]);          // 來自 GET /markets
export function useMarket() { return { currentMarket, markets, setMarket, marketMeta, metrics }; }
```

**狀態優先權**：當 URL path 與 localStorage 不一致時（例如使用者收到美股連結但上次用台股），
以 **URL path > localStorage > 預設 `'tw'`** 為優先順序。
在 `router.beforeEach` 中同步 `currentMarket` 與 URL 的 `:market` 參數，確保兩者始終一致：

```js
router.beforeEach((to) => {
  const { setMarket } = useMarket();
  if (to.params.market) setMarket(to.params.market, { syncUrl: false });
});
```

切換市場時：重新載入該市場標的清單 → `[` `]` 快捷鍵循環範圍自動縮到當前市場 →
若目前停在他市場個股頁則導向該市場第一檔。

### 8.5 頂部列：市場切換 + Ctrl K 搜尋

雛形指出目前**同一視窗有兩個個股切換器**（頂部 `select` + 頁內卡片）。頁內那個已移除，
剩下的頂部 `select` 改為 omnibox，並在**右側新增市場切換按鈕**：

```
┌─────────────────────────────────────────────────────────────────────┐
│ M MyStock   [ 搜尋代號或名稱…     Ctrl K ]    ● 收盤  [台股|美股]  王 │
└─────────────────────────────────────────────────────────────────────┘
```

**市場切換按鈕**（右上角）：
* 採用 segmented control 樣式（`台股` / `美股` 雙按鈕），與聚合週期切換器視覺風格一致。
* 點擊切換後呼叫 `setMarket()`，全域狀態、`data-market` 屬性、`localStorage` 同步更新。
* 切換觸發：① 首頁熱力圖重新載入對應市場的股票 ② omnibox 搜尋範圍縮到當前市場
  ③ `[` `]` 快捷鍵循環範圍同步 ④ 若當前在他市場個股頁，導向新市場第一檔。
* 按鈕位於 `AppTopbar.vue`，全站任何頁面都能一鍵切換，不限於首頁。

**Omnibox**（Ctrl K）：
* `Ctrl/⌘ K` 開啟，結果依市場分組（台股一組、美股一組），代號與名稱模糊比對。
* 打 `/search?q=`（見 7.1）；第一階段可先用前端已載入的清單做本地比對再改打後端。
* 選擇結果後自動切換到對應市場。

**狀態徽章**：
* 身分列的 `● 收盤 / 盤後` 狀態徽章由 `meta.session_state` 驅動（見 6.4），顯示**當前所選市場**的交易狀態。

### 8.6 各頁面調整

| 檔案 | 調整 |
| :--- | :--- |
| `HeatmapDashboard.vue` | ①僅顯示當前市場的股票卡片（由全域 `currentMarket` 驅動，不再有頁面級篩選） ②`getPriceColorClass()`、`getCardBorderClass()`、`getSparklineOption()` **改用 `--up`/`--down`**（全頁共用同一市場的漲跌色） ③卡片加交易所徽章、幣別符號 |
| `StockDashboard.vue` | ① 指標盤五格改由 `metrics` 陣列動態組裝（含 `frequency` 徽章）② 明細表格欄位由 `metrics` 決定 ③ `$`／`張`／`萬元` 改走 8.7 的 formatter ④ `exportCSV()` 表頭沿用當前欄位組成 ⑤ 身分列加交易所／證券類型徽章 |
| `StockCharts.vue` | ① 主圖改為 **K 線 + 下方成交量**（雛形的 `drawCandles` 佈局）② 分頁由 `meta.panels` 產生：台股「法人籌碼／信用交易／明細資料」，美股「空方部位／機構持股／明細資料」③ 同分頁內圖表以 ECharts `connect` 連動游標 ④ `activeTab` 寫回 URL `?tab=` |
| `ChartDetailView.vue` | `chartTabs` 依 `metrics` 過濾；套用色彩配額 |
| `chartExplanations.js` | 改為 `{ common: {...}, tw: {...}, us: {...} }` 三層，`kline`／`volume` 放 `common`；新增 `short-interest`、`days-to-cover`、`holders` 說明。分頁底部說明改為**收合、點開才展開** |
| `stockApi.js` | 各方法加 `market` 參數；新增 `getMarkets()`、`search(q)` |
| `AppTopbar.vue` | `select` 改 omnibox；**右側加市場切換 segmented control**（`台股` / `美股`）；加 `session_state` 徽章 |
| `AppMenu.vue` | 「選股與圖表分析」的固定連結 `/stock/2330` 改為依當前市場動態產生 |
| `AppLayout.vue` | 根容器掛 `:data-market="currentMarket"` |
| `components/ErrorState.vue` | **新增**：統一錯誤狀態元件，依 `error.code` 渲染圖示、文字與操作按鈕（見 7.5） |

### 8.7 格式化集中出口 `utils/format.js`

雛形的「格式化集中」原則，新增單一出口取代散落各處的字面量：

```js
formatPrice(value, meta)    // → 'NT$102.85' / '$232.14'
formatVolume(value, meta)   // → '24,879 張' / '48.2M 股'
formatAmount(value, meta)   // → '+8,195 萬元' / '$2.8B'
formatChange(diff, pct)     // → '+0.80 (+0.78%)'
```

所有幣別、單位、小數位、千分位一律由此產生，元件內不得再出現 `$`、`張`、`萬元` 字面量。

---

## 9. 分階段實作

| Phase | 內容 | 是否需要對方配合 |
| :--- | :--- | :--- |
| **0 · 前端可獨立先做** | ①`--up`/`--down` CSS 變數化，`HeatmapDashboard.vue` 接上 ②色彩配額：刪掉六種裝飾色與彩色圓球 ③`tab` 寫回 URL ④`utils/format.js` 建立並替換字面量 ⑤`components/ErrorState.vue` 建立 | 不需後端 |
| **1 · 後端市場抽象** | 建 `backend/markets/`，TWSE 邏輯整段搬進 `tw.py`（含 `FIELD_MAP` 中文→英文鍵名轉換）；`config.py` 加 `US_STOCK_CODES` + `ENABLED_MARKETS`；`migrate_data_layout.py` 搬 `data/*.json` → `data/tw/` **並轉換鍵名為英文**；`stock_service.py` 欄位常數改英文鍵名 | 前端零變化 |
| **2 · 美股資料管線** | `requirements.txt` 加 `yfinance`；實作 `markets/us.py` 的 `fetch()` / `validate_symbols()` / `session_state()`；跑一次抓取產出 `data/us/*.json`（英文鍵名）；SI 與 13F 快照（6.2a／6.3a） | — |
| **3 · API 契約** | 各端點加 `market`；新增 `GET /markets`、`GET /search`；`chart-data` 補 `market`／`meta`／`metrics`／`volume`；統一錯誤回應格式（見 7.5） | — |
| **4 · 前端雙市場** | `useMarket.js`（含 URL > localStorage 優先權）；`AppTopbar.vue` 右上角市場切換 segmented control；路由改 `/stock/:market/:symbol` + 301；指標盤與分頁改由 `metrics` 驅動；`frequency` 徽章；ECharts `connect` 游標連動 | 依賴 Phase 3 |
| **5 · 介面優化收尾** | Ctrl K omnibox（打 `/search`）；`session_state` 徽章；圖表說明改收合；美股「已還原權值」標註 | 依賴 Phase 3 |
| **6 · 低頻資料歷史（獨立提案）** | SI 歷史階梯線（FINRA／Nasdaq，6.2b）；13F 五季長條圖（SEC EDGAR，6.3b） | 各自為獨立工程 |
| **7 · 排程（併入既有提案）** | 依 [`mysql_migration_and_scheduling_design.md`](./mysql_migration_and_scheduling_design.md) 第 5 節，加入美股收盤規則：台灣時間隔日 04:00／05:00，**夏令時每年變動兩次**，須以 `zoneinfo` 動態計算，不可寫死小時數 | — |

**Phase 0 與 Phase 1 可並行**（一個純前端、一個純後端，無交集）。
Phase 6 刻意排在最後且標為獨立提案——SI 歷史與 13F 彙總的工程量各自不小於 Phase 1～5 的總和，
不應綁進「雙市場切換」的交付範圍。

---

## 10. 風險與注意事項

| 風險 | 對策 |
| :--- | :--- |
| **`SPCX` 抓不到資料** | `validate_symbols()` 先探測，失敗者寫入 `_symbols.json` 標 `unresolved`，管理頁顯示警示，不阻斷其他標的 |
| **雛形把 SI／13F 畫成時間序列，但免費源只有快照** | 見 6.2／6.3：快照先上指標盤方塊，歷史圖表等資料源到位再開分頁；**只有一個資料點時不要開分頁** |
| **雛形把盤前／盤後價標為「即時」** | 見 6.4：狀態徽章可做（純時區計算），實際價格需要即時報價通道，不在本次範圍 |
| **股票分割造成 K 線斷崖** | 美股用 `auto_adjust=True` 存還原價，`meta.price_adjusted` 標示，UI 顯示「已還原權值」 |
| **台股／美股價格還原方式不一致** | 已知且刻意的不對稱，在文件與 UI 標註；未來若要統一，以台股加入除權息還原為方向 |
| **夏令時間** | 美股收盤對應台灣時間會在 04:00／05:00 間切換，一律用 `zoneinfo` 換算 |
| **yfinance 為非官方 API** | 集中在 `markets/us.py` 單一檔案，換源時只改這一支；抓取失敗需寫入 `fetch_status.logs` 而非靜默吞掉 |
| **抓取任務單例鎖** | 第一階段一次只跑一個市場；快照加 `market` 欄位讓 UI 說清楚正在同步誰 |
| **前端硬編色碼殘留** | `HeatmapDashboard.vue` 是唯一還在寫死漲跌色的檔案，列為 Phase 0 必改項 |
| **`metrics` 驅動被繞過** | 不支援的能力回 `null` 而非 `[]`／`0`；review 檢查 `|| []` 是否把 `null` 洗成空陣列 |
| **301 導向遺漏** | 舊網址 `/stock/2330`、`/stock/2330/chart/kline` 都需覆蓋；加入前端路由測試 |

---

## 11. 驗收檢查清單

**資料與 API**

- [ ] 不帶 `market` 參數時，所有既有 API 回應與改動前一致
- [ ] `data/tw/` 搬移後，既有六檔台股頁面完全正常
- [ ] 台股 JSON 鍵名已全部轉為英文（`open`、`close`、`volume` 等），無中文鍵殘留
- [ ] 美股四檔中三檔有資料，`SPCX` 被明確標記而非靜默消失
- [ ] `/api/v1/stocks/NVDA/chart-data` 的 `institutional` 為 `null`、`market` 為 `"us"`
- [ ] `.env` 只需改一行字串即可增減任一市場的追蹤標的
- [ ] API 錯誤回應符合 §7.5 格式（含 `error.code`），前端能正確呈現對應錯誤狀態

**市場切換**

- [ ] 右上角市場切換 segmented control 在所有頁面可見且能正確切換
- [ ] 切換市場後，omnibox 搜尋、`[` `]` 快捷鍵、熱力圖三處清單同步縮到該市場
- [ ] `/stock/2330` 301 導向 `/stock/tw/2330`；`/stock/tw/2330?tab=margin` 重整後仍停在信用交易分頁
- [ ] 直接輸入 `/stock/us/NVDA?tab=margin` 顯示 `ErrorState` 元件提示「此市場不提供此分析」
- [ ] 收到美股連結（URL path = `us`）時，即使 localStorage 為 `tw`，市場仍切換到 `us`
- [ ] `ENABLED_MARKETS=tw` 時，`GET /markets` 只回傳台股，右上角切換按鈕隱藏

**顯示層**

- [ ] 台股模式下上漲卡片為紅色；切換至美股模式後上漲卡片變為綠色
- [ ] 深色／淺色主題切換後，K 線的漲跌色仍正確（驗證 ECharts 有跟上 CSS 變數）
- [ ] 美股個股頁不出現「三大法人」「融資餘額」「券資比」任何欄位、圖表或 CSV 表頭
- [ ] 美股頁面幣別為 `$`、成交量單位為「股」；台股維持 `NT$` 與「張」
- [ ] Short Interest／13F 方塊帶 <kbd>雙週</kbd>／<kbd>季</kbd> 徽章
- [ ] 全域搜尋 `text-red-500`、`text-emerald-500`、`#ef4444`、`#ec4899`、`#06b6d4`、`#f97316`、`#8b5cf6` 在 `src/` 內零命中
- [ ] `$`、`張`、`萬元` 字面量在元件內零命中（只存在於 `utils/format.js`）
- [ ] 同一分頁內的圖表滑鼠游標連動
