<template>
  <div class="space-y-4">
    <!-- 日期區間只在此顯示一次，不再逐張圖卡重複 -->
    <div v-if="dateRangeText" class="flex justify-end">
      <span class="num text-xs font-semibold text-surface-600 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 px-2.5 py-1 rounded-lg border border-surface-200 dark:border-surface-700">
        <i class="pi pi-calendar text-[10px] mr-1 text-primary"></i>{{ dateRangeText }}
      </span>
    </div>

    <!-- 主圖：K 線圖獨佔全寬，是本頁最重要的單一事實 -->
    <div class="card shadow-sm border border-surface-200 dark:border-surface-700 rounded-xl bg-surface-0 dark:bg-surface-900 overflow-hidden">
      <div
        @click="goToDetail('kline')"
        class="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b border-surface-100 dark:border-surface-800 cursor-pointer hover:bg-surface-50 dark:hover:bg-surface-800/40 transition-colors"
      >
        <h3 class="text-base font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
          <i class="pi pi-chart-bar text-surface-400"></i> K 線圖 (蠟燭圖)
        </h3>
        <div class="flex items-center gap-3 text-[11px] font-semibold text-surface-500">
          <span class="flex items-center gap-1"><i class="inline-block w-2 h-2 rounded-sm" :style="{ background: upDown.up }"></i>上漲</span>
          <span class="flex items-center gap-1"><i class="inline-block w-2 h-2 rounded-sm" :style="{ background: upDown.down }"></i>下跌</span>
        </div>
      </div>
      <div class="p-4">
        <v-chart class="chart-container-primary" :option="klineOption" :update-options="{ notMerge: true }" autoresize />
        <ChartExplanationBlock :explanation="chartExplanations.kline" />
      </div>
    </div>

    <!-- 次要籌碼圖表：分頁收納，避免與主圖搶視覺權重 -->
    <div class="card shadow-sm border border-surface-200 dark:border-surface-700 rounded-xl bg-surface-0 dark:bg-surface-900 overflow-hidden">
      <div class="flex items-center gap-1 px-3 pt-2.5 border-b border-surface-100 dark:border-surface-800 bg-surface-50/60 dark:bg-surface-800/30">
        <button
          v-for="t in tabs"
          :key="t.id"
          @click="activeTab = t.id"
          :class="[
            'px-3.5 py-2 text-sm font-bold rounded-t-lg flex items-center gap-1.5 border-b-2 -mb-px transition-colors',
            activeTab === t.id
              ? 'text-primary border-primary'
              : 'text-surface-500 border-transparent hover:text-surface-800 dark:hover:text-surface-200'
          ]"
        >
          <i :class="['pi', t.icon]"></i> {{ t.label }}
        </button>
      </div>

      <div class="p-4">
        <!-- 法人籌碼 -->
        <div v-if="activeTab === 'institutional'" class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div @click="goToDetail('institutional')" class="cursor-pointer group">
            <h4 class="text-sm font-bold text-surface-700 dark:text-surface-300 mb-2 flex items-center gap-1.5 group-hover:text-primary transition-colors">
              <i class="pi pi-users text-surface-400"></i> 三大法人買賣超 (張)
            </h4>
            <v-chart class="chart-container-sm" :option="institutionalOption" :update-options="{ notMerge: true }" autoresize />
            <ChartExplanationBlock :explanation="chartExplanations.institutional" compact @click.stop />
          </div>
          <div @click="goToDetail('amount')" class="cursor-pointer group">
            <h4 class="text-sm font-bold text-surface-700 dark:text-surface-300 mb-2 flex items-center gap-1.5 group-hover:text-primary transition-colors">
              <i class="pi pi-dollar text-surface-400"></i> 估算買賣超金額 (萬元)
            </h4>
            <v-chart class="chart-container-sm" :option="estimatedAmountOption" :update-options="{ notMerge: true }" autoresize />
            <ChartExplanationBlock :explanation="chartExplanations.amount" compact @click.stop />
          </div>
        </div>

        <!-- 信用交易 -->
        <div v-else-if="activeTab === 'margin'" class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div @click="goToDetail('margin-long')" class="cursor-pointer group">
            <h4 class="text-sm font-bold text-surface-700 dark:text-surface-300 mb-2 flex items-center gap-1.5 group-hover:text-primary transition-colors">
              <i class="pi pi-chart-line text-surface-400"></i> 融資餘額 (張)
            </h4>
            <v-chart class="chart-container-sm" :option="marginLongOption" :update-options="{ notMerge: true }" autoresize />
            <ChartExplanationBlock :explanation="chartExplanations['margin-long']" compact @click.stop />
          </div>
          <div @click="goToDetail('margin-short')" class="cursor-pointer group">
            <h4 class="text-sm font-bold text-surface-700 dark:text-surface-300 mb-2 flex items-center gap-1.5 group-hover:text-primary transition-colors">
              <i class="pi pi-sort-alt text-surface-400"></i> 融券餘額 (張)
            </h4>
            <v-chart class="chart-container-sm" :option="marginShortOption" :update-options="{ notMerge: true }" autoresize />
            <ChartExplanationBlock :explanation="chartExplanations['margin-short']" compact @click.stop />
          </div>
          <div @click="goToDetail('short-ratio')" class="cursor-pointer group md:col-span-2">
            <h4 class="text-sm font-bold text-surface-700 dark:text-surface-300 mb-2 flex items-center gap-1.5 group-hover:text-primary transition-colors">
              <i class="pi pi-percentage text-surface-400"></i> 券資比 (%)
            </h4>
            <v-chart class="chart-container-sm" :option="shortRatioOption" :update-options="{ notMerge: true }" autoresize />
            <ChartExplanationBlock :explanation="chartExplanations['short-ratio']" compact @click.stop />
          </div>
        </div>

        <!-- 空頭持倉 (美股) -->
        <div v-else-if="activeTab === 'short'" class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <!-- TODO: Empty placeholder since we only have latest summary for US right now, or we can just chart the flat line -->
          <div class="col-span-1 md:col-span-2 p-6 text-center text-surface-500">
            歷史空頭趨勢圖表即將支援
          </div>
        </div>

        <!-- 機構持股 (美股) -->
        <div v-else-if="activeTab === 'holders'" class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="col-span-1 md:col-span-2 p-6 text-center text-surface-500">
            歷史機構持股趨勢圖表即將支援
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
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

const panelLabels = {
  'institutional': { label: '法人籌碼', icon: 'pi-users' },
  'margin': { label: '信用交易', icon: 'pi-wallet' },
  'short': { label: '空頭持倉', icon: 'pi-sort-alt' },
  'holders': { label: '機構持股', icon: 'pi-users' }
};

const tabs = computed(() => {
  const panels = props.chartData?.meta?.panels || ['institutional', 'margin'];
  return panels
    .filter(p => p !== 'table' && panelLabels[p])
    .map(p => ({
      id: p,
      ...panelLabels[p]
    }));
});

const activeTab = ref(tabs.value.length > 0 ? tabs.value[0].id : 'institutional');

watch(tabs, (newTabs) => {
  if (newTabs.length > 0 && !newTabs.find(t => t.id === activeTab.value)) {
    activeTab.value = newTabs[0].id;
  }
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
  height: 420px;
}
.chart-container-sm {
  width: 100%;
  height: 260px;
}
</style>
