<template>
  <div class="space-y-4">
    <!-- 日期區間只在此顯示一次，不再逐張圖卡重複 -->
    <div v-if="dateRangeText" class="flex justify-end">
      <span class="num text-xs font-semibold text-surface-600 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 px-2.5 py-1 rounded-lg border border-surface-200 dark:border-surface-700">
        <i class="pi pi-calendar text-[10px] mr-1 text-primary"></i>{{ dateRangeText }}
      </span>
    </div>

    <!-- 儀表板拖曳網格 -->
    <draggable
      v-model="widgets"
      item-key="id"
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-4"
      handle=".drag-handle"
      animation="200"
    >
      <template #item="{ element }">
        <div :class="['card shadow-sm border border-surface-200 dark:border-surface-700 rounded-xl bg-surface-0 dark:bg-surface-900 overflow-hidden flex flex-col', element.colSpan || 'col-span-1']">
          <div
            class="flex items-center justify-between gap-2 px-4 py-3 border-b border-surface-100 dark:border-surface-800 bg-surface-50/60 dark:bg-surface-800/30"
          >
            <div class="flex items-center gap-2">
              <i class="pi pi-bars drag-handle cursor-move text-surface-400 hover:text-surface-600 transition-colors p-1 -ml-1"></i>
              <h3 
                class="text-sm font-bold text-surface-900 dark:text-surface-0 flex items-center gap-1.5 transition-colors"
                :class="{'cursor-pointer hover:text-primary': element.route}"
                @click="element.route ? goToDetail(element.route) : null"
              >
                <i :class="['pi', element.icon, 'text-surface-400']"></i> {{ element.title }}
              </h3>
            </div>
            
            <div v-if="element.id === 'kline'" class="flex items-center gap-3 text-[11px] font-semibold text-surface-500">
              <span class="flex items-center gap-1"><i class="inline-block w-2 h-2 rounded-sm" :style="{ background: upDown.up }"></i>上漲</span>
              <span class="flex items-center gap-1"><i class="inline-block w-2 h-2 rounded-sm" :style="{ background: upDown.down }"></i>下跌</span>
            </div>
          </div>
          
          <div class="p-4 flex-1 w-full min-w-0 overflow-hidden">
            <v-chart v-if="!element.emptyPlaceholder" :class="element.id === 'kline' ? 'chart-container-primary' : 'chart-container-sm'" :option="getOption(element.id)" :update-options="{ notMerge: true }" autoresize />
            <ChartExplanationBlock v-if="!element.emptyPlaceholder && chartExplanations[element.id]" :explanation="chartExplanations[element.id]" :compact="element.id !== 'kline'" />
            <div v-if="element.emptyPlaceholder" class="h-full flex items-center justify-center p-6 text-center text-surface-500">
              {{ element.emptyPlaceholder }}
            </div>
          </div>
        </div>
      </template>
    </draggable>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import draggable from 'vuedraggable';
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

const router = useRouter();

const props = defineProps({
  chartData: {
    type: Object,
    required: true
  },
  stockId: String,
  period: String,
  months: Number,
  market: String // 'tw' | 'us'；未提供時 getUpDownColor 退回台股慣例
});

const upDown = computed(() => getUpDownColor(props.market));

