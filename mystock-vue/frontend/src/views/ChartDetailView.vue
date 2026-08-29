<template>
  <div class="chart-detail-root">
    <!-- ══════════════════════════════════════════════════
         Sticky 控制條：貼附在 AppTopbar (4rem) 正下方
         含返回按鈕、圖表 Tab 切換、週期與時間範圍選擇器
    ═══════════════════════════════════════════════════ -->
    <div class="chart-control-bar sticky top-16 z-30 bg-surface-0/95 dark:bg-surface-900/95 backdrop-blur-md border-b border-surface-200 dark:border-surface-700 shadow-sm">
      <div class="max-w-7xl mx-auto px-6 py-2.5 flex flex-wrap items-center gap-x-3 gap-y-2">
        <!-- 返回按鈕群 -->
        <div class="flex items-center gap-2 shrink-0">
          <button
            @click="router.push('/')"
            class="px-2.5 py-1 text-xs font-bold bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-lg flex items-center gap-1 transition-colors"
          >
            <i class="pi pi-home"></i>
          </button>
          <button
            @click="router.push(`${basePath}/${market}/${stockId}`)"
            class="px-2.5 py-1 text-xs font-bold bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-lg flex items-center gap-1 transition-colors"
          >
            <i class="pi pi-arrow-left"></i> <span class="hidden sm:inline">返回儀表板</span>
          </button>
        </div>

        <!-- 股票名稱 + 日期 -->
        <div class="flex items-center gap-2 shrink-0">
          <span class="font-black text-surface-900 dark:text-surface-0">
            <span class="num">{{ stockId }}</span>
            <span v-if="stockName" class="text-primary ml-1">{{ stockName }}</span>
          </span>
          <span v-if="dateRangeText" class="num text-xs font-bold bg-primary-50 dark:bg-primary-900/30 text-primary px-2 py-0.5 rounded border border-primary/20 hidden md:inline">
            <i class="pi pi-calendar mr-1"></i>{{ dateRangeText }}
          </span>
        </div>

        <!-- 圖表 Tab 切換 -->
        <div class="flex flex-wrap items-center gap-0.5 bg-surface-100 dark:bg-surface-800 p-0.5 rounded-lg border border-surface-200 dark:border-surface-700">
          <button
            v-for="tab in chartTabs"
            :key="tab.value"
            @click="switchChartType(tab.value)"
            :class="[
              'px-2.5 py-1 text-xs font-bold rounded-md transition-all duration-150 whitespace-nowrap',
              chartType === tab.value
                ? 'bg-primary text-primary-contrast shadow-sm'
                : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
            ]"
          >
            {{ tab.label }}
          </button>
        </div>

        <!-- 右側：週期 + 時間範圍 -->
        <div class="flex flex-wrap items-center gap-2 ml-auto">
          <!-- 週期（日/週/月線） -->
          <div class="flex items-center gap-0.5 bg-surface-100 dark:bg-surface-800 p-0.5 rounded-lg border border-surface-200 dark:border-surface-700">
            <button
              v-for="p in periodOptions"
              :key="p.value"
              @click="setPeriod(p.value)"
              :class="[
                'px-2.5 py-1 text-xs font-bold rounded-md transition-all duration-150',
                period === p.value
                  ? 'bg-primary text-primary-contrast shadow-sm'
                  : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
              ]"
            >
              {{ p.label }}
            </button>
          </div>

          <!-- 時間範圍 -->
          <div class="flex items-center gap-0.5 bg-surface-100 dark:bg-surface-800 p-0.5 rounded-lg border border-surface-200 dark:border-surface-700">
            <button
              v-for="m in monthOptions"
              :key="m.value"
              @click="setMonths(m.value)"
              :class="[
                'px-2.5 py-1 text-xs font-bold rounded-md transition-all duration-150',
                months === m.value
                  ? 'bg-primary text-primary-contrast shadow-sm'
                  : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
              ]"
            >
              {{ m.label }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════
         主內容區
    ═══════════════════════════════════════════════════ -->
    <div class="p-6 max-w-7xl mx-auto space-y-4">
    <!-- 載入中狀態 -->
    <div v-if="loading" class="flex flex-col items-center justify-center p-12 card bg-surface-0 dark:bg-surface-900 rounded-2xl border border-surface-200 dark:border-surface-700">
      <i class="pi pi-spin pi-spinner text-primary text-4xl mb-3"></i>
      <p class="text-sm font-semibold text-surface-600 dark:text-surface-400">加載圖表數據中...</p>
    </div>

    <!-- 錯誤訊息 -->
    <div v-else-if="error" class="card p-6 border border-red-300 bg-red-50 dark:bg-red-900/20 rounded-2xl text-red-700 dark:text-red-300">
      <div class="flex items-center gap-3">
        <i class="pi pi-exclamation-circle text-2xl"></i>
        <div>
          <h4 class="font-bold">資料讀取失敗</h4>
          <p class="text-sm mt-0.5">{{ error }}</p>
        </div>
      </div>
    </div>

    <!-- 圖表顯示區 -->
    <div v-else class="card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div class="flex items-center flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
        <h3 class="text-xl font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
          <i :class="['pi text-primary', currentTabInfo?.icon]"></i>
          {{ currentTabInfo?.label }}
        </h3>
        <div class="flex items-center gap-2">
          <!-- 技術指標副圖開關（KD／MACD／RSI 三選一，Phase1-基礎量化與技術面 設計文件 §9 Q-2）：
               只在 K 線圖頁籤顯示；資料筆數不足暖身期時個別停用並提示原因。 -->
          <div v-if="chartType === 'kline'" class="flex items-center gap-1">
            <button
              v-for="opt in subchartOptions"
              :key="opt.value"
              type="button"
              @click="toggleSubchart(opt.value)"
              :disabled="!opt.available"
              :aria-pressed="subchartMode === opt.value"
              :title="opt.available ? opt.title : '資料筆數不足，無法計算'"
              :class="[
                'px-2.5 py-1 text-xs font-bold rounded-md flex items-center gap-1 border transition-colors',
                !opt.available
                  ? 'text-surface-300 dark:text-surface-600 border-surface-200 dark:border-surface-700 cursor-not-allowed'
                  : subchartMode === opt.value
                    ? 'bg-primary/10 text-primary border-primary/30'
                    : 'text-surface-500 border-surface-200 dark:border-surface-700 hover:text-primary hover:bg-surface-100 dark:hover:bg-surface-800'
              ]"
            >
              {{ opt.label }}
            </button>
          </div>
          <span v-if="dateRangeText" class="text-xs font-semibold text-surface-600 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 px-3 py-1 rounded-lg border border-surface-200 dark:border-surface-700">
            <i class="pi pi-calendar text-xs mr-1 text-primary"></i>資料區間：{{ dateRangeText }}
          </span>
        </div>
      </div>
      <v-chart
        :class="['chart-container-large', { 'chart-container-large--subchart': activeSubchart !== 'none' }]"
        :option="currentChartOption"
        :update-options="{ notMerge: true }"
        autoresize
      />

      <ChartExplanationBlock :explanation="currentExplanation" />
      <ChartExplanationBlock v-if="activeSubchart !== 'none' && chartExplanations[activeSubchart]" :explanation="chartExplanations[activeSubchart]" />
    </div>
    </div><!-- /內容區 -->
  </div><!-- /chart-detail-root -->
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { stockApi } from '@/service/stockApi';
import { indexApi } from '@/service/indexApi';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart, LineChart, CandlestickChart } from 'echarts/charts';
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent
} from 'echarts/components';
import VChart from 'vue-echarts';
import { getUpDownColor } from '@/utils/marketColors';
import { buildMovingAverageSeries } from '@/utils/movingAverage';
import { chartExplanations } from '@/utils/chartExplanations';
import ChartExplanationBlock from '@/components/ChartExplanationBlock.vue';

