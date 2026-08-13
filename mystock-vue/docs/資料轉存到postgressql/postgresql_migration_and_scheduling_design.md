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

PostgreSQL 全程在 Docker 中執行，不額外安裝本機資料庫；`db`／`flyway`／`backup` 三個服務都定義在同一份 compose 檔，`docker-compose up -d` 即可拉起完整資料層：

```yaml
services:
  db:
    image: postgres:15
    container_name: mystock_db
    restart: unless-stopped
    environment:
      TZ: UTC
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - ./postgres_data:/var/lib/postgresql/data   # 資料持久化，容器刪除重建不丟資料
    ports:
      - "5432:5432"                                 # 本機開發連線用，正式環境可移除對外暴露
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10

  flyway:
    image: flyway/flyway:10
    container_name: mystock_flyway
    depends_on:
      db:
        condition: service_healthy   # 等 db healthcheck 通過才跑遷移（見第 3.2 節）
    volumes:
      - ./db/migration:/flyway/sql
    command: >
      -url=jdbc:postgresql://db:5432/${POSTGRES_DB}
      -user=${POSTGRES_USER} -password=${POSTGRES_PASSWORD} migrate

  backup:
    image: prodrigestivill/postgres-backup-local:15
    container_name: mystock_backup
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      POSTGRES_HOST: db
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      SCHEDULE: "@daily"       # 每日定時執行 pg_dump，語法與第 5 節排程分開、互不影響
      BACKUP_KEEP_DAYS: 30
      BACKUP_KEEP_WEEKS: 4
      BACKUP_KEEP_MONTHS: 6
    volumes:
      - ./backups:/backups     # 備份檔落在主機硬碟，容器重建、映像更新都不會遺失
```

* **服務 `db`**：映像檔用 `postgres:15`（或最新穩定版）；時區固定 `TZ=UTC`；掛載 `./postgres_data` 做資料持久化；`healthcheck` 供 `flyway`／`backup` 服務的 `depends_on` 判斷是否已就緒。
* **服務 `flyway`**：與 `db` 用 `condition: service_healthy` 連動，避免資料庫還沒就緒就搶跑遷移（呼應第 3.2 節）。
* **服務 `backup`**：見第 6 節「資料備份與監控策略」的完整說明——這裡先把落地的 compose 定義列出，第 6 節聚焦保留策略與還原驗證。

### 2.2 環境變數規劃 (`.env`)
沿用 `backend/.env`（`config.py` 已在讀取這份檔案，不另開第二份設定檔），新增以下鍵值，避免將密碼提交至版本控制：
```ini
# --- PostgreSQL ---
POSTGRES_DB=mystock_db
POSTGRES_USER=stock_user
POSTGRES_PASSWORD=stock_password
POSTGRES_HOST=localhost        # 容器間互連時（如 Flyway、未來的背景排程容器）改用服務名 db
POSTGRES_PORT=5432

# --- 讀取來源切換（見第 4.2 節） ---
DATA_SOURCE=json                # json | postgres，控制 API 讀取來源
```

`backend/.env.example` 需同步補上這幾個鍵（值留空或給預設），供新環境快速建置。

---

## 3. 資料庫 Schema 設計與 Flyway 版本控管

> 圖像化版本（ERD + UML）見 [`database_design_erd_uml.md`](./database_design_erd_uml.md)；本節是文字/表格版的權威定義，圖僅為輔助閱讀，欄位異動時以本節為準同步更新該文件。

### 3.1 核心資料表設計 (Schema Design)
為了保持資料儲存的彈性（相容台/美股不同指標），並兼顧關聯式資料庫的查詢效率，採用結構化欄位搭配 `JSONB` 欄位。

**Table: `symbols` (追蹤標的管理表)**
集中管理系統目前追蹤的個股。依 `multi_market_tw_us_design.md` 第 4.2 節的規劃，`_symbols.json` 在資料庫上線前是
標的索引的 source of truth，資料庫導入後將由這張表取代（`_symbols.json` 屆時可降級為初始化種子或移除），
因此欄位需完整覆蓋該檔案目前承載的資訊，而不只是最小的追蹤清單：

