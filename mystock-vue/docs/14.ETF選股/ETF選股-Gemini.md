序號,代碼,ETF 名稱,類型分類,配息頻率,主要除息月份,殖利率區間 (歷史年化),收益平準金
1,0050,元大台灣50,市值型,半年配,1月、7月,約 2% ~ 4%,否
2,0056,元大高股息,高股息,季配,1、4、7、10月,約 6% ~ 10%,有
3,00878,國泰永續高股息,高股息/ESG,季配,2、5、8、11月,約 6% ~ 9%,有
4,00919,群益台灣精選高息,高股息,季配,3、6、9、12月,約 9% ~ 11%,有
5,00929,復華台灣科技優息,科技高股息,月配,每月月中,約 7% ~ 10%,有
6,006208,富邦台50,市值型,半年配,7月、11月,約 2% ~ 3.5%,否
7,00713,元大台灣高息低波,低波高股息,季配,3、6、9、12月,約 6% ~ 9%,有
8,00940,元大台灣價值高息,價值高股息,月配,每月月初/中,約 5% ~ 7%,有
9,00939,統一台灣高息動能,動能高股息,月配,每月月底,約 5% ~ 8%,有
10,00881,國泰台灣科技龍頭,科技產業,半年配,2月、8月,約 3% ~ 6%,否
11,0052,富邦科技,科技/半導體,年配,10月,約 1.5% ~ 3%,否
12,00850,元大台灣ESG永續,市值/ESG,季配,2、5、8、11月,約 4% ~ 6%,有
13,00922,國泰台灣領袖50,市值型,半年配,3月、10月,約 4% ~ 6%,有
14,00923,群益台ESG低碳50,市值/低碳,半年配,2月、8月,約 4% ~ 6%,有
15,00918,大華優利高填息30,高填息/高股息,季配,3、6、9、12月,約 8% ~ 11%,有
16,00915,凱基優選高股息30,高股息/低波,季配,3、6、9、12月,約 8% ~ 10%,有
17,00891,中信關鍵半導體,半導體主題,季配,1、4、7、10月,約 4% ~ 6%,有
18,00892,富邦台灣半導體,半導體主題,半年配,1月、7月,約 3% ~ 5%,否
19,00935,野村臺灣新科技50,科技/AI,半年配,3月、9月,約 2.5% ~ 4.5%,有
20,00927,群益半導體收益,半導體高股息,季配,1、4、7、10月,約 6% ~ 8%,有
21,00692,富邦公司治理,市值/ESG,半年配,7月、11月,約 4% ~ 5.5%,否
22,00936,台新臺灣永續高息中小,中小型高股息,月配,每月中旬,約 6% ~ 9%,有
23,00946,群益科技高息成長,科技高股息,月配,每月上旬,約 6% ~ 8%,有
24,00757,統一FANG+,海外科技股票,不配息,無,0% (累積型),否
25,00662,富邦NASDAQ,海外科技股票,不配息,無,0% (累積型),否
26,00830,國泰費城半導體,海外科技股票,年配,1月,約 1% ~ 2.5%,否
27,00679B,元大美債20年,長期美債,季配,1、4、7、10月,約 3.8% ~ 5%,有
28,00687B,國泰20年美債,長期美債,季配,1、4、7、10月,約 3.8% ~ 5%,有
29,00720B,元大投資級公司債,投資級公司債,季配,1、4、7、10月,約 5% ~ 6.5%,有
30,00937B,群益ESG投等債20+,長期投等債,月配,每月中旬,約 6% ~ 6.8%,有



**有的**，抓取台股、美股與 ETF 的配息資料有幾種主流 API 與開放端點可以串接。

配合系統先前的 **「兩段式資料管線 (ELT：API $\to$ 落地 JSON $\to$ PostgreSQL)」** 與物件導向 `Data Provider` 架構，以下推薦三種最適合整合進 Python 系統的資料來源：

---

### 一、 主流配息 API 資料來源比較

