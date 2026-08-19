// =====================================================
// Shared JS — MyStock 股價相對低點選股 Prototype
// 對應規格：docs/13.選股功能/股價相對低點.md（v2.0）
// 全部為 Mock 資料，僅供 UI 原型評估
// =====================================================

// ── Theme ─────────────────────────────────────────
(function () {
  const saved = localStorage.getItem('proto-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  document.addEventListener('DOMContentLoaded', syncThemeIcon);
})();

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('proto-theme', next);
  syncThemeIcon();
  document.dispatchEvent(new CustomEvent('proto-theme-change', { detail: { theme: next } }));
}

function syncThemeIcon() {
  const icon = document.getElementById('theme-icon');
  if (!icon) return;
  icon.className = isDark() ? 'pi pi-sun' : 'pi pi-moon';
}

function isDark() {
  return document.documentElement.getAttribute('data-theme') === 'dark';
}

// ── 條件定義（規格 §4.2 C1~C6）────────────────────
const CONDITION_DEFS = [
  {
    code: 'C1',
    key: 'valuation',
    name: '估值低檔',
    icon: 'pi-percentage',
    desc: '本益比、股價淨值比與殖利率同時進入價值區間，提供安全邊際。',
    spec: '§4.2 C1',
    source: 'ctx.valuation（當日 point-in-time）',
    params: ['pe_max', 'pe_min', 'pb_max', 'dividend_yield_min'],
    thresholdText: (p) => `PE ≤ ${p.pe_max}｜PB ≤ ${p.pb_max}｜殖利率 ≥ ${p.dividend_yield_min}%`
  },
  {
    code: 'C2',
    key: 'fundamental',
    name: '基本面守衛（避開價值陷阱）',
    icon: 'pi-shield',
    desc: '近 N 個「已公開」月份營收 YoY 皆不為負；月營收次月 11 日起才可見（point-in-time）。',
    spec: '§4.2 C2',
    source: 'ctx.revenue_yoy ＋ ctx.revenue',
    params: ['revenue_yoy_min', 'revenue_consecutive_months'],
    thresholdText: (p) => `連續 ${p.revenue_consecutive_months} 個月 YoY ≥ ${p.revenue_yoy_min}%`
  },
  {
    code: 'C3',
    key: 'oversold',
    name: '超跌狀態（季線負乖離）',
    icon: 'pi-arrow-down-right',
    desc: '近 N 日內曾出現 BIAS60 低於門檻。狀態式判斷，非既有 bias 條件的「跨越當天」語意。',
    spec: '§4.2 C3',
    source: 'ctx.bias[60]',
    params: ['bias_ma_period', 'bias_max', 'bias_lookback_days'],
    thresholdText: (p) => `近 ${p.bias_lookback_days} 日內 BIAS${p.bias_ma_period} ≤ ${p.bias_max}%`
  },
  {
    code: 'C4',
    key: 'momentum',
    name: '動能超賣（KD）',
    icon: 'pi-chart-line',
    desc: '近 N 日內 K 值曾進入超賣區。取代 v1.0 的 RSI —— 本專案無 RSI 指標（ADR-RL-02）。',
    spec: '§4.2 C4',
    source: 'ctx.kd[(9,3,3)]',
    params: ['kd_oversold', 'kd_lookback_days'],
    thresholdText: (p) => `近 ${p.kd_lookback_days} 日內 K ≤ ${p.kd_oversold}`
  },
  {
    code: 'C5',
    key: 'chip',
    name: '籌碼洗盤',
    icon: 'pi-users',
    desc: '融資餘額近 N 日減幅達門檻（浮額清洗），且外資或投信近 5 日至少 3 日淨買超。',
    spec: '§4.2 C5',
    source: 'indicators/chip.change_pct()、net_buy_days()',
    params: ['margin_change_window', 'margin_change_max_pct', 'institutional_window', 'institutional_min_buy_days'],
    thresholdText: (p) => `融資 ${p.margin_change_window} 日 ≤ ${p.margin_change_max_pct}%｜法人 ${p.institutional_window} 日買超 ≥ ${p.institutional_min_buy_days} 日`
  },
  {
    code: 'C6',
    key: 'confirm',
    name: '右側止跌確認',
    icon: 'pi-check-circle',
    desc: '收盤價站回月線且量能放大。必要條件，不得降級為濾網（ADR-RL-03）。',
    spec: '§4.2 C6',
    source: 'ctx.ma[20]、ctx.volumes、ctx.volume_ma',
    params: ['above_ma_period', 'volume_multiple'],
    thresholdText: (p) => `收盤 ≥ MA${p.above_ma_period} 且 量 ≥ ${p.volume_multiple}× 5日均量`
  }
];

