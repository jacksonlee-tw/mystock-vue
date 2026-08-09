---
applyTo: "backend/**/*.py"
---

# 後端 Python 開發規範（自動注入）

本指引在編輯 `backend/` 下任何 `.py` 檔案時自動生效。

## 架構分層（嚴格遵守）

```
Router → Service → Repository → Model / Schema
```

| 層 | 允許 | 禁止 |
|----|------|------|
| **Router** | 接收 HTTP 請求、參數驗證、回傳回應 | 不含業務邏輯、不直接操作 DB |
| **Service** | 業務規則、流程編排、跨 Repo 協調 | 不處理 HTTP 細節（status_code） |
| **Repository** | 資料庫 CRUD、查詢組合、分頁 | 不含業務判斷邏輯 |
| **Model** | ORM 實體定義、關聯映射 | 不含行為方法 |
| **Schema** | 請求/回應 DTO、欄位驗證 | 不含 DB 操作 |

## 命名慣例

| 類型 | 規則 | 範例 |
|------|------|------|
| 檔案名 | snake_case | `weighing_record.py` |
| 類別 | PascalCase | `WeighingRecord` |
| 函式/變數 | snake_case | `get_by_id` |
| 常數 | UPPER_SNAKE_CASE | `DEFAULT_PAGE_SIZE` |
| 路由前綴 | kebab-case | `/api/v1/weighing-records` |
| Repository | `*_repo.py` | `weighing_record_repo.py` |
| Service | `*_service.py` | `weighing_service.py` |
| Router | `*_router.py` | `weighing_router.py` |

## 技術棧約束

- Python 3.11+、FastAPI 0.110+、SQLAlchemy 2.0+（async）、Pydantic 2.x
- 資料庫 Session 使用依賴注入 `Depends(get_db)`，禁止在函式內自行建立 Session
- 所有 DB 操作使用 async/await
- Pydantic Schema 必須繼承 `BaseModel`，使用 `model_config = ConfigDict(from_attributes=True)`
- Router 使用 `APIRouter(prefix=..., tags=[...])`

## import 排序（isort 風格）

```python
# 1. 標準庫
import os
from datetime import datetime

# 2. 第三方套件
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# 3. 專案模組
from app.dependencies import get_db
from app.schemas.common import PageResponse
```

## 錯誤處理

- 業務錯誤使用自訂 `AppException` 或 `HTTPException`
- Repository 層不捕獲異常，讓 Service 層統一處理
- 禁止空的 `except: pass`

## 安全性

- 密碼不可明文儲存（使用 bcrypt/passlib）
- SQL 查詢使用 ORM 或參數化查詢，禁止字串拼接
- 環境變數使用 `app.config.Settings`（Pydantic Settings），禁止硬編碼
