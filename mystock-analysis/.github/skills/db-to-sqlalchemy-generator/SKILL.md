---
name: db-to-sqlalchemy-generator
description: >-
  從 DB 規格書或 DDL 自動產生 SQLAlchemy 2.0 ORM 模型與 Pydantic DTO Schema。
  當使用者提到以下任何一項時，務必使用此 Skill：
  產生 SQLAlchemy 模型、DB 規格轉 ORM、產生 Entity 類別、產生 Model、
  產生 Pydantic schema、DDL 轉 SQLAlchemy、資料表轉 Python 模型、
  db to model、db to entity、schema generator、ORM 模型生成、
  從資料庫設計產生程式碼、models.py 生成、schemas.py 生成。
  即使使用者只說「幫我產生 Model」、「把 DB 規格轉成程式碼」、
  「產生這個模組的 ORM」，也應觸發此 Skill。
---

# DB 規格書 → SQLAlchemy Model + Pydantic Schema 生成 Skill

## 目標

從 `db-spec-generator` 產出的 DB 規格書（或 DDL / 口頭描述），自動產生：
1. **SQLAlchemy 2.0 ORM Model**（`models/*.py`）
2. **Pydantic 2.x DTO Schema**（`schemas/*.py`）
3. **Alembic 遷移提示**（建議的遷移指令）

產出程式碼遵循 `fastapi-development` Skill 的架構規範。

---

## 前置讀取（每次必讀）

1. `.github/skills/fastapi-development/SKILL.md` — 架構分層與命名規範
2. 對應的 DB 規格書文件（使用者指定或自動搜尋）

---

## 輸入來源

| 輸入類型 | 說明 | 範例 |
|---------|------|------|
| **DB 規格書** | `db-spec-generator` 產出的設計文件 | `docs/02_Design/db/ecard-weighing-db規格書.md` |
| **SQL DDL** | CREATE TABLE 語句 | `CREATE TABLE ec_weighing_record (...)` |
| **既有 Model** | 需更新/補充的 SQLAlchemy 模型 | `app/models/weighing_record.py` |
| **口頭描述** | 使用者描述資料表結構 | 「幫我產生使用者管理的 Model」 |

---

## 轉換規則

### 規則 1：資料表名稱 → 類別名稱

| DB 慣例 | Python 慣例 | 範例 |
|---------|------------|------|
| `ec_weighing_record` | `WeighingRecord` | 移除前綴，PascalCase |
| `cm_user` | `User` | 移除 `cm_` 前綴 |
| `sd_rw_card` | `SdRwCard` | 保留業務前綴 |

### 規則 2：欄位類型對照

| DB 類型 | SQLAlchemy 類型 | Python 類型提示 |
|---------|----------------|----------------|
| `INT` / `INTEGER` | `Integer` | `Mapped[int]` |
| `BIGINT` | `BigInteger` | `Mapped[int]` |
| `VARCHAR(n)` / `NVARCHAR(n)` | `String(n)` | `Mapped[str]` |
| `TEXT` / `NTEXT` | `Text` | `Mapped[str]` |
| `DECIMAL(p,s)` / `NUMERIC(p,s)` | `Numeric(p,s)` | `Mapped[float]` |
| `FLOAT` / `REAL` | `Float` | `Mapped[float]` |
| `BOOLEAN` / `BIT` | `Boolean` | `Mapped[bool]` |
| `DATE` | `Date` | `Mapped[date]` |
| `DATETIME` / `TIMESTAMP` | `DateTime(timezone=True)` | `Mapped[datetime]` |
| `BLOB` / `VARBINARY` | `LargeBinary` | `Mapped[bytes]` |
| `JSON` / `JSONB` | `JSON` | `Mapped[dict]` |

### 規則 3：約束對照

| DB 約束 | SQLAlchemy 表達 |
|---------|----------------|
| `PRIMARY KEY` | `primary_key=True` |
| `NOT NULL` | `nullable=False`（Mapped 預設行為） |
| `NULL` | `Mapped[xxx \| None]`, `nullable=True` |
| `DEFAULT value` | `default=value` 或 `server_default=text("value")` |
| `UNIQUE` | `unique=True` |
| `FOREIGN KEY` | `ForeignKey("table.column")` |
| `INDEX` | `index=True` 或 `Index(...)` in `__table_args__` |
| `CHECK` | `CheckConstraint(...)` in `__table_args__` |

### 規則 4：關聯映射