| 欄位名稱 | 資料型別 | 說明 |
| :--- | :--- | :--- |
| `symbol` | VARCHAR(20) | 主鍵 (PK)，股票代號 (如 '2330', 'AAPL') |
| `market_type` | VARCHAR(10) | 市場別 ('TW', 'US') |
| `name` | VARCHAR(100) | 公司/標的名稱，`status='unresolved'` 時可為 NULL |
| `exchange` | VARCHAR(20) | 交易所 (如 'TWSE', 'NASDAQ')，對應前端身分列徽章來源 |
| `security_type` | VARCHAR(20) | 證券類型 (如 '普通股', 'ETF') |
| `status` | VARCHAR(20) | 驗證狀態 ('active', 'unresolved')，取代 JSON 版同名欄位（如 `SPCX` 案例） |
| `is_active` | BOOLEAN | 是否持續追蹤更新 (預設 true) |
| `created_at` | TIMESTAMP | 建立時間 |

**Table: `daily_stock_data` (每日個股交易資料表)**
將目前爬蟲抓回的資料（開高低收等）獨立為關聯式欄位，以提升繪圖與指標計算效能。台股特有籌碼資料則存入 `market_specific_data` JSONB 欄位保留擴充性。

| 欄位名稱 | 資料型別 | 說明 | 對應爬蟲原始欄位 (台股 / 美股) |
| :--- | :--- | :--- | :--- |
| `id` | BIGSERIAL | 主鍵 (PK)，自動遞增 | - |
| `symbol` | VARCHAR(20) | 股票代號 (FK to symbols) | `股票名稱` (輔助) / `symbol` |
| `market_type` | VARCHAR(10) | 市場別 ('TW', 'US') | - |
| `trade_date` | DATE | 交易日期 (當地市場時間) | JSON Key / `date` |
| `open_price` | NUMERIC(15,4) | 開盤價 | `開盤價` / `open` |
| `high_price` | NUMERIC(15,4) | 最高價 | `最高價` / `high` |
| `low_price`  | NUMERIC(15,4) | 最低價 | `最低價` / `low` |
| `close_price`| NUMERIC(15,4) | 收盤價 | `收盤價` / `close` |
| `volume`     | BIGINT    | 成交量 (股) | `成交股數(股)` / `volume` |
| `turnover`   | BIGINT    | 成交金額 | `成交金額(元)` / `amount` |
| `transaction_count` | INTEGER | 成交筆數 (美股可為 NULL) | `成交筆數(筆)` / - |
| `market_specific_data` | JSONB | 市場特有資料 (如台股籌碼面) | 詳見下方 JSON 結構說明 |
| `created_at` | TIMESTAMP | 建立時間 (UTC) | - |
| `updated_at` | TIMESTAMP | 更新時間 (UTC) | - |

* **`market_specific_data` JSONB 結構說明 (以台股為例)**:
  由於台股爬蟲包含大量法人買賣超、融資融券等籌碼資訊，這些資料欄位隨時可能擴充或異動，統一存放在 JSONB 中兼顧儲存彈性：
  ```json
  {
    "institutional_investors": {
      "foreign_net_buy": -8703,         // 外資買賣超(張)
      "investment_trust_net_buy": 0,    // 投信買賣超(張)
      "dealer_net_buy": 5800,           // 自營商買賣超(張)
      "total_net_buy": -13609,          // 合計買賣超(張)
      "estimated_net_buy_amount": -140580.97 // 估算買賣超金額(萬元)
    },
    "margin_trading": {
      "margin_purchase": 863,           // 融資買進(張)
      "margin_sale": 1025,              // 融資賣出(張)
      "margin_cash_repayment": 36,      // 融資現金償還(張)
      "margin_prev_balance": 25389,     // 融資前日餘額(張)
      "margin_balance": 25191,          // 融資餘額(張)
      "short_purchase": 133,            // 融券買進(張)
      "short_sale": 230,                // 融券賣出(張)
      "short_cash_repayment": 0,        // 融券現券償還(張)
      "short_prev_balance": 476,        // 融券前日餘額(張)
      "short_balance": 573,             // 融券餘額(張)
      "margin_short_offset": 19         // 資券互抵(張)
    }
  }
  ```

  > **美股（或未來無籌碼資料的市場）**：`market_specific_data` 直接寫入 `NULL`，而非空物件 `{}`。
  > 沿用 `multi_market_tw_us_design.md` 訂下的「不支援的能力回傳 `null` 而非零值」原則，
  > 避免前端誤判成「這檔沒有法人買賣超」而非「這個市場本身沒有這種資料」。