use([
  CanvasRenderer,
  BarChart,
  LineChart,
  CandlestickChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent
]);

const route = useRoute();
const router = useRouter();

// 指數／個股共用本頁（大盤指數功能規劃書 §10.1）：由路由 meta.kind 判斷，
// 決定要呼叫哪個 API、顯示哪些頁籤、返回鍵導去哪裡。
const kind = computed(() => route.meta.kind || 'stock');
const basePath = computed(() => (kind.value === 'index' ? '/index' : '/stock'));

const stockId = ref(route.params.id || route.params.code || '2330');
const market = ref(route.params.market || 'tw');
const chartType = ref(route.params.chartType || (kind.value === 'index' ? 'kline' : 'institutional'));
const period = ref(route.query.period || 'daily');
const months = ref(Number(route.query.months) || 3);

const loading = ref(true);
const error = ref(null);
const chartData = ref(null);

const stockChartTabs = [
  { value: 'institutional', label: '三大法人', icon: 'pi-users' },
  { value: 'kline', label: 'K線圖', icon: 'pi-chart-bar' },
  { value: 'amount', label: '估算金額', icon: 'pi-dollar' },
  { value: 'margin-long', label: '融資餘額', icon: 'pi-chart-line' },
  { value: 'margin-short', label: '融券餘額', icon: 'pi-sort-alt' },
  { value: 'short-ratio', label: '券資比', icon: 'pi-percentage' }
];

