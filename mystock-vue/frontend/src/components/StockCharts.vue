<template>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
    <!-- 1. 三大法人買賣超 (張) -->
    <div @click="goToDetail('institutional')" class="card p-4 shadow-sm border border-surface-200 dark:border-surface-700 rounded-xl bg-surface-0 dark:bg-surface-900 cursor-pointer hover:border-primary/50 hover:shadow-md transition-all">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-4">
        <h3 class="text-lg font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
          <i class="pi pi-users text-primary"></i> 三大法人買賣超 (張)
        </h3>
        <span v-if="dateRangeText" class="text-xs font-semibold text-surface-600 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 px-2 py-0.5 rounded border border-surface-200 dark:border-surface-700">
          <i class="pi pi-calendar text-[10px] mr-1 text-primary"></i>{{ dateRangeText }}
        </span>
      </div>
      <v-chart class="chart-container" :option="institutionalOption" :update-options="{ notMerge: true }" autoforesize />
    </div>

    <!-- 2. K線圖 (Candlestick) -->
    <div @click="goToDetail('kline')" class="card p-4 shadow-sm border border-surface-200 dark:border-surface-700 rounded-xl bg-surface-0 dark:bg-surface-900 cursor-pointer hover:border-primary/50 hover:shadow-md transition-all">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-4">
        <h3 class="text-lg font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
          <i class="pi pi-chart-bar text-red-500"></i> K 線圖 (蠟燭圖)
        </h3>
        <span v-if="dateRangeText" class="text-xs font-semibold text-surface-600 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 px-2 py-0.5 rounded border border-surface-200 dark:border-surface-700">
          <i class="pi pi-calendar text-[10px] mr-1 text-red-500"></i>{{ dateRangeText }}
        </span>
      </div>
      <v-chart class="chart-container" :option="klineOption" :update-options="{ notMerge: true }" autoforesize />
    </div>

    <!-- 3. 估算買賣超金額 (萬元) -->
    <div @click="goToDetail('amount')" class="card p-4 shadow-sm border border-surface-200 dark:border-surface-700 rounded-xl bg-surface-0 dark:bg-surface-900 cursor-pointer hover:border-primary/50 hover:shadow-md transition-all">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-4">
        <h3 class="text-lg font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
          <i class="pi pi-dollar text-cyan-500"></i> 估算買賣超金額 (萬元)
        </h3>
        <span v-if="dateRangeText" class="text-xs font-semibold text-surface-600 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 px-2 py-0.5 rounded border border-surface-200 dark:border-surface-700">
          <i class="pi pi-calendar text-[10px] mr-1 text-cyan-500"></i>{{ dateRangeText }}
        </span>
      </div>
      <v-chart class="chart-container" :option="estimatedAmountOption" :update-options="{ notMerge: true }" autoforesize />
    </div>

    <!-- 4. 融資餘額 (張) -->
    <div @click="goToDetail('margin-long')" class="card p-4 shadow-sm border border-surface-200 dark:border-surface-700 rounded-xl bg-surface-0 dark:bg-surface-900 cursor-pointer hover:border-primary/50 hover:shadow-md transition-all">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-4">
        <h3 class="text-lg font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
          <i class="pi pi-chart-line text-pink-500"></i> 融資餘額 (張)
        </h3>
        <span v-if="dateRangeText" class="text-xs font-semibold text-surface-600 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 px-2 py-0.5 rounded border border-surface-200 dark:border-surface-700">
          <i class="pi pi-calendar text-[10px] mr-1 text-pink-500"></i>{{ dateRangeText }}
        </span>
      </div>
      <v-chart class="chart-container" :option="marginLongOption" :update-options="{ notMerge: true }" autoforesize />
    </div>

    <!-- 5. 融券餘額 (張) -->
    <div @click="goToDetail('margin-short')" class="card p-4 shadow-sm border border-surface-200 dark:border-surface-700 rounded-xl bg-surface-0 dark:bg-surface-900 cursor-pointer hover:border-primary/50 hover:shadow-md transition-all">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-4">
        <h3 class="text-lg font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
          <i class="pi pi-sort-alt text-emerald-500"></i> 融券餘額 (張)
        </h3>
        <span v-if="dateRangeText" class="text-xs font-semibold text-surface-600 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 px-2 py-0.5 rounded border border-surface-200 dark:border-surface-700">
          <i class="pi pi-calendar text-[10px] mr-1 text-emerald-500"></i>{{ dateRangeText }}
        </span>
      </div>
      <v-chart class="chart-container" :option="marginShortOption" :update-options="{ notMerge: true }" autoforesize />
    </div>

    <!-- 6. 券資比 (%) -->
    <div @click="goToDetail('short-ratio')" class="card p-4 shadow-sm border border-surface-200 dark:border-surface-700 rounded-xl bg-surface-0 dark:bg-surface-900 cursor-pointer hover:border-primary/50 hover:shadow-md transition-all">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-4">
        <h3 class="text-lg font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
          <i class="pi pi-percentage text-orange-500"></i> 券資比 (%)
        </h3>
        <span v-if="dateRangeText" class="text-xs font-semibold text-surface-600 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 px-2 py-0.5 rounded border border-surface-200 dark:border-surface-700">
          <i class="pi pi-calendar text-[10px] mr-1 text-orange-500"></i>{{ dateRangeText }}
        </span>
      </div>
      <v-chart class="chart-container" :option="shortRatioOption" :update-options="{ notMerge: true }" autoforesize />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
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

