# Phase 7：PTT 論壇情緒分析 需求規格書

| 項目 | 內容 |
| --- | --- |
| 模組 | PTT 論壇情緒分析 |
| 對應既有模組 | `db/migration/`（新增資料表）、`repositories/`（新增 `forum_repository.py`）；後續切片才會觸及 `services/`（新增抓取／評分管線）、`api/v1/endpoints/`、前端首頁摘要卡 |
| 版本 | v1.1（P0：規格文件＋資料庫 schema＋repository；P1：抓取器，見 §0.1、§6） |
| 狀態 | **P0／P1 已完成**：`V25__Create_forum_sentiment_tables.sql`、`repositories/forum_repository.py`、
`backend/tests/test_forum_repository.py`（P0）與 `services/forum_fetcher.py`、
`backend/tests/test_forum_fetcher.py`（P1）已落地，本片不含 LLM 評分（`sentiment_*` 欄位仍全部
`NULL`）。P2（LLM 情緒評分）／P3（API 端點）／P4（首頁摘要卡）**尚未開發**，見 §6。 |

---

## 0. 修訂紀錄與決策（ADR）

### 0.1 v1.0 本次交付範圍

依使用者拍板的需求（每天爬 PTT 股板熱門標的，討論內容丟 AI 做情緒分析，整理成表格，首頁放摘要卡），
本文件先把**整個功能**的範圍與設計前提定案，但**本次只實作 P0**：資料庫 schema 與 repository 層。
抓取器（`services/`）、LLM 評分、API 端點、前端摘要卡皆為後續獨立切片，依
[incremental-implementation](../../../.agents/skills/incremental-implementation/SKILL.md) 精神先交付
可獨立驗證的一塊，不在同一個切片裡把整條管線一次做完。

**本次新增／異動檔案**：

- `backend/db/migration/V25__Create_forum_sentiment_tables.sql`（新增，`forum_post`／`forum_post_symbol` 兩張表）
- `backend/repositories/forum_repository.py`（新增，唯一 SQL 入口）
- `backend/tests/test_forum_repository.py`（新增，mock `AsyncSession` 驗證 SQL 參數組裝與回傳值轉換）

**本次未動的檔案**（刻意，非漏做，見 §6）：`services/news_fetcher.py`（既有的 `fetch_ptt_stock()`
只抓標題與討論篇數，本次新功能刻意用獨立模組取代它抓內文的部分，不是在既有函式上疊加）、
`stock_news`／`stock_discussion_buzz` 相關程式碼、`services/chip_provider.py`、
`strategies/conditions_sentiment.py`——這四者依使用者指示**絕對不可碰**，見 ADR-P7-03。

### 0.2 決策紀錄

