<template>
  <!-- 盤面摘要帶：取代原本每個指標一張的 KPI 卡片矩陣（台股 15 張、4 欄×4 列，約佔一整個螢幕高），
       改成依主題分組的一條摘要（當日區間／三大法人／信用交易／估值／月營收），顯示的指標與數值完全不減少，
       每一列仍可點擊切換下方圖表舞台（emit select → StockDashboard.setActiveChart）。
       CLAUDE.md 鐵則 2（同一列卡片等高）：各組是同一個 CSS Grid 的格子，Grid 預設 stretch 讓同列等高；
       刻意不使用 .card class，避開 _utils.scss 的 legacy `.card { margin-bottom: 2rem; &:last-child {...} }`。 -->
  <section
    class="strip-wrap rounded-2xl border border-surface-200 dark:border-surface-700/80 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden"
    aria-label="盤面摘要"
  >
    <div class="strip" :style="{ '--strip-cols': stripCols }">
      <!-- 當日區間：固定第一組，最低～最高的區間條上標出收盤位置 -->
      <div class="grp">
        <div class="grp-head">
          <span class="grp-title" style="--dot: var(--p-surface-400)">當日區間</span>
          <span v-if="summary.date" class="grp-meta num">{{ summary.date }}</span>
        </div>
        <button
          type="button"
          class="kv kv--block"
          :aria-current="activeWidget === 'kline'"
          title="切換到 K 線圖"
          @click="emit('select', 'price')"
        >
          <span class="range-ends num">
            <span>{{ formatPrice(summary.low, meta) }}</span>
            <span>{{ formatPrice(summary.high, meta) }}</span>
          </span>
          <span v-if="closePos !== null" class="range-track" aria-hidden="true">
            <span class="range-mark" :style="{ left: `${closePos}%` }"></span>
          </span>
          <span class="range-labels"><span>當日最低</span><span>當日最高</span></span>
        </button>
        <div class="range-foot">
          <span>收盤 <span class="num">{{ formatPrice(summary.close, meta) }}</span></span>
          <span v-if="amplitude !== null">振幅 <span class="num">{{ amplitude.toFixed(2) }}%</span></span>
        </div>
      </div>

      <div v-for="group in groups" :key="group.id" class="grp">
        <div class="grp-head">
          <span class="grp-title" :style="{ '--dot': group.dot }">{{ group.label }}</span>
          <span v-if="group.hint" class="grp-meta">{{ group.hint }}</span>
        </div>
        <component
          :is="row.clickable ? 'button' : 'div'"
          v-for="row in group.rows"
          :key="row.key"
          v-bind="row.clickable ? { type: 'button', title: `切換到「${row.label}」圖表`, 'aria-current': activeWidget === row.widget } : {}"
          class="kv"
          :class="{ 'kv--total': row.emphasis }"
          @click="row.clickable && emit('select', row.key)"
        >
          <span class="kv-label">{{ row.label }}</span>
          <span class="kv-bar" :class="{ 'kv-bar--axis': row.bar }" aria-hidden="true">
            <i v-if="row.bar" :style="row.bar"></i>
          </span>
          <span class="kv-value num" :class="{ 'is-empty': row.empty }" :style="row.color ? { color: row.color } : undefined">
            {{ row.text }}<small v-if="row.unit">{{ row.unit }}</small>
          </span>
        </component>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';
import { formatPrice, formatPercent } from '@/utils/format';
import { colorForValue } from '@/utils/marketColors';
import { widgetIdForMetric } from '@/utils/metricWidget';

const props = defineProps({
  metrics: { type: Array, default: () => [] }, // 後端 chart-data 的 metrics（markets/*.py 的 Metric 定義）
  summary: { type: Object, default: () => ({}) }, // latest_summary
  meta: { type: Object, default: null },
  market: { type: String, default: 'tw' },
  prevClose: { type: Number, default: null }, // 前一筆收盤，算振幅用；沒有就不顯示振幅
  activeChartId: { type: String, default: null } // StockCharts 目前顯示的 widget id，用來標示對應的列
});

