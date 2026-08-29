// 漲跌配色：使用者明確規定不分台股／美股，一律「紅漲綠跌」（勿改回美股慣例的綠漲紅跌）。
// 所有需要畫「漲跌」語意色的地方（KPI 卡、明細表格、K 線圖）都應該透過這裡取色，
// 不要在元件裡直接寫 text-red-500 / #ef4444 等字面色碼——之後要調整色碼才不用逐一改字面值。

export const MARKET_COLORS = {
    tw: { up: '#dc2626', down: '#16a34a' }, // 紅漲 / 綠跌
    us: { up: '#dc2626', down: '#16a34a' } // 紅漲 / 綠跌（依使用者規定，與台股一致）
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

/**
 * 從 CSS 變數 `--up` 和 `--down` 讀取動態色碼 (Phase 0 新增)
 * 供 ECharts 或 JS 邏輯使用。
 * @param {HTMLElement} [el] - 供 getComputedStyle 讀取的 DOM，預設 document.documentElement
 */
export function getUpDownColorFromCSS(el) {
    if (typeof window === 'undefined') return MARKET_COLORS[DEFAULT_MARKET];
    const target = el || document.documentElement;
    const style = getComputedStyle(target);
    const up = style.getPropertyValue('--up').trim() || MARKET_COLORS[DEFAULT_MARKET].up;
    const down = style.getPropertyValue('--down').trim() || MARKET_COLORS[DEFAULT_MARKET].down;
    return { up, down };
}

/**
 * HEX 色碼轉 rgba() 字串，供 ECharts areaStyle/itemStyle 需要透明度分級的地方共用
 * （原本各圖表元件各自寫一份，抽成共用函式）。非 HEX 開頭時原樣（或 transparent）回傳。
 * @param {string} hex
 * @param {number} alpha - 0~1
 */
export function hexToRgba(hex, alpha) {
    if (!hex || !hex.startsWith('#')) return alpha <= 0 ? 'transparent' : hex;
    const r = parseInt(hex.slice(1, 3), 16) || 0;
    const g = parseInt(hex.slice(3, 5), 16) || 0;
    const b = parseInt(hex.slice(5, 7), 16) || 0;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

