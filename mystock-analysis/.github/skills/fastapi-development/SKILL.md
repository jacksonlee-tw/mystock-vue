---
name: fastapi-development
description: >-
  Python FastAPI 後端開發技能。涵蓋架構分層、路由組織、依賴注入、Pydantic 模型、
  SQLAlchemy ORM、非同步處理、錯誤處理、安全驗證等完整開發流程，
  適用於任何採用 FastAPI 技術棧的專案。
  當使用者提到以下任何一項時，務必使用此 Skill：
  FastAPI 開發、後端 API 實作、Python 後端架構、FastAPI router 撰寫、
  Pydantic schema 定義、SQLAlchemy model 撰寫、FastAPI 依賴注入、
  後端錯誤處理、JWT 認證、CORS 設定、FastAPI middleware、
  後端分頁查詢、資料庫連線設定、Alembic 遷移、
  或任何 backend/ 目錄下的 .py 程式修改。
  即使使用者只說「寫後端」、「加一個 API」、「修改後端邏輯」，也應觸發此 Skill。
---

# Python FastAPI 後端開發指引

本 Skill 定義 FastAPI + SQLAlchemy + Pydantic 技術棧的架構模式與開發規範，
與前端 `primevue3-development` Skill 互為對照，確保前後端架構一致性。

**基礎技術棧：**
- Python 3.11+
- FastAPI 0.110+
- SQLAlchemy 2.0+（async）
- Pydantic 2.x（資料驗證與序列化）
- Alembic（資料庫遷移）
- Uvicorn（ASGI 伺服器）
- PostgreSQL 14+（主資料庫，可替換為 SQL Server）

**可選擴充：**
- Redis（快取 / Session）
- Celery（非同步任務佇列）
- python-jose / PyJWT（JWT 認證）

> **專案客製化：** 若 `references/project-conventions.md` 存在，讀取該檔以獲取
> 專案特定的資料庫連線、環境變數、命名慣例等資訊。本文件只定義通用架構模式。

---

## 1. 架構分層原則

核心理念與前端相同 — **關注分離**：

```
Router (router/*.py)              ← 路由定義：端點、參數驗證、HTTP 回應
  └→ Service (services/*.py)      ← 業務邏輯：編排、計算、規則驗證
       └→ Repository (repos/*.py) ← 資料存取：SQL 查詢、ORM 操作
            └→ Model (models/*.py)← ORM 定義：SQLAlchemy 實體
                 └→ Schema (schemas/*.py) ← Pydantic DTO：請求/回應格式
```

| 層 | 職責 | 禁止 |
|----|------|------|
| **Router** | 接收 HTTP 請求、參數驗證、回傳回應 | 不含業務邏輯、不直接操作 DB |
| **Service** | 業務規則、流程編排、跨 Repo 協調 | 不處理 HTTP 細節（status code 等） |
| **Repository** | 資料庫 CRUD、查詢組合、分頁 | 不含業務判斷邏輯 |
| **Model** | ORM 實體定義、關聯映射 | 不含行為方法（純資料結構） |
| **Schema** | 請求/回應 DTO、欄位驗證 | 不含 DB 操作 |

---

