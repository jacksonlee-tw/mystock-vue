---
applyTo: "backend/app/schemas/**/*.py"
---

# Pydantic Schema 規範（自動注入）

本指引在編輯 Pydantic DTO Schema 檔案時自動生效。

## 技術要求

- Pydantic 2.x（`BaseModel` + `ConfigDict`）
- 使用 `model_config = ConfigDict(from_attributes=True)` 支援 ORM → Schema 轉換

## Schema 分類慣例

每個模組的 Schema 檔案應定義以下類別：

| 類別 | 命名 | 用途 |
|------|------|------|
| Base | `XxxBase` | 共用欄位（建立/更新共享） |
| Create | `XxxCreate(XxxBase)` | 建立請求 DTO |
| Update | `XxxUpdate(XxxBase)` | 更新請求 DTO（欄位皆 Optional） |
| Response | `XxxResponse(XxxBase)` | 回應 DTO（含 id + timestamps） |
| Query | `XxxQuery` | 查詢條件 DTO（分頁/篩選） |

## 範本

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class WeighingRecordBase(BaseModel):
    vehicle_no: str = Field(..., min_length=1, max_length=20, description="車號")
    material_code: str = Field(..., max_length=20, description="物料代碼")
    gross_weight: float | None = Field(None, ge=0, description="毛重(kg)")

class WeighingRecordCreate(WeighingRecordBase):
    pass

class WeighingRecordUpdate(BaseModel):
    vehicle_no: str | None = Field(None, max_length=20)
    material_code: str | None = Field(None, max_length=20)
    gross_weight: float | None = Field(None, ge=0)

class WeighingRecordResponse(WeighingRecordBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime | None = None

class WeighingRecordQuery(BaseModel):
    vehicle_no: str | None = None
    material_code: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
```

## 共用 Schema（`common.py`）

```python
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    message: str = "OK"
```

## 驗證規則

- 字串欄位：加 `min_length` / `max_length`
- 數值欄位：加 `ge` / `le` 範圍限制
- 必填欄位：使用 `...`（Ellipsis）
- 選填欄位：使用 `None` 預設值 + `| None` 型別
- 所有 Field 加 `description` 中文說明

## 禁止事項

- 不在 Schema 中操作資料庫
- 不使用 Pydantic v1 語法（`class Config:`、`orm_mode`）
- 不使用 `Optional[str]` 舊寫法（改用 `str | None`）
