// =====================================================
// Shared JS — MyStock 整合訊息通知平台 Prototype
// 所有資料皆為 Mock，僅供 UI/流程評估
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
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  icon.className = isDark ? 'pi pi-sun' : 'pi pi-moon';
}

// ── Topbar ────────────────────────────────────────
const ADMIN_NAV = [
  { key: 'channels',      href: 'channels.html',        icon: 'pi-send',            label: '管道設定' },
  { key: 'recipients',    href: 'recipients.html',      icon: 'pi-users',           label: '收件人' },
  { key: 'subscriptions', href: 'subscriptions.html',   icon: 'pi-filter',          label: '訂閱規則' },
  { key: 'preview',       href: 'message-preview.html', icon: 'pi-comment',         label: '訊息外觀' },
  { key: 'logs',          href: 'logs.html',            icon: 'pi-history',         label: '發送紀錄' }
];

/**
 * mode: 'admin' → 管理端導覽列；'self' → 收件人自助頁（無管理導覽）
 */
function renderTopbar(activeKey, mode = 'admin') {
  const host = document.getElementById('topbar-host');
  if (!host) return;

  const nav = mode === 'admin'
    ? `<nav class="topbar-nav">${ADMIN_NAV.map(n => `
        <a href="${n.href}" class="nav-link ${n.key === activeKey ? 'active' : ''}">
          <i class="pi ${n.icon}"></i>${n.label}
        </a>`).join('')}</nav>`
    : '';

  const sub = mode === 'admin' ? '整合訊息通知平台' : '我的通知設定';
  const home = mode === 'admin' ? 'index.html' : '#';

  host.innerHTML = `
    <header class="topbar">
      <div class="topbar-brand">
        <a href="${home}" class="brand-icon" style="text-decoration:none"><i class="pi pi-bell"></i></a>
        <span class="brand-name">MyStock</span>
        <span class="brand-sep">|</span>
        <span class="brand-sub">${sub}</span>
      </div>
      <div class="topbar-actions">
        ${nav}
        <button class="icon-btn" onclick="toggleTheme()" title="切換深色模式">
          <i class="pi pi-moon" id="theme-icon"></i>
        </button>
      </div>
    </header>`;
  syncThemeIcon();
}

// ── Toast ─────────────────────────────────────────
function toast(msg, icon = 'pi-check-circle') {
  let host = document.querySelector('.toast-host');
  if (!host) {
    host = document.createElement('div');
    host.className = 'toast-host';
    document.body.appendChild(host);
  }
  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = `<i class="pi ${icon}"></i>${msg}`;
  host.appendChild(el);
  setTimeout(() => el.remove(), 2600);
}

// ── Modal ─────────────────────────────────────────
function openModal(id) { document.getElementById(id)?.classList.add('open'); }
function closeModal(id) { document.getElementById(id)?.classList.remove('open'); }

document.addEventListener('click', (e) => {
  if (e.target.classList?.contains('modal-backdrop')) e.target.classList.remove('open');
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') document.querySelectorAll('.modal-backdrop.open').forEach(m => m.classList.remove('open'));
});

// =====================================================
// Mock Data
// =====================================================