## 2. 目錄結構

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 應用入口
│   ├── config.py                  # 環境設定（Pydantic Settings）
│   ├── database.py                # 資料庫連線引擎 & Session
│   ├── dependencies.py            # 共用依賴注入（get_db, get_current_user）
│   ├── exceptions.py              # 自訂異常類別
│   ├── exception_handlers.py      # 全域異常處理器
│   │
│   ├── models/                    # SQLAlchemy ORM 模型
│   │   ├── __init__.py
│   │   ├── base.py                # 共用 Base + Mixin（id, timestamps）
│   │   ├── user.py
│   │   └── weighing_record.py
│   │
│   ├── schemas/                   # Pydantic DTO
│   │   ├── __init__.py
│   │   ├── common.py              # 共用 Schema（分頁、回應包裝）
│   │   ├── user.py
│   │   └── weighing_record.py
│   │
│   ├── repos/                     # Repository 資料存取層
│   │   ├── __init__.py
│   │   ├── base.py                # BaseRepository（泛型 CRUD）
│   │   ├── user_repo.py
│   │   └── weighing_record_repo.py
│   │
│   ├── services/                  # Service 業務邏輯層
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   └── weighing_service.py
│   │
│   ├── routers/                   # FastAPI Router（端點定義）
│   │   ├── __init__.py
│   │   ├── user_router.py
│   │   └── weighing_router.py
│   │
│   ├── middleware/                 # 中介軟體
│   │   ├── __init__.py
│   │   ├── cors.py
│   │   └── logging_middleware.py
│   │
│   └── utils/                     # 工具函式
│       ├── __init__.py
│       ├── security.py            # JWT 工具（建立/驗證 token）
│       └── pagination.py          # 分頁工具
│
├── alembic/                       # 資料庫遷移
│   ├── env.py
│   └── versions/
│
├── tests/                         # 測試
│   ├── conftest.py
│   ├── test_user_router.py
│   └── test_weighing_service.py
│
├── alembic.ini
├── requirements.txt
├── pyproject.toml
└── .env.example
```

---

## 3. 檔案命名規範

| 類型 | 命名規則 | 範例 |
|------|---------|------|
| Model | snake_case.py | `weighing_record.py` |
| Schema | snake_case.py（同 Model） | `weighing_record.py` |
| Repository | snake_case + `_repo.py` | `weighing_record_repo.py` |
| Service | snake_case + `_service.py` | `weighing_service.py` |
| Router | snake_case + `_router.py` | `weighing_router.py` |
| 類別名 | PascalCase | `WeighingRecord`, `WeighingRecordCreate` |
| 函式/變數 | snake_case | `get_by_id`, `is_active` |
| 常數 | UPPER_SNAKE_CASE | `DEFAULT_PAGE_SIZE`, `JWT_SECRET_KEY` |
| 路由前綴 | kebab-case | `/api/v1/weighing-records` |

---

## 4. 應用入口 (main.py)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.routers import user_router, weighing_router
from app.exception_handlers import register_exception_handlers
from app.middleware.cors import setup_cors
from app.database import engine
from app.models.base import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

# Middleware
setup_cors(app)

# Exception handlers
register_exception_handlers(app)

# Routers
app.include_router(user_router.router, prefix="/api/v1")
app.include_router(weighing_router.router, prefix="/api/v1")
```

---

## 5. 環境設定 (config.py)

使用 Pydantic Settings 管理環境變數，支援 `.env` 檔案：

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Application
    PROJECT_NAME: str = "eCard API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/ecard"

    # Security
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]


settings = Settings()
```

---

## 6. 資料庫連線 (database.py)

```python
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

---

## 7. Model 層（SQLAlchemy ORM）

### 7.1 Base Model + Mixin

```python
# models/base.py
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """共用時間戳欄位，所有 Model 繼承使用。"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    """邏輯刪除 Mixin。"""
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

### 7.2 Model 定義範例

```python
# models/weighing_record.py
from sqlalchemy import String, Numeric, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class WeighingRecord(Base, TimestampMixin):
    __tablename__ = "ec_weighing_record"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    card_no: Mapped[str] = mapped_column(String(20), index=True)
    plate_number: Mapped[str] = mapped_column(String(20))
    gross_weight: Mapped[float] = mapped_column(Numeric(10, 2))
    tare_weight: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    net_weight: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="PENDING")

    # Foreign key
    operator_id: Mapped[int] = mapped_column(ForeignKey("cm_user.id"))
    operator: Mapped["User"] = relationship(back_populates="weighing_records")

    __table_args__ = (
        Index("ix_weighing_card_status", "card_no", "status"),
    )
```

---

## 8. Schema 層（Pydantic DTO）

### 8.1 共用 Schema

```python
# schemas/common.py
from pydantic import BaseModel
from typing import Generic, TypeVar

T = TypeVar("T")


