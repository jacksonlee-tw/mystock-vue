// 個人投資記帳模組共用格式化工具，供 views/portfolio/*.vue 共用（避免每頁各刻一份）。
// marketMeta 對應 backend/markets/{tw,us}.py 的 MarketMeta（currency_symbol / lot_size）。
export const marketMeta = {
    tw: { label: '台股', symbol: 'NT$', lotSize: 1000 },
    us: { label: '美股', symbol: '$', lotSize: 1 }
};

export function fmtNum(n) {
    return Math.round(n || 0).toLocaleString();
}

// 美股金額保留 2 位小數，台股四捨五入到整數
export function fmtAmt(n, market) {
    if (market === 'us') {
        return (n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return Math.round(n || 0).toLocaleString();
}

export function fmtPct(n) {
    if (n === null || n === undefined) return '—';
    return (n >= 0 ? '+' : '') + n.toFixed(1) + '%';
}

export function signed(n, market) {
    const v = n || 0;
    return (v >= 0 ? '+' : '-') + fmtAmt(Math.abs(v), market);
}

// 台股張/股輔助顯示（lot_size = 1000，見 markets/tw.py）
export function lotLabel(shares, market) {
    if (market !== 'tw') return '';
    const lot = marketMeta.tw.lotSize;
    const full = Math.floor(shares / lot);
    const odd = shares % lot;
    if (full === 0) return `${odd} 股（零股）`;
    return odd === 0 ? `${full} 張` : `${full} 張 ${odd} 股`;
}

export const TW_ETF_RE = /^00\d{2,4}[A-Za-z]?$/;
export function isTwEtfSymbol(symbol) {
    return TW_ETF_RE.test(String(symbol || '').toUpperCase());
}

// PrimeVue <DatePicker> 綁定的是 JS Date；API 要的是 'YYYY-MM-DD'（後端 Pydantic date 欄位）。
export function toIsoDate(date) {
    if (!date) return null;
    const d = date instanceof Date ? date : new Date(date);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}

export function fromIsoDate(isoStr) {
    if (!isoStr) return null;
    const [y, m, d] = isoStr.split('-').map(Number);
    return new Date(y, m - 1, d);
}

export function todayDate() {
    return new Date();
}