// 指數目前只有 OHLCV（P1 爬蟲範圍，見 services/index_fetcher.py），頁籤只給 K 線圖／成交金額，
// 不假裝有三大法人／融資融券資料（P-4「誠實標示資料缺口」）。
const indexChartTabs = [
  { value: 'kline', label: 'K線圖', icon: 'pi-chart-bar' },
  { value: 'index-turnover', label: '成交金額', icon: 'pi-dollar' }
];

const chartTabs = computed(() => (kind.value === 'index' ? indexChartTabs : stockChartTabs));

// 技術指標副圖開關：KD／MACD／RSI 三選一（Phase1-基礎量化與技術面 設計文件 §9 Q-2，
// 沿用 KD 指標 設計規格書 §7.4 的既有慣例，規格同 StockCharts.vue，兩處各自實作一份是既有慣例
// ——見 StockCharts.vue 對應區塊註解）。狀態存 localStorage，並相容遷移舊版單一布林開關。
const SUBCHART_MODE_STORAGE_KEY = 'mystock:chart:subchart-mode';
const LEGACY_KD_VISIBLE_KEY = 'mystock:chart:kd-visible';

function loadInitialSubchartMode() {
  const stored = localStorage.getItem(SUBCHART_MODE_STORAGE_KEY);
  if (stored === 'kd' || stored === 'macd' || stored === 'rsi' || stored === 'none') return stored;
  return localStorage.getItem(LEGACY_KD_VISIBLE_KEY) === '1' ? 'kd' : 'none';
}
const subchartMode = ref(loadInitialSubchartMode());

const kdData = computed(() => chartData.value?.kd || null);
const macdData = computed(() => chartData.value?.macd || null);
const rsiData = computed(() => chartData.value?.rsi || null);
const kdAvailable = computed(() => !!kdData.value?.k?.some((v) => v != null));
const macdAvailable = computed(() => !!macdData.value?.dif?.some((v) => v != null));
const rsiAvailable = computed(() => {
  const r = rsiData.value;
  return !!(r?.rsi_14?.some((v) => v != null) || r?.rsi_6?.some((v) => v != null));
});

const subchartOptions = computed(() => [
  { value: 'kd', label: 'KD', title: 'KD 隨機指標副圖', available: kdAvailable.value },
  { value: 'macd', label: 'MACD', title: 'MACD 副圖', available: macdAvailable.value },
  { value: 'rsi', label: 'RSI', title: 'RSI 副圖', available: rsiAvailable.value }
]);

const activeSubchart = computed(() => {
  if (chartType.value !== 'kline') return 'none';
  const mode = subchartMode.value;
  if (mode === 'kd' && kdAvailable.value) return 'kd';
  if (mode === 'macd' && macdAvailable.value) return 'macd';
  if (mode === 'rsi' && rsiAvailable.value) return 'rsi';
  return 'none';
});

// 警示看板 → 圖表跳轉（KD指標 設計規格書 §7.5）：?indicator=kd|macd|rsi 強制切到對應副圖
// （chartType 本來就已經是路由的一部分，目標網址本身就是 .../chart/kline，不需要另外導頁切頁籤）；
// ?highlight=YYYY-MM-DD 在該日期畫一條貫穿主圖與副圖的垂直線。
watch(
  () => route.query.indicator,
  (indicator) => {
    if (indicator === 'kd' || indicator === 'macd' || indicator === 'rsi') subchartMode.value = indicator;
  },
  { immediate: true }
);
const highlightDate = computed(() => route.query.highlight || null);

function toggleSubchart(mode) {
  const availabilityMap = { kd: kdAvailable.value, macd: macdAvailable.value, rsi: rsiAvailable.value };
  if (!availabilityMap[mode]) return;
  subchartMode.value = subchartMode.value === mode ? 'none' : mode;
  localStorage.setItem(SUBCHART_MODE_STORAGE_KEY, subchartMode.value);
}
const currentTabInfo = computed(() => chartTabs.value.find(t => t.value === chartType.value));
const currentExplanation = computed(() => chartExplanations[chartType.value] || null);
const dates = computed(() => chartData.value?.dates || []);
const stockName = computed(() => chartData.value?.stock_name || '');