| 編號 | 決策 | 理由 |
| --- | --- | --- |
| ADR-P7-01 | 只做 PTT Stock 板，**不做 Dcard** | Dcard 個股板已被 Cloudflare 擋下（403 + 需通過 CAPTCHA 才能取得內容），要繞過等於主動規避對方的 bot 偵測機制——這已超出「爬蟲」的合理範圍，屬於刻意規避存取限制，不予實作。PTT 網頁版無此限制，且既有 `services/news_fetcher.py` 已有可行的 PTT 存取先例（`fetch_ptt_stock()`），技術路徑已驗證可行 |
| ADR-P7-02 | 抓**內文＋推文**，不只抓標題 | 實測 PTT Stock 板索引頁 124 篇樣本，按分類拆開統計標題含股號的命中率（詳見 §2.2 表格），整體僅約 15%（18/124）標題含可辨識股號，但分類間差異極大：`[新聞]`（佔樣本 53%）命中率僅 5%、`[請益]` 0%，是拉低整體命中率的主因；`[標的]` 命中率其實高達 86%、`[心得]` 100%。若比照既有 `fetch_ptt_stock()` 只看標題，會漏掉約 5/6 的實際討論內容，主要漏在 `[新聞]`／`[請益]`／`[閒聊]`／`[公告]` 這幾類——尤其 `[請益]` 股號確實多半寫在內文而非標題（例如標題只寫「請益一檔金融股」）。實測單篇 `[標的]` 文章頁可額外拿到：內文 492 字、83 則推文（推 48／噓 0／→ 35）、真實時間戳——不論標題命中率高低，內文與推文都是「討論內容」的主體，值得投入 LLM 情緒分析（不同分類是否該採不同抽取策略〔例如 `[標的]`／`[心得]` 優先信任標題、其餘類別必須看內文〕，**推測，待 P1 實作時驗證**） |
| ADR-P7-03 | 與既有新聞情緒**完全隔離**：獨立資料表 `forum_post`／`forum_post_symbol`，不與 `stock_news`／`stock_discussion_buzz` 共用任何表或欄位；程式碼禁止修改 `services/chip_provider.py`、`strategies/conditions_sentiment.py` | 兩者資料特性差異大（新聞是編輯把關過的正式報導，PTT 是未經審核的鄉民言論，情緒雜訊比例、造假動機、可信度都不同量級），混在同一張表或同一套評分管線裡，會讓既有 Phase 4 新聞情緒的品質受論壇雜訊污染。使用者明確要求兩者不得互相影響，寧可欄位重複也要維持資料邊界清楚，未來若要合併呈現，交由呈現層（API／前端）各自查詢後合併，不在資料層或評分邏輯層合併 |
| ADR-P7-04 | 用「貼文表＋標的關聯表」（`forum_post` + `forum_post_symbol`），不像 `stock_news` 那樣一篇文章對應 N 列（`stock_news` 是 `symbol` 直接放在主表上，同一則新聞被 N 檔股票提及就重複 N 列） | PTT 一篇文章（尤其 `[標的]`／`[閒聊]`）常同時討論多檔個股，若比照 `stock_news` 複製 N 列，內文、推噓數、情緒評分（同一篇文章的情緒是對整篇文章評的，不是逐股各評一次）都會被重複儲存 N 份，SimHash／去重、LLM 評分次數也會被放大 N 倍，且未來若要重新判斷「這篇文章到底提到哪些股票」（例如改進股號辨識邏輯）需要動到已評分的內文列，語意上不乾淨。改為貼文只存一份、`forum_post_symbol` 純粹記錄「這篇文章提及哪些標的、怎麼比對到的」（`matched_by`：`code` 用股號比對、`name` 用公司名稱比對），情緒評分針對貼文本身做一次，不因提及股數而重算或重複計費 |
| ADR-P7-05 | 去重鍵採 `(source, post_key)`，`post_key` 為 PTT 網址中的 `M.xxx.A.xxx` 識別碼，而非直接用完整 URL | PTT 同一篇文章的網址可能因來源（PTT 網頁版 `www.ptt.cc` vs. 特定看板鏡像）或查詢參數（例如 `?ajaxsource=`）而有多種寫法，但 `M.xxx.A.xxx` 這段識別碼本身是站方保證的穩定鍵；用它去重比用整串 URL 更抗網址格式變動。`url` 欄位仍完整保留供前端連結使用 |
| ADR-P7-06 | 本次 P0 只交付 schema 與 repository，`sentiment_score` 等欄位全部允許 `NULL`，不在本切片內開發抓取器與 LLM 評分 | 依 [incremental-implementation](../../../.agents/skills/incremental-implementation/SKILL.md)：資料模型與存取層是後續抓取器、評分管線、API 共同的地基，值得先獨立交付並驗證（migration 可套用、repository 方法可被單元測試覆蓋），避免在同一個切片裡把「抓取穩定度」「LLM 提示詞設計」「API 契約」「前端呈現」四個各自有風險的子問題綁在一起除錯 |

---

## 1. 範圍與設計前提

### 1.1 核心目標

每日抓取 PTT 股板熱門標的討論（內文＋推文），交由 LLM 做情緒分析，整理成跨標的排行表，
於首頁提供摘要卡，作為技術／籌碼／基本面／新聞情緒（Phase 4）之外的第五道輔助觀察面向——
**論壇散戶情緒**。與 Phase 4 新聞情緒不同，PTT 內容未經編輯審核，設計上視為「雜訊比例更高、
需獨立評估品質」的資料來源，不與新聞情緒混用同一套邏輯或閾值。

### 1.2 交付內容（完整功能願景，涵蓋本次與後續切片）

