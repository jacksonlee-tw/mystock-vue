---
name: usecase-to-design
description: 根據 Use Case 文件、Delphi 原始碼（.pas / .dfm）與資料庫規格書，自動產生系統設計文件（System Design Document）。每份設計文件包含功能說明、資料表明細、ER Diagram（Mermaid）、相關 Delphi 程式清單及 SQL 語句。當使用者要求「產生設計文件」、「生成系統設計」、「從 use case 產生 SD」、「use case 轉設計」、「幫我寫系統設計文件」、「分析這個模組的設計」、「design document」、「SD 文件」時，務必使用此 Skill。適用對象：MM_D7、MM_D10 或任何包含 Delphi/Object Pascal 程式碼的磅秤系統模組。
---

# Use Case → 系統設計文件（System Design Document）轉換 Skill

## 目標

從 Use Case 需求文件出發，結合 Delphi 原始碼分析與資料庫規格書，產生完整的系統設計文件，讓開發團隊理解每個模組的技術實作細節、資料流與程式檔案關聯。

## 輸入來源

此 Skill 依賴三大資料來源，缺一不可：

| 來源 | 路徑 | 說明 |
|------|------|------|
| Use Case 文件 | `docs/01_Requirements/use-cases/<子目錄>/UC-*.md` | 業務需求規格 |
| Delphi 原始碼 | `MM_D10/Source/` 及 `MM_D10/COMMON/` | 程式實作（.pas + .dfm） |
| 資料庫規格書 | `docs/02_Design/db/mmsystem-db規格書.md` | 資料表定義與欄位說明 |

若使用者未明確指定，預設使用 `MM_D10`（現行版本）。

## 分析流程

### 步驟 1：讀取 Use Case 文件

從指定的 Use Case 文件中提取：
- **UC 代號與名稱**（例：`UC-arrivePlant-廠門地磅作業`）
- **使用案例清單**（每個子功能 UC 的編號、名稱、說明）
- **業務流程**（主要流程步驟、替代流程）
- **涉及的資料欄位**（輸入/輸出）
- **模組代號**（從檔名推導，例：`UC-arrivePlant-廠門地磅作業.md` → `uarrivePlant`）

### 步驟 2：識別主要 Delphi 程式檔案

根據 Use Case 的模組代號，在 MM_D10 目錄中找出對應的 Delphi 檔案：

**檔案搜尋策略：**
1. 搜尋名稱匹配的 `.pas` 與 `.dfm`（例：`uarrivePlant.pas`、`uarrivePlant.dfm`）
2. 搜尋帶後綴的變體版本（`_00`、`_x`、`_old`、`new`、`bak`）
3. 排除明確的備份檔（含「副本」字樣）

**常用模組名稱與檔案對應表：**

| Use Case 模組 | 主要程式檔案 | 備註 |
|--------------|-------------|------|
| arrivePlant | `uarrivePlant.pas` | 另有 `_00`、`_x` 變體 |
| instore | `uInstore.pas` | 同時包含 A2/B2 邏輯 |
| outstore | `uInOutStore.pas` | ⚠ `uOutStore.pas` 為 Stub，實際邏輯在此 |
| flishwork | `uflishwork.pas`、`uflishworknew.pas` | 新舊版並存 |
| inOutKaijin | `uInOutKaijin.pas` | 借金開金 |
| kajin | `ukajin.pas` | 開金作業 |
| gdh | `uGDH.pas`、`uGDHMD.pas` | 過磅查詢 |
| exceptNo | `uexceptNo.pas` | 例外處理 |
| dayrep | `udayrep.pas`、`udayprint.pas` | 日報表 |
| logon | `ulogon.pas` | 登入 |
| user | `uUser.pas`、`uUserALL.pas` | 使用者管理 |
| dbrights | `uDbRights.pas` | 權限管理 |
| dbmaterial | `uDbMaterial.pas` | 物料維護 |
| paras | `uParas.pas`、`uSetParam.pas` | 系統參數 |
| truck | `utruck.pas` | 車輛管理 |
| auto | `uAUTO.pas` | 自動化 |
| led | `uled.pas` | LED 控制 |

### 步驟 3：深度分析 Delphi 原始碼

對每個主要 `.pas` 檔案進行以下分析：

#### 3.1 提取 uses 清單

讀取 `interface` 及 `implementation` 區段的 `uses` 清單，識別所有相依模組。

常見基礎模組（通常出現在 uses 中但不列入設計文件）：
- Windows、SysUtils、Classes、Graphics、Controls、Forms、Dialogs
- StdCtrls、ExtCtrls、ComCtrls、Buttons、Menus
- DB、ADODB

**需列入設計文件的相依模組：**

