---
name: api-spec-generator
description: >-
  根據使用者提供的模組需求、資料表結構或 Use Case 文件，自動套用 API 規格書範本，
  產生完整的 RESTful API 規格文件（含 CRUD 端點、請求/響應範例、驗證規則、錯誤碼定義、
  架構圖與業務流程圖）。當使用者提到以下任何一項時，務必使用此 Skill：
  產生 API 規格書、生成 API 文件、API spec、API 規格、RESTful API 設計、
  寫 API 文件、API 規格文件、建立 API 規格、API specification、
  從資料表產生 API、從 use case 產生 API、模組 API 設計、後端 API 規格、
  Spring Boot API 規格、JPA API 設計、更新 API、修改 API、API 變更、
  新增 API 端點、調整 API 欄位、API 規格更新、同步 API 文件。
  即使使用者只說「幫我寫這個模組的 API」、「產生後端規格」、
  「我改了 API，幫我更新規格書」或「新增了一個端點，更新文件」，也應觸發此 Skill。
  當使用者修改、新增或刪除任何 API 端點時，務必同步更新對應的 API 規格書，
  確保規格文件與實際 API 實作保持一致。
---

# API 規格書產生器 Skill

## 目標

根據使用者提供的模組資訊（資料表結構、Use Case、口頭描述等），自動套用專案標準 API 規格書範本，產生或更新 RESTful API 規格文件。產出文件需符合 Spring Boot 3 + JPA/Hibernate 實作慣例，並可直接交付前後端開發人員使用。

**重要原則**：當 API 端點有任何異動（新增、修改、刪除端點或欄位），必須同步更新對應的 API 規格書，確保文件與實作永遠一致。

## 範本位置

**必讀範本檔案**（每次觸發時都必須讀取）：

```
docs/11_Standards_and_Templates/templates/document-templates/[專案名稱]-API規格書-template.md
```

此範本為最終輸出的結構基礎，所有產出文件必須嚴格遵循此範本的章節結構與格式。

## 輸入來源

使用者可能提供以下一或多種輸入，Skill 需能靈活組合運用：

| 輸入類型 | 說明 | 範例 |
|---------|------|------|
| **資料表結構** | DB 規格書或 SQL DDL | `CREATE TABLE th_employee (...)` |
| **Use Case 文件** | 需求文件描述的業務功能 | `docs/01_Requirements/use-cases/XXX/使用案例.md` |
| **口頭描述** | 使用者直接描述模組功能 | 「幫我寫一個員工管理的 API」 |
| **Entity / DTO 類別** | Java Entity 或 DTO 原始碼 | `EmployeeEntity.java` |
| **既有 API 端點** | 已有的 Controller 程式碼 | `EmployeeController.java` |

## 產出步驟

### 步驟 1：讀取範本

**每次執行必須先讀取範本檔案**：

```
docs/11_Standards_and_Templates/templates/document-templates/[專案名稱]-API規格書-template.md
```

從範本中提取以下結構框架：
- 文件資訊表格格式
- API 設計原則章節
- API 清單總覽表格格式
- API 詳細規格（每個端點）的格式：摘要表、請求參數表、請求範例、成功響應、錯誤響應
- 統一錯誤響應格式與錯誤碼定義
- 系統架構 Mermaid 圖
- 實作層級（Controller / Service / Repository / Entity / DTO）說明格式
- Entity 關聯 ER Diagram 格式
- 業務流程 Sequence Diagram 格式

### 步驟 2：收集模組資訊

根據使用者輸入，確認以下資訊（不足時主動詢問）：

| 必要資訊 | 說明 |
|---------|------|
| **專案名稱** | 用於文件標題與套件路徑（例如 `ecard`、`thmcpa`） |
| **模組名稱** | 業務模組識別（例如 `weighing`、`employee`） |
| **資源名稱（複數）** | RESTful 路徑中的資源名（例如 `employees`、`weighing-records`） |
| **對應資料表** | 主要操作的資料表名稱與欄位 |
| **業務功能** | 需要哪些 CRUD 操作、是否有特殊端點（批次/匯出等） |

