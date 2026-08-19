// 均線策略觸發方向的顯示輔助。多空分類邏輯對齊 backend/strategies/direction.py，
// 兩邊各自實作是因為分屬前後端不同執行環境，但規則必須保持一致。

// KD 隨機指標新增 kd_golden_cross / kd_death_cross（KD指標 設計規格書 §5.5，四處同步之一）。
// 順帶補上 bottom_turnover/short_squeeze（籌碼選股策略）與 distribution_top/revenue_yoy_decline
// （賣股策略）——這四個既有方向字串一直沒登記在這裡：前兩個因為 classifyDirection() 預設就是
// bullish，缺漏不影響顯示；但後兩個是空方訊號，缺漏會讓看板把它們畫成多方（箭頭/顏色錯誤），
// 是既有 bug，藉這次同步一併修正（見 backend/strategies/direction.py 對照）。
// pick_ / exit_ 補上明確前綴（股價相對低點 需求規格書 §10.2）：兩者原本只靠下方
// classifyDirection() 的預設值（bullish）湊巧命中正確結果 —— pick_ 剛好該是 bullish，
// 但 exit_ 該是 bearish 卻沒有任何前綴會命中，只是尚未被任何既有 exit_ 方向字串觸發到而已。
// 明確登記，維持與 backend/strategies/direction.py 的規則一致（本檔開頭註解即為此約定）。
const BULLISH_PREFIXES = [
    'cross_above', 'golden_cross', 'bullish_alignment', 'squeeze_breakout', 'oversold', 'pullback_support',
    'bottom_turnover', 'short_squeeze',
    'kd_golden_cross',
    'pick_'
];
const BEARISH_PREFIXES = [
    'cross_under', 'death_cross', 'bearish_alignment', 'overbought',
    'distribution_top', 'revenue_yoy_decline',
    'kd_death_cross',
    'exit_'
];

export function classifyDirection(direction) {
    if (BEARISH_PREFIXES.some((p) => direction?.startsWith(p))) return 'bearish';
    return 'bullish';
}

// { icon: PrimeIcons class, colorClass: Tailwind 文字色 } —— 沿用專案既有的 text-up/text-down 慣例
// （見 frontend/src/views/HeatmapDashboard.vue），漲跌色系交給 project-style.css 依市場決定。
export function directionVisual(direction) {
    const bullish = classifyDirection(direction) === 'bullish';
    return {
        icon: bullish ? 'pi-arrow-up' : 'pi-arrow-down',
        colorClass: bullish ? 'text-up' : 'text-down'
    };
}

const LABEL_PATTERNS = [
    [/^cross_above_MA(\d+)$/, (m) => `突破 ${m[1]} 日均線`],
    [/^cross_under_MA(\d+)$/, (m) => `跌破 ${m[1]} 日均線`],
    [/^golden_cross_(\d+)_(\d+)$/, (m) => `${m[1]} 日／${m[2]} 日均線黃金交叉`],
    [/^death_cross_(\d+)_(\d+)$/, (m) => `${m[1]} 日／${m[2]} 日均線死亡交叉`],
    [/^bullish_alignment$/, () => '均線多頭排列成形'],
    [/^bearish_alignment$/, () => '均線空頭排列成形'],
    [/^squeeze_breakout$/, () => '均線糾結後帶量突破'],
    [/^overbought$/, () => '正乖離過大（超買）'],
    [/^oversold$/, () => '負乖離過大（超賣）'],
    [/^pullback_support_MA(\d+)$/, (m) => `回踩 ${m[1]} 日均線支撐`],
    [/^kd_golden_cross_oversold$/, () => 'KD 超賣區黃金交叉'],
    [/^kd_death_cross_overbought$/, () => 'KD 超買區死亡交叉'],
    // 選股策略方向文案（股價相對低點 需求規格書 §10.2；其餘既有 pick_ 方向沿用原始字串，
    // 屬既有技術債，見《選股爬蟲》§5.6，本次僅補登本模組新增的方向）
    [/^pick_relative_low$/, () => '相對低點承接精選']
];

export function formatDirectionLabel(direction) {
    for (const [pattern, format] of LABEL_PATTERNS) {
        const m = direction?.match(pattern);
        if (m) return format(m);
    }
    return direction || '';
}

export const STRENGTH_META = {
    strong: { label: '強', severity: 'success' },
    moderate: { label: '中', severity: 'warn' },
    weak: { label: '弱', severity: 'secondary' }
};