// ── 預設門檻（規格 §7 YAML 範本）──────────────────
const DEFAULT_PARAMS = {
  pe_max: 15.0,
  pe_min: 0.1,
  pb_max: 1.5,
  dividend_yield_min: 4.0,
  revenue_yoy_min: 0.0,
  revenue_consecutive_months: 2,
  bias_ma_period: 60,
  bias_max: -15.0,
  bias_lookback_days: 10,
  kd_oversold: 20,
  kd_lookback_days: 10,
  margin_change_window: 10,
  margin_change_max_pct: -5.0,
  institutional_window: 5,
  institutional_min_buy_days: 3,
  above_ma_period: 20,
  volume_multiple: 1.5,
  // 名單語意（§9）
  max_picks_per_day: 10,
  sort_by: 'dividend_yield',
  cooldown_days: 20,
  universe_tier: 'top500'
};

// ── 策略清單（現行 4 檔 ＋ 本規格新增）──────────────
const STRATEGIES = [
  { id: 'pick_valuation_low_pe', name: '低本益比高殖利率精選', icon: 'pi-percentage', status: 'live' },
  { id: 'pick_revenue_growth_momentum', name: '營收高成長動能精選', icon: 'pi-bolt', status: 'live' },
  { id: 'pick_chip_institutional_resonance', name: '法人籌碼共振精選', icon: 'pi-users', status: 'live' },
  { id: 'pick_multi_factor_resonance', name: '多因子共振旗艦精選', icon: 'pi-star-fill', status: 'live' },
  {
    id: 'pick_relative_low_zone',
    name: '相對低點承接精選',
    icon: 'pi-arrow-down-right',
    status: 'planned',
    description: '低估值（PE/PB/殖利率）＋ 營收未衰退 ＋ 季線極端負乖離 ＋ KD 超賣 ＋ 融資洗盤法人低接 ＋ 帶量站回月線，六項條件全部 AND 成立才入選。',
    scope: 'universe',
    universe_tier: 'top500',
    max_picks_per_day: 10,
    cooldown_days: 20,
    sort_by: 'dividend_yield'
  }
];

const TRADE_DATE = '2026-08-20';

