// =====================================================
// Shared JS — MyStock 極端抄底策略警示 Prototype
// =====================================================

// ── Theme ─────────────────────────────────────────
(function () {
  const saved = localStorage.getItem('proto-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
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
  icon.className = document.documentElement.getAttribute('data-theme') === 'dark' ? 'pi pi-sun' : 'pi pi-moon';
}
document.addEventListener('DOMContentLoaded', syncThemeIcon);

// ── Module state ───────────────────────────────────
// dormant | awakened | kill
let MODULE_STATE = 'awakened'; // Demo: show awakened state

function getModuleState() { return MODULE_STATE; }
function setModuleState(s) {
  MODULE_STATE = s;
  renderModuleStatus();
}

function renderModuleStatus() {
  const els = document.querySelectorAll('[data-module-status]');
  const stateLabel = { dormant: '🟢 休眠中', awakened: '🔴 已喚醒 · 掃描中', kill: '⚫ Kill Switch 啟動' };
  const stateClass = { dormant: 'dormant', awakened: 'awakened', kill: 'kill' };
  els.forEach(el => {
    el.className = 'module-status ' + (stateClass[MODULE_STATE] || 'dormant');
    el.innerHTML = `<span class="module-status-dot"></span>${stateLabel[MODULE_STATE] || ''}`;
  });
  // Add crisis bar to topbar if awakened
  const topbar = document.querySelector('.topbar');
  if (topbar) {
    topbar.classList.toggle('crisis-active', MODULE_STATE === 'awakened');
  }
}

// ── Utility ────────────────────────────────────────
function formatDate(ts) {
  const d = new Date(ts);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function formatTime(ts) {
  const d = new Date(ts);
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}

// ── Mock data: Crisis Alerts ───────────────────────
const CRISIS_ALERTS = [
  {
    id: 'crisis-20260811-2330-001',
    timestamp: '2026-08-11T13:30:00+08:00',
    stock_id: '2330',
    stock_name: '台積電',
    market: 'tw',
    module: 'extreme_risk',
    strategy_id: 'crisis_rebound',
    scenario: 'limit_down_opened',
    scenario_label: '情境 A：跌停打開爆量',
    scenario_icon: '💥',
    risk_level: 'CRITICAL',
    signal_strength: 'strong',
    market_context: {
      index_change_percent: -4.2,
      index_bias_20: -9.5,
      awakened_by: 'market_crash',
      awakened_label: '大盤暴跌 ≥ 3%',
    },
    details: {
      close: 850.0,
      limit_down_price: 832.0,
      low: 832.0,
      high: 865.0,
      bias_20_percent: -12.3,
      bias_60_percent: -18.7,
      volume: 125000,
      volume_ratio: 3.2,
      margin_change_3d_percent: -6.5,
      institutional_net_buy: 15000,
    },
    guardrails_passed: ['universe_filter', 'liquidity_check'],
    stop_loss: { price_stop: 832.0, time_stop_days: 3, time_stop_target_percent: 3.0 },
    capital: { max_order_ntd: 30000, order_type: '零股委託' },
    suggested_action: '跌停打開爆量承接，限零股小額測試。停損 T 日最低價 $832。'
  },
  {
    id: 'crisis-20260811-0050-001',
    timestamp: '2026-08-11T13:30:00+08:00',
    stock_id: '0050',
    stock_name: '元大台灣50',
    market: 'tw',
    module: 'extreme_risk',
    strategy_id: 'crisis_rebound',
    scenario: 'extreme_negative_bias',
    scenario_label: '情境 B：極端負乖離',
    scenario_icon: '📉',
    risk_level: 'CRITICAL',
    signal_strength: 'moderate',
    market_context: {
      index_change_percent: -4.2,
      index_bias_20: -9.5,
      awakened_by: 'market_crash',
      awakened_label: '大盤暴跌 ≥ 3%',
    },
    details: {
      close: 132.5,
      limit_down_price: null,
      low: 130.2,
      high: 135.8,
      bias_20_percent: -26.1,
      bias_60_percent: -31.4,
      volume: 85000,
      volume_ratio: 1.8,
      margin_change_3d_percent: null,
      institutional_net_buy: 8000,
    },
    guardrails_passed: ['universe_filter', 'liquidity_check'],
    stop_loss: { price_stop: 130.2, time_stop_days: 3, time_stop_target_percent: 3.0 },
    capital: { max_order_ntd: 30000, order_type: '零股委託' },
    suggested_action: '月線乖離 -26%、季線乖離 -31%，歷史極端超賣，小額分批觀察。'
  },
  {
    id: 'crisis-20260810-2317-001',
    timestamp: '2026-08-10T13:30:00+08:00',
    stock_id: '2317',
    stock_name: '鴻海',
    market: 'tw',
    module: 'extreme_risk',
    strategy_id: 'crisis_rebound',
    scenario: 'margin_call_washout',
    scenario_label: '情境 C：融資斷頭清洗',
    scenario_icon: '🏦',
    risk_level: 'CRITICAL',
    signal_strength: 'moderate',
    market_context: {
      index_change_percent: -3.1,
      index_bias_20: -8.2,
      awakened_by: 'market_extreme_bias',
      awakened_label: '大盤 20MA 負乖離 ≥ 8%',
    },
    details: {
      close: 178.0,
      limit_down_price: null,
      low: 174.5,
      high: 181.0,
      bias_20_percent: -16.8,
      bias_60_percent: -20.3,
      volume: 42000,
      volume_ratio: 1.6,
      margin_change_3d_percent: -7.2,
      institutional_net_buy: 5500,
    },
    guardrails_passed: ['universe_filter', 'liquidity_check'],
    stop_loss: { price_stop: 174.5, time_stop_days: 3, time_stop_target_percent: 3.0 },
    capital: { max_order_ntd: 30000, order_type: '零股委託' },
    suggested_action: '融資連 3 天大幅減少，外資今日轉買超，散戶籌碼清洗中。'
  },
  {
    id: 'crisis-20260809-2454-rejected',
    timestamp: '2026-08-09T13:30:00+08:00',
    stock_id: '2454',
    stock_name: '聯發科',
    market: 'tw',
    module: 'extreme_risk',
    strategy_id: 'crisis_rebound',
    scenario: 'limit_down_opened',
    scenario_label: '情境 A：跌停打開爆量',
    scenario_icon: '💥',
    risk_level: 'CRITICAL',
    signal_strength: 'weak',
    rejected: true,
    rejected_reason: '流動性不足：成交量 0.8× 均量，未達 2× 門檻',
    market_context: {
      index_change_percent: -3.5,
      index_bias_20: -7.1,
      awakened_by: 'market_crash',
      awakened_label: '大盤暴跌 ≥ 3%',
    },
    details: {
      close: 860.0,
      limit_down_price: 855.0,
      low: 855.0,
      high: 870.0,
      bias_20_percent: -18.0,
      bias_60_percent: -22.5,
      volume: 12000,
      volume_ratio: 0.8,
      margin_change_3d_percent: -4.1,
      institutional_net_buy: 0,
    },
    guardrails_passed: ['universe_filter'],
    guardrails_failed: ['liquidity_check'],
    stop_loss: null,
    capital: null,
    suggested_action: null,
  }
];

// ── Mock: Universe whitelist ───────────────────────
const UNIVERSE = [
  { symbol: '2330', name: '台積電',      large_cap: true,  constituent: true  },
  { symbol: '2317', name: '鴻海',        large_cap: true,  constituent: true  },
  { symbol: '0050', name: '元大台灣50',  large_cap: true,  constituent: true  },
  { symbol: '0056', name: '元大高股息',  large_cap: true,  constituent: false },
  { symbol: '2454', name: '聯發科',      large_cap: true,  constituent: true  },
  { symbol: '2881', name: '富邦金',      large_cap: true,  constituent: true  },
  { symbol: '2882', name: '國泰金',      large_cap: true,  constituent: true  },
  { symbol: '2891', name: '中信金',      large_cap: true,  constituent: true  },
  { symbol: '3711', name: '日月光投控',  large_cap: true,  constituent: true  },
  { symbol: '006208', name: '富邦台50',  large_cap: true,  constituent: false },
];

// ── Mock: Module status ────────────────────────────
const MODULE_STATUS_DATA = {
  module_state: 'awakened',
  last_awakened_at: '2026-08-11T09:01:00+08:00',
  awakened_reason: 'market_crash',
  awakened_reason_label: '大盤跌幅 -4.2%，觸發 ≥ 3% 門檻',
  universe_size: 10,
  capital_used_percent: 0.0,
  capital_limit_percent: 5.0,
  kill_switch_active: false,
  today_orders: 0,
  execution_mode: 'notify_only',
  market_context: {
    index_change_percent: -4.2,
    index_bias_20: -9.5,
  }
};

// ── Kill switch state ──────────────────────────────
let killSwitchActive = false;

function activateKillSwitch() {
  if (killSwitchActive) {
    deactivateKillSwitch();
    return;
  }
  const confirmed = confirm('⚠️ 確定要啟動緊急停止（Kill Switch）？\n\n啟動後，所有極端抄底策略的下單權限將立即切斷，模組轉為純通知模式。\n\n此操作需手動解除。');
  if (!confirmed) return;
  killSwitchActive = true;
  MODULE_STATE = 'kill';
  renderModuleStatus();
  document.body.classList.add('kill-switch-active');
  const killBars = document.querySelectorAll('.kill-switch-bar');
  killBars.forEach(b => b.classList.add('visible'));
  const killBtns = document.querySelectorAll('[data-kill-btn]');
  killBtns.forEach(b => { b.textContent = '⚫ Kill Switch 已啟動 — 點擊解除'; b.classList.add('btn-kill-active'); });
}
function deactivateKillSwitch() {
  const confirmed = confirm('確定要解除 Kill Switch 並恢復下單權限？');
  if (!confirmed) return;
  killSwitchActive = false;
  MODULE_STATE = 'awakened';
  renderModuleStatus();
  document.body.classList.remove('kill-switch-active');
  const killBars = document.querySelectorAll('.kill-switch-bar');
  killBars.forEach(b => b.classList.remove('visible'));
  const killBtns = document.querySelectorAll('[data-kill-btn]');
  killBtns.forEach(b => { b.textContent = '☠ 緊急停止 Kill Switch'; b.classList.remove('btn-kill-active'); });
}