// ── 管道 ──────────────────────────────────────────
const MOCK_CHANNELS = [
  {
    code: 'email',
    name: 'Email',
    icon: 'pi-envelope',
    status: 'enabled',
    statusLabel: '正常',
    desc: '以個人信箱寄送（已確認決策 Q-01）',
    settings: [
      { label: '寄件伺服器', value: 'smtp.example.com : 587' },
      { label: '寄件人', value: 'MyStock 通知 <jackson210@example.com>' },
      { label: '認證密碼', value: '••••••••••••', masked: true },
      { label: '主旨前綴', value: '【MyStock】' }
    ],
    quota: { used: 42, budget: 350, limit: 500 },
    note: '個人信箱有每日寄送量限制，達預算時自動改走 Telegram'
  },
  {
    code: 'telegram',
    name: 'Telegram',
    icon: 'pi-send',
    status: 'enabled',
    statusLabel: '正常',
    desc: '即時推播，適合單筆訊號',
    settings: [
      { label: '機器人名稱', value: '@MyStockAlertBot' },
      { label: '機器人憑證', value: '••••••••••••••••', masked: true },
      { label: '已綁定對話', value: '3 個' }
    ],
    quota: null,
    note: '使用者需先與機器人對話並完成綁定才能收訊'
  },
  {
    code: 'line',
    name: 'LINE',
    icon: 'pi-comments',
    status: 'future',
    statusLabel: '未啟用',
    desc: '未來擴充：僅需新增轉接單元與模板，路由與政策零改動',
    settings: [],
    quota: null,
    note: '本階段不開發，架構已預留'
  },
  {
    code: 'discord',
    name: 'Discord / Slack / Webhook',
    icon: 'pi-hashtag',
    status: 'future',
    statusLabel: '未啟用',
    desc: '未來擴充',
    settings: [],
    quota: null,
    note: '本階段不開發，架構已預留'
  }
];

// ── 收件人與端點 ──────────────────────────────────
const MOCK_RECIPIENTS = [
  {
    code: 'rcp-001',
    name: 'Jackson（我）',
    groups: ['本人'],
    status: 'active',
    endpoints: [
      {
        code: 'ep-001', channel: 'email', address: 'jackson210@gmail.com',
        verify: 'verified', mode: 'digest', quiet: '22:00–08:00', limit: 30,
        strengths: ['strong', 'moderate'], markets: ['tw', 'us'], paused: false
      },
      {
        code: 'ep-002', channel: 'telegram', address: '個人對話 · @jackson',
        verify: 'verified', mode: 'realtime', quiet: '無', limit: 50,
        strengths: ['strong', 'moderate'], markets: ['tw', 'us'], paused: false
      }
    ]
  },
  {
    code: 'rcp-002',
    name: '家人 A',
    groups: ['家人'],
    status: 'active',
    endpoints: [
      {
        code: 'ep-003', channel: 'email', address: 'familyA@example.com',
        verify: 'verified', mode: 'digest', quiet: '21:00–09:00', limit: 10,
        strengths: ['strong'], markets: ['tw'], paused: false
      },
      {
        code: 'ep-004', channel: 'telegram', address: '家庭群組 · MyStock 通知',
        verify: 'verified', mode: 'critical_only', quiet: '22:00–08:00', limit: 20,
        strengths: ['strong'], markets: ['tw'], paused: true, pauseUntil: '2026-08-20'
      }
    ]
  },
  {
    code: 'rcp-003',
    name: '同好 B',
    groups: ['同好'],
    status: 'active',
    endpoints: [
      {
        code: 'ep-005', channel: 'email', address: 'friendB@example.com',
        verify: 'pending', mode: 'digest', quiet: '22:00–08:00', limit: 30,
        strengths: ['strong', 'moderate'], markets: ['tw', 'us'], paused: false
      }
    ]
  }
];

// ── 訂閱規則 ──────────────────────────────────────
const MOCK_SUBSCRIPTIONS = [
  {
    code: 'sub-001',
    name: '本人：全部訊號',
    enabled: true,
    eventType: 'ALERT_SIGNAL',
    filters: { markets: ['tw', 'us'], strengths: ['strong', 'moderate'], signals: ['BUY', 'SELL'], categories: ['technical', 'chip', 'fundamental'], symbols: null },
    target: { type: 'group', label: '本人' }
  },
  {
    code: 'sub-002',
    name: '家人：台股強訊號',
    enabled: true,
    eventType: 'ALERT_SIGNAL',
    filters: { markets: ['tw'], strengths: ['strong'], signals: ['BUY', 'SELL'], categories: ['technical', 'chip'], symbols: null },
    target: { type: 'group', label: '家人' }
  },
  {
    code: 'sub-003',
    name: '自選股專屬警示',
    enabled: true,
    eventType: 'ALERT_SIGNAL',
    filters: { markets: ['tw'], strengths: ['strong', 'moderate', 'weak'], signals: ['SELL'], categories: ['technical'], symbols: ['2330', '2317', '0050'] },
    target: { type: 'recipient', label: 'Jackson（我）' }
  },
  {
    code: 'sub-004',
    name: '每日摘要',
    enabled: true,
    eventType: 'ALERT_DIGEST',
    filters: { markets: ['tw', 'us'], strengths: null, signals: null, categories: null, symbols: null },
    target: { type: 'group', label: '全部收件人' }
  },
  {
    code: 'sub-005',
    name: '系統異常告警',
    enabled: true,
    eventType: 'SYSTEM_HEALTH',
    filters: { markets: null, strengths: null, signals: null, categories: null, symbols: null },
    target: { type: 'recipient', label: 'Jackson（我）' }
  },
  {
    code: 'sub-006',
    name: '美股訊號（暫停中）',
    enabled: false,
    eventType: 'ALERT_SIGNAL',
    filters: { markets: ['us'], strengths: ['strong'], signals: ['BUY', 'SELL'], categories: ['technical'], symbols: null },
    target: { type: 'group', label: '同好' }
  }
];

