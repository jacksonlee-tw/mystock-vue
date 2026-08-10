/**
 * format.js — 格式化集中出口
 *
 * 所有幣別、單位、小數位、千分位一律由此產生。
 * 元件內不得再出現 '$'、'張'、'萬元' 字面量。
 *
 * @param {object} meta — 來自後端 chart-data 的 meta 物件，或 useMarket().marketMeta
 */

/**
 * 格式化股價
 * @param {number|null} value
 * @param {object} meta — { currency_symbol, price_decimals? }
 * @returns {string}  例：'NT$102.85' / '$232.14'
 */
export function formatPrice(value, meta = {}) {
    if (value === null || value === undefined || isNaN(Number(value))) return '—';
    const symbol = meta.currency_symbol || '';
    const decimals = meta.price_decimals ?? 2;
    return `${symbol}${Number(value).toLocaleString('zh-TW', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    })}`;
}

/**
 * 格式化成交量
 * @param {number|null} value
 * @param {object} meta — { volume_unit_label, lot_size }
 * @returns {string}  例：'24,879 張' / '48.2M 股'
 */
export function formatVolume(value, meta = {}) {
    if (value === null || value === undefined || isNaN(Number(value))) return '—';
    const unit = meta.volume_unit_label || '';
    const v = Number(value);

    // 美股：stock 以 shares 計，超過百萬顯示 M
    if (meta.lot_size === 1) {
        if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M ${unit}`;
        if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K ${unit}`;
        return `${v.toLocaleString()} ${unit}`;
    }

    // 台股：以「張」計（1張=1000股）
    const lots = Math.round(v / 1000);
    return `${lots.toLocaleString()} ${unit}`;
}

/**
 * 格式化成交金額
 * @param {number|null} value  — 原始元/美元
 * @param {object} meta — { currency_symbol, amount_unit_label, lot_size }
 * @returns {string}  例：'+8,195 萬元' / '$2.8B'
 */
export function formatAmount(value, meta = {}) {
    if (value === null || value === undefined || isNaN(Number(value))) return '—';
    const v = Number(value);
    const symbol = meta.currency_symbol || '';

    // 美股：顯示 B / M
    if (meta.lot_size === 1) {
        if (Math.abs(v) >= 1_000_000_000) return `${symbol}${(v / 1_000_000_000).toFixed(1)}B`;
        if (Math.abs(v) >= 1_000_000) return `${symbol}${(v / 1_000_000).toFixed(1)}M`;
        return `${symbol}${v.toLocaleString()}`;
    }

    // 台股：元 → 萬元
    const wan = Math.round(v / 10000);
    return `${wan.toLocaleString()} ${meta.amount_unit_label || '萬元'}`;
}

/**
 * 格式化漲跌幅
 * @param {number|null} diff   — 漲跌點數
 * @param {number|null} pct    — 漲跌百分比
 * @returns {string}  例：'+0.80 (+0.78%)' / '-5.2 (-2.34%)'
 */
export function formatChange(diff, pct) {
    if (diff === null || diff === undefined || isNaN(Number(diff))) return '—';
    const d = Number(diff);
    const p = Number(pct ?? 0);
    const sign = d >= 0 ? '+' : '';
    const pSign = p >= 0 ? '+' : '';
    return `${sign}${d.toFixed(2)} (${pSign}${p.toFixed(2)}%)`;
}

/**
 * 格式化法人買賣超（張）
 * @param {number|null} value
 * @param {string} unit — 預設 '張'
 */
export function formatLots(value, unit = '張') {
    if (value === null || value === undefined || isNaN(Number(value))) return '—';
    const v = Number(value);
    const sign = v >= 0 ? '+' : '';
    return `${sign}${v.toLocaleString()} ${unit}`;
}

/**
 * 格式化百分比
 * @param {number|null} value
 * @param {number} decimals
 */
export function formatPercent(value, decimals = 2) {
    if (value === null || value === undefined || isNaN(Number(value))) return '—';
    return `${Number(value).toFixed(decimals)}%`;
}