const emit = defineEmits(['select']);

// StockCharts 在 v-model 還是 null 時會退回第一個頁籤（K 線圖），這裡比照同一個預設
const activeWidget = computed(() => props.activeChartId || 'kline');

// 分組依據：先看指標 key 的明確對照（沒有 panel 的法人細項），其餘沿用後端 Metric.panel；
// 對不到的指標落到「其他指標」，確保後端新增指標時一定會顯示出來，不會被分組邏輯吃掉。
// dot 顏色刻意對齊 StockCharts.vue 同主題圖表的主色（法人合計線 #8b5cf6、本益比線 #f59e0b…）。
const GROUP_DEFS = {
  institutional: { label: '三大法人', hint: '買超 ＋ ／ 賣超 −', dot: '#8b5cf6', weight: 1.55 },
  margin: { label: '信用交易', dot: '#0ea5e9', weight: 1 },
  short: { label: '空頭部位', dot: '#0ea5e9', weight: 1.1 },
  holders: { label: '機構持股', dot: '#14b8a6', weight: 1 },
  valuation: { label: '估值', dot: '#f59e0b', weight: 1.2 },
  fundamental: { label: '月營收', dot: '#10b981', weight: 1 },
  other: { label: '其他指標', dot: 'var(--p-surface-400)', weight: 1 }
};
const KEY_GROUP = {
  foreign_buy_sell: 'institutional',
  trust_buy_sell: 'institutional',
  dealer_buy_sell: 'institutional',
  institutional_total: 'institutional',
  institutional_amount_est: 'institutional',
  short_ratio: 'short'
};
function groupOf(metric) {
  return KEY_GROUP[metric.key] || (GROUP_DEFS[metric.panel] ? metric.panel : 'other');
}

// 三大法人各列加一條以 0 為中線的雙向橫條，同一組共用一個比例尺，買賣方向與力道一眼可比
const BAR_KEYS = ['foreign_buy_sell', 'trust_buy_sell', 'dealer_buy_sell', 'institutional_total'];

const hasValue = (v) => v !== undefined && v !== null && !Number.isNaN(Number(v));
// stock_service 以 0 代表缺值的價格（見 CLAUDE.md 爬蟲段落），價格類一律 > 0 才算有值
const hasPrice = (v) => hasValue(v) && Number(v) > 0;

// 後端 Metric 目前沒有 format 欄位（只有 key/label/unit/frequency/tile/panel/tone），
// 所以「這是不是可正可負、要不要上色」用 key 的命名模式判斷，而不是不存在的 metric.format。
// revenue_yoy／revenue_mom（Phase2-籌碼面與基本面量化擴充 設計文件 FR-2）：可正可負，
// 需顯示正負號並依專案紅漲綠跌慣例上色。
function isSignedMetric(metric) {
  return metric.key.includes('buy_sell') || metric.key === 'institutional_total' || metric.key.includes('amount')
    || metric.key === 'revenue_yoy' || metric.key === 'revenue_mom';
}

// 指標數值：統一用千分位＋最多 2 位小數，可正可負的指標加上正負號。
function formatMetricValue(value, metric) {
  if (!hasValue(value)) return '—';
  const v = Number(value);
  const decimals = Number.isInteger(v) ? 0 : 2;
  const formatted = v.toLocaleString('zh-TW', { minimumFractionDigits: 0, maximumFractionDigits: decimals });
  return isSignedMetric(metric) && v >= 0 ? `+${formatted}` : formatted;
}

const barScale = computed(() => {
  const values = props.metrics
    .filter((m) => BAR_KEYS.includes(m.key) && hasValue(props.summary[m.key]))
    .map((m) => Math.abs(Number(props.summary[m.key])));
  return values.length ? Math.max(...values) : 0;
});

