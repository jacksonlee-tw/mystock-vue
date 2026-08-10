# 系統設計規劃：資料庫導入與排程自動化 (PostgreSQL & Automation Design)

這份文件說明了將目前基於 JSON 檔案的資料儲存方式，平滑升級為 PostgreSQL 資料庫，並加入自動化排程與資料補齊機制的完整規劃。本設計考量了未來「台股/美股雙市場」的擴充性，並確保系統轉換期間的穩定性。

---

## 1. 執行摘要 (Executive Summary)

* **目標**：解決檔案系統在跨日期範圍查詢時的效能瓶頸，並建立可靠的自動化資料抓取機制。
* **核心策略**：
  * **雙軌並行 (Dual Write)**：過渡期間同時保留 JSON 與 PostgreSQL 寫入，確保隨時可退回舊架構。
  * **JSON 欄位保留彈性**：利用 PostgreSQL 的 `JSONB` 欄位儲存爬蟲原始資料，相容不同市場與券商的欄位差異，並具備優異的查詢效能。
  * **排程與自動修復**：實作背景排程定期抓取，並具備系統啟動時的歷史缺漏資料自動補齊能力。

---

## 2. 基礎架構：Docker Compose 與環境配置

我們將使用 Docker Compose 來統一管理 PostgreSQL 及其他相關服務，確保開發與生產環境的一致性。

### 2.1 Docker Compose 規劃 (`docker-compose.yml`)
* **服務 `db`**: 
  * 映像檔：使用 `postgres:15` (或最新穩定版)。
  * 時區：透過環境變數 `TZ=UTC` 統一資料庫時區為 UTC。
* **Volume**: 掛載 `./postgres_data:/var/lib/postgresql/data` 以確保資料持久化。
* **Port**: 映射 `5432:5432` 供本機開發連線。

### 2.2 環境變數規劃 (`.env`)
抽離連線資訊至 `.env`，避免將密碼提交至版本控制：
```ini
POSTGRES_DB=mystock_db
POSTGRES_USER=stock_user
POSTGRES_PASSWORD=stock_password
```

---

## 3. 資料庫 Schema 設計與 Flyway 版本控管

### 3.1 核心資料表設計 (Schema Design)
為了保持資料儲存的彈性（相容台/美股不同指標），並兼顧關聯式資料庫的查詢效率，採用結構化欄位搭配 `JSONB` 欄位。

**Table: `symbols` (追蹤標的管理表)**
集中管理系統目前追蹤的個股，取代或輔助現有 `_symbols.json`。
| 欄位名稱 | 資料型別 | 說明 |
| :--- | :--- | :--- |
| `symbol` | VARCHAR(20) | 主鍵 (PK)，股票代號 (如 '2330', 'AAPL') |
| `market_type` | VARCHAR(10) | 市場別 ('TW', 'US') |
| `is_active` | BOOLEAN | 是否持續追蹤更新 (預設 true) |
| `created_at` | TIMESTAMP | 建立時間 |

**Table: `daily_stock_data` (每日個股交易資料表)**
| 欄位名稱 | 資料型別 | 說明 |
| :--- | :--- | :--- |
| `id` | BIGSERIAL | 主鍵 (PK)，自動遞增 |
| `symbol` | VARCHAR(20) | 股票代號 (FK to symbols) |
| `market_type` | VARCHAR(10) | 市場別 ('TW', 'US')，加速分區查詢 |
| `trade_date` | DATE | 交易日期 (當地市場時間) |
| `raw_data` | JSONB | **爬蟲抓取的完整原始資料** (保留欄位彈性與高效查詢) |
| `created_at` | TIMESTAMP | 建立時間 (UTC) |
| `updated_at` | TIMESTAMP | 更新時間 (UTC) |

* **索引 (Indexes)**: 建立 Unique Index 於 `(symbol, trade_date)`，避免重複寫入同一天的資料。建立 Index 於 `trade_date` 與 `market_type` 加速時間範圍與市場查詢。並可為 `raw_data` 建立 GIN 索引加速 JSON 內部欄位搜尋。

**Table: `crawler_logs` (爬蟲執行紀錄表 - 規劃中)**
* 用於紀錄排程執行的狀態 (成功/失敗、處理筆數、錯誤訊息)，方便後續排查與建立監控警告。

### 3.2 使用 Flyway 控管資料表異動
* **導入方式**: 於 `docker-compose.yml` 引入 `flyway/flyway` 容器，與 `db` 容器連動。`docker-compose up` 啟動時自動執行 SQL 遷移。
* **腳本管理**: 將遷移檔存放於 `db/migration`。
  * `V1__Create_symbols_and_daily_data.sql`：建立基礎資料表與索引。
  * `V2__xxx.sql`：未來擴充欄位或建立 View 時使用，落實資料庫版本控管。

---

## 4. 實作架構：雙寫機制與讀取切換

