# 技能：TCCI FastAPI 企業架構開發者

## 說明
此技能配置 Agent 使用 **TCCI Clean Architecture** 開發 FastAPI 後端應用程式，這是一個結合領域驅動設計 (DDD)、工作單位模式 (UoW)、依賴注入 (Dishka) 和完整國際化 (i18n) 支援的實用 Clean Architecture。它確保單一職責、依賴反轉、交易管理、可測試性，並強制實施統一的全域例外處理和多語系翻譯機制。

### 參考資源
- **Clean Architecture 架構設計**：[fastapi-clean-example](https://github.com/ivan-borovets/fastapi-clean-example)

---

## 專案資料夾標準結構 (Project Structure)

開發任何新功能時，必須嚴格遵守以下分層目錄結構：

```
backend/
├── core/                        ← ⚙️ 橫切關注（Cross-Cutting Concerns）
│   ├── config.py                # 全域設定（HOST、PORT、CORS、PyInstaller 相容）
│   ├── exceptions.py            # AppException（error_code 驅動，不寫死語言文字）
│   ├── handlers.py              # 全域例外攔截 handler + i18n 翻譯
│   ├── i18n.py                  # 多語系支援（zh-TW / zh-CN, lru_cache）
│   └── container.py             # Dishka IoC 容器（UoWProvider, Scope.REQUEST）
├── domain/                      ← 🟡 領域層（Domain Layer — 最核心、最穩定）
│   ├── entities/                # Entity 類別（有 Identity + 業務規則方法）
│   ├── value_objects/           # Value Object（frozen dataclass, 不可變, 值相等）
│   └── ports/                   # Repository ABC 介面 + UnitOfWork ABC
├── infrastructure/              ← 🟢 基礎設施層（Infrastructure — Port 實作）
│   ├── sql/                     # SQL Repository 實作（pyodbc, 不呼叫 commit）
│   ├── memory/                  # Memory Repository 實作（測試 + DB 降轉）
│   └── uow.py                  # SqlUnitOfWork / MemoryUnitOfWork / create_uow()
├── services/                    ← 🧠 應用邏輯層（Application / Service Layer）
│   └── xxx_service.py           # Use Case 函式（接收 UoW，呼叫 uow.commit()）
├── api/v1/endpoints/            ← 🔵 展示層（Presentation — 薄 Controller）
│   └── xxx.py                   # FromDishka[UnitOfWork] + DishkaRoute
├── schemas/                     ← 📋 DTO 層（Request + Response Pydantic Model）
│   ├── weighbridge.py           # Request DTOs
│   └── responses.py             # Response DTOs（BaseResponse 繼承體系）
├── db/                          ← 💾 DB 層
│   ├── session.py               # pyodbc 連線管理 + 降轉旗標（create_connection）
│   └── engi    ne.py                # SQLAlchemy Engine（Connection Pool 管理）
├── crud/                        ← 📁 CRUD 層（向後相容保留，新功能不再新增）
└── tests/                       ← 🧪 測試
    ├── conftest.py              # 共用 fixture（MemoryStore + MemoryUoW）
    └── unit/                    # Service 單元測試（零 DB 依賴）
```

**語系定義檔**：位於專案根目錄 `locales/` 下
```
locales/
├── zh-TW.json                   # 繁體中文
└── zh-CN.json                   # 簡體中文
```

---

## 架構核心原則

| 原則 | 說明 |
|------|------|
| **Dependency Rule** | 依賴方向向內：Presentation → Service → Domain。Infrastructure 向內「實作」Domain Port。 |
| **Dependency Inversion (DIP)** | Service 層依賴 Domain Port（ABC 介面），不依賴 SQL/Memory 具體實作。 |
| **Dependency Injection** | Dishka IoC 容器（`FromDishka[UnitOfWork]`），Controller 只接收依賴、不建立依賴。 |
| **Unit of Work** | 交易邊界統一由 Service 層呼叫 `uow.commit()`，Repository 不 commit。 |
| **DB/Memory 雙軌** | DB 不可用時自動降轉至 MemoryUnitOfWork，開發/展示/測試環境零 DB 依賴。 |
| **i18n Error Handling** | Service 只拋 `AppException(error_code)`，Handler 統一翻譯為使用者語言文字。 |

---

## 開發模式與執行動作 (Execution Modes)

當使用者要求「新增功能 (Feature Generation)」時，Agent **必須**依序產出以下內容：

1. **Request Schema** (`schemas/weighbridge.py`) — Pydantic 輸入 DTO
2. **Response Schema** (`schemas/responses.py`) — Pydantic 輸出 DTO
3. **Domain Entity / Value Object** (`domain/entities/` 或 `domain/value_objects/`) — 若有新業務規則
4. **Repository Port** (`domain/ports/`) — 若需新的 Repository 方法，擴充 ABC
5. **SQL Repository** (`infrastructure/sql/`) — 實作新方法（不呼叫 commit）
6. **Memory Repository** (`infrastructure/memory/`) — 實作新方法（記憶體版）
7. **Service 函式** (`services/xxx_service.py`) — 業務邏輯（接收 `uow: UnitOfWork`）
8. **Controller** (`api/v1/endpoints/xxx.py`) — 薄路由（`FromDishka[UnitOfWork]`）
9. **i18n JSON** (`locales/zh-TW.json` + `locales/zh-CN.json`) — 新增 error_code 對應文字
10. **單元測試** (`tests/unit/test_xxx_service.py`) — 使用 MemoryUoW

**【Agent 強制動作】**：
- 必須同步產出 i18n JSON 擴充內容（繁體中文 zh-TW + 簡體中文 zh-CN）
- 必須同步產出至少一個 Service 單元測試
- 若新增了 Port 方法，SQL 和 Memory 兩個 Repository 都必須實作

---

## 開發規範與守則 (Development Guidelines)

### 1. 分層職責 (Layer Responsibilities)

| 層 | 目錄 | 職責 | 禁止事項 |
|----|------|------|----------|
| **Presentation** | `api/v1/endpoints/` | 接收 HTTP Request → 注入 UoW → 呼叫 Service → 回傳 Response | ❌ 不含任何業務邏輯、不操作 DB |
| **Service** | `services/` | 業務流程編排（組合 Domain + Repository 呼叫）、呼叫 `uow.commit()` | ❌ 不操作 DB、不拋 HTTPException |
| **Domain** | `domain/entities/`, `domain/value_objects/` | 封裝核心業務規則（淨重計算、驗證等） | ❌ 不依賴任何外部框架 |
| **Port** | `domain/ports/` | 定義 Repository ABC 介面 + UnitOfWork ABC | ❌ 不含實作邏輯 |
| **Infrastructure** | `infrastructure/sql/`, `infrastructure/memory/` | 實作 Repository Port（SQL 或記憶體） | ❌ 不呼叫 `commit()`（由 UoW 控制）|
| **Schema** | `schemas/` | Pydantic Request/Response DTO | ❌ 不含業務邏輯 |

### 2. Controller 規範 (Thin Controller Pattern)

Controller **必須**使用以下模式：

```python
from fastapi import APIRouter, Depends
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute

router = APIRouter(prefix="/api/xxx", tags=["功能名稱"], route_class=DishkaRoute)

@router.post("/action", response_model=XxxResponse)
def api_action(
    request_dto: XxxRequest,
    uow: FromDishka[UnitOfWork],
    locale: str = Depends(get_locale),
):
    return xxx_service_function(uow, request_dto, locale)
```

**關鍵規則**：
- 使用 `def`（非 `async def`），因底層 pyodbc 為同步 I/O，FastAPI 自動以 ThreadPool 執行
- 使用 `FromDishka[UnitOfWork]` 注入 UoW（由 Dishka 自動管理生命週期）
- 使用 `Depends(get_locale)` 從 Accept-Language Header 取得語系
- 必須宣告 `response_model=XxxResponse`（Swagger 文件自動生成）
- Controller 只做三件事：接收 → 呼叫 Service → 回傳

### 3. Service 規範 (Service Layer Pattern)

```python
from backend.core.i18n import DEFAULT_LOCALE, translate
from backend.core.exceptions import AppException
from backend.domain.ports.unit_of_work import UnitOfWork

def do_something(uow: UnitOfWork, record, locale: str = DEFAULT_LOCALE) -> dict:
    # 1. 使用 Domain Entity 執行業務規則
    # 2. 透過 uow.xxx_repo 存取 Repository（如 uow.tickets, uow.po）
    # 3. 呼叫 uow.commit() 提交交易
    # 4. 回傳 dict（符合 Response Schema 結構）
    # 5. 錯誤時 raise AppException("ERROR_CODE", status_code=4xx)
    ...
```

**關鍵規則**：
- 第一個參數必須是 `uow: UnitOfWork`
- 透過 `uow.tickets`、`uow.po`、`uow.auth` 等屬性存取 Repository
- 所有可翻譯訊息使用 `translate(key, locale, **kwargs)` 取得
- 錯誤只拋 `AppException(error_code, status_code)`，**絕不寫死語言文字**
- 寫入完成後呼叫 `uow.commit()`
- 回傳 dict 必須包含 `status`、`message`、`dbMode` 等標準欄位

### 4. Domain Entity 規範

```python
class XxxEntity:
    def __init__(self, id: str, ...):
        self._id = id  # 唯一識別碼（不可變）
    
    @property
    def id(self) -> str:
        return self._id
    
    def business_rule_method(self, ...) -> ...:
        """封裝業務規則（如計算、驗證、狀態轉換）"""
        ...
    
    @staticmethod
    def resolve_xxx(input: str) -> str:
        """靜態規則映射"""
        ...
```

**關鍵規則**：
- Entity 有唯一識別碼（Identity），以 property 暴露、不可變
- 業務規則（計算、驗證）封裝為 Entity 方法
- **不依賴任何外部框架**（無 FastAPI、無 SQLAlchemy、無 Pydantic）
- Value Object 使用 `@dataclass(frozen=True, slots=True)` 實作

### 5. Repository Port 規範

```python
from abc import ABC, abstractmethod

class XxxRepository(ABC):
    @abstractmethod
    def create(self, data: dict) -> dict: ...
    
    @abstractmethod
    def get_by_id(self, id: str) -> dict | None: ...
    
    @abstractmethod
    def list_all(self, limit: int = 100) -> list[dict]: ...
```

**關鍵規則**：
- 定義在 `domain/ports/` 目錄
- 使用 Python ABC（`abstractmethod`）
- 參數與回傳值使用 Python 原生型別（`dict`、`list`、`str`），不用框架型別
- 每新增一個 Port 方法，`infrastructure/sql/` 和 `infrastructure/memory/` 都必須實作

### 6. Unit of Work 規範

UnitOfWork 是 Repository 的容器 + 交易邊界控制：

```python
class UnitOfWork(ABC):
    tickets: TicketRepository
    po: PoRepository
    auth: AuthRepository
    trucks: TruckRepository
    warnlog: WarnlogRepository
    traces: TraceRepository
    
    @abstractmethod
    def commit(self) -> None: ...
    
    @abstractmethod
    def rollback(self) -> None: ...
    
    @property
    @abstractmethod
    def db_mode(self) -> str: ...
```

**新增 Repository 時**：需同步更新 `UnitOfWork` ABC + `SqlUnitOfWork` + `MemoryUnitOfWork` 的屬性。

### 7. SQL Repository 規範

```python
class SqlXxxRepository(XxxRepository):
    def __init__(self, conn):
        self._conn = conn
    
    def create(self, data: dict) -> dict:
        cur = self._conn.cursor()
        cur.execute("INSERT INTO ... VALUES (?, ?, ?)", ...)
        # ⚠️ 絕不呼叫 conn.commit()（由 UoW 控制）
        return data
```

**關鍵規則**：
- `conn` 在 `__init__` 中注入，方法中使用 `self._conn`
- 使用參數化查詢（`?` placeholder），**嚴禁字串拼接 SQL**
- **絕不呼叫 `conn.commit()` 或 `conn.rollback()`**（由 UoW 統一控制）
- 所有 SQL Repository 共用同一條 DB 連線（透過 SqlUnitOfWork）

### 8. Memory Repository 規範

```python
from backend.infrastructure.memory import MemoryStore

class MemoryXxxRepository(XxxRepository):
    def __init__(self, store: MemoryStore):
        self._store = store
    
    def create(self, data: dict) -> dict:
        self._store.xxx_store[data['id']] = data
        return data
```

**關鍵規則**：
- 接收 `MemoryStore` 實例（非全域 dict），確保測試隔離
- 使用 `self._store.lock` 進行執行緒安全操作（需修改共享狀態時）
- 與 SQL Repository 行為一致（相同的參數、相同的回傳結構）

### 9. 全域例外處理與多國語系 (Global Exception Handling & i18n)

* **Service 層絕對純淨**：嚴禁在 `services/` 或 Repository 層拋出 `fastapi.HTTPException`。遇到業務錯誤時，只拋出：
  ```python
  raise AppException("ERROR_CODE", status_code=404, param1="value1")
  ```
  **絕不在這裡寫死任何語言的錯誤文字**。

* **i18n 字典產出要求**：當定義了新的 `error_code` 或成功訊息 key 時，**必須同時產出**：
  ```json
  // locales/zh-TW.json (新增)
  {
    "ITEM_OUT_OF_STOCK": "該商品目前庫存不足",
    "ITEM_CREATED_SUCCESS": "商品「{item_name}」已成功建立"
  }
  
  // locales/zh-CN.json (新增)
  {
    "ITEM_OUT_OF_STOCK": "该商品目前库存不足",
    "ITEM_CREATED_SUCCESS": "商品「{item_name}」已成功创建"
  }
  ```
  翻譯文字中可使用 `{param}` 佔位符，由 `translate(key, locale, **kwargs)` 自動格式化。

* **Handler 統一攔截**：`handlers.py` 攔截 `AppException`，自動翻譯為標準 JSON 回應：
  ```json
  {"success": false, "error_code": "ERROR_CODE", "message": "翻譯後的文字"}
  ```

### 10. Schema 規範 (Request & Response DTO)

**Request Schema**（`schemas/weighbridge.py`）：
```python
class XxxRequest(BaseModel):
    field1: str
    field2: Optional[int] = None
```

**Response Schema**（`schemas/responses.py`）：
```python
class XxxResponse(BaseResponse):
    """對應端點的回應 DTO"""
    message: str
    customField: str
```

**關鍵規則**：
- 所有 Response 繼承 `BaseResponse`（含 `status: str`）
- `@router.post(response_model=XxxResponse)` 必須宣告，用於 Swagger 自動文件
- Request 和 Response 分開定義（輸入 ≠ 輸出）

### 11. 單元測試規範

```python
import pytest
from backend.schemas.weighbridge import XxxRequest
from backend.services.xxx_service import do_something

def _make_request(**overrides) -> XxxRequest:
    defaults = {"field1": "value1", "field2": 42}
    defaults.update(overrides)
    return XxxRequest(**defaults)

class TestDoSomething:
    def test_success(self, uow):
        result = do_something(uow, _make_request(), "zh-TW")
        assert result["status"] == "success"
    
    def test_not_found_raises(self, uow):
        with pytest.raises(AppException):
            do_something(uow, _make_request(field1="nonexistent"), "zh-TW")
```

**關鍵規則**：
- 使用 `conftest.py` 提供的 `uow` fixture（MemoryUoW，零 DB 依賴）
- 每個測試函式取得獨立的 MemoryStore 實例（測試隔離）
- 測試 Service 函式，不測 Controller（Controller 僅為薄適配器）
- 使用 `_make_request()` 工廠函式建立測試用 DTO

### 12. Dishka IoC 容器規範

```python
# core/container.py
from dishka import Provider, Scope, provide, make_container

class UoWProvider(Provider):
    scope = Scope.REQUEST

    @provide(provides=UnitOfWork)
    def get_uow(self) -> Iterator[UnitOfWork]:
        if is_fallback():
            yield MemoryUnitOfWork()
            return
        conn = create_connection()
        if conn is None:
            yield MemoryUnitOfWork()
            return
        uow = SqlUnitOfWork(conn)
        try:
            yield uow
        except Exception:
            uow.rollback()
            raise
        finally:
            conn.close()
```

**關鍵規則**：
- 使用 generator `yield` 模式——Dishka 在 Request 結束時自動 cleanup
- DB 不可用時自動降轉至 `MemoryUnitOfWork`
- Scope.REQUEST：每次 HTTP Request 一個 UoW 實例
- `main.py` 中呼叫 `setup_dishka(container, app)` 掛載

---

## 範本導覽與設計目的 (Templates Overview & Purpose)

本 Skill 提供標準化開發範本位於 `templates/` 資料夾下。Agent 生成程式碼時，**必須遵循**這些範本的設計模式：

| # | 範本 | 對應層 | 說明 |
|---|------|--------|------|
| 1 | `domain_entity.py.tmpl` | Domain Layer | Entity 類別（業務規則封裝，無外部依賴） |
| 2 | `domain_value_object.py.tmpl` | Domain Layer | Value Object（frozen dataclass，不可變） |
| 3 | `domain_port.py.tmpl` | Domain Layer | Repository ABC 介面定義 |
| 4 | `sql_repository.py.tmpl` | Infrastructure Layer | SQL Repository 實作（不 commit） |
| 5 | `memory_repository.py.tmpl` | Infrastructure Layer | Memory Repository 實作（測試用） |
| 6 | `service.py.tmpl` | Service Layer | 業務邏輯函式（接收 UoW） |
| 7 | `api_router.py.tmpl` | Presentation Layer | 薄 Controller（FromDishka + DishkaRoute） |
| 8 | `schema_request.py.tmpl` | DTO Layer | Pydantic Request Model |
| 9 | `schema_response.py.tmpl` | DTO Layer | Pydantic Response Model（繼承 BaseResponse） |
| 10 | `unit_test.py.tmpl` | Test Layer | Service 單元測試（MemoryUoW fixture） |