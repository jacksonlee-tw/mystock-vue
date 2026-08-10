/**
 * useMarket — 全域市場狀態 singleton
 *
 * 優先權：URL path (:market) > localStorage > 預設 'tw'
 * Phase 0：僅 localStorage 持久化，markets 清單為靜態預設值。
 * Phase 4：接 GET /api/v1/markets，補齊 markets、marketMeta、metrics。
 */
import { ref, computed } from 'vue';

// ── 靜態預設（Phase 4 前使用） ──────────────────────────────────────
const DEFAULT_MARKETS = [
    {
        code: 'tw',
        label: '台股',
        exchange: 'TWSE',
        currency: 'TWD',
        currency_symbol: 'NT$',
        lot_size: 1000,
        volume_unit_label: '張',
        amount_unit_label: '萬元',
        price_adjusted: false,
        up_down_convention: 'red_up',  // 紅漲綠跌
        timezone: 'Asia/Taipei',
        panels: ['institutional', 'margin', 'table'],
        session_state: 'closed',
        tracked_count: 0
    },
    {
        code: 'us',
        label: '美股',
        exchange: 'NASDAQ',
        currency: 'USD',
        currency_symbol: '$',
        lot_size: 1,
        volume_unit_label: '股',
        amount_unit_label: '百萬美元',
        price_adjusted: true,
        up_down_convention: 'green_up',  // 綠漲紅跌
        timezone: 'America/New_York',
        panels: ['short', 'holders', 'table'],
        session_state: 'closed',
        tracked_count: 0
    }
];

// ── Singleton 狀態 ──────────────────────────────────────────────────
const _stored = typeof localStorage !== 'undefined'
    ? (localStorage.getItem('mystock.market') || 'tw')
    : 'tw';

const currentMarket = ref(_stored);
const markets = ref(DEFAULT_MARKETS);
const _initialized = ref(false);

// ── 計算屬性 ────────────────────────────────────────────────────────
const marketMeta = computed(() =>
    markets.value.find(m => m.code === currentMarket.value) || DEFAULT_MARKETS[0]
);

const enabledMarkets = computed(() => markets.value);

// ── 方法 ────────────────────────────────────────────────────────────

/**
 * 設定當前市場，同步更新 localStorage。
 * @param {string} market  - 'tw' | 'us'
 * @param {object} options - { syncUrl: boolean }（內部用，防止循環）
 */
function setMarket(market, options = {}) {
    const valid = markets.value.map(m => m.code);
    if (!valid.includes(market)) return;
    currentMarket.value = market;
    if (typeof localStorage !== 'undefined') {
        localStorage.setItem('mystock.market', market);
    }
}

/**
 * Phase 4 時從 API 更新市場清單。
 * @param {Array} apiMarkets
 */
function setMarketsFromApi(apiMarkets) {
    if (Array.isArray(apiMarkets) && apiMarkets.length > 0) {
        markets.value = apiMarkets.map(m => ({
            ...(m.meta || m), // 兼容 API 層級與舊層級
            metrics: m.metrics || [],
            session_state: m.session_state || 'closed'
        }));
        // 若當前市場不在可用清單中，切換到第一個
        if (!markets.value.find(m => m.code === currentMarket.value)) {
            setMarket(markets.value[0].code);
        }
    }
}

export function useMarket() {
    return {
        currentMarket,
        markets,
        marketMeta,
        enabledMarkets,
        setMarket,
        setMarketsFromApi,
    };
}