import { useRouter } from 'vue-router';

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

const router = useRouter();

const props = defineProps({
  chartData: {
    type: Object,
    required: true
  },
  stockId: String,
  period: String,
  months: Number
});

function goToDetail(chartType) {
  if (props.stockId) {
    router.push({
      path: `/stock/${props.stockId}/chart/${chartType}`,
      query: { period: props.period, months: props.months }
    });
  }
}

const dates = computed(() => props.chartData?.dates || []);

const dateRangeText = computed(() => {
  if (props.chartData?.start_date && props.chartData?.end_date) {
    return `${props.chartData.start_date} ~ ${props.chartData.end_date}`;
  }
  if (dates.value && dates.value.length > 0) {
    return `${dates.value[0]} ~ ${dates.value[dates.value.length - 1]}`;
  }
  return '';
});

// 1. 三大法人買賣超 Option
const institutionalOption = computed(() => {
  const inst = props.chartData?.institutional || {};
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['外資', '投信', '自營商', '合計'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: dates.value },
    yAxis: { type: 'value', name: '張' },
    series: [
      { name: '外資', type: 'bar', data: inst.foreign || [], itemStyle: { color: '#ef4444' } },
      { name: '投信', type: 'bar', data: inst.trust || [], itemStyle: { color: '#3b82f6' } },
      { name: '自營商', type: 'bar', data: inst.dealer || [], itemStyle: { color: '#f59e0b' } },
      { name: '合計', type: 'line', data: inst.total || [], itemStyle: { color: '#8b5cf6' }, lineStyle: { width: 3 } }
    ]
  };
});

// 2. K 線圖 (Candlestick) Option
const klineOption = computed(() => {
  const kline = props.chartData?.kline || [];
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
    grid: { left: '3%', right: '4%', bottom: '10%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: dates.value },
    yAxis: { type: 'value', scale: true },
    series: [
      {
        type: 'candlestick',
        data: kline,
        itemStyle: {
          color: '#ef4444',        // 陽線 (漲) - 紅
          color0: '#22c55e',       // 陰線 (跌) - 綠
          borderColor: '#ef4444',
          borderColor0: '#22c55e'
        }
      }
    ]
  };
});

// 3. 估算買賣超金額 Option
const estimatedAmountOption = computed(() => {
  const amounts = props.chartData?.institutional?.estimated_amount || [];
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '10%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: dates.value },
    yAxis: { type: 'value', name: '萬元' },
    series: [
      {
        name: '估算買賣超金額',
        type: 'line',
        data: amounts,
        smooth: true,
        itemStyle: { color: '#06b6d4' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(6, 182, 212, 0.4)' },
              { offset: 1, color: 'rgba(6, 182, 212, 0.0)' }
            ]
          }
        }
      }
    ]
  };
});

// 4. 融資餘額 Option
const marginLongOption = computed(() => {
  const longs = props.chartData?.margin?.long_balance || [];
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '10%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: dates.value },
    yAxis: { type: 'value', name: '張', scale: true },
    series: [
      {
        name: '融資餘額',
        type: 'line',
        data: longs,
        smooth: true,
        itemStyle: { color: '#ec4899' },
        lineStyle: { width: 3 }
      }
    ]
  };
});

// 5. 融券餘額 Option
const marginShortOption = computed(() => {
  const shorts = props.chartData?.margin?.short_balance || [];
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '10%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: dates.value },
    yAxis: { type: 'value', name: '張', scale: true },
    series: [
      {
        name: '融券餘額',
        type: 'line',
        data: shorts,
        smooth: true,
        itemStyle: { color: '#10b981' },
        lineStyle: { width: 3 }
      }
    ]
  };
});

// 6. 券資比 Option
const shortRatioOption = computed(() => {
  const ratios = props.chartData?.margin?.short_ratio || [];
  return {
    tooltip: { trigger: 'axis', formatter: '{b}<br/>券資比: {c}%' },
    grid: { left: '3%', right: '4%', bottom: '10%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: dates.value },
    yAxis: { type: 'value', name: '%', scale: true },
    series: [
      {
        name: '券資比',
        type: 'line',
        data: ratios,
        smooth: true,
        itemStyle: { color: '#f97316' },
        lineStyle: { width: 3 }
      }
    ]
  };
});
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: 320px;
}
</style>