- 每日抓取 PTT Stock 板熱門文章的內文與推文，依股號／公司名稱比對出提及的標的，存入獨立資料表。
- 交由 LLM 對每篇文章做情緒評分（分數＋標籤＋理由），比照 Phase 4 `ai/providers.py` 的既有抽象。
- 依標的彙整成排行表：討論則數、推噓總數、平均情緒分數、代表性貼文。
- 首頁新增摘要卡，呈現當日論壇熱度前 N 檔標的。

**本次（P0）僅交付**：資料庫 schema（§4）與 repository（§5）。抓取／評分／API／前端見 §6 路線圖。

### 1.3 既有系統前提（重用什麼、不重建什麼）

- **PTT 存取路徑已有先例**：`services/news_fetcher.py` 的 `fetch_ptt_stock()` 已驗證過 PTT Stock
  板索引頁的頁面結構與存取方式（含 18 歲同意頁處理），後續切片的內文＋推文抓取器可參考其
  HTTP 存取與節流寫法，但**不得在該函式上疊加**——它是 Phase 4 既有新聞/討論量管線的一部分
  （寫入 `stock_discussion_buzz`），本功能是獨立管線，寫入獨立表。
- **LLM Provider 可重用、配額不可共用**：比照 Phase 4 ADR-P4-03 的既有決策，`ai/providers.py`
  的 `PROVIDER_REGISTRY` 抽象可直接沿用，但配額計數器需獨立（後續切片再定案是否新增
  `FORUM_LLM_DAILY_QUOTA`，本次不涉及）。
- **`symbols` 主檔可直接查代號／名稱比對**：`scripts/init_symbol_master.py` 已建立完整 TW 代號與
  名稱主檔，股號／公司名稱比對（`matched_by`）可直接查 `symbols` 表，不需另建對照表。
- **設定檔路徑**：若後續切片需要來源設定（例如熱門文章的篩選門檻），比照 Phase 4
  `strategy_config/news_sources.yaml` 的既有慣例放在 `backend/strategy_config/`，不新建
  `backend/config/`（CLAUDE.md 已記錄這會撞名）。

### 1.4 不在本文件範圍

- Dcard 或其他論壇來源（ADR-P7-01，已排除）。
- 本次不實作抓取器、LLM 評分邏輯、API 端點、前端摘要卡（見 §6，留給後續切片）。
- 論壇情緒與既有新聞情緒（Phase 4）、策略引擎（`strategies/`）的任何整合——本階段是純粹的
  「呈現輔助資訊」功能，不影響任何既有選股或警示邏輯。
- 情緒與股價的回測／勝率統計（樣本量不足，且非本次範圍）。

---

## 2. 資料來源與抓取範圍（規格定案，實作留待 P1）

### 2.1 只做 PTT Stock 板

已實測 Dcard 個股板回應 403 並要求通過 CAPTCHA 才能取得內容，判定為刻意的 bot 防護，
不予繞過（ADR-P7-01）。PTT 網頁版目前無此限制。

### 2.2 抓取範圍：內文＋推文，而非只抓標題

實測數據（已由使用者驗證，作為本節設計依據）：

| 觀察對象 | 樣本 | 結果 |
| --- | --- | --- |
| PTT 股板每日文章量 | 索引頁抽樣 | 每日僅 20～40 篇，請求成本低（每篇 0.12 秒） |
| 標題含可辨識股號比例（整體） | 索引頁 124 篇樣本 | 約 15%（18/124）標題含股號 |
| 單篇 `[標的]` 文章頁可取得的內容 | 單篇實測 | 內文 492 字、推文 83 則（推 48／噓 0／→ 35）、真實時間戳 |

#### 分類命中率（實測，124 篇樣本按分類拆開統計）

| 分類 | 篇數 | 標題含股號 | 命中率 |
| --- | ---: | ---: | ---: |
| `[新聞]` | 66 | 3 | 5% |
| `[請益]` | 21 | 0 | 0% |
| `[閒聊]` | 16 | 3 | 19% |
| `[公告]` | 8 | 1 | 12% |
| `[標的]` | 7 | 6 | **86%** |
| `[心得]` | 5 | 5 | 100% |
| (無分類) | 1 | 0 | 0% |

