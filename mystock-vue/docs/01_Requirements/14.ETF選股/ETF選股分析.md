# ETF 選股系統分析文件

## 1. 系統目標
為現有的 Python (FastAPI + Docker + PostgreSQL / Parquet) + Vue 前端系統架構，擴充「ETF 選股與分析模組（ETF Screener & Analytics Module）」。
針對 ETF 獨有特性（成分股穿透、折溢價、配息組成、費用率），提供完整的過濾、分析與策略制定功能。

## 2. 資料來源與收集策略
採用兩段式資料管線 (ELT：API -> 落地 JSON -> PostgreSQL) 整合。

### 推薦資料來源
| 資料來源 | 支援市場/類型 | 應用場景 |
| -------- | ------------ | -------- |
| **FinMind API** | 台股 (上市/上櫃/ETF) | 最佳台股來源。提供結構化 JSON，涵蓋除權息日、現金/股票股利及結果。 |
| **TWSE / TPEX OpenAPI** | 台股 (上市/上櫃) | 官方免費資料。包含除權除息預告表與計算結果表 (需注意爬蟲限制)。 |
| **yfinance** | 美股、台股 (代碼加 .TW) | 美股及台美 ETF 歷史配息快速抓取 (台股建議搭配驗證)。 |

### Provider 介面擴充
- 在系統 `providers/base.py` 擴充 `@abstractmethod def fetch_dividends(...)`。
- 實作 `FinMindProvider` 及 `YahooProvider` 介面。
- 落地的配息資料匯入 `etf_dividend_history`，並可與記帳模組 `user_transactions` 自動對帳。

## 3. ETF 選股模組架構
系統功能涵蓋八大層面：
1. 基礎屬性濾網 (Universe)
2. 配息與現金流 (Dividend Flow)
3. 估值與成本 (NAV/Expense)
4. 成分股穿透 (Look-Through)
5. 動態策略清單 (Presets)
6. 組合模擬回測 (Portfolio Sim)
7. 戰情室 UI (Vue Web)
8. 排程與儲存 (Pipeline)

## 4. 功能需求規格

### 4.1 基礎屬性濾網 (Universe & Categorization)
- **多層次類型分類**：市場類型 (台股、美股、債券、槓桿等) 及主題標籤 (市值、高股息、ESG、半導體等)。
- **規模與流動性門檻**：AUM 資產規模下限、日成交量/金額門檻。
- **受益人數增長率**：追蹤集保戶週/月增減率。

### 4.2 配息能力與收益品質 (Dividend & Income Screener)
- **配息頻率**：月配、季配、半年配、年配、不配息 (累積型)。
- **殖利率區間**：近 1 年滾動累計年化殖利率、最新單次預估年化殖利率。
- **填息能力**：歷史平均填息天數、歷史填息成功率。
- **配息來源拆解**：股利所得 (54C)、收益平準金、資本公積與財產交易所得 (76T) 佔比。

### 4.3 評價、成本與折溢價 (Valuation & Cost)
- **折溢價監控**：即時/歷史市價與淨值 (NAV) 偏差。
- **總內扣費用率**：經理費 + 保管費 + 換股交易摩擦成本。
- **追蹤誤差**：追蹤指數與 ETF 淨值變動的年化標準差。

### 4.4 成分股穿透與重疊度 (Constituent Look-Through)
- **前 10 大成分股集中度**：單一個股權重上限設定。
- **跨 ETF 重疊矩陣**：選定 ETF 組合之間的加權重疊比例。
- **特定個股曝險度**：篩選持有特定個股 (如：台積電) 且佔比達門檻的 ETF。

### 4.5 技術與動能指標 (Momentum & Trend)
- **均線多空排列**：日/週線 20MA、60MA 等位置過濾。
- **含息總報酬率排名**：近 1、3 月及 1、3 年含息累積報酬。
- **風險報酬比**：夏普值 (Sharpe Ratio) 與波動度/最大回撤 (MDD)。

## 5. 預設選股策略範本 (Strategy Presets)
內建於系統供一鍵套用的經典策略：
1. **高息穩健現金流**：月/季配 + 近1年殖利率 > 6.5% + 填息率 > 75% + 平準金佔比 < 40%。
2. **市值成長低費用**：市值型 + 總費用率 < 0.4% + 規模 > 100億 + 站上季線。
3. **折價撿便宜套利**：折價 < -0.8% + 流動性 > 2000張。
4. **產業動能突破**：科技/半導體/AI + 近3月含息報酬前 15% + 突破 5日均量。
5. **股債雙存平衡**：股票 ETF + 長期美債 (負相關性配置)。

## 6. 設定檔結構設計
採用設定檔驅動 (Configuration-Driven) 模式，使用 YAML 管理過濾條件 (`config/etf_strategies.yaml`)。

## 7. API 端點與前端 UI 規劃

### 後端 API (FastAPI)
- `GET /api/v1/etf/screen`: 執行篩選並回傳符合條件的 ETF 清單。
- `GET /api/v1/etf/{symbol}/summary`: 單一 ETF 基本資料、即時折溢價、費用率與歷年配息表。
- `GET /api/v1/etf/{symbol}/holdings`: 取得該 ETF 最新前 10 大成分股及權重。
- `POST /api/v1/etf/overlap-analysis`: 多檔 ETF 成分股交集與重疊度矩陣。
- `POST /api/v1/etf/dividend-calendar`: 計算自選組合 1~12 月預估現金流排程。

### 前端 UI (Vue)
- **ETF 篩選雷達面板 (Screener Panel)**：多維度滑桿與 Tag 選擇器，即時調整過濾條件。
- **自組月月配模擬器 (Monthly Cash Flow Calculator)**：勾選組合並即時繪製每月現金流柱狀圖。
- **持股重疊熱力圖 (Overlap Heatmap)**：ECharts 繪製 ETF 間重疊矩陣與單一大型股曝險比例。
