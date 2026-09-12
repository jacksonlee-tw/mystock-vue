"""L3 近似標題去重（docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md §3.3，ADR-P4-02）。

獨立成一個模組（不是併入 news_fetcher.py）：去重邏輯未來很可能被情緒評分 job 複用來排除
`is_duplicate` 列，放進抓取器檔案會造成不必要耦合（見 Phase4 文件 §15.4 落差點）。

L1（`(symbol, news_url)`）與 L2（`(symbol, title_hash, effective_trade_date)`）唯一索引已在
`NewsRepository.insert_news_if_new()` 由資料庫把關；本模組只處理「插入成功後」的 L3 步驟——
在同一標的近 `dedup_window_hours` 小時內找出既有代表列，用 SimHash 漢明距離判斷是否為改寫
標題的近似重複。
"""
import logging
from datetime import datetime, timedelta

from indicators.news_time import hamming_distance
from repositories.news_repository import NewsRepository
from services.news_config import NewsSourcesConfig

logger = logging.getLogger("mystock-backend")


async def resolve_l3_duplicate(
    repo: NewsRepository,
    *,
    news_id: int,
    symbol: str,
    source_id: str,
    simhash_value: int,
    published_at: datetime,
    config: NewsSourcesConfig,
) -> None:
    """對剛插入的 `news_id` 做 L3 近似比對；命中時依 `weight` 決定誰是代表列。

    `weight` 相同時保留既有代表列（新進者不因平手就搶走代表權，理由：既有代表列往往是
    較早發布的原始來源，符合「保留權重最高」規格字面上「最高」是唯一勝出條件的精神）。
    """
    if simhash_value == 0:
        return  # 空標題／過短標題不參與近似比對，避免全零指紋互相誤判

    since = published_at - timedelta(hours=config.dedup_window_hours)
    candidates = await repo.find_recent_candidates_for_dedup(symbol=symbol, since=since, exclude_id=news_id)

    new_weight = _weight_of(config, source_id)
    for candidate in candidates:
        if candidate["simhash"] is None:
            continue
        if hamming_distance(simhash_value, candidate["simhash"]) > config.dedup_hamming_max:
            continue

        candidate_weight = _weight_of(config, candidate["source"])
        if new_weight > candidate_weight:
            # 新進者權重較高，改把既有代表列標記為重複、指向新進者
            await repo.mark_duplicate(candidate["id"], news_id)
        else:
            # 既有代表列權重相同或較高，新進者標記為重複
            await repo.mark_duplicate(news_id, candidate["id"])
        return  # 找到第一個命中即可判定，同一則新聞不需比對多個候選


def _weight_of(config: NewsSourcesConfig, source_id: str) -> float:
    source = config.get(source_id)
    return source.weight if source else 1.0