function metricRow(metric) {
  const value = props.summary[metric.key];
  const empty = !hasValue(value);
  let bar = null;
  if (BAR_KEYS.includes(metric.key) && !empty && barScale.value > 0) {
    const v = Number(value);
    bar = {
      width: `${(Math.abs(v) / barScale.value) * 50}%`,
      background: colorForValue(v, props.market),
      [v >= 0 ? 'left' : 'right']: '50%'
    };
  }
  return {
    key: metric.key,
    label: metric.label,
    unit: metric.unit,
    text: formatMetricValue(value, metric),
    empty,
    color: isSignedMetric(metric) && !empty ? colorForValue(Number(value), props.market) : null,
    bar,
    clickable: true,
    widget: widgetIdForMetric(metric.key),
    emphasis: metric.key === 'institutional_total'
  };
}

const groups = computed(() => {
  const byId = new Map();
  const ensure = (id) => {
    if (!byId.has(id)) byId.set(id, { id, ...GROUP_DEFS[id], rows: [] });
    return byId.get(id);
  };
  const metricKeys = new Set(props.metrics.map((m) => m.key));

  for (const metric of props.metrics) {
    const group = ensure(groupOf(metric));
    group.rows.push(metricRow(metric));

    // 台股的券資比不是獨立 Metric、只在 latest_summary 裡，原本掛在融券卡片的副標；
    // 改成信用交易組裡獨立一列，點了直接切到券資比圖表
    if (metric.key === 'short_balance' && !metricKeys.has('short_ratio') && hasValue(props.summary.short_ratio)) {
      group.rows.push({
        key: 'short_ratio',
        label: '券資比',
        text: formatPercent(props.summary.short_ratio),
        color: 'var(--p-orange-500)',
        clickable: true,
        widget: widgetIdForMetric('short_ratio')
      });
    }
  }

  // 月營收有公布時滯，標示實際資料月份，避免使用者誤以為是當月數字（FR-2）
  if (byId.has('fundamental')) {
    const month = props.summary.revenue_visible_month;
    byId.get('fundamental').rows.push({
      key: 'revenue_visible_month',
      label: '資料月份',
      text: month || '—',
      empty: !month,
      clickable: false
    });
  }

  return Array.from(byId.values());
});

// 容器夠寬時所有組排成一列，欄寬依各組內容量加權；窄時退回 3／2／1 欄（見 style 的 container query）
const stripCols = computed(() => ['1.15fr', ...groups.value.map((g) => `${g.weight}fr`)].join(' '));

const closePos = computed(() => {
  const { low, high, close } = props.summary;
  if (!hasPrice(low) || !hasPrice(high) || !hasPrice(close) || Number(high) <= Number(low)) return null;
  const pos = ((Number(close) - Number(low)) / (Number(high) - Number(low))) * 100;
  return Math.min(100, Math.max(0, pos));
});

const amplitude = computed(() => {
  const { low, high } = props.summary;
  if (!hasPrice(low) || !hasPrice(high) || !hasPrice(props.prevClose)) return null;
  return ((Number(high) - Number(low)) / Number(props.prevClose)) * 100;
});
</script>

<style scoped>
.strip-wrap {
  container-type: inline-size;
  --strip-line: color-mix(in srgb, var(--p-text-color) 10%, transparent);
}