// ── 警示訊號（沿用既有 alerts 資料形狀） ──────────
const MOCK_ALERTS = [
  {
    id: 'alert-20260814-2330-001', stock_id: '2330', stock_name: '台積電', market: 'tw',
    strategy_id: 'price_cross_ma', strategy_name: '收盤價跌破關鍵均線', category: 'technical',
    direction: 'cross_under_MA20', signal_type: 'SELL', signal_strength: 'moderate',
    trade_date: '2026-08-14',
    details: { close: 1085, ma_period: 20, ma_value: 1102.5, bias_percent: -1.59 },
    filters_passed: ['volume_confirm'],
    suggested_action: '跌破 MA20，可留意減碼或設定停損'
  },
  {
    id: 'alert-20260814-2317-001', stock_id: '2317', stock_name: '鴻海', market: 'tw',
    strategy_id: 'ma_golden_death_cross', strategy_name: '均線死亡交叉', category: 'technical',
    direction: 'death_cross_5_20', signal_type: 'SELL', signal_strength: 'strong',
    trade_date: '2026-08-14',
    details: { close: 205, ma_period: 20, ma_value: 211.3, bias_percent: -2.98 },
    filters_passed: ['volume_confirm', 'candlestick_confirm'],
    suggested_action: 'MA5 下穿 MA20，短線轉弱，建議減碼'
  },
  {
    id: 'alert-20260814-1101-001', stock_id: '1101', stock_name: '台泥', market: 'tw',
    strategy_id: 'chip_distribution_top', strategy_name: '高檔出貨', category: 'chip',
    direction: 'distribution', signal_type: 'SELL', signal_strength: 'moderate',
    trade_date: '2026-08-14',
    details: { close: 32.5, foreign_net: -8200, margin_change: 3100 },
    filters_passed: ['institutional_sell'],
    suggested_action: '法人連 3 賣且融資增，籌碼轉壞'
  },
  {
    id: 'alert-20260814-2884-001', stock_id: '2884', stock_name: '玉山金', market: 'tw',
    strategy_id: 'price_cross_ma', strategy_name: '收盤價突破關鍵均線', category: 'technical',
    direction: 'cross_above_MA60', signal_type: 'BUY', signal_strength: 'moderate',
    trade_date: '2026-08-14',
    details: { close: 28.4, ma_period: 60, ma_value: 27.9, bias_percent: 1.79 },
    filters_passed: ['volume_confirm'],
    suggested_action: '站上 MA60，可納入多頭觀察清單'
  },
  {
    id: 'alert-20260814-0050-001', stock_id: '0050', stock_name: '元大台灣50', market: 'tw',
    strategy_id: 'ma_alignment', strategy_name: '均線多頭排列', category: 'technical',
    direction: 'bull_alignment', signal_type: 'BUY', signal_strength: 'weak',
    trade_date: '2026-08-14',
    details: { close: 107.8, ma_period: 20, ma_value: 106.1, bias_percent: 1.6 },
    filters_passed: [],
    suggested_action: '均線多頭排列成形，趨勢偏多'
  },
  {
    id: 'alert-20260814-NVDA-001', stock_id: 'NVDA', stock_name: 'NVIDIA', market: 'us',
    strategy_id: 'extreme_bias', strategy_name: '乖離率過大警示', category: 'technical',
    direction: 'bias_high', signal_type: 'WARNING', signal_strength: 'strong',
    trade_date: '2026-08-14',
    details: { close: 182.4, ma_period: 20, ma_value: 158.2, bias_percent: 15.3 },
    filters_passed: ['volume_confirm'],
    suggested_action: '正乖離過大，注意追高風險'
  },
  {
    id: 'alert-20260814-TSLA-001', stock_id: 'TSLA', stock_name: 'Tesla', market: 'us',
    strategy_id: 'ma_squeeze_breakout', strategy_name: '均線糾結突破', category: 'technical',
    direction: 'squeeze_break_up', signal_type: 'BUY', signal_strength: 'moderate',
    trade_date: '2026-08-14',
    details: { close: 342.1, ma_period: 20, ma_value: 335.8, bias_percent: 1.88 },
    filters_passed: ['volume_confirm'],
    suggested_action: '均線糾結後向上突破，動能轉強'
  },
  {
    id: 'alert-20260814-1760-001', stock_id: '1760', stock_name: '寶齡富錦', market: 'tw',
    strategy_id: 'fundamental_revenue_decline', strategy_name: '營收連續衰退出場', category: 'fundamental',
    direction: 'revenue_decline', signal_type: 'SELL', signal_strength: 'weak',
    trade_date: '2026-08-14',
    details: { close: 88.3, yoy: -12.4, months: 3 },
    filters_passed: [],
    suggested_action: '營收連 3 月年減，基本面轉弱'
  }
];

