<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <!-- 頂部導覽與控制列 -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div class="flex flex-col md:flex-row items-start md:items-center gap-4">
        <!-- 返回按鈕群 -->
        <div class="flex items-center gap-2">
          <button 
            @click="router.push('/')" 
            class="px-3 py-1.5 text-xs font-bold bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-lg flex items-center gap-1.5 transition-colors shadow-sm"
          >
            <i class="pi pi-home"></i> 熱力圖
          </button>
          <button 
            @click="router.push(`/stock/${stockId}`)" 
            class="px-3 py-1.5 text-xs font-bold bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-lg flex items-center gap-1.5 transition-colors shadow-sm"
          >
            <i class="pi pi-arrow-left"></i> 返回個股儀表板
          </button>
        </div>
        <div>
          <h1 class="text-xl font-black text-surface-900 dark:text-surface-0 flex flex-wrap items-center gap-2">
            <span>{{ stockId }} <span v-if="stockName" class="text-primary">{{ stockName }}</span> 圖表明細</span>
            <span v-if="dateRangeText" class="px-2.5 py-0.5 text-xs font-bold bg-primary-50 dark:bg-primary-900/30 text-primary rounded-md border border-primary/20">
              <i class="pi pi-calendar mr-1"></i> {{ dateRangeText }}
            </span>
          </h1>
        </div>
      </div>

      <!-- 切換圖表類型 (Tab) -->
      <div class="flex flex-wrap items-center gap-1 bg-surface-100 dark:bg-surface-800 p-1 rounded-lg border border-surface-200 dark:border-surface-700">
        <button 
          v-for="tab in chartTabs" 
          :key="tab.value" 
          @click="switchChartType(tab.value)"
          :class="[
            'px-3 py-1.5 text-xs font-bold rounded-md transition-colors',
            chartType === tab.value 
              ? 'bg-primary text-primary-contrast shadow-sm' 
              : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
          ]"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

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
          <i :class="['pi', currentTabInfo?.icon, currentTabInfo?.colorClass]"></i>
          {{ currentTabInfo?.label }}
        </h3>
        <span v-if="dateRangeText" class="text-xs font-semibold text-surface-600 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 px-3 py-1 rounded-lg border border-surface-200 dark:border-surface-700">
          <i class="pi pi-calendar text-xs mr-1 text-primary"></i>資料區間：{{ dateRangeText }}
        </span>
      </div>
      <v-chart class="chart-container-large" :option="currentChartOption" :update-options="{ notMerge: true }" autoforesize />
    </div>
  </div>
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
const chartType = ref(route.params.chartType || 'institutional');
const period = ref(route.query.period || 'daily');
const months = ref(Number(route.query.months) || 3);

const loading = ref(true);
const error = ref(null);
const chartData = ref(null);

const chartTabs = [
  { value: 'institutional', label: '三大法人', icon: 'pi-users', colorClass: 'text-primary' },
  { value: 'kline', label: 'K線圖', icon: 'pi-chart-bar', colorClass: 'text-red-500' },
  { value: 'amount', label: '估算金額', icon: 'pi-dollar', colorClass: 'text-cyan-500' },
  { value: 'margin-long', label: '融資餘額', icon: 'pi-chart-line', colorClass: 'text-pink-500' },
  { value: 'margin-short', label: '融券餘額', icon: 'pi-sort-alt', colorClass: 'text-emerald-500' },
  { value: 'short-ratio', label: '券資比', icon: 'pi-percentage', colorClass: 'text-orange-500' }
];

const currentTabInfo = computed(() => chartTabs.find(t => t.value === chartType.value));
const dates = computed(() => chartData.value?.dates || []);
const stockName = computed(() => chartData.value?.stock_name || '');

