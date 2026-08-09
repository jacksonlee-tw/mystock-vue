# 系統設計規劃：資料庫導入與排程自動化 (MySQL & Automation Design)

這份文件說明了將目前基於 JSON 檔案的資料儲存方式，升級為 MySQL 資料庫，並加入自動化排程與資料檢查機制的完整計畫。

## 1. 基礎架構：使用 Docker Compose 啟動 MySQL
我們將使用 Docker Compose 來統一管理 MySQL 及其他相關服務。密碼與環境變數透過 `.env` 檔案管理。

### 1.1 Docker Compose 規劃 (`docker-compose.yml`)
將會在專案根目錄或 `backend` 目錄下建立 `docker-compose.yml`：
* **服務 `db`**: 使用 `mysql:8.0` (或最新穩定版)。
* **Volume**: 掛載 `./mysql_data:/var/lib/mysql` 以確保資料持久化。
* **Port**: 映射 `3306:3306`。

### 1.2 環境變數規劃 (`.env`)
建立 `.env` 檔案於同層目錄，記錄開發用的明碼帳密：
```ini
MYSQL_ROOT_PASSWORD=root_password
MYSQL_DATABASE=mystock_db
MYSQL_USER=stock_user
MYSQL_PASSWORD=stock_password
```

---

## 2. 資料庫設計與 Flyway 版本控管

### 2.1 資料表結構設計 (Schema Design)
為了保持資料儲存的彈性（例如未來新增不同券商或不同市場的資料欄位），並兼顧關聯式資料庫的查詢效率，資料表設計將採用結構化欄位搭配 `JSON` 型態欄位。

**Table: `daily_stock_data`** (每日個股交易資料表)

| 欄位名稱 | 資料型別 | 說明 |
| :--- | :--- | :--- |
| `id` | BIGINT AUTO_INCREMENT | 主鍵 (PK) |
| `symbol` | VARCHAR(20) | 股票代號 (如 '2330', 'AAPL') |
| `market_type` | VARCHAR(10) | 市場別 ('TW', 'US')，保留美股擴充性 |
| `trade_date` | DATE | 交易日期 |
| `open_price` | DECIMAL(10,4) | 開盤價 (可選，若需獨立查詢可拉出) |
| `close_price` | DECIMAL(10,4) | 收盤價 (可選，用於快速圖表繪製) |
| `raw_data` | JSON | **爬蟲抓取的完整原始資料** (保留彈性) |
| `created_at` | TIMESTAMP | 建立時間 |
| `updated_at` | TIMESTAMP | 更新時間 |

* **索引 (Indexes)**: 建立 Unique Index 於 `(symbol, trade_date)`，避免重複寫入同一天的資料。建立 Index 於 `trade_date` 加速時間範圍查詢。

### 2.2 使用 Flyway 控管資料表異動
* **導入方式**: 可在 `docker-compose.yml` 中加入 `flyway/flyway` 容器，並與 `db` 容器連動。當 `docker-compose up` 啟動時，Flyway 會自動檢查並執行 SQL 遷移腳本。
* **腳本管理**: 將建立資料夾存放遷移檔 (例如 `db/migration`)。
    * `V1__Create_daily_stock_data_table.sql`：建立基礎結構。
    * 未來若需新增特定索引或檢視表，直接新增 `V2__xxx.sql`，達到版本控管目的。

---

## 3. 資料匯入與後端讀取機制修改

### 3.1 爬蟲資料轉存機制 (JSON -> MySQL)
目前爬蟲先將資料存入 `.json`。我們將保留此做法做為第一層備份，並增加第二階段的處理邏輯：
1. **觸發轉存**: 爬蟲完成 JSON 檔案寫入後，觸發轉存腳本。
2. **解析與 Upsert**: 讀取該 JSON 檔，將資料轉換並寫入 MySQL。
3. **衝突處理**: 使用 `INSERT ... ON DUPLICATE KEY UPDATE` (Upsert 機制)，若該日期與代號的資料已存在，則更新 `raw_data` 與 `updated_at`。

### 3.2 後端 (Backend) 資料來源切換
1. **ORM 導入**: 在 Python 後端導入 `SQLAlchemy` 或是輕量級的資料庫連線池。
2. **API 修改**: 修改提供前端圖表與列表的 API，由原本的 `讀取 JSON 檔案 -> 解析` 改為 `執行 SQL 查詢 -> 回傳結果`。
3. **優點**: 大幅提升時間區間查詢的效能，並支援更複雜的排序與過濾。

---

## 4. MySQL 資料備份機制
針對 MySQL 提供定時備份方案，避免資料遺失。
* **備份腳本**: 撰寫一個簡單的 Shell Script 執行 `mysqldump`。
* **自動化執行**:
    * **方案 A**: 在 Python 後端排程中加入備份任務（透過 `subprocess` 執行）。
    * **方案 B (推薦)**: 在 Docker 中加入另一個輕量級的 cron 容器 (例如 `databack/mysql-backup`)，定期自動將資料庫 dump 成 SQL 檔並壓縮，存放在主機的 `./backups` 目錄。

---

## 5. 每日自動排程與動態抓取邏輯
系統需具備自動化維護資料的能力，排程系統預計使用 Python 的 `APScheduler` 或類似套件實作於 Backend 中。

### 5.1 啟動時的時間判斷與當日資料抓取
當 Backend 服務啟動，或排程每日定時觸發時，需判斷當下時間：
* **台股邏輯 (TW)**:
    * 收盤時間設定為 `13:30` (可加上緩衝設定為 `14:00` 確保證交所資料已產出)。
    * 若目前時間 **大於** `13:30`，且資料庫中無當天資料，則觸發台股爬蟲抓取「當日」最新資料。
* **美股擴充彈性 (US)**:
    * 將「市場別」、「收盤時間(時區)」與「爬蟲函式」設計為設定檔 (Config) 驅動。
    * 美股收盤時間為台灣時間凌晨 `04:00` 或 `05:00` (冬/夏令時)。未來排程只需依據設定檔新增美股的檢查規則即可。

### 5.2 盤後定時抓取排程
除了系統啟動時的檢查，排程器 (Scheduler) 會註冊每日定時任務：
* 例如：每日下午 14:30 啟動台股例行爬蟲。
* 任務啟動時同樣會先檢查 DB 是否已有資料，避免重複抓取。

---

## 6. 系統啟動時的歷史資料補齊檢查 (3 個月內)
為了確保系統有足夠的資料繪圖與分析，每次 Backend 啟動時需執行「健康檢查 (Health Check)」。

### 6.1 缺漏檢查邏輯
1. **計算時間範圍**: 取出 `今日 - 90 天` 作為起始日期，`今日` 為結束日期。
2. **獲取實際交易日**:
    * 透過第三方 API 或預先建立的行事曆機制，取得這 90 天內實際的「交易日列表」(排除六日與國定假日)。
3. **比對資料庫**:
    * 查詢資料庫中這段期間擁有的資料日期 (`SELECT DISTINCT trade_date FROM daily_stock_data WHERE trade_date BETWEEN ...`)。
4. **找出差集**: `實際交易日列表` 減去 `資料庫已有日期`，得到「缺漏日期清單」。

### 6.2 自動補齊作業
* 若發現缺漏日期清單不為空，則針對這些日期依序觸發爬蟲。
* **實作考量 (Rate Limiting)**: 為避免短時間內大量請求被目標網站封鎖 (Ban)，補齊作業需加入適當的延遲 (Delay, 例如每抓一天暫停 3-5 秒)，並盡量放在背景異步執行 (Background Task)，不阻擋主程式啟動。