// ── Mock 入選名單（details 欄位對照規格 §5.2）────────
const MOCK_PICKS = [
  {
    stock_id: '2603', stock_name: '長榮', market: 'tw', trade_date: TRADE_DATE,
    strategy_id: 'pick_relative_low_zone', direction: 'pick_relative_low',
    signal_type: 'BUY', signal_strength: 'strong', category: 'stock_picking',
    filters_passed: ['institutional_buy'],
    industry: '航運',
    details: {
      close: 168.5, pe_ratio: 6.8, pb_ratio: 1.12, dividend_yield: 7.24,
      yoy_percent: 3.6, visible_month: '2026-07',
      bias_percent: -12.8, bias_min_in_window: -19.4, kd_k_min_in_window: 11.2,
      margin_change_pct: -9.7, foreign_buy_days: 4, trust_buy_days: 3,
      ma_period: 20, ma_value: 165.2, volume_ratio: 2.34
    }
  },
  {
    stock_id: '2002', stock_name: '中鋼', market: 'tw', trade_date: TRADE_DATE,
    strategy_id: 'pick_relative_low_zone', direction: 'pick_relative_low',
    signal_type: 'BUY', signal_strength: 'moderate', category: 'stock_picking',
    filters_passed: ['institutional_buy'],
    industry: '鋼鐵',
    details: {
      close: 21.35, pe_ratio: 14.2, pb_ratio: 0.86, dividend_yield: 5.16,
      yoy_percent: 1.2, visible_month: '2026-07',
      bias_percent: -14.1, bias_min_in_window: -17.8, kd_k_min_in_window: 14.6,
      margin_change_pct: -6.3, foreign_buy_days: 3, trust_buy_days: 1,
      ma_period: 20, ma_value: 21.02, volume_ratio: 1.82
    }
  },
  {
    stock_id: '1101', stock_name: '台泥', market: 'tw', trade_date: TRADE_DATE,
    strategy_id: 'pick_relative_low_zone', direction: 'pick_relative_low',
    signal_type: 'BUY', signal_strength: 'strong', category: 'stock_picking',
    filters_passed: ['institutional_buy'],
    industry: '水泥',
    details: {
      close: 29.8, pe_ratio: 12.9, pb_ratio: 0.94, dividend_yield: 5.03,
      yoy_percent: 6.8, visible_month: '2026-07',
      bias_percent: -13.4, bias_min_in_window: -16.2, kd_k_min_in_window: 17.9,
      margin_change_pct: -5.8, foreign_buy_days: 5, trust_buy_days: 2,
      ma_period: 20, ma_value: 29.15, volume_ratio: 1.96
    }
  },
  {
    stock_id: '2105', stock_name: '正新', market: 'tw', trade_date: TRADE_DATE,
    strategy_id: 'pick_relative_low_zone', direction: 'pick_relative_low',
    signal_type: 'BUY', signal_strength: 'moderate', category: 'stock_picking',
    filters_passed: [],
    industry: '橡膠',
    details: {
      close: 38.45, pe_ratio: 11.6, pb_ratio: 1.24, dividend_yield: 4.68,
      yoy_percent: 0.4, visible_month: '2026-07',
      bias_percent: -15.9, bias_min_in_window: -18.1, kd_k_min_in_window: 13.4,
      margin_change_pct: -7.1, foreign_buy_days: 3, trust_buy_days: 0,
      ma_period: 20, ma_value: 38.20, volume_ratio: 1.61
    }
  },
  {
    stock_id: '2884', stock_name: '玉山金', market: 'tw', trade_date: TRADE_DATE,
    strategy_id: 'pick_relative_low_zone', direction: 'pick_relative_low',
    signal_type: 'BUY', signal_strength: 'moderate', category: 'stock_picking',
    filters_passed: ['institutional_buy'],
    industry: '金融',
    details: {
      close: 26.15, pe_ratio: 11.1, pb_ratio: 1.18, dividend_yield: 4.52,
      yoy_percent: 8.9, visible_month: '2026-07',
      bias_percent: -11.7, bias_min_in_window: -15.6, kd_k_min_in_window: 18.8,
      margin_change_pct: -5.4, foreign_buy_days: 4, trust_buy_days: 1,
      ma_period: 20, ma_value: 25.88, volume_ratio: 1.54
    }
  },
  {
    stock_id: '9910', stock_name: '豐泰', market: 'tw', trade_date: TRADE_DATE,
    strategy_id: 'pick_relative_low_zone', direction: 'pick_relative_low',
    signal_type: 'BUY', signal_strength: 'weak', category: 'stock_picking',
    filters_passed: [],
    industry: '製鞋',
    details: {
      close: 112.0, pe_ratio: 14.7, pb_ratio: 1.42, dividend_yield: 4.11,
      yoy_percent: 2.1, visible_month: '2026-07',
      bias_percent: -16.4, bias_min_in_window: -21.3, kd_k_min_in_window: 9.6,
      margin_change_pct: -11.2, foreign_buy_days: 3, trust_buy_days: 0,
      ma_period: 20, ma_value: 111.5, volume_ratio: 1.52
    }
  },
  {
    stock_id: '1440', stock_name: '南紡', market: 'tw', trade_date: TRADE_DATE,
    strategy_id: 'pick_relative_low_zone', direction: 'pick_relative_low',
    signal_type: 'BUY', signal_strength: 'weak', category: 'stock_picking',
    filters_passed: [],
    industry: '紡織',
    details: {
      close: 17.9, pe_ratio: 13.3, pb_ratio: 0.79, dividend_yield: 4.36,
      yoy_percent: 0.9, visible_month: '2026-07',
      bias_percent: -12.2, bias_min_in_window: -15.1, kd_k_min_in_window: 19.4,
      margin_change_pct: -5.1, foreign_buy_days: 3, trust_buy_days: 0,
      ma_period: 20, ma_value: 17.72, volume_ratio: 1.58
    }
  }
];