const upDown = computed(() => getUpDownColor(market.value));

const dateRangeText = computed(() => {
  if (chartData.value?.start_date && chartData.value?.end_date) {
    return `${chartData.value.start_date} ~ ${chartData.value.end_date}`;
  }
  if (dates.value && dates.value.length > 0) {
    return `${dates.value[0]} ~ ${dates.value[dates.value.length - 1]}`;
  }
  return '';
});

// 週期選項
 const periodOptions = [
  { label: '日線', value: 'daily' },
  { label: '週線', value: 'weekly' },
  { label: '月線', value: 'monthly' }
];

const monthOptions = [
  { label: '1個月', value: 1 },
  { label: '3個月', value: 3 },
  { label: '6個月', value: 6 },
  { label: '1年',   value: 12 }
];

onMounted(() => {
  loadStockData();
});

watch([() => route.params.id, () => route.params.code, () => route.params.market, () => route.params.chartType], ([newId, newCode, newMarket, newType]) => {
  let shouldReload = false;
  const combinedId = newId || newCode;
  if (combinedId && combinedId !== stockId.value) {
    stockId.value = combinedId;
    shouldReload = true;
  }
  if (newMarket && newMarket !== market.value) {
    market.value = newMarket;
    shouldReload = true;
  }
  if (shouldReload) loadStockData();
  if (newType && newType !== chartType.value) {
    chartType.value = newType;
  }
});

// URL query 是週期／範圍狀態的唯一來源：可重整、可分享、可上一頁返回。
watch(() => route.query.period, (v) => {
  const p = v || 'daily';
  if (p !== period.value) {
    period.value = p;
    loadStockData();
  }
});
watch(() => route.query.months, (v) => {
  const m = Number(v) || 3;
  if (m !== months.value) {
    months.value = m;
    loadStockData();
  }
});

async function loadStockData() {
  loading.value = true;
  error.value = null;
  try {
    const res = kind.value === 'index'
      ? await indexApi.getChartData(stockId.value, period.value, months.value, market.value)
      : await stockApi.getChartData(stockId.value, period.value, months.value, market.value);
    if (res.success) {
      chartData.value = res.data;
    } else {
      error.value = '載入資料時發生未知錯誤';
    }
  } catch (err) {
    error.value = err.response?.data?.error?.message || err.response?.data?.detail || err.message || '連線後端 API 失敗';
  } finally {
    loading.value = false;
  }
}

function switchChartType(type) {
  // 使用 replace 避免堆疊瞬戒歷史
  router.replace({
    path: `${basePath.value}/${market.value}/${stockId.value}/chart/${type}`,
    query: { period: period.value, months: months.value }
  });
}

function setPeriod(p) {
  if (period.value === p) return;
  router.replace({ query: { ...route.query, period: p } });
}

function setMonths(m) {
  if (months.value === m) return;
  router.replace({ query: { ...route.query, months: m } });
}

// === Options ===
const dataZoomConfig = [
  { type: 'inside', start: 0, end: 100 },
  { type: 'slider', start: 0, end: 100 }
];

// 副圖線色與 tooltip 分組（規格同 StockCharts.vue，Phase1-基礎量化與技術面 設計文件 §9 Q-2）。
const SUBCHART_FAST_COLOR = '#6366f1';
const SUBCHART_SLOW_COLOR = '#ec4899';
const SUBCHART_BAND_COLOR = 'rgba(148, 163, 184, 0.12)';
const SUBCHART_SERIES_NAMES = {
  kd: ['K', 'D'],
  macd: ['DIF', '訊號線', 'MACD 柱狀圖'],
  rsi: ['RSI(6)', 'RSI(14)'],
  none: []
};

function seriesValue(point) {
  const raw = point?.data;
  if (raw != null && typeof raw === 'object' && 'value' in raw) return raw.value;
  return raw;
}