class PageParams(BaseModel):
    """分頁查詢參數。"""
    page: int = 1
    size: int = 20


class PageResponse(BaseModel, Generic[T]):
    """標準分頁回應，對應前端 DataTable lazy 分頁。"""
    content: list[T]
    total_elements: int
    total_pages: int
    page: int
    size: int


class ApiResponse(BaseModel, Generic[T]):
    """統一 API 回應格式。"""
    success: bool = True
    data: T | None = None
    message: str = "操作成功"


class ErrorResponse(BaseModel):
    """錯誤回應格式。"""
    success: bool = False
    error_code: str
    message: str
    detail: str | None = None
```

### 8.2 模組 Schema 範例

```python
# schemas/weighing_record.py
from datetime import datetime
from pydantic import BaseModel, Field


class WeighingRecordBase(BaseModel):
    card_no: str = Field(..., max_length=20, description="IC 卡號")
    plate_number: str = Field(..., max_length=20, description="車牌號碼")
    gross_weight: float = Field(..., ge=0, description="毛重 (kg)")


class WeighingRecordCreate(WeighingRecordBase):
    """建立過磅記錄的請求 DTO。"""
    operator_id: int


class WeighingRecordUpdate(BaseModel):
    """更新過磅記錄（部分更新）。"""
    tare_weight: float | None = Field(None, ge=0, description="皮重 (kg)")
    net_weight: float | None = Field(None, ge=0, description="淨重 (kg)")
    status: str | None = Field(None, max_length=10)


class WeighingRecordRead(WeighingRecordBase):
    """過磅記錄回應 DTO。"""
    id: int
    tare_weight: float | None
    net_weight: float | None
    status: str
    operator_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

---

## 9. Repository 層（資料存取）

### 9.1 BaseRepository（泛型 CRUD）

```python
# repos/base.py
from typing import TypeVar, Generic, Type
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import Base
from app.schemas.common import PageParams, PageResponse

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: int) -> ModelType | None:
        return await self.session.get(self.model, id)

    async def get_all(self, page_params: PageParams) -> PageResponse:
        # Count
        count_stmt = select(func.count()).select_from(self.model)
        total = (await self.session.execute(count_stmt)).scalar_one()

        # Query
        offset = (page_params.page - 1) * page_params.size
        stmt = select(self.model).offset(offset).limit(page_params.size)
        result = await self.session.execute(stmt)
        items = result.scalars().all()

        return PageResponse(
            content=items,
            total_elements=total,
            total_pages=(total + page_params.size - 1) // page_params.size,
            page=page_params.page,
            size=page_params.size,
        )

    async def create(self, obj: ModelType) -> ModelType:
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: ModelType, data: dict) -> ModelType:
        for key, value in data.items():
            if value is not None:
                setattr(obj, key, value)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, id: int) -> bool:
        obj = await self.get_by_id(id)
        if obj:
            await self.session.delete(obj)
            await self.session.flush()
            return True
        return False
```

### 9.2 模組 Repository 範例

```python
# repos/weighing_record_repo.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.weighing_record import WeighingRecord
from app.repos.base import BaseRepository


class WeighingRecordRepo(BaseRepository[WeighingRecord]):
    def __init__(self, session: AsyncSession):
        super().__init__(WeighingRecord, session)

    async def get_by_card_no(self, card_no: str) -> list[WeighingRecord]:
        stmt = select(WeighingRecord).where(
            WeighingRecord.card_no == card_no
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_records(self) -> list[WeighingRecord]:
        stmt = select(WeighingRecord).where(
            WeighingRecord.status == "PENDING"
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

---

## 10. Service 層（業務邏輯）

Service 編排多個 Repository，實作業務規則：

```python
# services/weighing_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.repos.weighing_record_repo import WeighingRecordRepo
from app.models.weighing_record import WeighingRecord
from app.schemas.weighing_record import WeighingRecordCreate, WeighingRecordUpdate
from app.schemas.common import PageParams, PageResponse
from app.exceptions import NotFoundError, BusinessError