* **索引 (Indexes)**: 
  * 建立 Unique Index 於 `(symbol, trade_date)`，確保資料唯一性 (Upsert 基準)。
  * 建立 Index 於 `trade_date` 與 `market_type` 加速範圍查詢與市場分區。
  * 建立 GIN 索引於 `market_specific_data`，加速「欄位是否存在」「JSON 包含關係」查詢（`?`、`@>` 運算子）。
  * **數值範圍過濾另建 Expression Index**：GIN 索引不加速「外資買超 > N」這類數值比較。
    高頻查詢欄位需另建 B-tree 表達式索引，例如：

    ```sql
    CREATE INDEX idx_daily_foreign_net_buy ON daily_stock_data (
      ((market_specific_data->'institutional_investors'->>'foreign_net_buy')::numeric)
    );
    ```

    若某欄位查詢頻率高到需要常態排序/範圍掃描，應考慮直接升級為結構化欄位，而非留在 JSONB 內。

**Table: `crawler_logs` (爬蟲執行紀錄表)**
第 5、6 節的排程防呆與異常通知都依賴這張表，提前定義結構以免留白到實作階段才發現欄位不足：

| 欄位名稱 | 資料型別 | 說明 |
| :--- | :--- | :--- |
| `id` | BIGSERIAL | 主鍵 (PK) |
| `market_type` | VARCHAR(10) | 市場別 ('TW', 'US') |
| `trigger_type` | VARCHAR(20) | 觸發來源 ('scheduled', 'backfill', 'manual') |
| `started_at` | TIMESTAMP | 開始時間 (UTC) |
| `finished_at` | TIMESTAMP | 結束時間 (UTC)，執行中為 NULL |
| `status` | VARCHAR(20) | 'running' / 'success' / 'partial_failure' / 'failed' |
| `symbols_success` | INTEGER | 成功抓取的標的數 |
| `symbols_failed` | INTEGER | 失敗的標的數 |
| `error_message` | TEXT | 失敗訊息摘要（可為 NULL） |

* **索引**：`(market_type, started_at)`，方便查「這個市場最近一次成功是何時」。
* **與防呆機制互補**：第 5.1 節「任務啟動時先查詢 DB 是否已有當日資料」查的是 `daily_stock_data`，
  防的是漏抓；本表最近一筆 `status='success'` 的時間則用於偵測「連續多天沒有成功紀錄」，防的是連續失敗被忽略——兩者互補，缺一不可。

### 3.2 使用 Flyway 控管資料表異動
* **導入方式**: 於 `docker-compose.yml` 引入 `flyway/flyway` 容器，透過 `depends_on` + `condition: service_healthy`
  等待 `db` 容器的 healthcheck 通過後才執行，避免資料庫尚未就緒就搶跑遷移。`docker-compose up` 啟動時自動執行 SQL 遷移。
* **腳本管理**: 將遷移檔存放於 `db/migration`。
  * `V1__Create_symbols_and_daily_data.sql`：建立基礎資料表與索引。
  * `V2__xxx.sql`：未來擴充欄位或建立 View 時使用，落實資料庫版本控管。
* **Rollback 策略**: Flyway 社群版不支援自動 `undo migrate`，任何遷移一旦套用即不可自動逆轉。
  因此每個 `Vn__xxx.sql` 都應設計成向前相容的小步異動（如新增欄位給預設值，避免直接改型別或刪欄位）；
  若真的寫錯，以新增一支修正用的 `Vn+1__Fix_xxx.sql` 補救，不去改動已套用的舊遷移檔。

---

## 4. 實作架構：雙寫機制與讀取切換

為了降低系統轉換風險，架構調整將採「雙軌並行」策略。