function buildKdSubSeries(kd, highlightMarkLine) {
  return [
    {
      name: 'K',
      type: 'line',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: kd.k,
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 1.5, color: SUBCHART_FAST_COLOR },
      itemStyle: { color: SUBCHART_FAST_COLOR },
      z: 3,
      markArea: {
        silent: true,
        itemStyle: { color: SUBCHART_BAND_COLOR },
        data: [
          [{ yAxis: kd.overbought }, { yAxis: 100 }],
          [{ yAxis: 0 }, { yAxis: kd.oversold }]
        ]
      },
      markLine: {
        silent: true,
        symbol: 'none',
        label: { show: false },
        lineStyle: { type: 'dashed', color: '#94a3b8', width: 1 },
        data: [{ yAxis: kd.overbought }, { yAxis: kd.oversold }]
      }
    },
    {
      name: 'D',
      type: 'line',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: kd.d,
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 1.5, color: SUBCHART_SLOW_COLOR },
      itemStyle: { color: SUBCHART_SLOW_COLOR },
      z: 3,
      markLine: highlightMarkLine
    }
  ];
}

function buildMacdSubSeries(macd, highlightMarkLine) {
  const histogramData = (macd.histogram || []).map((v) =>
    v == null ? null : { value: v, itemStyle: { color: v >= 0 ? upDown.value.up : upDown.value.down } }
  );
  return [
    {
      name: 'DIF',
      type: 'line',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: macd.dif,
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 1.5, color: SUBCHART_FAST_COLOR },
      itemStyle: { color: SUBCHART_FAST_COLOR },
      z: 3,
      markLine: {
        silent: true,
        symbol: 'none',
        label: { show: false },
        lineStyle: { type: 'dashed', color: '#94a3b8', width: 1 },
        data: [{ yAxis: 0 }]
      }
    },
    {
      name: '訊號線',
      type: 'line',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: macd.signal,
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 1.5, color: SUBCHART_SLOW_COLOR },
      itemStyle: { color: SUBCHART_SLOW_COLOR },
      z: 3,
      markLine: highlightMarkLine
    },
    {
      name: 'MACD 柱狀圖',
      type: 'bar',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: histogramData,
      barMaxWidth: 6,
      z: 2
    }
  ];
}

function buildRsiSubSeries(rsi, highlightMarkLine) {
  return [
    {
      name: 'RSI(6)',
      type: 'line',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: rsi.rsi_6,
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 1.5, color: SUBCHART_FAST_COLOR },
      itemStyle: { color: SUBCHART_FAST_COLOR },
      z: 3,
      markArea: {
        silent: true,
        itemStyle: { color: SUBCHART_BAND_COLOR },
        data: [
          [{ yAxis: rsi.overbought }, { yAxis: 100 }],
          [{ yAxis: 0 }, { yAxis: rsi.oversold }]
        ]
      },
      markLine: {
        silent: true,
        symbol: 'none',
        label: { show: false },
        lineStyle: { type: 'dashed', color: '#94a3b8', width: 1 },
        data: [{ yAxis: rsi.overbought }, { yAxis: rsi.oversold }]
      }
    },
    {
      name: 'RSI(14)',
      type: 'line',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: rsi.rsi_14,
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 1.5, color: SUBCHART_SLOW_COLOR },
      itemStyle: { color: SUBCHART_SLOW_COLOR },
      z: 3,
      markLine: highlightMarkLine
    }
  ];
}

