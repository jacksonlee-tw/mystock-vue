"""TWSE 請求層：行程級共用的自適應限流器 + 帶重試的 JSON 請求。

為什麼限流放這裡而不是散在各爬蟲的 time.sleep()：
  TWSE 是「按來源 IP」限流，對它而言請求速率只跟「全行程每秒送出幾個請求」有關，
  跟開了幾條執行緒無關。舊版把 sleep(3.5~5.5) 寫死在三個迴圈裡，只能單執行緒序列跑，
  82% 的時間都花在睡覺。把節流集中成一個跨執行緒共用的限流器後：
    * 速率上限由限流器一處決定（.env 可調），與併發數脫鉤；
    * 併發只負責把「網路往返時間」疊起來，不會讓速率超標；
    * 任一執行緒被擋時，整個行程一起降速、一起冷卻，而不是其他執行緒繼續猛打。

TWSE 沒有公開的官方限流數字，所以不寫死猜測值：從保守的起始間隔開始，連續成功就逐步
加速到下限，遇到逾時／連線被丟棄／回傳非 JSON（被擋時常回 HTML）就倍增間隔並全域冷卻。
"""
import logging
import random
import threading
import time
from typing import Optional

import requests

from config import get_twse_rate_settings

logger = logging.getLogger("mystock-backend")

_TWSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.twse.com.tw/zh/trading/historical/stock-day.html",
}
_TWSE_TIMEOUT = (5, 20)  # (連線 timeout, 讀取 timeout)


class AdaptiveRateLimiter:
    """跨執行緒共用的「最小間隔」限流器，間隔會依成功／被擋自動升降速。

    acquire() 在鎖內預約下一個放行時間點、鎖外睡到那個時間，所以即使多條執行緒同時
    呼叫，放行時間點也會彼此相隔 interval，不會一擁而上。"""

    def __init__(self, start_interval: float, min_interval: float, max_interval: float,
                 speedup_after: int = 10, speedup_step: float = 0.25,
                 clock=time.monotonic, sleep=time.sleep):
        self._interval = start_interval
        self._min = min_interval
        self._max = max_interval
        self._speedup_after = speedup_after
        self._speedup_step = speedup_step
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_slot = 0.0
        self._success_streak = 0

    @property
    def interval(self) -> float:
        with self._lock:
            return self._interval

    def acquire(self) -> None:
        with self._lock:
            now = self._clock()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self._interval
        wait = slot - now
        if wait > 0:
            self._sleep(wait)

    def on_success(self) -> None:
        with self._lock:
            self._success_streak += 1
            if self._success_streak >= self._speedup_after:
                self._success_streak = 0
                self._interval = max(self._min, self._interval - self._speedup_step)

    def on_throttle(self, cooldown: float = 0.0) -> None:
        """遇到逾時／被擋：間隔倍增，並讓「所有」執行緒的下一次放行至少延後 cooldown 秒。"""
        with self._lock:
            self._success_streak = 0
            self._interval = min(self._max, self._interval * 2)
            self._next_slot = max(self._next_slot, self._clock() + cooldown)


_limiter: Optional[AdaptiveRateLimiter] = None
_limiter_lock = threading.Lock()

_twse_session = requests.Session()
_twse_session.headers.update(_TWSE_HEADERS)


def get_twse_limiter() -> AdaptiveRateLimiter:
    global _limiter
    with _limiter_lock:
        if _limiter is None:
            settings = get_twse_rate_settings()
            _limiter = AdaptiveRateLimiter(
                start_interval=settings["start_interval"],
                min_interval=settings["min_interval"],
                max_interval=settings["max_interval"],
            )
        return _limiter


def twse_get_json(url: str, max_retries: int = 3, *, session=None, limiter=None) -> dict:
    """對 TWSE API 發送請求。每次嘗試（含重試）都先向限流器取號，失敗時通知限流器降速並
    全域冷卻（指數退避 + jitter）。重試耗盡後拋出最後一個例外，由呼叫端決定該筆資料視為抓取失敗。"""
    session = session or _twse_session
    limiter = limiter or get_twse_limiter()
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        limiter.acquire()
        try:
            resp = session.get(url, timeout=_TWSE_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            # ValueError：回傳非 JSON（TWSE 擋人時常回 HTML 頁面），與連線被丟棄同樣視為被擋訊號
            last_exc = e
            backoff = (2 ** attempt) * 5 + random.uniform(1, 3)
            limiter.on_throttle(cooldown=backoff)
            if attempt < max_retries - 1:
                logger.warning(
                    f"[TWSE] 請求逾時/失敗（第 {attempt + 1}/{max_retries} 次），"
                    f"全域冷卻 {backoff:.1f}s 後重試: {url} ({e})"
                )
            continue
        limiter.on_success()
        return data
    raise last_exc