### 步驟 3：產生 API 清單

根據業務功能，列出所有需要的 API 端點，遵循範本的路徑設計標準：

| HTTP 方法 | 路徑格式 | 用途 |
|----------|----------|------|
| GET | `/api/{resources}` | 查詢列表（分頁） |
| GET | `/api/{resources}/{id}` | 查詢單筆 |
| POST | `/api/{resources}` | 新增 |
| PUT | `/api/{resources}/{id}` | 更新 |
| DELETE | `/api/{resources}/{id}` | 刪除 |
| POST | `/api/{resources}/batch` | 批次操作（視需求） |
| GET | `/api/{resources}/export` | 匯出功能（視需求） |

### 步驟 4：為每個端點產生詳細規格

每個 API 端點必須包含以下完整內容（嚴格遵循範本格式）：

#### 4.1 端點摘要表
```markdown
| 項目 | 說明 |
|------|------|
| **HTTP Method** | GET / POST / PUT / DELETE |
| **URL** | `/api/{resources}` |
| **功能** | 功能描述 |
| **對應資料表** | `table_name` |
```

#### 4.2 請求參數 / Body
- **GET 列表**：Query Parameters 表格（含參數名稱、類型、必填、預設值、描述、驗證規則）
- **GET 單筆**：路徑參數表格
- **POST / PUT**：JSON Body 範例 + 欄位驗證規則表格

#### 4.3 請求範例
完整的 HTTP 請求範例，含 Headers

#### 4.4 成功響應
- GET 列表：含 `content`、`pageable`、`totalElements` 等分頁結構
- GET 單筆 / POST / PUT：含完整 entity 資料
- DELETE：`data: null`
- 外層統一格式：`{ success, message, data, timestamp }`

#### 4.5 錯誤響應
至少提供一個相關的錯誤響應範例（400 / 404 / 409 等）

### 步驟 5：產生架構與流程圖

依範本格式產生以下 Mermaid 圖表：

1. **API 架構概覽**（`graph TB`）：Controller → Service → Repository → Database
2. **Entity 關聯 ER Diagram**（`erDiagram`）：根據資料表關聯
3. **標準 CRUD 流程**（`sequenceDiagram`）：前端 → Controller → Service → Repository → DB
4. **批次處理流程**（如有批次端點）
5. **分頁查詢流程**（如有列表查詢）

### 步驟 6：產生實作層級說明

按範本格式列出每一層的類別：

| 層級 | 套件路徑模式 | 產出內容 |
|------|------------|---------|
| Controller | `com.tcci.{project}.controller.{module}` | 類別表格 + 程式碼範例 |
| Service | `com.tcci.{project}.service.{module}` | Interface + Impl + ValidationService |
| Repository | `com.tcci.{project}.repository` | 介面定義 + 查詢方法 + 使用範例 |
| Entity | `com.tcci.{project}.entity` | Entity 類別 + JPA 註解 |
| DTO | `com.tcci.{project}.dto` | Request / Response DTO |

### 步驟 7：組裝最終文件

將所有產出內容按範本章節順序組裝：

1. **文件資訊**（更新專案名稱、日期、版本）
2. **API 設計原則**（直接沿用範本）
3. **API 清單總覽**（步驟 3 產出）
4. **API 詳細規格**（步驟 4 產出，每個端點一節）
5. **統一錯誤響應格式**（沿用範本的錯誤碼定義）
6. **系統架構**（步驟 5 的架構圖 + 專案結構表）
7. **實作層級說明**（步驟 6 產出）
8. **資料存取層**（Entity + Repository + ER Diagram）
9. **業務流程圖**（步驟 5 的 Sequence Diagram）

## 輸出位置

產出檔案命名規則：`{專案名稱}-API規格書.md`

建議存放路徑：
```
docs/02_Design/api/{專案名稱}-API規格書.md
```

