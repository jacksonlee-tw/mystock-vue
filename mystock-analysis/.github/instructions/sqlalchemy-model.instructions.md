---
applyTo: "backend/app/models/**/*.py"
---

# SQLAlchemy Model 規範（自動注入）

本指引在編輯 ORM Model 檔案時自動生效。

## 技術要求

- SQLAlchemy 2.0+（Mapped 註解風格）
- 所有 Model 繼承 `Base`（定義在 `app/models/base.py`）
- 使用 `Mapped[]` + `mapped_column()` 取代舊版 `Column()`

## 基礎範本

```python
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class WeighingRecord(Base):
    __tablename__ = "WEIGHING_RECORD"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_no: Mapped[str] = mapped_column(String(20), nullable=False, comment="車號")
    gross_weight: Mapped[float | None] = mapped_column(comment="毛重(kg)")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="建立時間"
    )
```

## 命名規則

| 項目 | 規則 | 範例 |
|------|------|------|
| 類別名 | PascalCase（單數） | `WeighingRecord` |
| `__tablename__` | UPPER_SNAKE_CASE | `"WEIGHING_RECORD"` |
| 欄位名 | snake_case | `vehicle_no` |
| 外鍵欄位 | `<table>_id` | `card_id` |

## 共用 Mixin

```python
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=func.now())
```

## 關聯定義

- 一對多：父表使用 `relationship(back_populates=...)`
- 多對一：子表使用 `ForeignKey` + `relationship(back_populates=...)`
- `cascade` 預設 `"all, delete-orphan"`（父表端）
- 禁止使用 `backref`（改用雙向 `back_populates`）

## 禁止事項

- 不在 Model 中寫業務方法（純資料結構）
- 不在 Model 中 import Service 或 Router
- 不使用 `Column()` 舊語法