| 資料來源 | 支援市場 / 類型 | 特點與優勢 | 取得方式 / 套件 | 費用與限制 |
| --- | --- | --- | --- | --- |
| **1. FinMind API (最推薦台股)** | 台股上市/上櫃/ETF | 提供結構化 JSON，涵蓋除權息日、現金股利、股票股利、除權息結果。格式極乾淨。 | `FinMind` Python 套件或直接呼叫 REST API | 免費註冊即可取得 Token，提供每日請求額度。 |
| **2. TWSE / TPEX 官方 OpenAPI** | 台股上市 / 上櫃 | 官方第一手資料，包含除權除息預告表與計算結果表，完全免費。 | `requests` 呼叫 OpenAPI / 證交所公開端點 | 完全免費，但需注意爬蟲節流（Throttling）限制。 |
| **3. yfinance (美股與全球標的)** | 美股、台股 (代碼加 `.TW`) | 一行指令直接抓出完整歷史配息時間序列 (`Series`)。 | `import yfinance as yf` | 免費開源，抓美股極其穩定，台股建議搭配驗證。 |

---

### 二、 實戰 API 抓取與 JSON 落地範例

#### 1. 使用 FinMind API（台股個股 / ETF 歷史配息）

FinMind 的 `TaiwanStockDividend` 與 `TaiwanStockDividendResult` 資料集非常適合用來追蹤除息日程與現金股利。

```python
import os
import json
import requests
import pandas as pd

def fetch_tw_dividends_finmind(symbol: str, api_token: str = "") -> str:
    """
    從 FinMind 抓取個股/ETF歷史配息資料，並落地為 JSON
    """
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockDividend",
        "data_id": symbol,
        "start_date": "2015-01-01",
        "token": api_token  # 填入免費申請的 Token
    }
    
    response = requests.get(url, params=params, timeout=10)
    res_data = response.json()
    
    if res_data.get("msg") != "success" or not res_data.get("data"):
        print(f"[{symbol}] 抓取配息失敗或無資料")
        return ""
    
    # 落地為原始 JSON 緩衝檔 (配合系統 ELT 設計)
    save_dir = "data/raw/dividends"
    os.makedirs(save_dir, exist_ok=True)
    file_path = f"{save_dir}/{symbol}_dividends.json"
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(res_data["data"], f, ensure_ascii=False, indent=2)
        
    print(f"✅ [{symbol}] 配息資料已落地: {file_path}")
    return file_path

```

#### 2. 使用 yfinance（美股個股 / 台美 ETF）

若是分析美股（如 AAPL、SPY）或快速取得歷史配息，使用 `yfinance` 最為簡便：

```python
import os
import json
import yfinance as yf
import pandas as pd

def fetch_us_dividends_yfinance(symbol: str) -> str:
    """
    從 Yahoo Finance 抓取配息紀錄並落地成 JSON
    """
    # 台股加 .TW (如 0050.TW / 2330.TW)，美股直接輸入代碼
    ticker_symbol = f"{symbol}.TW" if symbol.isdigit() else symbol
    ticker = yf.Ticker(ticker_symbol)
    
    # dividends 回傳 Pandas Series，Index 為 Date，Value 為配息金額
    div_series = ticker.dividends
    
    if div_series.empty:
        print(f"[{symbol}] 查無配息紀錄")
        return ""
    
    # 轉為標準字典清單格式
    div_df = div_series.reset_index()
    div_df.columns = ["date", "dividend"]
    div_df["date"] = div_df["date"].dt.strftime("%Y-%m-%d")
    records = div_df.to_dict(orient="records")
    
    # 落地 JSON
    save_dir = "data/raw/dividends"
    os.makedirs(save_dir, exist_ok=True)
    file_path = f"{save_dir}/{symbol}_yf_dividends.json"
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
        
    print(f"✅ [{symbol}] Yahoo 配息資料已落地: {file_path}")
    return file_path

```

---

### 三、 系統架構整合建議

1. **Provider 介面擴充**：在系統的 `providers/base.py` 中新增 `@abstractmethod def fetch_dividends(...)` 抽象方法，由 `FinMindProvider` 或 `YahooProvider` 分別實作。
2. **入庫與記帳串接**：將落地的配息資料解析後，可直接匯入我們先前規劃的 `etf_dividend_history`（ETF 歷史除息表）或個人記帳模組中的 `user_transactions`（作為 `action='DIVIDEND'` 的自動對帳來源）。

為配合您現有的 **Python (FastAPI + Docker + PostgreSQL / Parquet) + Vue 前端** 系統架構，為您規劃專屬的 **「ETF 選股與分析模組（ETF Screener & Analytics Module）」**。