| 關聯類型 | SQLAlchemy 表達 |
|---------|----------------|
| 一對多（父→子） | 父端 `relationship("Child", back_populates="parent")` |
| 多對一（子→父） | 子端 `ForeignKey` + `relationship("Parent", back_populates="children")` |
| 多對多 | 中間表 + 雙邊 `relationship(secondary=assoc_table)` |

---

## 產出步驟

### Step 1：解析 DB 規格書

從規格書中提取每張資料表的：
- 表名、中文說明
- 所有欄位（名稱、類型、約束、預設值、說明）
- 索引定義
- 外鍵關聯
- 業務規則約束

### Step 2：產生 SQLAlchemy Model

每張資料表產生獨立的 `.py` 檔案，遵循格式：

```python
# models/<table_name>.py
"""<中文說明> ORM 模型。"""
from datetime import datetime
from sqlalchemy import String, Integer, Numeric, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class <ClassName>(Base, TimestampMixin):
    __tablename__ = "<db_table_name>"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Columns（按規格書欄位順序）
    <field_name>: Mapped[<type>] = mapped_column(<SQLAlchemyType>, <constraints>)

    # Relationships
    <relation_name>: Mapped["<RelatedClass>"] = relationship(back_populates="<inverse>")

    # Table-level constraints
    __table_args__ = (
        Index("<index_name>", "<col1>", "<col2>"),
    )
```

**檢查清單：**
- [ ] 所有必填欄位都沒有 `nullable=True`
- [ ] 外鍵欄位有對應的 `relationship`
- [ ] 複合索引定義在 `__table_args__`
- [ ] 使用 `TimestampMixin`（若有 created_at / updated_at）
- [ ] 使用 `SoftDeleteMixin`（若有 is_deleted / deleted_at）

### Step 3：產生 Pydantic Schema

每個 Model 產生對應的 Schema 檔案，包含 4 個標準 DTO：

```python
# schemas/<table_name>.py
"""<中文說明> DTO Schema。"""
from datetime import datetime
from pydantic import BaseModel, Field


class <Name>Base(BaseModel):
    """共用欄位（Create & Read 共用）。"""
    <field>: <type> = Field(..., description="<中文說明>")


class <Name>Create(<Name>Base):
    """建立請求 DTO — 包含所有建立時必填欄位。"""
    pass  # 或追加建立時額外必填欄位


class <Name>Update(BaseModel):
    """更新請求 DTO — 所有欄位可選（部分更新）。"""
    <field>: <type> | None = Field(None, description="<中文說明>")


class <Name>Read(<Name>Base):
    """回應 DTO — 包含 id、時間戳等系統欄位。"""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

**Schema 生成規則：**
- `Base`：放入業務必填欄位（NOT NULL 且非系統自動填入）
- `Create`：繼承 Base，追加建立時額外必填（如 operator_id）
- `Update`：所有業務欄位改為 `Optional`，用於 PATCH 式部分更新
- `Read`：繼承 Base，追加 `id` + 時間戳 + 關聯欄位

### Step 4：產生 `__init__.py` 匯出

```python
# models/__init__.py
from app.models.user import User
from app.models.weighing_record import WeighingRecord

__all__ = ["User", "WeighingRecord"]
```

### Step 5：輸出摘要

```
✅ 已產生 SQLAlchemy Model：
   - app/models/<name>.py（N 張資料表）

✅ 已產生 Pydantic Schema：
   - app/schemas/<name>.py（N × 4 個 DTO）

💡 建議執行 Alembic 遷移：
   alembic revision --autogenerate -m "add <module> tables"
   alembic upgrade head
```

---

## 輸出路徑

| 檔案類型 | 路徑 |
|---------|------|
| Model | `backend/app/models/<table_name>.py` |
| Schema | `backend/app/schemas/<table_name>.py` |
| Model init | `backend/app/models/__init__.py`（更新） |
| Schema init | `backend/app/schemas/__init__.py`（更新） |

> 若 `backend/` 不存在，依使用者指定的專案根目錄調整。

---

## 特殊處理

| 情況 | 處理方式 |
|------|---------|
| 資料表有 `is_deleted` | 自動套用 `SoftDeleteMixin` |
| 資料表有 `created_at` + `updated_at` | 自動套用 `TimestampMixin` |
| 多對多關聯 | 產生中間表 Model + 雙向 `relationship(secondary=...)` |
| 欄位有 CHECK 約束 | 在 `__table_args__` 加入 `CheckConstraint(...)` |
| 欄位有 ENUM 值域 | 產生 Python `StrEnum` 類別，放在 `schemas/enums.py` |
| SQL Server 專用類型 | 使用 `sqlalchemy.dialects.mssql` 對應類型 |
