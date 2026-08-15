"""
notify/timeutil.py
共用時間欄位轉換工具。

notify_endpoint 的 quiet_start / quiet_end / digest_send_time 是 Postgres TIME 欄位；
asyncpg 綁定參數時要求原生 datetime.time 物件，不接受 'HH:MM' 字串（比照 TIMESTAMPTZ 欄位
只接受原生 datetime、不接受 isoformat() 字串的教訓 —— 同一個坑，這次是 TIME 型別版本）。

凡是要把使用者輸入（設定檔字串、表單字串）寫進這三個欄位的地方，一律先過這裡的 parse_time()，
不要在各處各自重複解析邏輯。
"""
from __future__ import annotations
from datetime import time
from typing import Any


def parse_time(val: Any) -> time | None:
    """把 None / datetime.time / 'HH:MM' / 'HH:MM:SS' 字串統一轉成 datetime.time（或 None）。"""
    if val is None:
        return None
    if isinstance(val, time):
        return val
    if isinstance(val, str):
        if not val.strip():
            return None
        parts = [int(p) for p in val.split(":")]
        while len(parts) < 3:
            parts.append(0)
        return time(*parts[:3])
    raise TypeError(f"無法解析為 time：{val!r}")