const widgetDefinitions = [
  { id: 'kline', title: 'K 線圖 (蠟燭圖)', icon: 'pi-chart-bar', colSpan: 'md:col-span-2 lg:col-span-2', route: 'kline', panel: 'always' },
  { id: 'institutional', title: '三大法人買賣超 (張)', icon: 'pi-users', route: 'institutional', panel: 'institutional' },
  { id: 'amount', title: '估算買賣超金額 (萬元)', icon: 'pi-dollar', route: 'amount', panel: 'institutional' },
  { id: 'margin-long', title: '融資餘額 (張)', icon: 'pi-chart-line', route: 'margin-long', panel: 'margin' },
  { id: 'margin-short', title: '融券餘額 (張)', icon: 'pi-sort-alt', route: 'margin-short', panel: 'margin' },
  { id: 'short-ratio', title: '券資比 (%)', icon: 'pi-percentage', route: 'short-ratio', colSpan: 'md:col-span-2 lg:col-span-2', panel: 'margin' },
  { id: 'short-us', title: '空頭持倉', icon: 'pi-sort-alt', panel: 'short', emptyPlaceholder: '歷史空頭趨勢圖表即將支援', colSpan: 'md:col-span-2 lg:col-span-2' },
  { id: 'holders-us', title: '機構持股', icon: 'pi-users', panel: 'holders', emptyPlaceholder: '歷史機構持股趨勢圖表即將支援', colSpan: 'md:col-span-2 lg:col-span-2' }
];

const widgets = ref([]);
const LOCAL_STORAGE_KEY = 'mystock_dashboard_layout';

function initWidgets() {
  const activePanels = props.chartData?.meta?.panels || ['institutional', 'margin'];
  const allowedWidgets = widgetDefinitions.filter(w => w.panel === 'always' || activePanels.includes(w.panel));
  
  const savedOrder = localStorage.getItem(LOCAL_STORAGE_KEY);
  let orderIds = [];
  try {
    if (savedOrder) orderIds = JSON.parse(savedOrder);
  } catch (e) {}

  let ordered = [];
  if (orderIds && orderIds.length > 0) {
    orderIds.forEach(id => {
      const w = allowedWidgets.find(x => x.id === id);
      if (w) ordered.push(w);
    });
    allowedWidgets.forEach(w => {
      if (!ordered.find(x => x.id === w.id)) ordered.push(w);
    });
  } else {
    ordered = [...allowedWidgets];
  }
  widgets.value = ordered;
}

watch(() => props.chartData?.meta?.panels, () => {
  initWidgets();
}, { immediate: true });

watch(widgets, (newVal) => {
  const orderIds = newVal.map(w => w.id);
  localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(orderIds));
}, { deep: true });

function getOption(id) {
  switch (id) {
    case 'kline': return klineOption.value;
    case 'institutional': return institutionalOption.value;
    case 'amount': return estimatedAmountOption.value;
    case 'margin-long': return marginLongOption.value;
    case 'margin-short': return marginShortOption.value;
    case 'short-ratio': return shortRatioOption.value;
    default: return null;
  }
}

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

// 三大法人買賣超 Option
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

// K 線圖 (Candlestick) Option ── 疊加 5/20/60 期均線，標籤依目前聚合週期顯示「日/週/月均線」
const klineOption = computed(() => {
  const kline = props.chartData?.kline || [];
  const ma = buildMovingAverageSeries(kline, props.period);
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params) => {
        const candle = params.find((p) => p.seriesType === 'candlestick') || params[0];
        if (!candle || !candle.data) return '';
        const date = candle.name;
        const [open, close, low, high] = candle.data;
        const change = close - open;
        const color = change >= 0 ? upDown.value.up : upDown.value.down;
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
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, height: 18, bottom: 4 }
    ],
    grid: { left: '3%', right: '4%', bottom: '14%', top: '12%', containLabel: true },
    xAxis: { type: 'category', data: dates.value },
    yAxis: { type: 'value', scale: true },
    series: [
      {
        type: 'candlestick',
        data: kline,
        itemStyle: {
          color: upDown.value.up, // 陽線 (漲)
          color0: upDown.value.down, // 陰線 (跌)
          borderColor: upDown.value.up,
          borderColor0: upDown.value.down
        }
      },
      ...ma.series
    ]
  };
});

// 估算買賣超金額 Option
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

// 融資餘額 Option
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

// 融券餘額 Option
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

// 券資比 Option
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
.chart-container-primary {
  width: 100%;
  height: 320px;
}
.chart-container-sm {
  width: 100%;
  height: 260px;
}
</style>
