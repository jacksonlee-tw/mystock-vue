---
name: api-integration-test-generator
description: >-
  從 API 規格書自動產生 pytest 整合測試案例，涵蓋正常流程、邊界條件、錯誤碼驗證。
  當使用者提到以下任何一項時，務必使用此 Skill：
  產生 API 測試、整合測試案例、pytest 測試、API test、integration test、
  測試案例生成、自動產生測試、從 API 規格產生測試、endpoint 測試、
  寫 API 測試、後端測試、router test、產生 conftest、
  E2E API 測試、回歸測試案例。
  即使使用者只說「幫我寫測試」、「產生這個 API 的測試案例」、
  「跑一下後端測試」，也應觸發此 Skill。
---

# API 規格書 → pytest 整合測試案例生成 Skill

## 目標

從 `api-spec-generator` 產出的 API 規格書，自動產生：
1. **conftest.py**（測試基礎設施：DB fixture、HTTP client、測試資料工廠）
2. **test_<module>_router.py**（端點整合測試，含 Happy Path + Error Cases）
3. **test_<module>_service.py**（Service 單元測試，選擇性產出）

產出測試遵循 `fastapi-development` Skill 的測試規範。

---

## 前置讀取（每次必讀）

1. `.github/skills/fastapi-development/SKILL.md` — 測試配置與規範（§17）
2. 對應的 API 規格書文件
3. 對應的 Schema 定義（確保測試資料型別正確）

---

## 輸入來源

| 輸入類型 | 說明 | 範例 |
|---------|------|------|
| **API 規格書** | 端點定義與回應格式 | `docs/02_Design/api/ecard-weighing-API規格書.md` |
| **Router 程式碼** | 已產生的 FastAPI Router | `app/routers/weighing_router.py` |
| **Schema 定義** | Pydantic DTO 欄位與驗證 | `app/schemas/weighing_record.py` |

---

## 測試案例生成規則

### 每個端點的標準測試矩陣

| S/N | 測試類型 | 測試名稱格式 | 優先度 |
|-----|---------|-------------|--------|
| 1 | Happy Path | `test_<action>_success` | 必產 |
| 2 | 404 Not Found | `test_<action>_not_found` | GET/PUT/DELETE 必產 |
| 3 | 422 Validation | `test_<action>_invalid_<field>` | POST/PUT 必產 |
| 4 | 409 Conflict | `test_<action>_duplicate` | POST 有唯一約束時 |
| 5 | 401 Unauthorized | `test_<action>_unauthorized` | 有認證需求時 |
| 6 | 403 Forbidden | `test_<action>_forbidden` | 有權限檢查時 |
| 7 | 邊界條件 | `test_<action>_<boundary>` | 有 min/max 約束時 |
| 8 | 分頁驗證 | `test_list_pagination` | LIST 端點必產 |
| 9 | 排序驗證 | `test_list_sort_by_<field>` | 有排序參數時 |
| 10 | 篩選驗證 | `test_list_filter_by_<field>` | 有篩選參數時 |

### 端點 → 測試對照

| 端點 | 自動產生的測試 |
|------|--------------|
| `GET /resources` | `test_list_success`, `test_list_pagination`, `test_list_empty` |
| `GET /resources/{id}` | `test_get_success`, `test_get_not_found` |
| `POST /resources` | `test_create_success`, `test_create_invalid_*`, `test_create_missing_required` |
| `PUT /resources/{id}` | `test_update_success`, `test_update_not_found`, `test_update_invalid_*` |
| `DELETE /resources/{id}` | `test_delete_success`, `test_delete_not_found` |

---

## 產出步驟

### Step 1：產生 / 更新 conftest.py

若 `tests/conftest.py` 不存在，產生完整版本：

```python
# tests/conftest.py
"""測試基礎設施：資料庫 fixture、HTTP client、測試資料工廠。"""
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from app.main import app
from app.dependencies import get_db
from app.models.base import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSession = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session():
    """每個測試前建立全新的資料庫表，測試後清除。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSession() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session):
    """帶有測試 DB 的 FastAPI 測試 Client。"""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

### Step 2：產生測試資料工廠

為每個模組產生測試資料 fixture：

```python
# tests/factories/<module>_factory.py
"""<中文名稱> 測試資料工廠。"""


def make_<resource>_data(**overrides) -> dict:
    """產生有效的<中文名稱>建立請求資料。"""
    defaults = {
        # 從 Schema Create 的欄位定義產生合理預設值
        "<field1>": "<valid_value>",
        "<field2>": <valid_value>,
    }
    defaults.update(overrides)
    return defaults


def make_<resource>_invalid_data(scenario: str) -> dict:
    """產生無效的測試資料（依場景）。"""
    base = make_<resource>_data()
    if scenario == "missing_required":
        del base["<required_field>"]
    elif scenario == "invalid_type":
        base["<field>"] = "not_a_number"
    elif scenario == "exceed_max_length":
        base["<string_field>"] = "x" * 999
    return base
```

### Step 3：產生 Router 整合測試

```python
# tests/test_<module>_router.py
"""<中文名稱> API 端點整合測試。"""
import pytest
from tests.factories.<module>_factory import make_<resource>_data

API_PREFIX = "/api/v1/<resource-path>"


# ============================================================
# POST — 建立
# ============================================================

