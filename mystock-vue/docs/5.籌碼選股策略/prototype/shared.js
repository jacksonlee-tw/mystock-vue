// =====================================================
// Shared JS — MyStock 籌碼選股警示系統 Prototype
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
    market: 'large',
    strategy_id: 'foreign_core',
    strategy_name: '外資連續買超 (大於 10% 成交量)',
    direction: 'buy',
    signal_strength: 'strong',
    details: { close: 1020.0, foreign_buy: 15400, trust_buy: 800, margin_change: -200 },
    filters_passed: ['trend_ma60_up'],
    suggested_action: '外資買盤積極，大型股波段起漲點，可納入核心配置'
  },
  {
    id: 'alert-20260811-3529-001',
    timestamp: '2026-08-11T14:30:00+08:00',
    stock_id: '3529',
    stock_name: '力旺',
    market: 'mid_small',
    strategy_id: 'trust_satellite',
    strategy_name: '投信破冰連續買超',
    direction: 'buy',
    signal_strength: 'strong',
    details: { close: 2450.0, foreign_buy: -150, trust_buy: 450, margin_change: 0 },
    filters_passed: ['seasonality_q3'],
    suggested_action: '投信季末作帳啟動，短線爆發力強，設定 10MA 停損'
  },
  {
    id: 'alert-20260811-2603-001',
    timestamp: '2026-08-11T14:30:00+08:00',
    stock_id: '2603',
    stock_name: '長榮',
    market: 'large',
    strategy_id: 'bottom_washout',
    strategy_name: '底部換手 (散戶退、法人進)',
    direction: 'buy',
    signal_strength: 'moderate',
    details: { close: 185.0, foreign_buy: 5200, trust_buy: 1200, margin_change: -4500 },
    filters_passed: ['trend_ma20_breakout'],
    suggested_action: '融資大減法人大買，籌碼沉澱完成，波段買點'
  },
  {
    id: 'alert-20260811-3231-001',
    timestamp: '2026-08-11T13:15:00+08:00',
    stock_id: '3231',
    stock_name: '緯創',
    market: 'mid_small',
    strategy_id: 'top_short_squeeze',
    strategy_name: '高檔軋空 (券資比激增)',
    direction: 'buy',
    signal_strength: 'moderate',
    details: { close: 125.0, foreign_buy: 8500, trust_buy: 0, margin_change: -1200 },
    filters_passed: ['high_short_ratio'],
    suggested_action: '散戶做空遭法人硬軋，短線動能極強，注意追高風險'
  },
  {
    id: 'alert-20260810-6274-001',
    timestamp: '2026-08-10T14:30:00+08:00',
    stock_id: '6274',
    stock_name: '台燿',
    market: 'mid_small',
    strategy_id: 'top_distribution',
    strategy_name: '高檔出貨 (法人倒貨、融資暴增)',
    direction: 'sell',
    signal_strength: 'strong',
    details: { close: 175.0, foreign_buy: -3500, trust_buy: -1200, margin_change: 2500 },
    filters_passed: ['trend_ma20_breakdown'],
    suggested_action: '主力高檔倒貨給散戶，極度危險，請儘速停損或避開'
  }
];

const STRATEGY_META = {
  foreign_core:      { label: '外資大型波段 (核心)', icon: 'pi-chart-line',          color: 'blue' },
  trust_satellite:   { label: '投信中小作帳 (衛星)', icon: 'pi-bolt',               color: 'amber' },
  bottom_washout:    { label: '底部換手 (洗盤)',      icon: 'pi-arrow-right-arrow-left', color: 'green' },
  top_short_squeeze: { label: '高檔軋空 (暴走)',      icon: 'pi-angle-double-up',    color: 'red' },
  top_distribution:  { label: '高檔出貨 (崩盤前)',    icon: 'pi-angle-double-down',  color: 'red' }
};

const DIRECTION_META = {
  buy:  { label: '多方/買進', icon: '▲', bull: true  },
  sell: { label: '空方/警示', icon: '▼', bull: false }
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
