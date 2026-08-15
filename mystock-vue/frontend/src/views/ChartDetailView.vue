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
            @click="router.push(`/stock/${market}/${stockId}`)"
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
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
        <h3 class="text-xl font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
          <i :class="['pi text-primary', currentTabInfo?.icon]"></i>
          {{ currentTabInfo?.label }}
        </h3>
        <span v-if="dateRangeText" class="text-xs font-semibold text-surface-600 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 px-3 py-1 rounded-lg border border-surface-200 dark:border-surface-700">
          <i class="pi pi-calendar text-xs mr-1 text-primary"></i>資料區間：{{ dateRangeText }}
        </span>
      </div>
      <v-chart class="chart-container-large" :option="currentChartOption" :update-options="{ notMerge: true }" autoresize />

      <ChartExplanationBlock :explanation="currentExplanation" />
    </div>
    </div><!-- /內容區 -->
  </div><!-- /chart-detail-root -->
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { stockApi } from '@/service/stockApi';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart, LineChart, CandlestickChart } from 'echarts/charts';
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent
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
  DataZoomComponent
]);

const route = useRoute();
const router = useRouter();

const stockId = ref(route.params.id || '2330');
const market = ref(route.params.market || 'tw');
const chartType = ref(route.params.chartType || 'institutional');
const period = ref(route.query.period || 'daily');
const months = ref(Number(route.query.months) || 3);

const loading = ref(true);
const error = ref(null);
const chartData = ref(null);

const chartTabs = [
  { value: 'institutional', label: '三大法人', icon: 'pi-users' },
  { value: 'kline', label: 'K線圖', icon: 'pi-chart-bar' },
  { value: 'amount', label: '估算金額', icon: 'pi-dollar' },
  { value: 'margin-long', label: '融資餘額', icon: 'pi-chart-line' },
  { value: 'margin-short', label: '融券餘額', icon: 'pi-sort-alt' },
  { value: 'short-ratio', label: '券資比', icon: 'pi-percentage' }
];

const currentTabInfo = computed(() => chartTabs.find(t => t.value === chartType.value));
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

watch([() => route.params.id, () => route.params.market, () => route.params.chartType], ([newId, newMarket, newType]) => {
  let shouldReload = false;
  if (newId && newId !== stockId.value) {
    stockId.value = newId;
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
    const res = await stockApi.getChartData(stockId.value, period.value, months.value, market.value);
    if (res.success) {
      chartData.value = res.data;
    } else {
      error.value = '載入資料時發生未知錯誤';
    }
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || '連線後端 API 失敗';
  } finally {
    loading.value = false;
  }
}

function switchChartType(type) {
  // 使用 replace 避免堆疊瞬戒歷史
  router.replace({
    path: `/stock/${market.value}/${stockId.value}/chart/${type}`,
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
            params
              .filter((p) => p.seriesType === 'line' && p.data != null)
              .forEach((p) => {
                html += `<div>${p.marker}${p.seriesName}: ${p.data}</div>`;
              });
            return html;
          }
        },
        legend: { data: ma.names, top: 0, right: 0, itemWidth: 14, itemHeight: 8, textStyle: { fontSize: 11 } },
        dataZoom: dataZoomConfig,
        grid: { left: '3%', right: '4%', bottom: '15%', top: '12%', containLabel: true },
        xAxis: { type: 'category', data: d },
        yAxis: { type: 'value', scale: true },
        series: [
          {
            type: 'candlestick',
            data: kline,
            itemStyle: {
              color: upDown.value.up,
              color0: upDown.value.down,
              borderColor: upDown.value.up,
              borderColor0: upDown.value.down
            }
          },
          ...ma.series
        ]
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
</style>