七類篇數加總 66+21+16+8+7+5+1=124，與樣本數一致（18/124 ≈ 15%）。拉低整體命中率的主因是
`[新聞]`（佔樣本 53%、但命中率僅 5%），而非原先推測的 `[標的]`——`[標的]` 標題命中率其實
高達 86%（實測範例標題「[標的] 生達1720、儒鴻1476、宏全9939…」，四個股號全在標題），真正
0% 命中的是 `[請益]`。不同分類是否該採不同的股號抽取策略（例如 `[標的]`／`[心得]` 優先信任
標題、`[新聞]`／`[請益]`／`[閒聊]`／`[公告]` 必須看內文），**推測，待 P1 實作時驗證**。

**補充**：上述 15%（18/124）是**只用股號比對**標題的結果；P1 實作時改採「股號∪公司中文
名稱」雙路比對（`matched_by`：`code`／`name`），同一份樣本整體命中率可提升到約 17%
（21/124）。這個差距正是 P1 抓取器要做 code∪name 雙路比對、而非沿用既有 `fetch_ptt_stock()`
單純股號正規表示比對的依據。

結論：只抓標題會漏掉約 5/6 的實際討論內容（ADR-P7-02）。既有 `fetch_ptt_stock()`
只看標題正是這個缺口的成因，本功能刻意抓取文章內頁（內文＋全部推文）以彌補。

#### 2.2.1 公司名稱比對的短名稱防護：實測與決策（P1 落地後補測）

P1 實作 `_build_name_index()` 時，原本設計「名稱若是另一檔標的名稱的真子字串就整批排除」
（例如「台泥」是「台泥工程」的子字串，直接不讓「台泥」進比對表），理由是避免短名稱誤判成
別家公司全名的一部分。這條規則當初只用兩列虛構資料驗證過，**從未對真實台股代號主檔量測
真實影響**，事後驗證發現規則不可用，改用下述策略。

**實測方法**：`StockRepository.list_symbols_sync(market_type="tw")` 取台股全代號主檔
（2026-09-28 量測，2447 檔，其中 2412 檔名稱長度達 `MIN_SYMBOL_NAME_LENGTH`），套用舊規則
統計丟棄檔數，並檢查 23 檔 PTT 討論度最高的熱門股是否還在最終比對表裡。

**實測數字**：

| 觀察對象 | 數字 |
| --- | --- |
| 名稱長度達標、進入候選的檔數 | 2412 |
| 舊規則最終比對表大小 | 2312 |
| 被舊規則整批丟棄的檔數 | 100（100/2412 ≈ **4.15%**） |
| 23 檔熱門股裡被丟棄的檔數 | **10 檔（43%）** |

全域丟棄比例只有 4.15%，看起來很低，但丟棄的檔案**剛好集中在討論度最高的那群股票**：
長榮（子字串於「長榮航」「長榮鋼」「長榮航太」）、台塑（「台塑化」）、南亞（「南亞科」）、
中鋼（「中鋼特」「中鋼構」）、統一（「統一超」「統一證」等一長串統一系 ETF／基金）、
華新（「華新科」）、聯電（「台聯電」）、國泰金（「國泰金乙特」）、富邦金（「富邦金乙特」
「富邦金丙特」）、台泥（「台泥乙特」）——這些短名稱在 PTT 上幾乎都是單獨提及母公司本身，
舊規則卻讓它們整批抽不到任何標的，等於讓熱門股的召回率全毀。其餘 13 檔熱門股
（台積電、鴻海、聯發科、陽明、萬海、廣達、緯創、中華電、玉山金、兆豐金、亞泥、大立光，
另日月光在主檔中查無此名稱、與本規則無關）不受影響。

**判準對照本文件既定標準**：丟棄比例雖低於 15% 門檻，但熱門股「大多保留」的條件不成立
（43% 熱門股被誤砍），**現行（舊）規則不可用**，需要改進。

**決策**：改採「同一段文字裡最長優先」策略——`_build_name_index()` 不再整批丟棄短名稱，
所有名稱都留在比對表裡；判斷邏輯下放到 `_extract_symbols()`：同一篇文章裡，若某名稱是
另一個也命中的較長名稱的真子字串，只採計較長名稱、短名稱的命中捨棄（例如同時出現
「長榮」與「長榮航」時只算「長榮航」）；短名稱單獨出現（沒有更長的命中）時仍正常計入，
不犧牲召回率。詳見 `services/forum_fetcher.py` `_build_name_index()` / `_extract_symbols()`
docstring 與 `tests/test_forum_fetcher.py` `BuildNameIndexTests` /
`ExtractSymbolsLongestMatchTests`。