| 模組 | 說明 |
|------|------|
| `dmconnect` | 資料庫連線模組 |
| `ushare` | 共用函式（insertIntotrace_mstr、Autocode 等） |
| `uglobal` | 全域設定與變數 |
| `xUtils` | 擴充工具函式 |
| `UScale` / `UScale1` | 磅秤設備通訊 |
| `UCardDLL` / `CardRW` | IC 卡讀寫 |
| `uled` / `LEDDLL` | LED 看板控制 |
| `RF_DLL_Def` | RF 讀卡器定義 |
| `sysfunction` | 系統公用函式 |
| `ReportDM` | 報表資料模組 |
| `uExceptUser` | 主管帳密覆核 |
| `ukajin` | 開金作業 |
| `uInstore` | 入庫作業 |
| `uInOutStore` | 入出庫整合 |

#### 3.2 提取所有 SQL 語句

掃描 `.pas` 中所有 SQL 關鍵字，按操作類型分類：

**搜尋模式：**
- `INSERT INTO <table>` → 新增操作
- `UPDATE <table> SET` → 更新操作
- `DELETE FROM <table>` → 刪除操作
- `SELECT ... FROM <table>` → 查詢操作
- `ALTER VIEW <view>` → 動態視圖建立
- `EXEC <procedure>` / `sp_` 前綴 → 預存程序呼叫

**重要 SQL 模式（本專案特有）：**

```pascal
// 版本控制查詢模式（務必在設計文件中說明）
WHERE dbno = '{dbno}'
  AND version = (SELECT MAX(version) FROM CMM_SCALE WHERE dbno = '{dbno}')

// 動態 VIEW 建立模式
ALTER VIEW vCMM_SCALE_One AS SELECT ... FROM CMM_SCALE WHERE ...
```

#### 3.3 提取程序與函式

識別所有 `procedure` 和 `function` 宣告：
- **事件處理程序**：`Button1Click`、`EdtXxxChange`、`Timer1Timer`、`FormCreate`
- **業務邏輯函式**：`checkWorkFlow`、`IsWarningMessage`、`getamstore` 等
- **資料存取函式**：`ExistRecord`、`sExecSQL`、`insertIntotrace_mstr`

對每個程序標註其核心動作（驗證→SQL→顯示→列印）。

#### 3.4 分析 .dfm 表單元件

掃描 `.dfm` 中主要元件區塊：

| 元件類型 | 設計文件用途 |
|---------|------------|
| `TGroupBox` | 表單區塊劃分 |
| `TButton` / `TSpeedButton` / `TBitBtn` | 使用者操作觸發點 |
| `TEdit` / `TComboBox` | 輸入欄位 |
| `TDBGrid` / `TDBGridEh` | 查詢結果顯示 |
| `TTimer` | 自動化操作（磅秤讀取、IC 卡偵測） |
| `frxReport` / `frxPreview` | 報表列印 |
| `TADOQuery` / `TADOCommand` | 資料庫查詢元件 |

### 步驟 4：交叉比對資料庫規格書

讀取 `docs/02_Design/db/mmsystem-db規格書.md`，將 SQL 中使用的資料表：
1. 確認表名與欄位是否存在於規格書
2. 提取欄位定義（資料型態、PK、NULL、說明）
3. 識別跨表關聯（外鍵、JOIN 條件）

**核心資料表：**

| 資料表 | 用途 | 常出現模組 |
|-------|------|-----------|
| CMM_SCALE | 過磅記錄主檔 | arrivePlant、instore、outstore、flishwork |
| MM_POWO_SCALE | 採購/生產單主檔 | arrivePlant、instore |
| MM_SCALE | SAP 對接記錄 | arrivePlant |
| trace_mstr | 操作追蹤稽核 | 所有模組 |
| Warnlog | 警告日誌 | arrivePlant |
| MMWeighrec | 秤重記錄 | arrivePlant |
| TruckList | 車輛清單 | arrivePlant、outstore |
| MMDB | 跨廠區比對 | arrivePlant、flishwork |
| MMPARAS | 系統參數 | instore、outstore、通用 |
| DHNO | 磅單流水號 | arrivePlant |
| user_mstr1 | 使用者帳號 | arrivePlant、logon |
| dbpo | 磅單訂單對應 | arrivePlant |
| dbgroup | 磅單群組 | arrivePlant |
| MM_A1WGT_LOG | A1 秤重日誌 | arrivePlant |

### 步驟 5：生成系統設計文件

依照範本（`assets/design-template.md`）產生 Markdown 文件。

---

## 輸出規則

### 文件命名

```
SD-<模組代號>-<功能名稱>-系統設計.md
```

範例：`SD-arrivePlant-廠門地磅作業-系統設計.md`

### 輸出目錄

```
docs/02_Design/
```

### 文件結構