### 4.1 資料寫入 (Dual Write)
1. **初期維持 JSON**: 爬蟲邏輯初步不變，先將資料存入 `.json` 檔案。
2. **轉存時機採同步呼叫，不引入佇列**: 爬蟲完成單一標的 JSON 寫入後，直接在同一次流程呼叫轉存函式解析並 Upsert 至 PostgreSQL。
   以目前個位數市場、十餘檔標的、每日一批的規模，Celery / RabbitMQ 等訊息佇列是不必要的複雜度；
   若未來標的數成長到需要非同步重試或併發控制，再考慮引入佇列。
3. **衝突處理**: 針對 PostgreSQL 實作 `ON CONFLICT` 處理，若該日期與代號的資料已存在，更新全部欄位（而非單一欄位）：

   ```sql
   INSERT INTO daily_stock_data (
     symbol, market_type, trade_date, open_price, high_price, low_price, close_price,
     volume, turnover, transaction_count, market_specific_data, updated_at
   ) VALUES (...)
   ON CONFLICT (symbol, trade_date) DO UPDATE SET
     open_price = EXCLUDED.open_price,
     high_price = EXCLUDED.high_price,
     low_price = EXCLUDED.low_price,
     close_price = EXCLUDED.close_price,
     volume = EXCLUDED.volume,
     turnover = EXCLUDED.turnover,
     transaction_count = EXCLUDED.transaction_count,
     market_specific_data = EXCLUDED.market_specific_data,
     updated_at = NOW();
   ```

   > 初版設計曾用單一 `raw_data` JSONB 欄位存全部原始資料，當時 `ON CONFLICT` 只需更新這一欄。
   > 第 3.1 節改為「結構化欄位 + `market_specific_data`」後，Upsert 必須同步更新所有欄位，
   > 否則只更新到一半欄位會讓同一列出現新舊資料混雜。Code Review 時應核對 SET 子句欄位數與 Table 定義一致。

### 4.2 後端 (Backend) 讀取機制切換
1. **Repository Pattern**: 在 Python 後端導入 `SQLAlchemy 2.0`（Async ORM），並建立資料存取層 (Data Access Layer)。
   FastAPI 本身是非同步框架，資料庫驅動選用 `asyncpg`，避免同步 `psycopg2` 呼叫阻塞事件迴圈中的其他請求；
   `requirements.txt` 新增 `sqlalchemy>=2.0`、`asyncpg`。
2. **環境變數控制**: 透過 `.env` 中的 `DATA_SOURCE=json|postgres` 切換讀取來源（見第 2.2 節）。
3. **API 改造**: 將提供前端圖表與列表的 API，由原本的「讀取 JSON 檔案 -> 解析」改為「執行 SQL 查詢 -> 聚合回傳」，大幅提升多日期區間的查詢效能。

---

## 5. 自動化排程與補齊機制 (Scheduler & Backfill)

系統需具備自動化維護資料的能力，預計使用 Python 的 `APScheduler` 實作於 Backend 服務中。

> **多 worker／多行程重複觸發風險**：`APScheduler` 的 `BackgroundScheduler` 是行程內排程，
> 若未來 `uvicorn` 改用多個 worker（`--workers N`）或 `--reload` 產生額外監控行程，
> 每個行程會各自跑一份排程，同一觸發時間會重複抓取 N 次。對策：
> * 目前規模先固定單一 worker 執行 API + 排程，最簡單且不會遇到此問題；
> * 若未來必須多 worker，排程需獨立成單一背景服務，或依賴 `crawler_logs` 的 `(market_type, started_at)`
>   做「當天已有 running/success 紀錄就跳過」的資料庫層防重，不要假設行程數量固定不變。

### 5.1 多市場定時抓取排程
針對不同市場的收盤時間，設定不同的 Cron Job：
* **台股 (TW)**: 
  * 收盤為 13:30，設定排程於每日 **14:30** 啟動例行爬蟲。
* **美股 (US)**: 
  * 收盤為台灣時間凌晨 04:00 (夏令) / 05:00 (冬令)，**每年隨夏令時間切換兩次**。
  * 排程統一設在每日 **06:00** 啟動——刻意預留 1～2 小時緩衝，使兩種收盤時間都已結束，
    因此排程觸發時間本身不需要每年手動調整；但爬蟲內部若有任何「距收盤 N 小時」的判斷邏輯，
    仍須用 `zoneinfo` 動態換算，不可寫死 UTC 偏移量（呼應 `multi_market_tw_us_design.md` 第 10 節列出的同一項風險）。
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

