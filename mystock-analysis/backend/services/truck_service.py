"""車輛清單業務邏輯層

負責車輛清單查詢的商業邏輯。
透過 UnitOfWork 存取 Repository。
"""
from typing import Optional

from backend.domain.ports.unit_of_work import UnitOfWork


def list_trucks(uow: UnitOfWork, keyword: Optional[str] = None) -> dict:
    """車輛清單查詢（排除黑名單，無需 locale）。"""
    trucks = uow.trucks.list_trucks(keyword)
    return {"count": len(trucks), "trucks": trucks}