ETF 的選股邏輯與個股不同，核心差異在於 **「成分股穿透（Holdings Look-Through）」**、**「折溢價套利/過熱（NAV Premium/Discount）」**、**「配息組成（54C / 平準金）」** 與 **「費用率損耗（Expense Drag）」**。

---

### 一、 ETF 選股模組架構與功能清單

```
┌──────────────────────────────────────────────────────────────────┐
│                      ETF 選股與分析模組架構                       │
├─────────────────┬──────────────────┬──────────────┬──────────────┤
│ 1. 基礎屬性濾網  │ 2. 配息與現金流  │ 3. 估值與成本│ 4. 成分股穿透│
│ (Universe)      │ (Dividend Flow)  │ (NAV/Expense)│ (Look-Through│
├─────────────────┼──────────────────┼──────────────┼──────────────┤
│ 5. 動態策略清單  │ 6. 組合模擬回測  │ 7. 戰情室 UI │ 8. 排程與儲存│
│ (Presets)       │ (Portfolio Sim)  │ (Vue Web)    │ (Pipeline)   │
└─────────────────┴──────────────────┴──────────────┴──────────────┘

```

#### 1. ETF 標的池與屬性篩選 (Universe & Categorization)

* **多層次類型分類篩選**：
* **市場類型**：台股原型（0050、0056）、美股/海外股票型（00757、00662）、債券型（00679B、00937B）、期貨型、槓桿/反向型。
* **主題標籤**：市值型、高股息型、ESG/低碳、半導體/AI 科技主題型。


* **規模與流動性門檻濾網**：
* **AUM 資產規模下限**（例如：排除規模 $< 10$ 億元標的，防範清算下市風險）。
* **日成交量 / 成交金額門檻**（例如：日均量 $> 1,000$ 張，排除流動性不足的冷門標的）。
* **受益人數增長率追蹤**（集保戶週/月增減率，觀測散戶與資金流向）。



#### 2. 配息能力與收益品質濾網 (Dividend & Income Screener)

* **配息頻率篩選**：支援單選/複選「月配息」、「季配息」、「半年配」、「年配息」或「不配息（累積型）」。
* **年化殖利率區間篩選**：
* 近 1 年滾動累計年化殖利率（Rolling 12M Yield）。
* 最新單次預估年化殖利率（近一次配息金額 $\times$ 年配次數 / 除息前一日收盤價）。


* **填息能力評估**：
* 歷史平均填息天數（如：$\le 30$ 天）。
* 歷史填息成功率（如：近 8 季填息率 $\ge 80\%$）。


* **配息來源健康度拆解**：
* 股利所得（54C）佔比。
* 收益平準金佔比（檢視是否有過度拿投資人本金配息）。
* 資本公積與財產交易所得（76T）佔比。



#### 3. 評價、成本與折溢價監控 (Valuation & Cost)

* **即時/歷史折溢價監控（Premium/Discount）**：
* 篩選當前市價與淨值（NAV）偏差幅度（如：篩選折價 $<-0.5\%$ 的潛在撿便宜標的，排除溢價 $>+1\%$ 的追高過熱標的）。


* **總內扣費用率（Total Expense Ratio）**：
* 篩選經理費 + 保管費 + 換股交易摩擦成本總計（如：市值型要求總費用 $< 0.4\%$）。


* **追蹤誤差與偏離度（Tracking Error）**：
* 追蹤指數與 ETF 淨值變動的年化標準差。



#### 4. 成分股穿透與重疊度濾網 (Constituent Look-Through)

* **前 10 大成分股權重集中度（Top 10 Concentration）**：
* 如：單一個股權重上限過濾（台積電 2330 佔比 $\le 30\%$ 或 $\ge 40\%$）。


* **跨 ETF 成分股重疊矩陣（Overlap Matrix）**：
* 計算選定 ETF 組合之間的加權重疊比例，防止看似分散實則重複重押相同個股（如：0050 與 006208 相關度 $>95\%$）。


* **特定個股穿透曝險度**：
* 輸入特定個股（如：2330 台積電、2454 聯發科），篩選出所有持有該個股且佔比大於 $5\%$ 的 ETF。



#### 5. 技術與動能指標濾網 (Momentum & Trend)

* [cite_start]**均線多空排列**：ETF 價格處於日/週線 20MA、60MA 之上。
* **含息總報酬率（Total Return）排名**：近 1 月、近 3 月、近 1 年、近 3 年含息累積報酬率（避免只看殖利率而忽視價差虧損）。
* **夏普值（Sharpe Ratio）與波動度**：依據年化波動度與最大回撤（MDD）篩選風險報酬比最佳的標的。