* **自動備份**：由第 2.1 節定義的 `backup` 服務（`prodrigestivill/postgres-backup-local`）負責，容器內部依 `SCHEDULE` 定時執行 `pg_dump`，
  產出的 `.sql.gz` 壓縮檔透過 volume 掛載寫入主機硬碟的 `./backups` 目錄——**備份檔案存放在主機檔案系統，而非容器內部**，
  容器被刪除、映像升級都不影響已備份的檔案。
* **保留策略**：`BACKUP_KEEP_DAYS` / `BACKUP_KEEP_WEEKS` / `BACKUP_KEEP_MONTHS` 三個環境變數控制備份輪替
  （見第 2.1 節範例：日備份留 30 天、週備份留 4 週、月備份留 6 個月），容器會自動清掉超過保留期的舊檔，`./backups` 目錄不會無限成長。
* **還原驗證（不可省略）**：備份「有產出檔案」不代表「真的能還原」。建議至少在 Phase 1 上線後與之後每次 PostgreSQL 大版本升級時，
  手動執行一次還原演練：起一個乾淨的臨時容器，用最新的 `.sql.gz` 還原，跑幾條查詢核對資料筆數與最新交易日，確認備份真實可用（對應第 10 節驗收清單）。
* **異常處理與通知 (Future Work)**:
  * 結合 `crawler_logs`，若排程連續失敗，可透過 Telegram 或 Discord Webhook 發送警告通知給開發者。

---

## 7. 階段性導入計畫 (Phased Rollout Plan)

為確保現有前端功能不受影響，整個移轉過程建議分為以下五個階段進行：

> **Phase 1、2 已實作完成**（`docker-compose.yml`、`db/`、`repositories/`、`scripts/import_json_to_postgres.py`）。
> Phase 3～5 的實作級設計（含既有程式碼的改動點與已知缺口）見
> [`phase3_5_read_switch_scheduler_retirement_design.md`](./phase3_5_read_switch_scheduler_retirement_design.md)，
> 本節僅保留階段輪廓。

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
  * **退役前必過第 10 節「退役 JSON」核對清單**，尤其是資料一致性比對，不能只憑「跑了一段時間沒報錯」判斷可以退役。
  * **`backend/data` 停止進版控**：確認 PostgreSQL 已是唯一資料來源、且已完成一次成功的備份還原驗證後，
    將 `backend/data/`（`.json` 每日資料檔）加入 `.gitignore`，並執行 `git rm -r --cached backend/data` 把已追蹤的檔案從版控移除
    （只加 `.gitignore` 對已追蹤檔案沒有效果，兩步都要做）。
    * 舊資料仍留在 git 歷史紀錄中（`git log` 可查、未來若要徹底清除需要 `git filter-repo`），這裡的目的是停止「未來」的異動繼續進版控，不是抹除過去。
    * `_no_trading_days.json`、`_symbols.json` 等索引檔若已被 `symbols` 表或對應機制取代，一併納入評估是否移除進版控。
    * 這一步刻意排在 Phase 5（確認退役之後），而非現在就執行——Phase 1～4 期間 JSON 仍是雙寫的一份、也是回退舊架構的安全網，過早移除版控等於提早拿掉這份保險。

---

## 8. 與「台股/美股雙市場」改造的銜接

本設計與 `multi_market_tw_us_design.md` 是兩份互相依賴的提案（該文件第 9 節 Phase 7 明確標註「依本文件第 5 節排程設計」），銜接重點：

* **Schema 已預留市場欄位**：`symbols.market_type`、`daily_stock_data.market_type` 從一開始就存在，不需要等雙市場改造完成才能設計 Schema。
* **一次性匯入腳本天然相容目錄搬遷**：Phase 2 的匯入腳本若採用 `data/**/*.json` 遞迴匯入，無論當時是扁平的 `data/{symbol}.json` 還是雙市場改造後的 `data/{market}/{symbol}.json`，都能正確匯入，兩個提案的實作順序因此可以互不阻塞——先做哪個都不影響另一個。
* **`symbols` 表可取代 `_symbols.json`**：第 3.1 節已將 `name`／`exchange`／`security_type`／`status` 併入 `symbols` 表，資料庫上線後 `_symbols.json` 即可依雙市場文件所述降級為初始化種子或移除。
* **建議順序**：若兩案都要做，建議先完成本文件 Phase 1～3（Schema、雙寫、讀取切換），再進行雙市場改造的美股資料管線——理由是雙寫機制上線後，美股資料一落地就直接進結構化欄位，不需要先寫一版 JSON-only 的美股邏輯，之後又重工一次轉存。

