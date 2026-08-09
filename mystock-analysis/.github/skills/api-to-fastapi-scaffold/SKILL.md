---
name: api-to-fastapi-scaffold
description: >-
  從 API 規格書自動產生 FastAPI Router、Service、Repository 框架程式碼。
  當使用者提到以下任何一項時，務必使用此 Skill：
  產生 API 實作框架、API spec 轉 FastAPI、產生 Router、產生 Service、
  API 規格轉程式碼、scaffold API、FastAPI 程式碼生成、
  怎麼實作這個 API、產生後端框架、API to code、endpoint scaffold、
  從規格書產生 FastAPI router、產生 CRUD router。
  即使使用者只說「幫我實作這個 API」、「產生後端程式」、
  「把 API 規格轉成程式碼」，也應觸發此 Skill。
---

# API 規格書 → FastAPI 框架程式碼生成 Skill

## 目標

從 `api-spec-generator` 產出的 API 規格書，自動產生三層框架程式碼：
1. **Router**（`routers/<module>_router.py`）— 端點定義、參數驗證
2. **Service**（`services/<module>_service.py`）— 業務邏輯骨架 + TODO 標記
3. **Repository**（`repos/<module>_repo.py`）— 資料存取查詢

產出程式碼遵循 `fastapi-development` Skill 的架構規範，搭配 `db-to-sqlalchemy-generator` 
產出的 Model 與 Schema 直接可用。

---

## 前置讀取（每次必讀）

1. `.github/skills/fastapi-development/SKILL.md` — 架構分層與命名規範
2. 對應的 API 規格書文件（使用者指定或自動搜尋）
3. 對應的 Model / Schema（若已存在則讀取，確保 import 一致）

---

## 輸入來源

| 輸入類型 | 說明 | 範例 |
|---------|------|------|
| **API 規格書** | `api-spec-generator` 產出的規格文件 | `docs/02_Design/api/ecard-weighing-API規格書.md` |
| **口頭描述** | 簡述需要哪些端點 | 「幫我產生使用者管理的 CRUD API」 |
| **既有程式碼** | 需補充端點的既有 Router | `app/routers/user_router.py` |

---

## 解析規則

### 從 API 規格書提取資訊

掃描規格書中的每個端點區塊，提取：

| 規格書欄位 | 對應程式碼 |
|-----------|-----------|
| HTTP Method + URL | `@router.<method>("<path>")` |
| 功能描述 | 函式 docstring |
| 請求參數 (Query) | 函式參數 + `Query(...)` |
| 路徑參數 | 函式參數（型別自動驗證） |
| 請求 Body | Pydantic Schema 參數 |
| 成功回應 | `response_model=ApiResponse[...]` |
| 錯誤回應 | Service 層的異常處理 |
| 驗證規則 | Schema Field constraints |
| 分頁參數 | `PageParams` 依賴 |

### 端點命名轉換

| API 規格 | Router 函式名 | Service 方法名 | Repo 方法名 |
|----------|-------------|---------------|-------------|
| `GET /resources` | `list_<resources>` | `list_<resources>` | `get_all` |
| `GET /resources/{id}` | `get_<resource>` | `get_by_id` | `get_by_id` |
| `POST /resources` | `create_<resource>` | `create_<resource>` | `create` |
| `PUT /resources/{id}` | `update_<resource>` | `update_<resource>` | `update` |
| `DELETE /resources/{id}` | `delete_<resource>` | `delete_<resource>` | `delete` |
| `POST /resources/batch` | `batch_<action>` | `batch_<action>` | 自訂 |
| `GET /resources/export` | `export_<resources>` | `export_<resources>` | 自訂 |

---

## 產出步驟

### Step 1：解析 API 規格書

從規格書中提取模組資訊：
- **模組名稱**（如 `weighing`）
- **資源名稱**（如 `weighing-records`）
- **端點清單**（method + path + 描述）
- **請求/回應格式**
- **對應資料表名稱**

### Step 2：產生 Repository

```python
# repos/<module>_repo.py
"""<中文名稱> 資料存取層。"""
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.<model_file> import <ModelClass>
from app.repos.base import BaseRepository


class <Module>Repo(BaseRepository[<ModelClass>]):
    def __init__(self, session: AsyncSession):
        super().__init__(<ModelClass>, session)

    # --- 自訂查詢方法（從 API 規格書的篩選條件推導）---

    async def find_by_<filter_field>(self, value: <type>) -> list[<ModelClass>]:
        """依 <欄位中文名> 查詢。"""
        stmt = select(<ModelClass>).where(<ModelClass>.<field> == value)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

### Step 3：產生 Service

```python
# services/<module>_service.py
"""<中文名稱> 業務邏輯層。"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.repos.<module>_repo import <Module>Repo
from app.models.<model_file> import <ModelClass>
from app.schemas.<schema_file> import <Name>Create, <Name>Update
from app.schemas.common import PageParams, PageResponse
from app.exceptions import NotFoundError, BusinessError


class <Module>Service:
    def __init__(self, session: AsyncSession):
        self.repo = <Module>Repo(session)
        self.session = session

    async def get_by_id(self, id: int) -> <ModelClass>:
        record = await self.repo.get_by_id(id)
        if not record:
            raise NotFoundError(f"<中文名稱> {id} 不存在")
        return record

    async def list_records(self, page_params: PageParams) -> PageResponse:
        return await self.repo.get_all(page_params)

    async def create(self, data: <Name>Create) -> <ModelClass>:
        record = <ModelClass>(**data.model_dump())
        # TODO: 補充業務驗證邏輯
        result = await self.repo.create(record)
        await self.session.commit()
        return result

    async def update(self, id: int, data: <Name>Update) -> <ModelClass>:
        record = await self.get_by_id(id)
        update_data = data.model_dump(exclude_unset=True)
        # TODO: 補充業務驗證邏輯
        result = await self.repo.update(record, update_data)
        await self.session.commit()
        return result

    async def delete(self, id: int) -> bool:
        await self.get_by_id(id)  # 確認存在
        # TODO: 補充刪除前業務檢查（如關聯資料）
        result = await self.repo.delete(id)
        await self.session.commit()
        return result
```

### Step 4：產生 Router

```python
# routers/<module>_router.py
"""<中文名稱> API 端點。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.services.<module>_service import <Module>Service
from app.schemas.<schema_file> import <Name>Create, <Name>Update, <Name>Read
from app.schemas.common import ApiResponse, PageResponse