每份系統設計文件必須包含以下章節（順序固定）：

1. **文件標頭**：對應 UC、模組代號、表單類別、版本、日期
2. **功能說明**（§1）
   - 1.1 模組概述（2–3 句描述業務目的）
   - 1.2 功能清單（表格：功能代號、名稱、說明）
   - 1.3 業務流程（Mermaid `flowchart TD`）
   - 1.4 模組架構關係（Mermaid `flowchart LR`，當架構複雜時）
3. **資料表明細**（§2）
   - 2.1 資料表清單（表格：表名、用途、操作類型）
   - 2.2 核心資料表欄位明細（每張表的欄位定義表格）
4. **ER Diagram**（§3）
   - Mermaid `erDiagram`，列出主要實體與關聯
5. **相關 Delphi 程式**（§4）
   - 4.1 程式檔案清單（表格：路徑、類型、說明）
   - 4.2 關鍵程序與函式（表格：名稱、說明）
   - 4.3 主要 SQL 語句（按操作分類，附程式碼區塊）
6. **附錄**（§5，視模組複雜度決定）
   - 外部 DLL 函式
   - 工作流程狀態值
   - LED 看板常數
   - 表單元件對照

### 撰寫注意事項

1. **版本控制查詢**：凡涉及 CMM_SCALE 的查詢，必須在 SQL 中明確標示 `WHERE version = (SELECT MAX(version) ...)` 的版本控制模式
2. **Form Stub 提醒**：若主程式檔案為 Stub（無業務邏輯），必須在模組概述中以 `> **重要架構說明**` 標註實際實作檔案
3. **動態 VIEW**：若模組使用 `ALTER VIEW` 動態建立視圖，需在 SQL 章節特別說明
4. **工作流程代碼**：統一使用 `'1'=單磅`、`'2'=雙磅`、`'3'=全流程（四磅點）` 說明
5. **四磅點編號**：A1（Port1 進廠）→ A2（Port2 入庫）→ B2（Port3 出庫）→ B1（Port4 出廠）
6. **Mermaid 語法限制**：
   - 使用 `flowchart TD` 或 `flowchart LR`
   - 使用 `erDiagram`
   - 節點標籤使用雙引號包裹含特殊字元的文字
   - 避免在 Mermaid 中使用 `&`、`<`、`>` 等 HTML 特殊字元
7. **繁體中文**撰寫所有說明文字
8. **SQL 語句**使用 ` ```sql ``` ` 程式碼區塊格式

---

## 多模組批次處理

若使用者要求一次生成多個 Use Case 的設計文件，依以下方式處理：

1. 先讀取資料庫規格書（只需讀一次，跨模組共用）
2. 逐一處理每個 Use Case：
   - 讀取 UC 文件
   - 分析對應 Delphi 原始碼（可使用子代理並行分析）
   - 生成設計文件
3. 每產生一份文件後，標記完成並進入下一份

**並行策略**：多個模組的 Delphi 原始碼分析可以並行啟動子代理，每個子代理負責：
- 讀取該模組的 `.pas` 和 `.dfm`
- 提取 SQL、函式、元件清單
- 回傳結構化分析結果

---

## 範例

### 輸入

使用者提供：
```
幫我把 UC-arrivePlant-廠門地磅作業 生成系統設計文件
```

### 處理流程

1. 讀取 `docs/01_Requirements/use-cases/A.arrivePlant/UC-arrivePlant-廠門地磅作業.md`
2. 讀取 `docs/02_Design/db/mmsystem-db規格書.md`
3. 分析 `MM_D10/Source/uarrivePlant.pas` + `uarrivePlant.dfm`
4. 分析相依：`sysfunction.pas`、`UCardDLL.pas`、`dmconnect.pas`、`ushare.pas`、`uglobal.pas`、`UScale.pas`
5. 交叉比對 SQL 中的表名與資料庫規格書
6. 產生 `docs/02_Design/SD-arrivePlant-廠門地磅作業-系統設計.md`

### 輸出

參見 `assets/design-template.md` 中的完整文件結構範本。

---

## 品質檢查清單

生成文件後，逐項確認：

- [ ] 文件標頭完整（UC 對應、模組代號、表單類別、版本、日期）
- [ ] 功能清單涵蓋所有主要按鈕事件
- [ ] 業務流程 Mermaid 圖可正確渲染
- [ ] 資料表清單與 SQL 中出現的表名一致
- [ ] 欄位明細與資料庫規格書吻合
- [ ] ER Diagram 包含所有相關表及關聯線
- [ ] 程式檔案清單包含主程式與關鍵相依模組
- [ ] SQL 語句按操作類型分類且完整
- [ ] 版本控制查詢模式已標示
- [ ] Form Stub 已正確標註（如適用）