const currentChartOption = computed(() => {
  const d = dates.value;
  if (!d.length) return {};

  switch (chartType.value) {
    case 'institutional':
      const inst = chartData.value?.institutional || {};
      return {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { data: ['外資', '投信', '自營商', '合計'], bottom: 0 },
        dataZoom: dataZoomConfig,
        grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
        xAxis: { type: 'category', data: d },
        yAxis: { type: 'value', name: '張' },
        series: [
          { name: '外資', type: 'bar', data: inst.foreign || [], itemStyle: { color: '#94a3b8' } },
          { name: '投信', type: 'bar', data: inst.trust || [], itemStyle: { color: '#64748b' } },
          { name: '自營商', type: 'bar', data: inst.dealer || [], itemStyle: { color: '#cbd5e1' } },
          { name: '合計', type: 'line', data: inst.total || [], itemStyle: { color: '#334155' }, lineStyle: { width: 3 } }
        ]
      };
    case 'kline': {
      const kline = chartData.value?.kline || [];
      const ma = buildMovingAverageSeries(kline, period.value);
      const sub = activeSubchart.value; // 'none' | 'kd' | 'macd' | 'rsi'
      const showSubchart = sub !== 'none';

      const highlightMarkLine = highlightDate.value
        ? {
            silent: true,
            symbol: ['none', 'none'],
            lineStyle: { type: 'solid', color: '#7c3aed', width: 1.5 },
            label: { show: false },
            data: [{ xAxis: highlightDate.value }]
          }
        : undefined;

      const grid = showSubchart
        ? [
            { left: '3%', right: '4%', top: '8%', height: '50%', containLabel: true },
            { left: '3%', right: '4%', top: '66%', height: '16%', containLabel: true }
          ]
        : [{ left: '3%', right: '4%', bottom: '15%', top: '12%', containLabel: true }];

      const xAxis = [{ type: 'category', data: d, gridIndex: 0 }];
      const yAxis = [{ type: 'value', scale: true, gridIndex: 0 }];
      if (showSubchart) {
        xAxis.push({ type: 'category', data: d, gridIndex: 1, axisLabel: { show: false } });
        yAxis.push(
          sub === 'macd'
            ? { type: 'value', gridIndex: 1, scale: true }
            : { type: 'value', gridIndex: 1, min: 0, max: 100, interval: 50 }
        );
      }

      const series = [
        {
          type: 'candlestick',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: kline,
          itemStyle: {
            color: upDown.value.up,
            color0: upDown.value.down,
            borderColor: upDown.value.up,
            borderColor0: upDown.value.down
          },
          markLine: highlightMarkLine
        },
        ...ma.series
      ];

      if (sub === 'kd') series.push(...buildKdSubSeries(kdData.value, highlightMarkLine));
      else if (sub === 'macd') series.push(...buildMacdSubSeries(macdData.value, highlightMarkLine));
      else if (sub === 'rsi') series.push(...buildRsiSubSeries(rsiData.value, highlightMarkLine));

      return {
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' },
          formatter: (params) => {
            const candle = params.find((p) => p.seriesType === 'candlestick') || params[0];
            if (!candle || !candle.data) return '';
            const date = candle.name;
            // candle.data 是 ECharts candlestick 內部的 raw value，格式為
            // [類別索引, open, close, low, high]（開頭多一個座標軸索引維度，不是我們傳入的 [open,close,low,high]），
            // 需去掉第 0 個索引維度，否則開盤價會顯示成 K 棒的索引序號。
            const [openRaw, closeRaw, lowRaw, highRaw] = candle.data.slice(1);
            const change = closeRaw - openRaw;
            const color = change >= 0 ? upDown.value.up : upDown.value.down;
            // 美股價格是原始浮點數，統一只顯示到小數 2 位，避免撐爆 tooltip。
            const open = Number(openRaw).toFixed(2);
            const close = Number(closeRaw).toFixed(2);
            const low = Number(lowRaw).toFixed(2);
            const high = Number(highRaw).toFixed(2);
            let html = `
              <div class="font-bold">${date}</div>
              <div>開盤價: <span style="color:${color}">${open}</span></div>
              <div>最高價: <span style="color:${color}">${high}</span></div>
              <div>最低價: <span style="color:${color}">${low}</span></div>
              <div>收盤價: <span style="color:${color}">${close}</span> (${change >= 0 ? '+' : ''}${change.toFixed(2)})</div>
            `;

            const subNames = SUBCHART_SERIES_NAMES[sub] || [];
            const maLines = params.filter((p) => p.seriesType === 'line' && p.data != null && !subNames.includes(p.seriesName));
            const subLines = params.filter((p) => subNames.includes(p.seriesName) && p.data != null);

            if (maLines.length) {
              html += '<div class="mt-1 pt-1" style="border-top:1px dashed rgba(148,163,184,0.4)">';
              maLines.forEach((p) => { html += `${p.marker}${p.seriesName}: ${p.data}&nbsp;&nbsp;`; });
              html += '</div>';
            }
            if (subLines.length) {
              html += '<div class="mt-1 pt-1" style="border-top:1px dashed rgba(148,163,184,0.4)">';
              subLines.forEach((p) => { html += `${p.marker}${p.seriesName} ${Number(seriesValue(p)).toFixed(2)}&nbsp;&nbsp;`; });
              if (sub === 'kd') {
                const kVal = subLines.find((p) => p.seriesName === 'K')?.data;
                const kd = kdData.value;
                if (kVal != null && kd) {
                  if (kVal >= kd.overbought) html += '<span class="opacity-70">（超買）</span>';
                  else if (kVal <= kd.oversold) html += '<span class="opacity-70">（超賣）</span>';
                }
              } else if (sub === 'rsi') {
                const rVal = subLines.find((p) => p.seriesName === 'RSI(14)')?.data;
                const rsi = rsiData.value;
                if (rVal != null && rsi) {
                  if (rVal >= rsi.overbought) html += '<span class="opacity-70">（超買）</span>';
                  else if (rVal <= rsi.oversold) html += '<span class="opacity-70">（超賣）</span>';
                }
              } else if (sub === 'macd') {
                const histVal = seriesValue(subLines.find((p) => p.seriesName === 'MACD 柱狀圖'));
                if (histVal != null) {
                  html += histVal >= 0 ? '<span class="opacity-70">（多方動能）</span>' : '<span class="opacity-70">（空方動能）</span>';
                }
              }
              html += '</div>';
            }
            return html;
          }
        },
        legend: { data: ma.names, top: 0, right: 0, itemWidth: 14, itemHeight: 8, textStyle: { fontSize: 11 } },
        axisPointer: { link: [{ xAxisIndex: 'all' }] },
        dataZoom: [
          { type: 'inside', start: 0, end: 100, xAxisIndex: showSubchart ? [0, 1] : [0] },
          { type: 'slider', start: 0, end: 100, xAxisIndex: showSubchart ? [0, 1] : [0] }
        ],
        grid,
        xAxis,
        yAxis,
        series
      };
    }
    case 'amount':
      const amounts = chartData.value?.institutional?.estimated_amount || [];
      return {
        tooltip: { trigger: 'axis' },
        dataZoom: dataZoomConfig,
        grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
        xAxis: { type: 'category', data: d },
        yAxis: { type: 'value', name: '萬元' },
        series: [
          {
            name: '估算買賣超金額', type: 'line', data: amounts, smooth: true, itemStyle: { color: '#64748b' },
            areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(100, 116, 139, 0.4)' }, { offset: 1, color: 'rgba(100, 116, 139, 0.0)' }] } }
          }
        ]
      };
    case 'margin-long':
      const longs = chartData.value?.margin?.long_balance || [];
      return {
        tooltip: { trigger: 'axis' },
        dataZoom: dataZoomConfig,
        grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
        xAxis: { type: 'category', data: d },
        yAxis: { type: 'value', name: '張', scale: true },
        series: [{ name: '融資餘額', type: 'line', data: longs, smooth: true, itemStyle: { color: '#64748b' }, lineStyle: { width: 3 } }]
      };
    case 'margin-short':
      const shorts = chartData.value?.margin?.short_balance || [];
      return {
        tooltip: { trigger: 'axis' },
        dataZoom: dataZoomConfig,
        grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
        xAxis: { type: 'category', data: d },
        yAxis: { type: 'value', name: '張', scale: true },
        series: [{ name: '融券餘額', type: 'line', data: shorts, smooth: true, itemStyle: { color: '#64748b' }, lineStyle: { width: 3 } }]
      };
    case 'short-ratio':
      const ratios = chartData.value?.margin?.short_ratio || [];
      return {
        tooltip: { trigger: 'axis', formatter: '{b}<br/>券資比: {c}%' },
        dataZoom: dataZoomConfig,
        grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
        xAxis: { type: 'category', data: d },
        yAxis: { type: 'value', name: '%', scale: true },
        series: [{ name: '券資比', type: 'line', data: ratios, smooth: true, itemStyle: { color: '#64748b' }, lineStyle: { width: 3 } }]
      };
    case 'index-turnover': {
      const amounts = (chartData.value?.records || []).map((r) => r.amount || 0);
      return {
        tooltip: { trigger: 'axis' },
        dataZoom: dataZoomConfig,
        grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
        xAxis: { type: 'category', data: d },
        yAxis: { type: 'value', name: market.value === 'us' ? '美元' : '元' },
        series: [{ name: '成交金額', type: 'bar', data: amounts, itemStyle: { color: '#0ea5e9' } }]
      };
    }
    default:
      return {};
  }
});

</script>

<style scoped>
.chart-container-large {
  width: 100%;
  height: 600px; /* 大圖表高度 */
}

/* 副圖（KD／MACD／RSI）開啟時加高，避免主圖被壓扁（KD指標 設計規格書 §7.1/§7.4，
   Phase1-基礎量化與技術面 設計文件 §9 Q-2 擴充） */
.chart-container-large--subchart {
  height: 720px;
}
</style>