router = APIRouter(prefix="/<resource-path>", tags=["<中文標籤>"])


def get_service(db: AsyncSession = Depends(get_db)) -> <Module>Service:
    return <Module>Service(db)


@router.get("", response_model=ApiResponse[PageResponse[<Name>Read]])
async def list_<resources>(
    page: int = Query(1, ge=1, description="頁碼"),
    size: int = Query(20, ge=1, le=100, description="每頁筆數"),
    service: <Module>Service = Depends(get_service),
):
    """查詢<中文名稱>列表（分頁）。"""
    from app.schemas.common import PageParams
    result = await service.list_records(PageParams(page=page, size=size))
    return ApiResponse(data=result)


@router.get("/{id}", response_model=ApiResponse[<Name>Read])
async def get_<resource>(
    id: int,
    service: <Module>Service = Depends(get_service),
):
    """查詢單筆<中文名稱>。"""
    record = await service.get_by_id(id)
    return ApiResponse(data=record)


@router.post("", response_model=ApiResponse[<Name>Read], status_code=201)
async def create_<resource>(
    data: <Name>Create,
    service: <Module>Service = Depends(get_service),
):
    """建立<中文名稱>。"""
    record = await service.create(data)
    return ApiResponse(data=record, message="建立成功")


@router.put("/{id}", response_model=ApiResponse[<Name>Read])
async def update_<resource>(
    id: int,
    data: <Name>Update,
    service: <Module>Service = Depends(get_service),
):
    """更新<中文名稱>。"""
    record = await service.update(id, data)
    return ApiResponse(data=record, message="更新成功")


@router.delete("/{id}", response_model=ApiResponse)
async def delete_<resource>(
    id: int,
    service: <Module>Service = Depends(get_service),
):
    """刪除<中文名稱>。"""
    await service.delete(id)
    return ApiResponse(data=None, message="刪除成功")
```

### Step 5：產生 main.py Router 註冊提示

```python
# 在 app/main.py 中追加：
from app.routers import <module>_router
app.include_router(<module>_router.router, prefix="/api/v1")
```

### Step 6：輸出摘要

```
✅ 已產生 FastAPI 框架程式碼：

📂 Router:     app/routers/<module>_router.py（N 個端點）
📂 Service:    app/services/<module>_service.py（N 個方法）
📂 Repository: app/repos/<module>_repo.py（BaseRepository + 自訂查詢）

⚠️ TODO 標記位置（需手動補充業務邏輯）：
   - services/<module>_service.py: create() — 業務驗證
   - services/<module>_service.py: update() — 業務驗證
   - services/<module>_service.py: delete() — 關聯檢查

💡 下一步：
   1. 在 main.py 註冊 router
   2. 補充 Service 中的 TODO 業務邏輯
   3. 執行 pytest 驗證端點
```

---

## 輸出路徑

| 檔案類型 | 路徑 |
|---------|------|
| Router | `backend/app/routers/<module>_router.py` |
| Service | `backend/app/services/<module>_service.py` |
| Repository | `backend/app/repos/<module>_repo.py` |

---

## 特殊端點處理

| 端點類型 | 產生策略 |
|---------|---------|
| **批次操作** `POST /batch` | Service 增加 `batch_<action>` 方法，使用 `session.add_all` |
| **匯出** `GET /export` | Service 增加 `export_<resources>` 方法，回傳 `StreamingResponse` |
| **上傳** `POST /upload` | Router 使用 `UploadFile` 參數，Service 處理檔案儲存 |
| **狀態變更** `PATCH /{id}/status` | Service 增加 `change_status` 方法，含狀態機驗證 |
| **多條件查詢** | Repository 增加 `search` 方法，動態組合 `where` 條件 |
| **認證端點** | Router 加入 `Depends(get_current_user)` 依賴 |

---

## 與其他 Skill 的串接

```
db-spec-generator → DB 規格書
        ↓
db-to-sqlalchemy-generator → Model + Schema
        ↓
api-spec-generator → API 規格書
        ↓
api-to-fastapi-scaffold → Router + Service + Repository  ← 本 Skill
        ↓
api-integration-test-generator → pytest 測試案例
```
