// K 線圖均線疊圖工具。
// 沿用常見的 5 / 20 / 60 三線（短、中、長期）：
// 依目前選擇的聚合週期（日線/週線/月線），標籤自動改成「5日均線」「5週均線」「5月均線」，
// 這樣使用者切換日線/週線/月線時，均線名稱始終對應目前看到的每根 K 棒代表的時間單位。

const WINDOWS = [5, 20, 60];

const PERIOD_UNIT = {
    daily: '日',
    weekly: '週',
    monthly: '月'
};

// 與 K 線本身（漲跌色）跟三大法人圖（外資/投信/自營商/合計）都不同的三個色相，
// 避免均線顏色跟既有的語意色（漲跌）或類別色（法人別）搶戲或混淆。
const COLORS = ['#f59e0b', '#0ea5e9', '#8b5cf6'];

function sma(values, window) {
    const out = new Array(values.length).fill(null);
    let sum = 0;
    for (let i = 0; i < values.length; i++) {
        sum += values[i];
        if (i >= window) sum -= values[i - window];
        if (i >= window - 1) {
            out[i] = +(sum / window).toFixed(2);
        }
    }
    return out;
}

/**
 * @param {Array<[number, number, number, number]>} kline - [開盤, 收盤, 最低, 最高]
 * @param {string} period - 'daily' | 'weekly' | 'monthly'
 * @returns {{ names: string[], series: object[] }}
 */
export function buildMovingAverageSeries(kline, period) {
    const unit = PERIOD_UNIT[period] || '日';
    const closes = (kline || []).map((d) => (Array.isArray(d) ? d[1] : null));

    const series = WINDOWS.map((window, idx) => ({
        name: `${window}${unit}均線`,
        type: 'line',
        data: sma(closes, window),
        smooth: false,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.5, color: COLORS[idx] },
        itemStyle: { color: COLORS[idx] },
        z: 3
    }));

    return { names: series.map((s) => s.name), series };
}