.strip {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
}
@container (min-width: 34rem) {
  .strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@container (min-width: 50rem) {
  .strip { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@container (min-width: 62rem) {
  .strip { grid-template-columns: var(--strip-cols); }
}

/* 分隔線用往左、往上的 1px 陰影畫：不論換成幾欄，最左欄與第一列的線都會被外框 overflow:hidden 裁掉，
   不必依欄數寫 nth-child 規則 */
.grp {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
  padding: 0.7rem 1.1rem 0.6rem;
  box-shadow: -1px 0 0 var(--strip-line), 0 -1px 0 var(--strip-line);
}

.grp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}
.grp-title {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--p-text-muted-color);
}
.grp-title::before {
  content: '';
  width: 0.4rem;
  height: 0.4rem;
  border-radius: 2px;
  background: var(--dot);
}
.grp-meta {
  font-size: 0.62rem;
  color: var(--p-text-muted-color);
  white-space: nowrap;
}

.kv {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.55rem;
  width: calc(100% + 0.8rem);
  min-height: 1.6rem;
  margin-inline: -0.4rem;
  padding: 0.15rem 0.4rem;
  border-radius: 0.4rem;
  text-align: left;
  font: inherit;
  color: inherit;
  background: none;
  border: 0;
}
button.kv {
  cursor: pointer;
  transition: background-color 0.15s;
}
button.kv:hover {
  background: color-mix(in srgb, var(--p-text-color) 5%, transparent);
}
button.kv:focus-visible {
  outline: 2px solid var(--p-primary-color);
  outline-offset: -2px;
}
.kv[aria-current='true'] {
  background: color-mix(in srgb, var(--p-primary-color) 12%, transparent);
}

.kv-label {
  font-size: 0.72rem;
  color: var(--p-text-muted-color);
  white-space: nowrap;
}
.kv-value {
  font-size: 0.84rem;
  font-weight: 600;
  text-align: right;
  white-space: nowrap;
  color: var(--p-text-color);
}
.kv-value small {
  margin-left: 0.2rem;
  font-family: system-ui, sans-serif;
  font-size: 0.6rem;
  font-weight: 400;
  color: var(--p-text-muted-color);
}
.kv-value.is-empty {
  font-weight: 400;
  color: var(--p-text-muted-color);
}

.kv--total {
  margin-top: 0.15rem;
  padding-top: 0.35rem;
  border-top: 1px dashed var(--strip-line);
  border-radius: 0 0 0.4rem 0.4rem;
}
.kv--total .kv-label {
  font-weight: 700;
  color: var(--p-text-color);
}
.kv--total .kv-value {
  font-size: 0.95rem;
}

.kv-bar {
  position: relative;
  height: 0.35rem;
}
.kv-bar--axis {
  background: linear-gradient(var(--strip-line), var(--strip-line)) center / 1px 100% no-repeat;
}
.kv-bar i {
  position: absolute;
  top: 0;
  bottom: 0;
  border-radius: 2px;
  opacity: 0.85;
}

/* 當日區間
   align-items 必須明確設回 stretch：.kv 的 `align-items: center` 是給單列 grid 用的，沿用到這個直向 flex
   會把子元素水平置中、寬度縮成內容寬——區間條沒有內容，寬度會變 0，只剩收盤標記那條線。
   flex: 1＋垂直置中：讓區間圖吃滿同列其他組撐出來的高度，不在下方留一大塊空白。 */
.kv--block {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: stretch;
  justify-content: center;
  gap: 0.45rem;
  padding-block: 0.5rem;
}
.range-ends,
.range-labels,
.range-foot {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
}
.range-ends {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--p-text-color);
}
.range-labels {
  font-size: 0.62rem;
  color: var(--p-text-muted-color);
}
.range-track {
  position: relative;
  height: 0.45rem;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--down, #16a34a) 30%, transparent),
    color-mix(in srgb, var(--up, #dc2626) 30%, transparent)
  );
}
.range-mark {
  position: absolute;
  top: -0.2rem;
  bottom: -0.2rem;
  width: 3px;
  margin-left: -1.5px;
  border-radius: 2px;
  background: var(--p-text-color);
}
.range-foot {
  margin-top: auto;
  padding-top: 0.2rem;
  font-size: 0.68rem;
  color: var(--p-text-muted-color);
}
.range-foot .num {
  font-weight: 600;
  color: var(--p-text-color);
}
</style>