class WeighingService:
    def __init__(self, session: AsyncSession):
        self.repo = WeighingRecordRepo(session)
        self.session = session

    async def get_by_id(self, record_id: int) -> WeighingRecord:
        record = await self.repo.get_by_id(record_id)
        if not record:
            raise NotFoundError(f"過磅記錄 {record_id} 不存在")
        return record

    async def list_records(self, page_params: PageParams) -> PageResponse:
        return await self.repo.get_all(page_params)

    async def create_record(self, data: WeighingRecordCreate) -> WeighingRecord:
        record = WeighingRecord(**data.model_dump())
        result = await self.repo.create(record)
        await self.session.commit()
        return result

    async def complete_weighing(
        self, record_id: int, data: WeighingRecordUpdate
    ) -> WeighingRecord:
        record = await self.get_by_id(record_id)
        if record.status != "PENDING":
            raise BusinessError("只能完成狀態為 PENDING 的過磅記錄")

        update_data = data.model_dump(exclude_unset=True)
        if data.tare_weight is not None:
            update_data["net_weight"] = float(record.gross_weight) - data.tare_weight
            update_data["status"] = "COMPLETED"

        result = await self.repo.update(record, update_data)
        await self.session.commit()
        return result
```

---

## 11. Router 層（端點定義）

### 11.1 依賴注入

```python
# dependencies.py
from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

### 11.2 Router 範例

```python
# routers/weighing_router.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.services.weighing_service import WeighingService
from app.schemas.weighing_record import (
    WeighingRecordCreate,
    WeighingRecordUpdate,
    WeighingRecordRead,
)
from app.schemas.common import ApiResponse, PageResponse, PageParams

router = APIRouter(prefix="/weighing-records", tags=["過磅記錄"])


def get_service(db: AsyncSession = Depends(get_db)) -> WeighingService:
    return WeighingService(db)


@router.get("", response_model=ApiResponse[PageResponse[WeighingRecordRead]])
async def list_records(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    service: WeighingService = Depends(get_service),
):
    page_params = PageParams(page=page, size=size)
    result = await service.list_records(page_params)
    return ApiResponse(data=result)


@router.get("/{record_id}", response_model=ApiResponse[WeighingRecordRead])
async def get_record(
    record_id: int,
    service: WeighingService = Depends(get_service),
):
    record = await service.get_by_id(record_id)
    return ApiResponse(data=record)


@router.post("", response_model=ApiResponse[WeighingRecordRead], status_code=201)
async def create_record(
    data: WeighingRecordCreate,
    service: WeighingService = Depends(get_service),
):
    record = await service.create_record(data)
    return ApiResponse(data=record, message="過磅記錄建立成功")


@router.put("/{record_id}", response_model=ApiResponse[WeighingRecordRead])
async def update_record(
    record_id: int,
    data: WeighingRecordUpdate,
    service: WeighingService = Depends(get_service),
):
    record = await service.complete_weighing(record_id, data)
    return ApiResponse(data=record, message="過磅記錄更新成功")
```

---

## 12. 異常處理

### 12.1 自訂異常

```python
# exceptions.py
class AppError(Exception):
    """應用基礎異常。"""
    def __init__(self, message: str, error_code: str = "INTERNAL_ERROR"):
        self.message = message
        self.error_code = error_code


class NotFoundError(AppError):
    def __init__(self, message: str = "資源不存在"):
        super().__init__(message, "NOT_FOUND")


class BusinessError(AppError):
    def __init__(self, message: str = "業務邏輯錯誤"):
        super().__init__(message, "BUSINESS_ERROR")


class AuthenticationError(AppError):
    def __init__(self, message: str = "認證失敗"):
        super().__init__(message, "AUTHENTICATION_ERROR")


class PermissionError(AppError):
    def __init__(self, message: str = "權限不足"):
        super().__init__(message, "PERMISSION_DENIED")
```

### 12.2 全域異常處理器

