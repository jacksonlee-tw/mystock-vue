"""LLM 擷取個股的代號防幻覺校驗（比照 industry_chain/validator.py 的 V1／V2）。

差異在處置方式：產業鏈萃取校驗失敗就整條丟棄、不寫入資料庫；筆記解析的結果則是「使用者逐項
覆核後才套用」，所以這裡**不丟棄**，而是給每檔一個狀態讓 UI 標示、預設不勾選：

- verified       代號存在於 symbols 主檔，且名稱相符（正規化後互相包含，允許簡稱）
- name_mismatch  代號存在但名稱對不上——「公司對、代號記錯」是幻覺的典型型態，UI 上看不出來
- not_found      代號不存在於 symbols 主檔
- unverified     主檔查詢失敗（DATA_SOURCE=json 或 Postgres 不可用）；不可假裝已驗證

name_mismatch／not_found 會另外用模型宣稱的公司名稱去主檔查，剛好只對到一檔時附上 suggestion，
讓使用者一鍵改成正確代號。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Optional

from industry_chain.validator import _normalize_name
from note_ai.schema import ExtractedSymbol

logger = logging.getLogger("mystock-backend")

SymbolStatus = Literal["verified", "name_mismatch", "not_found", "unverified"]


@dataclass
class ValidatedSymbol:
    market: str
    symbol: str
    name: str  # 模型宣稱的名稱
    evidence: str
    status: SymbolStatus
    master_name: Optional[str] = None
    reason: Optional[str] = None
    suggestion: Optional[dict] = None


def _norm(name: str) -> str:
    return _normalize_name(name).lower()


def _names_match(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    return bool(na) and bool(nb) and (na in nb or nb in na)


def _normalize_code(code: str) -> str:
    return (code or "").strip().upper().removesuffix(".TW")


async def _suggest_by_name(repo, market: str, name: str, wrong_code: str) -> Optional[dict]:
    """用模型宣稱的公司名稱反查主檔；恰好只對到一檔（且不是原本那個錯的代號）才給建議。"""
    if not _norm(name):
        return None
    try:
        rows = await repo.search_symbols(name.strip(), market, limit=5)
    except Exception as exc:  # noqa: BLE001 — 建議是加分項，查詢失敗不影響驗證結果
        logger.warning("[筆記AI] 以名稱反查代號失敗（market=%s, name=%s）：%s", market, name, exc)
        return None
    matches = [r for r in rows if r.get("symbol") != wrong_code and _names_match(r.get("name", ""), name)]
    if len(matches) != 1:
        return None
    return {"market": market, "symbol": matches[0]["symbol"], "name": matches[0].get("name") or ""}


async def validate_symbols(symbols: list[ExtractedSymbol], *, repo=None) -> list[ValidatedSymbol]:
    """回傳與輸入同序（依首次出現）、已去重的校驗結果。repo 需有 get_symbols／search_symbols。"""
    if repo is None:
        from repositories.stock_repository import StockRepository
        repo = StockRepository()

    unique: list[ExtractedSymbol] = []
    seen: set[tuple[str, str]] = set()
    for s in symbols:
        code = _normalize_code(s.symbol)
        if not code or (s.market, code) in seen:
            continue
        seen.add((s.market, code))
        unique.append(s.model_copy(update={"symbol": code}))

    codes_by_market: dict[str, list[str]] = {}
    for s in unique:
        codes_by_market.setdefault(s.market, []).append(s.symbol)

    master: dict[tuple[str, str], str] = {}
    master_available = True
    try:
        for market, codes in codes_by_market.items():
            for row in await repo.get_symbols(codes, market):
                master[(market, row["symbol"])] = row.get("name") or ""
    except Exception as exc:  # noqa: BLE001 — DATA_SOURCE=json／Postgres 不可用：如實標示未驗證
        logger.warning("[筆記AI] 查詢 symbols 主檔失敗，個股一律標為未驗證：%s", exc)
        master_available = False

    out: list[ValidatedSymbol] = []
    for s in unique:
        base = dict(market=s.market, symbol=s.symbol, name=s.name, evidence=s.evidence)
        if not master_available:
            out.append(ValidatedSymbol(**base, status="unverified", reason="無法查詢代號主檔，未驗證"))
            continue

        master_name = master.get((s.market, s.symbol))
        if master_name is None:
            out.append(ValidatedSymbol(
                **base, status="not_found", reason=f"代號 {s.symbol} 不存在於 symbols 主檔",
                suggestion=await _suggest_by_name(repo, s.market, s.name, s.symbol),
            ))
        elif not _names_match(master_name, s.name):
            out.append(ValidatedSymbol(
                **base, status="name_mismatch", master_name=master_name,
                reason=f"名稱不符：{s.symbol} 應為「{master_name}」，模型給的是「{s.name}」",
                suggestion=await _suggest_by_name(repo, s.market, s.name, s.symbol),
            ))
        else:
            out.append(ValidatedSymbol(**base, status="verified", master_name=master_name))
    return out