const dateRangeText = computed(() => {
  if (chartData.value?.start_date && chartData.value?.end_date) {
    return `${chartData.value.start_date} ~ ${chartData.value.end_date}`;
  }
  if (dates.value && dates.value.length > 0) {
    return `${dates.value[0]} ~ ${dates.value[dates.value.length - 1]}`;
  }
  return '';
});

onMounted(() => {
  loadStockData();
});

watch([() => route.params.id, () => route.params.chartType], ([newId, newType]) => {
  if (newId && newId !== stockId.value) {
    stockId.value = newId;
    loadStockData();
  }
  if (newType && newType !== chartType.value) {
    chartType.value = newType;
  }
});

async function loadStockData() {
  loading.value = true;
  error.value = null;
  try {
    const res = await stockApi.getChartData(stockId.value, period.value, months.value);
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
  router.push({
    path: `/stock/${stockId.value}/chart/${type}`,
    query: { period: period.value, months: months.value }
  });
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
          { name: '外資', type: 'bar', data: inst.foreign || [], itemStyle: { color: '#ef4444' } },
          { name: '投信', type: 'bar', data: inst.trust || [], itemStyle: { color: '#3b82f6' } },
          { name: '自營商', type: 'bar', data: inst.dealer || [], itemStyle: { color: '#f59e0b' } },
          { name: '合計', type: 'line', data: inst.total || [], itemStyle: { color: '#8b5cf6' }, lineStyle: { width: 3 } }
        ]
      };
    case 'kline':
      const kline = chartData.value?.kline || [];
      return {
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' },
          formatter: (params) => {
            const param = params[0];
            if (!param || !param.data) return '';
            const date = param.name;
            const [open, close, low, high] = param.data;
            const change = close - open;
            const color = change >= 0 ? '#ef4444' : '#22c55e';
            return `
              <div class="font-bold">${date}</div>
              <div>開盤價: <span style="color:${color}">${open}</span></div>
              <div>最高價: <span style="color:${color}">${high}</span></div>
              <div>最低價: <span style="color:${color}">${low}</span></div>
              <div>收盤價: <span style="color:${color}">${close}</span> (${change >= 0 ? '+' : ''}${change.toFixed(2)})</div>
            `;
          }
        },
        dataZoom: dataZoomConfig,
        grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
        xAxis: { type: 'category', data: d },
        yAxis: { type: 'value', scale: true },
        series: [
          {
            type: 'candlestick',
            data: kline,
            itemStyle: { color: '#ef4444', color0: '#22c55e', borderColor: '#ef4444', borderColor0: '#22c55e' }
          }
        ]
      };
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
            name: '估算買賣超金額', type: 'line', data: amounts, smooth: true, itemStyle: { color: '#06b6d4' },
            areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(6, 182, 212, 0.4)' }, { offset: 1, color: 'rgba(6, 182, 212, 0.0)' }] } }
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
        series: [{ name: '融資餘額', type: 'line', data: longs, smooth: true, itemStyle: { color: '#ec4899' }, lineStyle: { width: 3 } }]
      };
    case 'margin-short':
      const shorts = chartData.value?.margin?.short_balance || [];
      return {
        tooltip: { trigger: 'axis' },
        dataZoom: dataZoomConfig,
        grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
        xAxis: { type: 'category', data: d },
        yAxis: { type: 'value', name: '張', scale: true },
        series: [{ name: '融券餘額', type: 'line', data: shorts, smooth: true, itemStyle: { color: '#10b981' }, lineStyle: { width: 3 } }]
      };
    case 'short-ratio':
      const ratios = chartData.value?.margin?.short_ratio || [];
      return {
        tooltip: { trigger: 'axis', formatter: '{b}<br/>券資比: {c}%' },
        dataZoom: dataZoomConfig,
        grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
        xAxis: { type: 'category', data: d },
        yAxis: { type: 'value', name: '%', scale: true },
        series: [{ name: '券資比', type: 'line', data: ratios, smooth: true, itemStyle: { color: '#f97316' }, lineStyle: { width: 3 } }]
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