// ── 發送紀錄 ──────────────────────────────────────
const MOCK_LOGS = [
  { code: 'msg-8841', time: '2026-08-14 14:32', event: 'ALERT_SIGNAL', title: '2317 鴻海 均線死亡交叉', recipient: 'Jackson（我）', channel: 'telegram', status: 'sent', attempts: 1, reason: '' },
  { code: 'msg-8840', time: '2026-08-14 14:32', event: 'ALERT_SIGNAL', title: '2317 鴻海 均線死亡交叉', recipient: '家人 A', channel: 'email', status: 'digested', attempts: 0, reason: '端點為摘要模式，併入 15:00 摘要' },
  { code: 'msg-8839', time: '2026-08-14 14:32', event: 'ALERT_SIGNAL', title: '2330 台積電 跌破 MA20', recipient: 'Jackson（我）', channel: 'telegram', status: 'sent', attempts: 1, reason: '' },
  { code: 'msg-8838', time: '2026-08-14 14:32', event: 'ALERT_SIGNAL', title: '1101 台泥 高檔出貨', recipient: '家人 A', channel: 'telegram', status: 'deferred', attempts: 0, reason: '端點暫停中（至 2026-08-20）' },
  { code: 'msg-8837', time: '2026-08-14 14:32', event: 'ALERT_SIGNAL', title: '0050 均線多頭排列', recipient: 'Jackson（我）', channel: 'telegram', status: 'throttled', attempts: 0, reason: 'weak 訊號不即時推送，改入摘要' },
  { code: 'msg-8836', time: '2026-08-14 14:31', event: 'ALERT_SIGNAL', title: '2330 台積電 跌破 MA20', recipient: '同好 B', channel: 'email', status: 'dead', attempts: 3, reason: '收件位址無效（550 mailbox not found），端點已自動停用' },
  { code: 'msg-8835', time: '2026-08-14 14:31', event: 'ALERT_SIGNAL', title: '2884 玉山金 突破 MA60', recipient: 'Jackson（我）', channel: 'telegram', status: 'sent', attempts: 1, reason: '' },
  { code: 'msg-8834', time: '2026-08-14 14:30', event: 'ALERT_SIGNAL', title: '2330 台積電 跌破 MA20', recipient: 'Jackson（我）', channel: 'telegram', status: 'skipped_duplicate', attempts: 0, reason: '同一事件已送過此端點（重跑掃描）' },
  { code: 'msg-8833', time: '2026-08-14 06:02', event: 'FETCH_FAILED', title: '美股抓取部分失敗（2 檔）', recipient: 'Jackson（我）', channel: 'telegram', status: 'sent', attempts: 2, reason: '第 1 次逾時，重試成功' },
  { code: 'msg-8832', time: '2026-08-13 15:00', event: 'ALERT_DIGEST', title: '2026-08-13 台股警示摘要', recipient: '家人 A', channel: 'email', status: 'sent', attempts: 1, reason: '' },
  { code: 'msg-8831', time: '2026-08-13 15:00', event: 'ALERT_DIGEST', title: '2026-08-13 台股警示摘要', recipient: 'Jackson（我）', channel: 'email', status: 'sent', attempts: 1, reason: '' },
  { code: 'msg-8830', time: '2026-08-13 14:35', event: 'ALERT_SIGNAL', title: '2603 長榮 底部換手', recipient: '家人 A', channel: 'telegram', status: 'failed', attempts: 2, reason: '對方服務暫時不可用，30 分鐘後重試' }
];