### 2.3 抓取節流與存取限制

- 每日文章量小（20～40 篇），對站方負載影響低，仍比照既有 `services/fetcher.py`／
  `news_fetcher.py` 的既有慣例採隨機延遲與失敗重試上限，不高頻併發抓取單一看板。
- 內文截斷長度、推文擷取上限（例如是否全部 83 則推文都存或只存代表性前 N 則）留給 P1
  抓取器實作時依實測內文長度分布決定，本文件不預先定死一個可能不符合實際分布的數字。

---

## 3. 資料模型設計

### 3.1 為何不像 `stock_news` 一篇文對應 N 列

見 ADR-P7-04：PTT 一篇文章常同時討論多檔個股，情緒評分是對整篇文章做的，不應因提及股數
被複製 N 份、評分 N 次。改採正規化設計：`forum_post` 存貼文本身（一列一篇文章），
`forum_post_symbol` 純粹記錄「這篇文章提及哪些標的」的關聯，情緒欄位只在 `forum_post` 上出現一次。

### 3.2 去重鍵設計

`(source, post_key)` 為唯一鍵（ADR-P7-05）。`source` 目前只有 `'ptt_stock'` 一種值，
保留欄位是為了未來若真的新增其他論壇來源時可以複用同一張表（雖然 Dcard 已被排除，但欄位
設計上不假設「永遠只有 PTT 一種來源」，避免真的要擴充時得改 schema）。

### 3.3 與既有新聞情緒的邊界（ADR-P7-03）

以下清單**本次與後續 PTT 相關切片一律不得修改**：

- `stock_news`、`stock_discussion_buzz` 兩張表與所有讀寫它們的程式碼
- `backend/services/chip_provider.py`
- `backend/strategies/conditions_sentiment.py`

論壇情緒若未來要影響策略引擎，需另立新的 condition 檔案（比照 `conditions_sentiment.py`
的既有慣例另開一個 `conditions_forum.py`，而非修改既有檔案），但這不在本文件規劃範圍內。

---

## 4. 資料庫設計（PostgreSQL）

新增 `backend/db/migration/V25__Create_forum_sentiment_tables.sql`（目前最新為 V24，比照
`V23__Create_news_and_macro_tables.sql` 的風格：繁中註解、`CREATE TABLE IF NOT EXISTS`、
註解標注對應文件章節）。與 Phase 4 三張新表相同，本功能兩張表**直接以 PostgreSQL 為唯一儲存**，
不參與 `DATA_SOURCE` 的 JSON／PG 雙軌切換（比照 ADR-P4-07 的既有決策：雙軌是為 OHLCV 設計，
論壇資料不值得再做一套）。

### 4.1 `forum_post`（貼文本身，含情緒評分）

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `id` | BIGSERIAL PK | |
| `source` | VARCHAR(20) | 目前僅 `'ptt_stock'`（§3.2） |
| `post_key` | TEXT | PTT 的 `M.xxx.A.xxx`，穩定去重鍵（ADR-P7-05） |
| `url` | TEXT | 完整網址，供前端連結 |
| `title` | TEXT | 文章標題 |
| `category` | VARCHAR(10) | 標的／請益／心得／新聞／閒聊等分類標記 |
| `author` | VARCHAR(40) | PTT 帳號 |
| `body_excerpt` | TEXT | 截斷後內文（截斷長度留給 P1 抓取器決定，見 §2.3） |
| `push_count` / `boo_count` / `arrow_count` | INTEGER NOT NULL DEFAULT 0 | 推／噓／→ 則數 |
| `posted_at` | TIMESTAMP | 文章真實發布時間 |
| `effective_trade_date` | DATE | 對齊交易日後的日期，比照 Phase 4 ADR-P4-05 的 point-in-time 精神，供未來排行／統計依交易日彙整；本次僅落地欄位，換算規則留給 P1 抓取器實作 |
| `sentiment_score` | NUMERIC(4,3) | -1.000～1.000，`NULL` = 尚未評分（P0 全部為 `NULL`） |
| `sentiment_label` | VARCHAR(10) | 評分後填入，例如 BULLISH／BEARISH／NEUTRAL |
| `sentiment_reason` | TEXT | LLM 評分理由，供人工稽核 |
| `sentiment_engine` | VARCHAR(20) | 標記評分引擎版本，供品質稽核 |
| `created_at` | TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP | |

