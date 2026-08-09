"""DB 連線狀態 API 路由（Controller 層）"""
from fastapi import APIRouter

from backend.db.session import is_fallback, DB_SERVER, DB_DATABASE, COMP_NO, PLANT_NO
from backend.schemas.responses import DbStatusResponse

router = APIRouter(prefix="/api/db", tags=["資料庫狀態"])


@router.get("/status", response_model=DbStatusResponse)
def db_status_api():
    """回傳目前 DB 連線狀態（前端標頭徽章用）"""
    return {
        "connected": not is_fallback(),
        "mode": "mssql" if not is_fallback() else "memory",
        "server": DB_SERVER,
        "database": DB_DATABASE,
        "compNo": COMP_NO,
        "plantNo": PLANT_NO,
    }
