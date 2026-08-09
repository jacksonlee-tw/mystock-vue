# FastAPI Clean Architecture 評估報告

本報告基於 [ivan-borovets/fastapi-clean-example](https://github.com/ivan-borovets/fastapi-clean-example) 對於 Clean Architecture（整潔架構）與 CQRS 在 FastAPI 專案中的實踐指南，針對目前 `\backend` 目錄下的 FastAPI 架構進行分析與評估。

## 1. Clean Architecture 核心理念概述

根據 `fastapi-clean-example` 的最佳實踐，Clean Architecture 的關鍵特徵包含：
* **依賴規則 (Dependency Rule)**：高層次（核心業務規則）不能依賴低層次（基礎設施、DB、第三方框架）。依賴方向永遠是指向內部的核心層。
* **分層設計**：
  * **Domain Layer (領域層)**：包含 Entities (實體)、Value Objects (值物件) 及其純業務規則，具備高內聚且不知曉任何外部框架。
  * **Application Layer (應用層)**：包含 Interactors 或 Services，負責協調領域物件與實作使用案例 (Use Cases)，透過抽象介面 (Ports) 與外部通訊。
  * **Infrastructure & Presentation Layers (基礎設施與表現層)**：包含 Web Framework (如 FastAPI)、資料庫 Adapter、ORM 庫等，作為可被替換的細節。
* **依賴反轉 (Dependency Inversion, DIP)**：不直接實作呼叫，而是透過介面（Port）進行解耦，讓 Adapter 去實作 Port。
* **依賴注入 (Dependency Injection, DI)**：不讓元件自己建立相依物件，而是從外部注入（推薦使用如 `Dishka` 的框架來避免 FastAPI `Depends` 滲透進業務邏輯）。
* **CQRS**：將「讀取 (Queries)」與「寫入 (Commands)」操作分離，進行不同的模型最佳化。

---

## 2. 目錄 `\backend` 現有架構分析

目前的 `\backend` 採用了常見的 **三層式架構 (Controller -> Service -> CRUD)**：
* `api/v1/endpoints/`: 擔任 Presentation Layer (Controller，負責路由、輸入驗證)。
* `services/`: 擔任 Application Layer (包含部分業務邏輯與流程協調)。
* `crud/`: 擔任 Infrastructure / Data Access Layer (直接執行 SQL 與存取記憶體資料)。

### 優點 (Pros)
1. **職責分離直觀**：Router 只負責處理 Request/Response 與 FastAPI 邏輯；Service 處理過磅邏輯；CRUD 專注在 SQL 操作。
2. **無狀態 (Stateless)**：API Router 沒有持有全域狀態，適合各種非同步環境。
3. **統一錯誤處理**：Service 透過發出 `AppException` 給 Controller 來做統一攔截處理。

### 缺點與 Clean Architecture 違規之處 (Cons & Violations)
1. **基礎設施外洩 (Leaking Infrastructure Details)**：
   * 在 Controller `entry.py` 中有 `with get_db_context() as conn:`，並將 `conn` (DB Connection) 這個屬於Infrastructure 的實體物件一路往下傳遞給 `Service`，甚至 `CRUD`。這違反了「依賴規則」，導致業務邏輯層被迫知道資料庫連線的細節。
2. **缺乏依賴反轉 (No Dependency Inversion)**：
   * `ticket_service.py` 頂端直接宣告 `from backend.crud import ticket_crud`，這產生了硬耦合 (`Service -> CRUD`)。若未來要抽換底層，必須改寫 Service 的匯入；若要撰寫單元測試，也較難利用介面進行 Mock。
3. **貧血模型 (Anemic Domain Model) 與無 Domain 層**：
   * 架構中並沒有真正的實體(Entities)與值物件，Service 主要是用字典(Dict) 與 Pydantic 的 DTOs 取代了實體。商業規則（如淨重計算、退貨邏輯）散落在 Service 的流程中，未能與資料緊密綁定（無豐富的領域知識封裝）。
4. **CRUD 混雜實作**：
   * `ticket_crud.py` 內部同時包含了 `pyodbc` 的 SQL 以及純 `memory dict` 的 Mock 邏輯（由 `conn is None` 來判斷）。在 Clean Architecture 中，應透過實現不同 Adapter 替換（如 `SqlTicketRepository` 和 `InMemoryTicketRepository`），而非在同一個檔案內寫 IF-ELSE。

---

## 3. 架構三構面評估

### 📌 易於了解 (Easy to Understand)
**評分：⭐ 高 (High)**
* 此三層架構非常平易近人。對於中小型專案或原型 (POC) 來說，不需經歷陡峭的 DDD 或泛型/介面學習曲線。
* 資料流動方向單一 (`API -> Service -> CRUD / DB`)，後端工程師通常一看就能明白。

### 📌 易於開發 (Easy to Develop)
**評分：⭐ 高 (High)**（針對初期與小規模）
* 新增功能時，只要在 `endpoints` 加路由 -> 在 `services` 加 function -> 在 `crud` 加 SQL 就能完工，開發速度極快。
* 直接覆用 `Dict` 或 Pydantic 模組當作資料傳遞載體，省去了 `DTO <-> Entity` 各式物件轉換 (Mapping) 的繁瑣工序。

### 📌 易於維護 (Easy to Maintain)
**評分：⚠️ 中/低 (Medium to Low)**（長期維護與測試觀點）
* **測試困難**：當專案變大時，由於 Service 與 CRUD 緊密耦合且依賴原生的 DB `conn`，要寫純淨的單元測試十分困難（只能仰賴傳入 `conn = None` 觸發 crud 內的特製 mock 分支，而非常規的依賴注入 Mocking）。
* **擴展性受限**：若此專案想要從 MSSQL (`pyodbc`) 切換到 SQLAlchemy 甚至別種類型的資料庫，牽涉 `conn` 的改動會波及 Controller 到 CRUD 各層。
* 隨時間推移，業務邏輯如果變複雜，全部塞在 `Service` 的函數會退化為義大利麵條式代碼 (Spaghetti Code)（也就是大泥球 Anti-Pattern）。

---

## 4. 改善與重構建議 (邁向 Clean Architecture)

若系統未來預期會有大量業務規則變更，或需要提高長遠的維護性，建議可分階段參考 `fastapi-clean-example` 進行以下重構：

1. **實作介面反轉 (Dependency Inversion with Ports / Repositories)** 
   - 建立 `domain/repositories/ticket_repository.py` 定義 `ITicketRepository` (Python `abc.ABC` 或 `Protocol`) 介面。
   - `services` 不吃 `conn`，而是依賴 `ITicketRepository` 來存取資料。
2. **引入依賴注入框架 (Dependency Injection)**
   - 引入像 `Dishka` 的控制反轉(IoC)庫。
   - 讓 `SqlTicketRepository` 實作 `ITicketRepository` 並由 DI 容器注入給 `Service`，徹底把 `conn` 從 API Router 和 Service 中消滅。
3. **分離 Domain Model**
   - 建立 `domain/entities/ticket.py` 封裝純秤重邏輯和檢核，確保邏輯不會散落在 `dict` 組裝區。
4. **引入 CQRS (可選)**
   - 把「寫入磅單」改放至 `commands/`；把單純查詢列表的工作獨立放入 `queries/` 來繞過領域複雜驗證，直接存取 DB 返回呈現資料。