class TestCreate<Resource>:
    """POST {API_PREFIX} 測試群組。"""

    @pytest.mark.asyncio
    async def test_create_success(self, client):
        """正常建立 — 回傳 201 + 完整資料。"""
        data = make_<resource>_data()
        response = await client.post(API_PREFIX, json=data)
        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["data"]["<key_field>"] == data["<key_field>"]
        assert "id" in body["data"]
        assert "created_at" in body["data"]

    @pytest.mark.asyncio
    async def test_create_missing_required(self, client):
        """缺少必填欄位 — 回傳 422。"""
        data = make_<resource>_data()
        del data["<required_field>"]
        response = await client.post(API_PREFIX, json=data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_invalid_field(self, client):
        """欄位值不合法 — 回傳 422。"""
        data = make_<resource>_data(<field>="<invalid_value>")
        response = await client.post(API_PREFIX, json=data)
        assert response.status_code == 422


# ============================================================
# GET — 列表查詢
# ============================================================

class TestList<Resources>:
    """GET {API_PREFIX} 測試群組。"""

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        """空資料 — 回傳空列表。"""
        response = await client.get(API_PREFIX)
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["content"] == []
        assert body["data"]["total_elements"] == 0

    @pytest.mark.asyncio
    async def test_list_with_data(self, client):
        """有資料 — 回傳正確筆數。"""
        # 先建立測試資料
        await client.post(API_PREFIX, json=make_<resource>_data())
        await client.post(API_PREFIX, json=make_<resource>_data())

        response = await client.get(API_PREFIX)
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total_elements"] == 2

    @pytest.mark.asyncio
    async def test_list_pagination(self, client):
        """分頁 — page & size 參數生效。"""
        for _ in range(5):
            await client.post(API_PREFIX, json=make_<resource>_data())

        response = await client.get(f"{API_PREFIX}?page=1&size=2")
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]["content"]) == 2
        assert body["data"]["total_elements"] == 5
        assert body["data"]["total_pages"] == 3


# ============================================================
# GET — 單筆查詢
# ============================================================

class TestGet<Resource>:
    """GET {API_PREFIX}/{{id}} 測試群組。"""

    @pytest.mark.asyncio
    async def test_get_success(self, client):
        """查詢存在的記錄 — 回傳 200。"""
        create_resp = await client.post(API_PREFIX, json=make_<resource>_data())
        record_id = create_resp.json()["data"]["id"]

        response = await client.get(f"{API_PREFIX}/{record_id}")
        assert response.status_code == 200
        assert response.json()["data"]["id"] == record_id

    @pytest.mark.asyncio
    async def test_get_not_found(self, client):
        """查詢不存在的記錄 — 回傳 404。"""
        response = await client.get(f"{API_PREFIX}/99999")
        assert response.status_code == 404
        assert response.json()["success"] is False


# ============================================================
# PUT — 更新
# ============================================================

class TestUpdate<Resource>:
    """PUT {API_PREFIX}/{{id}} 測試群組。"""

    @pytest.mark.asyncio
    async def test_update_success(self, client):
        """正常更新 — 回傳 200 + 更新後資料。"""
        create_resp = await client.post(API_PREFIX, json=make_<resource>_data())
        record_id = create_resp.json()["data"]["id"]

        update_data = {"<updatable_field>": "<new_value>"}
        response = await client.put(f"{API_PREFIX}/{record_id}", json=update_data)
        assert response.status_code == 200
        assert response.json()["data"]["<updatable_field>"] == "<new_value>"

    @pytest.mark.asyncio
    async def test_update_not_found(self, client):
        """更新不存在的記錄 — 回傳 404。"""
        response = await client.put(f"{API_PREFIX}/99999", json={"<field>": "<value>"})
        assert response.status_code == 404


# ============================================================
# DELETE — 刪除
# ============================================================

class TestDelete<Resource>:
    """DELETE {API_PREFIX}/{{id}} 測試群組。"""

    @pytest.mark.asyncio
    async def test_delete_success(self, client):
        """正常刪除 — 回傳 200。"""
        create_resp = await client.post(API_PREFIX, json=make_<resource>_data())
        record_id = create_resp.json()["data"]["id"]

        response = await client.delete(f"{API_PREFIX}/{record_id}")
        assert response.status_code == 200

        # 確認已刪除
        get_resp = await client.get(f"{API_PREFIX}/{record_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client):
        """刪除不存在的記錄 — 回傳 404。"""
        response = await client.delete(f"{API_PREFIX}/99999")
        assert response.status_code == 404
```

### Step 4：輸出摘要

```
✅ 已產生 pytest 整合測試：

📂 tests/conftest.py                    - 測試基礎設施
📂 tests/factories/<module>_factory.py  - 測試資料工廠
📂 tests/test_<module>_router.py        - N 個測試案例

📊 測試覆蓋：
   POST   — 3 案例（success / missing_required / invalid_field）
   GET    — 5 案例（list_empty / list_with_data / pagination / get_success / not_found）
   PUT    — 2 案例（success / not_found）
   DELETE — 2 案例（success / not_found）
   合計   — 12 案例

💡 執行測試：
   cd backend && pytest tests/test_<module>_router.py -v
```

---

## 輸出路徑

| 檔案類型 | 路徑 |
|---------|------|
| conftest | `backend/tests/conftest.py` |
| Factory | `backend/tests/factories/<module>_factory.py` |
| Router 測試 | `backend/tests/test_<module>_router.py` |
| Service 測試 | `backend/tests/test_<module>_service.py`（選擇性） |

---

## 與其他 Skill 的串接

```
api-spec-generator → API 規格書
        ↓
api-to-fastapi-scaffold → Router / Service / Repo
        ↓
api-integration-test-generator → pytest 測試案例  ← 本 Skill
        ↓
test-plan-generator → 完整測試計劃文件
```