// ── Mock 落選標的（示範 AND 語意與各項排除規則）────────
const MOCK_REJECTED = [
  {
    stock_id: '2330', stock_name: '台積電', industry: '半導體',
    failed: 'C1', reason: 'PE 24.6 > 15（估值未進入低檔區）',
    note: '成長股不會被本策略選出；此為 P0 絕對門檻的已知偏誤（§4.4）'
  },
  {
    stock_id: '4938', stock_name: '和碩', industry: '電子代工',
    failed: 'C2', reason: '近 2 個已公開月份營收 YoY 為 −8.4%、−12.1%',
    note: '典型「價值陷阱」：估值低是因為獲利下修，C2 守衛正確擋下（§2.1-1）'
  },
  {
    stock_id: '2317', stock_name: '鴻海', industry: '電子代工',
    failed: 'C3', reason: 'BIAS60 近 10 日最低 −4.2%，未達 −15%',
    note: '便宜但沒有超跌，不屬「相對低點」語意'
  },
  {
    stock_id: '1605', stock_name: '華新', industry: '電線電纜',
    failed: 'C5', reason: '融資 10 日變動 −1.2%，未達 −5%（浮額尚未清洗）',
    note: '散戶尚未退場，容易再破底'
  },
  {
    stock_id: '2812', stock_name: '台中銀', industry: '金融',
    failed: 'C6', reason: '收盤 15.85 仍在 MA20（16.12）之下，量能 0.9×',
    note: '左側；等帶量站回月線才算右側確認（ADR-RL-03）'
  },
  {
    stock_id: '2409', stock_name: '友達', industry: '面板',
    failed: 'C1', reason: 'PE 無值（虧損股，BWIBBU 回傳空值）',
    note: '缺值一律視為不成立，不補值（ADR-SP-08）'
  },
  {
    stock_id: '00878', stock_name: '國泰永續高股息', industry: 'ETF',
    failed: 'EXCLUDE', reason: '證券類別為 ETF，於 category=stock_picking 一律排除',
    note: 'scanner._is_chip_excluded()；ETF 永遠不會出現在本名單（§2.2-8、AC-6）'
  }
];

// ── 現有策略的名單筆數（供分頁 badge 顯示）───────────
const MOCK_COUNTS = {
  pick_valuation_low_pe: 10,
  pick_revenue_growth_momentum: 8,
  pick_chip_institutional_resonance: 6,
  pick_multi_factor_resonance: 4,
  pick_relative_low_zone: MOCK_PICKS.length
};