唯一鍵：`(source, post_key)`。

### 4.2 `forum_post_symbol`（貼文與標的的關聯）

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `post_id` | BIGINT NOT NULL REFERENCES forum_post(id) ON DELETE CASCADE | 貼文刪除時關聯列一併刪除 |
| `symbol` | VARCHAR(20) NOT NULL REFERENCES symbols(symbol) ON DELETE RESTRICT | 比照既有慣例，禁止刪除仍被引用的標的主檔列 |
| `matched_by` | VARCHAR(10) NOT NULL | `'code'`（股號比對）或 `'name'`（公司名稱比對），供事後稽核比對品質 |

複合主鍵 `(post_id, symbol)`——同一篇文章對同一標的只記一列，即使股號與名稱都比對到也不重複。

### 4.3 索引設計

| 索引 | 用途 |
| --- | --- |
| `idx_forum_post_effective_date` on `forum_post (effective_trade_date DESC)` | 依交易日查當日貼文（首頁摘要卡、排行表的主要查詢路徑） |
| `idx_forum_post_pending_sentiment` on `forum_post (id) WHERE sentiment_score IS NULL` | `list_unscored()` 的待評分佇列查詢，partial index 避免掃描已評分的大多數列 |
| `idx_forum_post_symbol_symbol` on `forum_post_symbol (symbol, post_id)` | 依標的聚合查詢（`list_top_discussed()` 的 JOIN 路徑）；複合主鍵 `(post_id, symbol)` 對「先查 post_id」的方向已有索引，但「先查 symbol」方向需要額外索引 |

---

## 5. Repository 設計

新增 `backend/repositories/forum_repository.py`，為 `forum_post`／`forum_post_symbol` 的唯一 SQL
入口（CLAUDE.md「SQL 只能寫在 `repositories/`」的既有邊界）。完全沿用 `news_repository.py` 的既有慣例：

- 建構子注入 `AsyncSession`（`self._s`），全部用 `text()` 寫原生 SQL，不用 ORM model。
- 本類別自身不 `commit()`，交易邊界由呼叫端（未來的抓取器／評分服務）決定。
- 提供 `get_background_session()` / `run_async()` 同步橋接（獨立的背景連線池 `_bg_engine`），
  給未來同步爬蟲模組（比照 `services/news_fetcher.py`）呼叫本 repository 的 async 方法用；
  P0 階段尚無呼叫端，但比照 `news_repository.py` 先備妥這組橋接，讓 P1 抓取器不需要再回頭補。

### 5.1 方法列表

| 方法 | 用途 |
| --- | --- |
| `upsert_post(...)` | 依 `(source, post_key)` upsert 一篇貼文，回傳 `post_id`；衝突時更新標題／內文／推噓數等可能隨重新抓取而變動的欄位，`posted_at`／`effective_trade_date`／情緒欄位不因重複抓取被覆蓋 |
| `replace_post_symbols(post_id, symbols)` | 覆寫某篇貼文的標的關聯（先刪後插），供股號辨識邏輯改進後重新比對時使用 |
| `list_unscored(limit)` | 回傳 `sentiment_score IS NULL` 的待評分貼文（`id`／`title`／`body_excerpt`／`category`／推噓數），供未來 LLM 批次評分使用 |
| `update_sentiment(post_id, *, score, label, reason, engine)` | 寫入評分結果 |
| `list_top_discussed(*, trade_date, limit)` | 跨標的排行：依 `symbol` 聚合當日貼文數、推文總數、噓文總數、平均情緒分數與代表性貼文 |
| `purge_expired(retention_months)` | 依 `effective_trade_date` 刪除逾保留期限的貼文（`forum_post_symbol` 隨 `ON DELETE CASCADE` 一併清除） |

`list_top_discussed()` 是全新的查詢型態——既有 `news_repository.py` 的 13 個方法全部要求呼叫端
先指定 `symbol=`，沒有任何跨股彙整查詢；本方法是本功能第一支「不知道要查哪一檔股票、反過來問
『今天哪些股票被討論最多』」的查詢，設計上用 `GROUP BY symbol` 一次查完，不對每檔股票各查一次
避免 N+1。