// ── Meta / 對照表 ─────────────────────────────────
const CHANNEL_META = {
  email:    { label: 'Email',    icon: 'pi-envelope', tag: 'tag-email' },
  telegram: { label: 'Telegram', icon: 'pi-send',     tag: 'tag-telegram' },
  line:     { label: 'LINE',     icon: 'pi-comments', tag: 'tag-future' }
};

const STATUS_META = {
  sent:              { label: '已送達',   tag: 'tag-ok',    icon: 'pi-check-circle' },
  failed:            { label: '失敗待重試', tag: 'tag-warn',  icon: 'pi-replay' },
  dead:              { label: '最終失敗', tag: 'tag-err',   icon: 'pi-times-circle' },
  digested:          { label: '併入摘要', tag: 'tag-neu',   icon: 'pi-inbox' },
  throttled:         { label: '超量轉摘要', tag: 'tag-neu', icon: 'pi-filter-slash' },
  deferred:          { label: '延後',     tag: 'tag-neu',   icon: 'pi-clock' },
  skipped_duplicate: { label: '重複略過', tag: 'tag-neu',   icon: 'pi-ban' },
  pending:           { label: '待發送',   tag: 'tag-neu',   icon: 'pi-hourglass' }
};

const STRENGTH_META = {
  strong:   { label: '強', tag: 'tag-strong' },
  moderate: { label: '中', tag: 'tag-moderate' },
  weak:     { label: '弱', tag: 'tag-weak' }
};

const SIGNAL_META = {
  BUY:     { label: '買進', tag: 'tag-bull', icon: '▲' },
  SELL:    { label: '賣出', tag: 'tag-bear', icon: '▼' },
  WARNING: { label: '警告', tag: 'tag-warn', icon: '!' }
};

const MARKET_META = {
  tw: { label: '台股', tag: 'tag-tw' },
  us: { label: '美股', tag: 'tag-us' }
};

const CATEGORY_META = {
  technical:   { label: '技術面' },
  chip:        { label: '籌碼面' },
  fundamental: { label: '基本面' }
};

const EVENT_META = {
  ALERT_SIGNAL:    { label: '策略警示訊號', severity: 'info' },
  ALERT_DIGEST:    { label: '每日警示摘要', severity: 'info' },
  FETCH_COMPLETED: { label: '每日抓取完成', severity: 'info' },
  FETCH_FAILED:    { label: '抓取失敗',     severity: 'critical' },
  SYSTEM_HEALTH:   { label: '系統異常',     severity: 'critical' }
};

// ── Utils ─────────────────────────────────────────
function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function tagHtml(cls, text) { return `<span class="tag ${cls}">${esc(text)}</span>`; }

document.addEventListener('DOMContentLoaded', syncThemeIcon);