// ── 條件檢核（前端重現 AND 短路語意）─────────────────
function evaluateConditions(pick, params) {
  const p = params || DEFAULT_PARAMS;
  const d = pick.details;
  const results = [];
  let shortCircuited = false;

  const push = (code, ok, actual, thresh, extra) => {
    if (shortCircuited) {
      results.push({ code, state: 'skip', actual, thresh, extra });
      return;
    }
    results.push({ code, state: ok ? 'pass' : 'fail', actual, thresh, extra });
    if (!ok) shortCircuited = true;
  };

  // C1 估值（PE / PB / 殖利率）
  const c1 = d.pe_ratio != null && d.pe_ratio <= p.pe_max && d.pe_ratio >= p.pe_min
    && d.pb_ratio != null && d.pb_ratio <= p.pb_max
    && d.dividend_yield != null && d.dividend_yield >= p.dividend_yield_min;
  push('C1', c1,
    `PE ${fmt(d.pe_ratio, 1)}x｜PB ${fmt(d.pb_ratio, 2)}｜殖利率 ${fmt(d.dividend_yield, 2)}%`,
    CONDITION_DEFS[0].thresholdText(p));

  // C2 營收守衛
  const c2 = d.yoy_percent != null && d.yoy_percent >= p.revenue_yoy_min;
  push('C2', c2,
    `YoY ${fmt(d.yoy_percent, 1)}%（${d.visible_month} 已公開）`,
    CONDITION_DEFS[1].thresholdText(p));

  // C3 超跌狀態
  const c3 = d.bias_min_in_window != null && d.bias_min_in_window <= p.bias_max;
  push('C3', c3,
    `近 ${p.bias_lookback_days} 日最低 BIAS60 ${fmt(d.bias_min_in_window, 1)}%`,
    CONDITION_DEFS[2].thresholdText(p));

  // C4 KD 超賣
  const c4 = d.kd_k_min_in_window != null && d.kd_k_min_in_window <= p.kd_oversold;
  push('C4', c4,
    `近 ${p.kd_lookback_days} 日最低 K ${fmt(d.kd_k_min_in_window, 1)}`,
    CONDITION_DEFS[3].thresholdText(p));

  // C5 籌碼洗盤
  const instOk = Math.max(d.foreign_buy_days || 0, d.trust_buy_days || 0) >= p.institutional_min_buy_days;
  const c5 = d.margin_change_pct != null && d.margin_change_pct <= p.margin_change_max_pct && instOk;
  push('C5', c5,
    `融資 ${fmt(d.margin_change_pct, 1)}%｜外資 ${d.foreign_buy_days} 日／投信 ${d.trust_buy_days} 日`,
    CONDITION_DEFS[4].thresholdText(p));

  // C6 右側確認
  const c6 = d.close != null && d.ma_value != null && d.close >= d.ma_value
    && d.volume_ratio != null && d.volume_ratio >= p.volume_multiple;
  push('C6', c6,
    `收盤 ${fmt(d.close, 2)} / MA20 ${fmt(d.ma_value, 2)}｜量 ${fmt(d.volume_ratio, 2)}×`,
    CONDITION_DEFS[5].thresholdText(p));

  return results;
}

function allPass(pick, params) {
  return evaluateConditions(pick, params).every(r => r.state === 'pass');
}

// ── 排序（重現 scanner._extract_sort_metric 的行為）────
// 注意：後端以子字串比對 pe / yield / yoy / chip / ratio，其餘一律 0.0（等同不排序），
// 且排序恆為 ascending，「越大越好」的欄位在 metric 內取負值（規格 §9）。
function extractSortMetric(pick, sortBy) {
  if (!sortBy) return 0;
  const d = pick.details || {};
  if (sortBy.includes('pe')) return d.pe_ratio != null ? d.pe_ratio : 999;
  if (sortBy.includes('yield')) return -(d.dividend_yield || 0);
  if (sortBy.includes('yoy')) return -(d.yoy_percent != null ? d.yoy_percent : -999);
  if (sortBy.includes('chip') || sortBy.includes('ratio')) return -(d.foreign_buy_days || 0);
  return 0;
}

function rankPicks(picks, sortBy, maxPicks) {
  const sorted = [...picks].sort((a, b) => extractSortMetric(a, sortBy) - extractSortMetric(b, sortBy));
  const kept = maxPicks ? sorted.slice(0, maxPicks) : sorted;
  return kept.map((p, i) => ({ ...p, rank_value: i + 1 }));
}