---

## 9. 風險與注意事項

| 風險 | 對策 |
| :--- | :--- |
| **Upsert 遺漏欄位**：結構化欄位改版後，`ON CONFLICT DO UPDATE` 若只更新部分欄位，會讓新舊資料混在同一列 | 見第 4.1 節，Upsert SQL 需列出全部欄位，Code Review 時核對欄位數與 Table 定義一致 |
| **GIN 索引誤用於數值範圍查詢** | GIN 只加速存在性／包含查詢；高頻數值篩選另建 Expression Index，或直接升級為結構化欄位（見 3.1） |
| **排程重複觸發**：多 worker 或 `--reload` 監控行程各自起一份 `APScheduler` | 見第 5 節，目前規模維持單 worker；擴充前先做資料庫層防重 |
| **Flyway 無自動 undo**：遷移一旦套用即不可自動逆轉 | 遷移採小步向前相容設計，寫錯以新遷移檔修正，不回頭改舊檔（見 3.2） |
| **夏令時間切換**：美股收盤對應台灣時間在 04:00／05:00 間每年切兩次 | 排程觸發時間本身有緩衝不受影響；但任何「距收盤 N 小時」的程式邏輯需用 `zoneinfo` 動態換算，不可寫死（見 5.1） |
| **雙寫期間 JSON 與 PostgreSQL 不一致而未被發現** | Phase 5 退役前需跑資料一致性比對（見第 10 節），而非僅憑「跑了一段時間沒報錯」判斷可以退役 |
| **回補作業把目標網站封鎖 IP** | 見第 5.2 節 Rate Limiting；首次上線回補天數較長時，優先小範圍測試觀察再放量 |
| **備份與正式庫版本不一致** | 備份容器或 `pg_dump` 腳本需釘選與 `postgres:15` 相容的版本，並定期實測還原（見第 10 節） |

---

## 10. 驗收檢查清單

**Schema 與遷移**

- [ ] `docker-compose up` 全新環境下，Flyway 遷移一次跑完不需手動介入
- [ ] `(symbol, trade_date)` Unique Index 存在，重複 Upsert 同一天資料不會產生兩列
- [ ] `market_specific_data` 在美股資料列為 `NULL`，而非 `{}`

**雙寫與一致性**

- [ ] 一次性匯入腳本重跑兩次（idempotent），PostgreSQL 資料列數不因重跑而重複增加
- [ ] 任選 5 檔標的、任選一段日期區間，JSON 檔案的收盤價／成交量與 PostgreSQL 查詢結果逐筆比對一致
- [ ] 爬蟲異常中斷後重跑，PostgreSQL 該筆資料被正確 Upsert 更新，不會殘留半筆舊資料
- [ ] `DATA_SOURCE=postgres` 時，既有前端圖表與列表頁渲染結果與 `DATA_SOURCE=json` 時一致

**排程與監控**

- [ ] 台股／美股排程各自在收盤後正確觸發，`crawler_logs` 有對應的 `success` 紀錄
- [ ] 手動將某天資料先寫入 DB 後重跑排程，防呆機制正確跳過（不重複抓取）
- [ ] 系統啟動時的歷史缺漏檢查能正確找出人為刪除的某天資料並自動回補
- [ ] 備份容器產出的 `.sql.gz` 檔案可成功還原到一個乾淨的資料庫，並通過基本查詢驗證

**退役 JSON（Phase 5 前必過）**

- [ ] 連續 N 天（建議至少 7 天）雙寫皆無資料不一致報告
- [ ] 所有讀取 API 已全面切換 `DATA_SOURCE=postgres` 且穩定運行
- [ ] 已確認沒有其他腳本或前端邏輯直接讀取 `data/*.json`（而非透過 API）
