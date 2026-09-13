// 判斷「這支股票的資料是否已經落後於預期的最後交易日」，供個股頁面的過期提示／重新抓取按鈕使用。
//
// 刻意不做精確的交易日曆比對（國定假日、盤中臨時休市等後端才有 no_trading_days 快取，前端拿不到）；
// 用「平日 + 收盤後緩衝時間」做保守估計即可——誤判頂多讓使用者多點一次「重新抓取」，並不會顯示錯誤
// 資料，比完全不提示好。台股排程 14:30 Asia/Taipei 抓取（見 services/scheduler.py），美股排程
// 06:00 Asia/Taipei 抓的是美股前一交易日資料，換算時區後緩衝時間設在美東 18:00。

const MARKET_TZ = { tw: 'Asia/Taipei', us: 'America/New_York' };
const CUTOFF_HOUR = { tw: 16, us: 18 };

function nowPartsInTz(timeZone) {
    // en-CA 的日期格式固定是 YYYY-MM-DD，省去自己重組欄位順序的麻煩。
    const fmt = new Intl.DateTimeFormat('en-CA', {
        timeZone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hour12: false
    });
    const parts = Object.fromEntries(fmt.formatToParts(new Date()).map((p) => [p.type, p.value]));
    // 24:00 在部分瀏覽器的 hour12:false 輸出會是 "24"，代表隔天 00:00，需要正規化避免誤判成當天傍晚。
    const hour = Number(parts.hour) % 24;
    return { dateKey: `${parts.year}-${parts.month}-${parts.day}`, hour };
}

function dayOfWeekUTC(dateKey) {
    const [y, m, d] = dateKey.split('-').map(Number);
    return new Date(Date.UTC(y, m - 1, d)).getUTCDay(); // 0=Sun ... 6=Sat
}

function addDaysToKey(dateKey, delta) {
    const [y, m, d] = dateKey.split('-').map(Number);
    const dt = new Date(Date.UTC(y, m - 1, d));
    dt.setUTCDate(dt.getUTCDate() + delta);
    return dt.toISOString().slice(0, 10);
}

/** 往前推到最近一個平日（週一~週五）；本身就是平日則原樣回傳。 */
function lastWeekdayOnOrBefore(dateKey) {
    let key = dateKey;
    while (dayOfWeekUTC(key) === 0 || dayOfWeekUTC(key) === 6) {
        key = addDaysToKey(key, -1);
    }
    return key;
}

/**
 * 估算「現在時間點理論上應該已經有資料的最後一個交易日」（YYYY-MM-DD，近似值）。
 * @param {string} [market] - 'tw' | 'us'
 */
export function expectedLatestTradingDate(market = 'tw') {
    const tz = MARKET_TZ[market] || MARKET_TZ.tw;
    const cutoff = CUTOFF_HOUR[market] ?? CUTOFF_HOUR.tw;
    const { dateKey, hour } = nowPartsInTz(tz);

    const lastWeekday = lastWeekdayOnOrBefore(dateKey);
    if (lastWeekday !== dateKey) {
        // 現在是週末，預期資料停在往前推到的那個平日
        return lastWeekday;
    }
    // 現在是平日：收盤+緩衝時間之前，預期資料還停留在前一個平日
    if (hour < cutoff) {
        return lastWeekdayOnOrBefore(addDaysToKey(dateKey, -1));
    }
    return dateKey;
}

/**
 * 判斷某股票目前資料是否落後於預期的最後交易日。
 * @param {string|null|undefined} latestDate - 目前已有資料的最後日期（YYYY-MM-DD）
 * @param {string} [market] - 'tw' | 'us'
 */
export function isDataStale(latestDate, market = 'tw') {
    if (!latestDate) return false;
    return latestDate < expectedLatestTradingDate(market);
}

/**
 * 估算落後的平日天數，供「重新抓取」彈窗的缺漏提示與預設區間使用。
 * @param {string|null|undefined} latestDate
 * @param {string} [market]
 */
export function staleWeekdaysCount(latestDate, market = 'tw') {
    if (!latestDate) return 0;
    const expected = expectedLatestTradingDate(market);
    if (latestDate >= expected) return 0;
    let count = 0;
    let cursor = addDaysToKey(latestDate, 1);
    while (cursor <= expected) {
        const dow = dayOfWeekUTC(cursor);
        if (dow !== 0 && dow !== 6) count++;
        cursor = addDaysToKey(cursor, 1);
    }
    return count;
}