// ── 建議動作模板（規格 §10.1）───────────────────────
function suggestedAction(pick) {
  const d = pick.details;
  const stop = d.ma_value ? (d.ma_value * 0.97).toFixed(2) : '—';
  return `已帶量站回 ${d.ma_period}MA，可分批建立第一筆部位（建議 1/3），跌破 ${stop} 停損。`;
}

// ── Formatters ────────────────────────────────────
function fmt(v, digits) {
  if (v == null || Number.isNaN(v)) return '—';
  return Number(v).toFixed(digits == null ? 2 : digits);
}
function strengthLabel(s) {
  return s === 'strong' ? '強烈' : s === 'moderate' ? '中等' : '一般';
}
function strengthClass(s) {
  return s === 'strong' ? 'tag-strong' : s === 'moderate' ? 'tag-moderate' : 'tag-weak';
}

// ── Toast ─────────────────────────────────────────
function showToast(title, detail, type) {
  let wrap = document.querySelector('.toast-wrap');
  if (!wrap) {
    wrap = document.createElement('div');
    wrap.className = 'toast-wrap';
    document.body.appendChild(wrap);
  }
  const el = document.createElement('div');
  el.className = `toast ${type || 'info'}`;
  el.innerHTML = `<div class="toast-title">${title}</div><div class="toast-detail">${detail}</div>`;
  wrap.appendChild(el);
  setTimeout(() => {
    el.style.transition = 'opacity 0.25s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 260);
  }, 3200);
}

// ── Collapsible ───────────────────────────────────
function toggleCollapse(headEl) {
  headEl.classList.toggle('open');
  const body = headEl.nextElementSibling;
  if (body) body.classList.toggle('open');
}

// ── Mock 走勢序列（供條件檢核頁的圖表使用）──────────
// 以固定種子產生：先一段下跌打出負乖離，再收斂反彈站回月線。
function mockSeries(symbol, days) {
  const n = days || 120;
  let seed = 0;
  for (const ch of symbol) seed += ch.charCodeAt(0);
  const rnd = () => {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  };
  const pick = MOCK_PICKS.find(p => p.stock_id === symbol) || MOCK_PICKS[0];
  const endClose = pick.details.close;
  const base = endClose * 1.34;

  const dates = [];
  const closes = [];
  const volumes = [];
  const start = new Date('2026-03-02');
  let cursor = new Date(start);
  for (let i = 0; i < n; i++) {
    while (cursor.getDay() === 0 || cursor.getDay() === 6) cursor.setDate(cursor.getDate() + 1);
    dates.push(cursor.toISOString().slice(0, 10));
    cursor = new Date(cursor.getTime() + 86400000);
  }

  // 形狀：0~65% 緩跌、65~85% 急殺（打出 −15% 以上負乖離）、85~100% 反彈站回月線
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1);
    let shape;
    if (t < 0.65) shape = 1 - 0.12 * (t / 0.65);
    else if (t < 0.86) shape = 0.88 - 0.20 * ((t - 0.65) / 0.21);
    else shape = 0.68 + 0.085 * ((t - 0.86) / 0.14);
    const noise = (rnd() - 0.5) * 0.018;
    closes.push(+(base * (shape + noise)).toFixed(2));
    const volBase = 1 + (rnd() - 0.35) * 0.5;
    const volSpike = t > 0.86 ? 1.5 + (t - 0.86) * 4 : (t > 0.7 && t < 0.86 ? 1.25 : 1);
    volumes.push(Math.round(12000 * volBase * volSpike));
  }
  // 尾端對齊 mock 的收盤價
  const scale = endClose / closes[n - 1];
  for (let i = 0; i < n; i++) closes[i] = +(closes[i] * scale).toFixed(2);

  const ohlc = closes.map((c, i) => {
    const prev = i === 0 ? c : closes[i - 1];
    const o = +(prev + (rnd() - 0.5) * c * 0.008).toFixed(2);
    const h = +(Math.max(o, c) * (1 + rnd() * 0.011)).toFixed(2);
    const l = +(Math.min(o, c) * (1 - rnd() * 0.013)).toFixed(2);
    return [o, c, l, h]; // ECharts candlestick 順序
  });

  return { dates, closes, volumes, ohlc };
}