為了降低系統轉換風險，架構調整將採「雙軌並行」策略。

### 4.1 資料寫入 (Dual Write)
1. **初期維持 JSON**: 爬蟲邏輯初步不變，先將資料存入 `.json` 檔案。
2. **非同步轉存**: 爬蟲完成 JSON 寫入後，觸發轉存腳本（或背景任務），將 JSON 內容解析並 Upsert 至 PostgreSQL。
3. **衝突處理**: 針對 PostgreSQL 實作 `ON CONFLICT` 處理，若該日期與代號的資料已存在，自動更新：
   `INSERT INTO ... ON CONFLICT (symbol, trade_date) DO UPDATE SET raw_data = EXCLUDED.raw_data, updated_at = NOW();`

### 4.2 後端 (Backend) 讀取機制切換
1. **Repository Pattern**: 在 Python 後端導入 `SQLAlchemy`，並建立資料存取層 (Data Access Layer)。
2. **環境變數控制**: 透過 `.env` 中的 `DATA_SOURCE=json|postgres` 切換讀取來源。
3. **API 改造**: 將提供前端圖表與列表的 API，由原本的「讀取 JSON 檔案 -> 解析」改為「執行 SQL 查詢 -> 聚合回傳」，大幅提升多日期區間的查詢效能。

---

## 5. 自動化排程與補齊機制 (Scheduler & Backfill)

系統需具備自動化維護資料的能力，預計使用 Python 的 `APScheduler` 實作於 Backend 服務中。

### 5.1 多市場定時抓取排程
針對不同市場的收盤時間，設定不同的 Cron Job：
* **台股 (TW)**: 
  * 收盤為 13:30，設定排程於每日 **14:30** 啟動例行爬蟲。
* **美股 (US)**: 
  * 收盤為台灣時間凌晨 04:00 (夏令) / 05:00 (冬令)。設定排程於每日 **06:00** 啟動爬蟲。
* **防呆機制**: 任務啟動時會先查詢 DB 是否已有當日資料，避免重複抓取與浪費系統資源。

### 5.2 系統啟動時的歷史資料補齊檢查 (Health Check)
為確保系統有足夠且連續的資料繪圖，Backend 啟動時將背景執行缺漏檢查：
1. **計算時間範圍**: 取出 `今日 - 90 天` (或可設定區間) 作為檢查範圍。
2. **獲取實際交易日**: 根據該市場的行事曆 (排除週末與國定假日) 取得應有的交易日列表。
3. **比對差集**: `應有交易日列表` 減去 `資料庫已有日期`，得到「缺漏日期清單」。
4. **自動補齊作業**:
   * 若清單不為空，則依序觸發爬蟲回補資料。
   * **Rate Limiting**: 為避免短時間大量請求被目標網站封鎖，回補作業需加入適當延遲 (例如每抓一天暫停 3-5 秒)，並限制並發數。

---

## 6. 資料備份與監控策略

* **自動備份腳本**: 
  * 在 Docker 中加入輕量級的 postgres 備份容器 (例如 `prodrigestivill/postgres-backup-local`)。
  * 每日定時執行 `pg_dump` 匯出 SQL 壓縮檔至主機的 `./backups` 目錄。
  * 設定保留策略 (如自動刪除 30 天前的備份檔)。
* **異常處理與通知 (Future Work)**:
  * 結合 `crawler_logs`，若排程連續失敗，可透過 Telegram 或 Discord Webhook 發送警告通知給開發者。

---

## 7. 階段性導入計畫 (Phased Rollout Plan)

為確保現有前端功能不受影響，整個移轉過程建議分為以下五個階段進行：

* **Phase 1: 基礎建設與 Schema 建立**
  * 撰寫 `docker-compose.yml` 與 Flyway 遷移腳本。
  * 本機端成功啟動 PostgreSQL 並完成 Schema 初始化。
* **Phase 2: 歷史資料匯入與雙寫實作 (Dual Write)**
  * 開發一次性轉檔腳本，將既有 `data/**/*.json` 全數匯入 PostgreSQL。
  * 修改爬蟲模組，在抓取完成後同時寫入 JSON 與 PostgreSQL。
* **Phase 3: 後端讀取 API 切換**
  * 後端實作 SQLAlchemy ORM。
  * 透過環境變數將 API 資料來源從 JSON 切換為 PostgreSQL，並進行前端圖表渲染驗證與效能測試。
* **Phase 4: 排程自動化與自動補齊實裝**
  * 導入 `APScheduler` 實作每日盤後定時抓取。
  * 實作系統啟動時的 `Health Check` 缺漏資料回補邏輯。
* **Phase 5: 舊架構退役與清理**
  * 系統穩定運行一段時間後，停止寫入 JSON 檔案。
  * 移除程式碼中解析 JSON 檔案的舊有邏輯，完成架構轉型。
