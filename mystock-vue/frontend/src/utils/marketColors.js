// 漲跌配色由市場決定：
// 台股慣例「紅漲綠跌」，美股／多數海外市場慣例「綠漲紅跌」。
// 所有需要畫「漲跌」語意色的地方（KPI 卡、明細表格、K 線圖）都應該透過這裡取色，
// 不要在元件裡直接寫 text-red-500 / #ef4444 等字面色碼——加入美股後才不用逐一改字面值。
//
// 目前後端資料尚未回傳 market 欄位（僅支援台股），因此預設一律為 'tw'；
// 一旦 chart-data API 開始回傳 market，呼叫端只要把該值傳進來即可自動切換配色，
// 不需要再改這支檔案或呼叫端的其他邏輯。

export const MARKET_COLORS = {
    tw: { up: '#dc2626', down: '#16a34a' }, // 紅漲 / 綠跌
    us: { up: '#16a34a', down: '#dc2626' } // 綠漲 / 紅跌
};

export const DEFAULT_MARKET = 'tw';

/**
 * 取得指定市場的漲跌色（十六進位色碼），供 DOM inline style 與 ECharts itemStyle 共用。
 * @param {string} [market] - 'tw' | 'us'，未知或缺省時退回台股慣例。
 */
export function getUpDownColor(market) {
    return MARKET_COLORS[market] || MARKET_COLORS[DEFAULT_MARKET];
}

/**
 * 依數值正負取得對應的漲跌色。0 視為平盤，回傳中性色。
 * @param {number} value
 * @param {string} [market]
 * @param {string} [neutral] - 平盤色，預設沿用目前的中性文字色
 */
export function colorForValue(value, market, neutral = 'inherit') {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return neutral;
    const { up, down } = getUpDownColor(market);
    return Number(value) >= 0 ? up : down;
}