---

### 二、 系統內建推薦 ETF 選股策略預設範本 (Strategy Presets)

系統可在設定檔中預載以下 5 種經典選股策略，供使用者一鍵套用或微調：

| 策略範本名稱 | 核心選股條件組合 | 目標族群 / 投資情境 |
| --- | --- | --- |
| **1. 高息穩健現金流** | `配息頻率 IN (月配, 季配)` + `近1年殖利率 > 6.5%` + `歷史填息率 > 75%` + `平準金佔比 < 40%` | 退休族、存股領息族 |
| **2. 市值成長低費用** | `類型 = 市值型` + `總費用率 < 0.4%` + `規模 > 100億` + `站上 60MA 季線` | 長期定期定額、指數化被動投資 |
| **3. 折價撿便宜套利** | `市價折價幅度 < -0.8%` + `流動性 > 2000張` + `排除槓桿/反向型` | 偏離均值回歸的短線交易者 |
| **4. 產業動能突破** | `主題 = 科技/半導體/AI` + `近3月含息報酬 前 15%` + `成交量突破 5日均量 1.5倍` | 順勢波段、題材動能交易 |
| **5. 股債雙存平衡** | `股票 ETF (0050/00878) + 長期美債 (00679B/00687B)` + `負相關性檢驗` | 降低總資產波動的資產配置 |

---

### 三、 模組設定檔結構設計 (config/etf_strategies.yaml)

遵循系統先前的 **「設定檔驅動（Configuration-Driven）」** 原則，ETF 篩選條件以 YAML 管理：

```yaml
# config/etf_strategies.yaml
etf_screeners:
  - id: "stable_high_dividend"
    name: "高息穩健填息策略"
    enabled: true
    universe: "tw_all_etfs"
    filters:
      - field: "dividend_frequency"
        operator: "IN"
        value: ["monthly", "quarterly"]
      - field: "dividend_yield_1y"
        operator: ">="
        value: 0.065   # 年化殖利率 >= 6.5%
      - field: "fill_rate"
        operator: ">="
        value: 0.75    # 填息成功率 >= 75%
      - field: "aum"
        operator: ">="
        value: 5000000000 # 規模 >= 50 億
      - field: "premium_discount_pct"
        operator: "<="
        value: 0.005   # 溢價不超過 0.5%

  - id: "low_cost_growth"
    name: "低成本市值長線成長"
    enabled: true
    universe: "tw_all_etfs"
    filters:
      - field: "category"
        operator: "=="
        value: "broad_market"
      - field: "expense_ratio"
        operator: "<="
        value: 0.004   # 總費用率 <= 0.4%
      - field: "trend_filter"
        indicator: "MA"
        period: 60
        condition: "price_above" # 價格在季線之上

```

---

### 四、 前端戰情室 UI 與 API 端點規劃 (FastAPI + Vue)

#### 1. FastAPI 後端端點規劃

* `GET /api/v1/etf/screen`: 傳入動態過濾條件（或 strategy_id），回傳符合條件的 ETF 清單與評分。
* `GET /api/v1/etf/{symbol}/summary`: 取得單一 ETF 的基本資料、即時折溢價、費用率與歷年配息表。
* `GET /api/v1/etf/{symbol}/holdings`: 取得該 ETF 最新前 10 大成分股及權重。
* `POST /api/v1/etf/overlap-analysis`: 傳入多檔 ETF 代碼（如 `["0050", "006208", "00878"]`），回傳成分股交集與重疊度矩陣 JSON。
* `POST /api/v1/etf/dividend-calendar`: 傳入投資組合自選 ETF，自動計算並輸出 1~12 月的預估現金流排程表。

#### 2. Vue 前端組件規劃

* **ETF 篩選雷達面板（Screener Panel）**：多維度滑桿與 Tag 選擇器（殖利率、費用率、折溢價、配息週期）。
* **自組月月配模擬器（Monthly Cash Flow Calculator）**：勾選不同月份除息的 ETF，即時繪製每月現金流柱狀圖。
* **持股重疊熱力圖（Overlap Heatmap）**：以 ECharts 繪製多檔 ETF 之間的成分股重疊度矩陣與單一大型股（如台積電）的綜合曝險比例。