若目錄不存在，自動建立。

## 關鍵規則

1. **必須讀取範本**：每次產出或更新前，先讀取範本檔案取得最新格式。不可憑記憶產出。
2. **API 異動必須同步更新規格書**：任何 API 端點的新增、修改、刪除，都必須同步更新對應的 API 規格書文件。包括但不限於：新增端點、修改請求/響應欄位、調整驗證規則、變更路徑、更新錯誤碼。
3. **更新時保留既有內容**：更新規格書時，僅修改受影響的章節，不重寫未變更的部分。更新 API 清單總覽表的狀態欄（新增標記 🆕、修改標記 🔄、刪除標記 ❌）。
4. **欄位對應資料表**：所有 API 欄位名稱必須與資料表欄位保持一致對應（camelCase ↔ snake_case）。
5. **驗證規則完整**：每個請求欄位都要有明確的驗證規則（`@NotBlank`、`@Size`、`@Min` 等）。
6. **範例資料真實**：JSON 範例中的資料要符合業務語境，不使用 lorem ipsum。
7. **錯誤碼統一**：使用範本定義的 7 種標準錯誤碼（VALIDATION_ERROR、RESOURCE_NOT_FOUND、DUPLICATE_KEY、BUSINESS_ERROR、UNAUTHORIZED、FORBIDDEN、INTERNAL_ERROR）。
8. **分頁格式統一**：列表查詢一律使用 Spring Data 分頁結構（`content`、`pageable`、`totalElements`）。
9. **時間戳格式**：`createtime`、`modifytime` 使用 `LocalDateTime`；日期欄位使用 `LocalDate`。
10. **版本追蹤**：更新規格書時，遞增文件版本號並更新「最後更新」日期。

## 範例：觸發方式

以下是使用者可能的觸發語句：

### 新建 API 規格書
- 「幫我產生員工管理模組的 API 規格書」
- 「根據這個資料表結構，生成 API 文件」
- 「我有個 use case，幫我寫對應的 API spec」
- 「產生 API 規格書」
- 「這個模組需要哪些 API？幫我寫成規格文件」
- 「Generate REST API specification for this module」

### 更新 API 規格書
- 「我改了 API，幫我更新規格書」
- 「新增了一個端點，更新 API 文件」
- 「這個欄位改名了，同步更新 API spec」
- 「刪除了某個 API，更新規格書」
- 「API 加了新的查詢參數，更新文件」
- 「更新 API 規格書」
- 「API 有變更，規格書要跟著改」

## 更新模式（Update Mode）

當使用者要求更新既有的 API 規格書時，執行以下流程：

### 步驟 U1：讀取範本與既有規格書

1. 讀取範本檔案：`docs/11_Standards_and_Templates/templates/document-templates/[專案名稱]-API規格書-template.md`
2. 讀取既有的 API 規格書檔案

### 步驟 U2：識別變更範圍

根據使用者描述或程式碼差異，識別哪些 API 端點受影響：
- **新增端點**：按範本格式新增完整的端點規格（摘要表 + 請求 + 響應 + 錯誤）
- **修改端點**：更新受影響的欄位、驗證規則、請求/響應範例
- **刪除端點**：從規格書中移除對應章節

### 步驟 U3：更新 API 清單總覽

在清單總覽表中標記變更狀態：

| 標記 | 含義 |
|------|------|
| 🆕 | 本次新增的端點 |
| 🔄 | 本次修改的端點 |
| ❌ | 本次刪除的端點（保留一個版本後移除） |

### 步驟 U4：同步更新相關章節

確保以下章節同步更新：
- API 清單總覽表
- 對應端點的詳細規格
- ER Diagram（若資料表結構變更）
- Entity / DTO 類別說明（若欄位變更）
- 業務流程圖（若流程變更）

### 步驟 U5：更新文件版本

- 遞增文件版本號（例如 `v0.1.0` → `v0.2.0`）
- 更新「最後更新」日期為當天