```python
# exception_handlers.py
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.exceptions import AppError, NotFoundError, AuthenticationError, PermissionError


def register_exception_handlers(app: FastAPI):

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error_code": exc.error_code, "message": exc.message},
        )

    @app.exception_handler(AuthenticationError)
    async def auth_handler(request: Request, exc: AuthenticationError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error_code": exc.error_code, "message": exc.message},
        )

    @app.exception_handler(PermissionError)
    async def permission_handler(request: Request, exc: PermissionError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "error_code": exc.error_code, "message": exc.message},
        )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error_code": exc.error_code, "message": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "message": "請求參數驗證失敗",
                "detail": str(exc.errors()),
            },
        )
```

---

## 13. 安全與認證

### 13.1 JWT 工具

```python
# utils/security.py
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
```

### 13.2 認證依賴

```python
# dependencies.py (追加)
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.utils.security import decode_access_token
from app.exceptions import AuthenticationError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise AuthenticationError()
    except Exception:
        raise AuthenticationError()

    from app.services.user_service import UserService
    service = UserService(db)
    user = await service.get_by_id(int(user_id))
    if not user:
        raise AuthenticationError("使用者不存在")
    return user
```

---

## 14. CORS 中介軟體

```python
# middleware/cors.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings


def setup_cors(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

---

## 15. 分頁查詢模式

前後端分頁對照（對應 PrimeVue DataTable lazy 模式）：

| 前端參數 | 後端參數 | 說明 |
|---------|---------|------|
| `event.page` | `page` (1-based) | 當前頁碼 |
| `event.rows` | `size` | 每頁筆數 |
| `event.sortField` | `sort_by` | 排序欄位 |
| `event.sortOrder` | `sort_order` (asc/desc) | 排序方向 |
| `event.filters` | Query params | 篩選條件 |

回應格式與前端 `totalRecords` 對應：
```json
{
  "success": true,
  "data": {
    "content": [...],
    "total_elements": 150,
    "total_pages": 8,
    "page": 1,
    "size": 20
  }
}
```

---

## 16. 資料庫遷移（Alembic）

```bash
# 初始化
alembic init alembic

# 產生遷移腳本
alembic revision --autogenerate -m "add weighing_record table"

# 執行遷移
alembic upgrade head

# 回退
alembic downgrade -1
```

`alembic/env.py` 中設定 async 模式並匯入所有 Model：
```python
from app.models.base import Base
from app.models import user, weighing_record  # 確保所有 Model 被載入
target_metadata = Base.metadata
```

---

## 17. 測試

### 17.1 測試配置

```python
# tests/conftest.py
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.dependencies import get_db
from app.models.base import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
engine = create_async_engine(TEST_DATABASE_URL)
TestSession = async_sessionmaker(bind=engine, class_=AsyncSession)


@pytest_asyncio.fixture
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSession() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

### 17.2 Router 測試範例

```python
# tests/test_weighing_router.py
import pytest


@pytest.mark.asyncio
async def test_create_weighing_record(client):
    response = await client.post("/api/v1/weighing-records", json={
        "card_no": "IC001",
        "plate_number": "粵A12345",
        "gross_weight": 15000.50,
        "operator_id": 1,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["card_no"] == "IC001"


@pytest.mark.asyncio
async def test_list_weighing_records(client):
    response = await client.get("/api/v1/weighing-records?page=1&size=10")
    assert response.status_code == 200
    data = response.json()
    assert "content" in data["data"]
```

---

## 18. 前後端對照速查表

| 前端 (PrimeVue) | 後端 (FastAPI) |
|-----------------|---------------|
| `xxxService.js` → `fetch/axios` | `routers/xxx_router.py` → 端點 |
| `useXxxApi.js` composable | `services/xxx_service.py` 業務邏輯 |
| Pinia store | JWT token / Session |
| `axiosConfig.js` interceptor | `middleware/` + `exception_handlers.py` |
| DataTable `@page` event | `PageParams(page, size)` |
| `ApiResponse.data.content` | `PageResponse.content` |
| `import.meta.env.VITE_API_BASE_URL` | `settings.CORS_ORIGINS` |
