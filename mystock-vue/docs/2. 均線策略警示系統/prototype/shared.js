// =====================================================
// Shared JS — MyStock 均線策略警示系統 Prototype
// =====================================================

// ── Theme ─────────────────────────────────────────
(function () {
  const saved = localStorage.getItem('proto-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  // Update icon when DOM ready
  document.addEventListener('DOMContentLoaded', () => syncThemeIcon());
})();

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('proto-theme', next);
  syncThemeIcon();
}

function syncThemeIcon() {
  const icon = document.getElementById('theme-icon');
  if (!icon) return;
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  icon.className = isDark ? 'pi pi-sun' : 'pi pi-moon';
}

// ── Toggle Switch helper ───────────────────────────
function initToggle(inputEl, onChange) {
  if (!inputEl) return;
  inputEl.addEventListener('change', () => onChange(inputEl.checked));
}

// ── Mock data ──────────────────────────────────────
const MOCK_ALERTS = [
  {
    id: 'alert-20260811-2330-001',
    timestamp: '2026-08-11T14:30:00+08:00',
    stock_id: '2330',
    stock_name: '台積電',
    market: 'tw',
    strategy_id: 'price_cross_ma',
    strategy_name: '收盤價突破 60 日季線',
    direction: 'cross_above',
    signal_strength: 'strong',
    details: { close: 1020.0, ma_period: 60, ma_value: 985.5, bias_percent: 3.5, volume_ratio: 1.8 },
    filters_passed: ['volume_confirm', 'institutional_buy', 'candlestick_confirm'],
    suggested_action: '可納入多頭觀察清單，停損參考季線下 3%（956 元）'
  },
  {
    id: 'alert-20260811-AAPL-001',
    timestamp: '2026-08-11T13:15:00+08:00',
    stock_id: 'AAPL',
    stock_name: 'Apple',
    market: 'us',
    strategy_id: 'ma_golden_death_cross',
    strategy_name: '20MA 穿越 60MA — 黃金交叉',
    direction: 'golden_cross',
    signal_strength: 'strong',
    details: { close: 195.3, ma_period: null, ma_value: null, bias_percent: null, volume_ratio: 2.1 },
    filters_passed: ['volume_confirm', 'candlestick_confirm'],
    suggested_action: '趨勢翻多確立，可分批建立多頭部位'
  },
  {
    id: 'alert-20260811-2454-001',
    timestamp: '2026-08-11T14:30:00+08:00',
    stock_id: '2454',
    stock_name: '聯發科',
    market: 'tw',
    strategy_id: 'extreme_bias',
    strategy_name: '負乖離過大（超賣警示）',
    direction: 'oversold',
    signal_strength: 'moderate',
    details: { close: 870.0, ma_period: 60, ma_value: 1023.5, bias_percent: -15.0, volume_ratio: 0.9 },
    filters_passed: ['market_trend'],
    suggested_action: '超跌反彈可能，建議小量觀察，確認量能配合'
  },
  {
    id: 'alert-20260811-TSLA-001',
    timestamp: '2026-08-11T12:45:00+08:00',
    stock_id: 'TSLA',
    stock_name: 'Tesla',
    market: 'us',
    strategy_id: 'ma_alignment',
    strategy_name: '多頭排列確立（5>10>20>60MA）',
    direction: 'bullish',
    signal_strength: 'moderate',
    details: { close: 248.0, ma_period: null, ma_value: null, bias_percent: null, volume_ratio: 1.3 },
    filters_passed: ['volume_confirm'],
    suggested_action: '趨勢動能強，可持股續抱或追買'
  },
  {
    id: 'alert-20260810-2317-001',
    timestamp: '2026-08-10T14:30:00+08:00',
    stock_id: '2317',
    stock_name: '鴻海',
    market: 'tw',
    strategy_id: 'price_cross_ma',
    strategy_name: '收盤價跌破 20 日月線',
    direction: 'cross_under',
    signal_strength: 'weak',
    details: { close: 185.0, ma_period: 20, ma_value: 188.5, bias_percent: -1.9, volume_ratio: 1.1 },
    filters_passed: [],
    suggested_action: '量能不足，觀察是否出現止跌訊號'
  },
  {
    id: 'alert-20260810-2412-001',
    timestamp: '2026-08-10T14:30:00+08:00',
    stock_id: '2412',
    stock_name: '中華電',
    market: 'tw',
    strategy_id: 'ma_pullback_support',
    strategy_name: '均線回踩支撐（月線附近）',
    direction: 'pullback_buy',
    signal_strength: 'strong',
    details: { close: 122.5, ma_period: 20, ma_value: 121.8, bias_percent: 0.6, volume_ratio: 1.7 },
    filters_passed: ['volume_confirm', 'candlestick_confirm', 'institutional_buy'],
    suggested_action: '多頭趨勢中拉回買點，停損月線下 2%'
  },
  {
    id: 'alert-20260809-2603-001',
    timestamp: '2026-08-09T14:30:00+08:00',
    stock_id: '2603',
    stock_name: '長榮',
    market: 'tw',
    strategy_id: 'ma_squeeze_breakout',
    strategy_name: '均線糾結突破',
    direction: 'breakout',
    signal_strength: 'strong',
    details: { close: 210.0, ma_period: null, ma_value: null, bias_percent: null, volume_ratio: 2.8 },
    filters_passed: ['volume_confirm', 'candlestick_confirm'],
    suggested_action: '盤整後帶量突破，籌碼沉澱完成，積極多方'
  }
];

const STRATEGY_META = {
  price_cross_ma:      { label: '收盤價突破/跌破', icon: 'pi-arrows-v',   color: 'blue' },
  ma_golden_death_cross: { label: '黃金/死亡交叉', icon: 'pi-sort-alt',   color: 'amber' },
  ma_alignment:        { label: '均線排列',         icon: 'pi-align-left', color: 'green' },
  ma_squeeze_breakout: { label: '均線糾結突破',     icon: 'pi-expand',     color: 'blue' },
  extreme_bias:        { label: '乖離率警示',       icon: 'pi-percentage', color: 'red' },
  ma_pullback_support: { label: '回踩支撐',         icon: 'pi-arrow-down', color: 'green' }
};

const DIRECTION_META = {
  cross_above:   { label: '突破',     icon: '▲', bull: true },
  cross_under:   { label: '跌破',     icon: '▼', bull: false },
  golden_cross:  { label: '黃金交叉', icon: '✕', bull: true },
  death_cross:   { label: '死亡交叉', icon: '✕', bull: false },
  bullish:       { label: '多頭排列', icon: '▲', bull: true },
  bearish:       { label: '空頭排列', icon: '▼', bull: false },
  oversold:      { label: '超賣反彈', icon: '↑', bull: true },
  overbought:    { label: '超買停利', icon: '↓', bull: false },
  breakout:      { label: '突破起漲', icon: '▲', bull: true },
  pullback_buy:  { label: '拉回買點', icon: '↩', bull: true }
};

function isBullish(a) {
  return DIRECTION_META[a.direction]?.bull ?? true;
}

function formatDate(ts) {
  const d = new Date(ts);
  const mo = String(d.getMonth() + 1).padStart(2, '0');
  const da = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mo}-${da}`;
}
function formatTime(ts) {
  const d = new Date(ts);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

// ── Misc utils ─────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  syncThemeIcon();
});