function sma(values, window) {
  const out = [];
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= window) sum -= values[i - window];
    out.push(i >= window - 1 ? +(sum / window).toFixed(2) : null);
  }
  return out;
}

function biasSeries(closes, maValues) {
  return closes.map((c, i) => (maValues[i] == null ? null : +(((c - maValues[i]) / maValues[i]) * 100).toFixed(2)));
}

// 與 indicators/stochastic.py 同型的簡化 KD（原型用途）
function kdSeries(ohlc, closes, n, k1, d1) {
  const period = n || 9;
  const ks = [];
  const ds = [];
  let k = 50, d = 50;
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) { ks.push(null); ds.push(null); continue; }
    let hi = -Infinity, lo = Infinity;
    for (let j = i - period + 1; j <= i; j++) {
      hi = Math.max(hi, ohlc[j][3]);
      lo = Math.min(lo, ohlc[j][2]);
    }
    const rsv = hi === lo ? 50 : ((closes[i] - lo) / (hi - lo)) * 100;
    k = (2 / 3) * k + (1 / 3) * rsv;
    d = (2 / 3) * d + (1 / 3) * k;
    ks.push(+k.toFixed(2));
    ds.push(+d.toFixed(2));
  }
  return { k: ks, d: ds };
}

// ── 資料就緒度 Mock（規格 §6、AC-7）──────────────────
const DATA_SOURCES = [
  {
    id: 'BWIBBU', name: '個股估值（PE / PB / 殖利率）', endpoint: 'TWSE BWIBBU_d / BWIBBU_ALL',
    fetcher: 'services/valuation_fetcher.py', table: 'daily_valuation',
    latest: '2026-08-20', coverageDays: 62, requiredDays: 720,
    backfill: 'BWIBBU_d 可帶日期（回溯上限待實測）；BWIBBU_ALL 為當日快照，無法回補',
    state: 'partial', usedBy: 'C1'
  },
  {
    id: 'T86', name: '三大法人買賣超', endpoint: 'TWSE T86',
    fetcher: 'services/fetcher.py / market_fetcher.py', table: 'daily_market_chip',
    latest: '2026-08-20', coverageDays: 62, requiredDays: 60,
    backfill: '可帶 date= 回溯多年', state: 'ready', usedBy: 'C5'
  },
  {
    id: 'MI_MARGN', name: '信用交易（融資融券）', endpoint: 'TWSE MI_MARGN',
    fetcher: 'services/fetcher.py / market_fetcher.py', table: 'daily_market_chip',
    latest: '2026-08-20', coverageDays: 62, requiredDays: 60,
    backfill: '可帶 date= 回溯多年', state: 'ready', usedBy: 'C5'
  },
  {
    id: 'REVENUE', name: '每月營業收入', endpoint: 'MOPS 全市場彙總',
    fetcher: 'services/revenue_market_fetcher.py', table: 'monthly_revenue',
    latest: '2026-07（2026-08-11 起可見）', coverageDays: 24, requiredDays: 24,
    backfill: '可補歷史月份（待實測）', state: 'ready', usedBy: 'C2'
  },
  {
    id: 'QUOTE', name: '全市場日行情（OHLCV）', endpoint: 'TWSE MI_INDEX',
    fetcher: 'services/market_fetcher.py', table: 'daily_market_quote',
    latest: '2026-08-20', coverageDays: 62, requiredDays: 60,
    backfill: '可帶 date= 回溯多年', state: 'ready', usedBy: 'C3 / C4 / C6'
  }
];

document.addEventListener('DOMContentLoaded', syncThemeIcon);