---

## 6. 後續切片路線圖（不在本文件本次交付範圍，僅記錄規劃）

| 階段 | 範圍 | 前置依賴 |
| --- | --- | --- |
| P0（已完成） | 規格文件＋`V25` migration＋`forum_repository.py`＋單元測試 | 無 |
| P1（已完成） | 抓取器 `services/forum_fetcher.py`：PTT Stock 板熱門文章列表＋內文＋推文抓取，股號／名稱比對寫入 `forum_post`／`forum_post_symbol`（`backend/tests/test_forum_fetcher.py`） | P0 |
| P2 | LLM 情緒評分：比照 Phase 4 `services/news_sentiment.py` 的批次評分骨架，呼叫 `list_unscored()`／`update_sentiment()` | P0、P1 |
| P3 | API 端點：`GET /api/v1/forum/top`（跨標的排行）等，比照既有 `{"success", "data"}` 信封慣例 | P0、P2 |
| P4 | 首頁摘要卡：新增 Vue 元件，比照 `frontend/src/components/home/` 下既有面板的版面慣例；需遵守 CLAUDE.md 兩條硬性規則（圖表切換不重置捲動位置、同列卡片高度一致） | P3 |

排程整合（每日抓取＋評分的觸發時間）、`.env` 設定項目（例如 `FORUM_FETCH_ENABLED`）、資料保留
天數等細節，留待 P1／P2 動工前依當時的既有排程慣例（`services/scheduler.py`）具體定案，本文件
不預先寫死可能與實作衝突的數字。

**P3（API 端點）注意事項**：實測在真實 Postgres 上呼叫 `list_top_discussed()`，`AVG()` 對
`NUMERIC(4,3)` 欄位取平均會放大精度，`avg_sentiment_score` 回傳的是
`Decimal('0.80000000000000000000')`（20 位小數）而非 3 位小數。目前不是缺陷（FastAPI 的
`jsonable_encoder` 能正確序列化），但 P3 組裝 API 回應時應該在 SQL 端 `ROUND(AVG(...), 3)`
或在組裝層轉成 `float`，避免前端拿到 20 位小數的字串。

---

## 7. 驗收條件（P0 範圍）

| 編號 | 驗收條件 |
| --- | --- |
| AC-P6-01 | `flyway migrate` 套用 `V25` 後，`forum_post`／`forum_post_symbol` 兩張表與 §4.3 全部索引皆存在，且未修改任何已套用的既有 `V*` 檔案 |
| AC-P6-02 | 對同一 `(source, post_key)` 呼叫兩次 `upsert_post()`，`forum_post` 僅有一列，第二次呼叫的推噓數等欄位更新生效，`posted_at`／情緒欄位不被覆蓋 |
| AC-P6-03 | `replace_post_symbols()` 呼叫後，該 `post_id` 的舊關聯列被新清單完全取代，不殘留舊資料 |
| AC-P6-04 | `list_unscored()` 只回傳 `sentiment_score IS NULL` 的貼文 |
| AC-P6-05 | `list_top_discussed()` 回傳依 `post_count` 排序的跨標的排行，且每筆包含推文總數、噓文總數、平均情緒分數與代表性貼文 |
| AC-P6-06 | `purge_expired()` 刪除逾保留月數的貼文後，對應的 `forum_post_symbol` 關聯列一併消失（`ON DELETE CASCADE`） |
| AC-P6-07 | `stock_news`／`stock_discussion_buzz`／`services/chip_provider.py`／`strategies/conditions_sentiment.py` 全數未被本次改動觸及 |
| AC-P6-08 | `cd backend && python -m pytest tests -q` 全綠，既有測試數量不因本次改動而減少 |

---

## 8. Critical Files

`backend/db/migration/V25__Create_forum_sentiment_tables.sql`（新增）、
`backend/repositories/forum_repository.py`（新增）、
`backend/repositories/news_repository.py`（P0 沿用的既有慣例範本，唯讀參考，不修改）、
`backend/tests/test_forum_repository.py`（新增）、
`backend/services/news_fetcher.py`（P1 抓取器的既有存取路徑參考，唯讀，不修改其現有函式）。
