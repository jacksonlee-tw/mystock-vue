<template>
  <div class="space-y-3">
    <!-- 日期區間只在此顯示一次 -->
    <div v-if="dateRangeText" class="flex justify-end">
      <span class="num text-xs font-semibold text-surface-600 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 px-2.5 py-1 rounded-lg border border-surface-200 dark:border-surface-700">
        <i class="pi pi-calendar text-[10px] mr-1 text-primary"></i>{{ dateRangeText }}
      </span>
    </div>

    <!-- 單一圖表舞台：一次只顯示一張圖，用上方頁籤切換或點選 KPI 卡（見 StockDashboard.vue）。
         所有圖表共用同一個固定高度容器，大小格式統一，不再逐張堆疊成長頁。 -->
    <div class="card shadow-sm border border-surface-200 dark:border-surface-700 rounded-xl bg-surface-0 dark:bg-surface-900 overflow-hidden">
      <div class="flex flex-wrap items-center gap-0.5 px-3 pt-2.5 pb-2 border-b border-surface-100 dark:border-surface-800 bg-surface-50/60 dark:bg-surface-800/30">
        <button
          v-for="w in availableWidgets"
          :key="w.id"
          :id="'widget-' + w.id"
          type="button"
          @click="activeId = w.id"
          :class="[
            'px-3 py-1.5 text-xs font-bold rounded-md flex items-center gap-1.5 transition-all duration-150',
            activeId === w.id
              ? 'bg-primary text-primary-contrast shadow-sm'
              : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
          ]"
        >
          <i :class="['pi', w.icon]"></i> {{ w.title }}
        </button>

        <!-- 放大：導去獨立的圖表明細頁（仍保留大圖檢視能力，只是不再是預設呈現方式） -->
        <button
          v-if="activeWidget?.route"
          type="button"
          @click="goToDetail(activeWidget.route)"
          class="ml-auto p-1.5 text-surface-400 hover:text-primary hover:bg-surface-100 dark:hover:bg-surface-800 rounded-md transition-colors"
          title="放大檢視此圖表"
        >
          <i class="pi pi-window-maximize text-xs"></i>
        </button>
      </div>

      <div class="p-4">
        <div v-if="activeId === 'kline'" class="flex items-center justify-end gap-3 text-[11px] font-semibold text-surface-500 mb-2">
          <span class="flex items-center gap-1"><i class="inline-block w-2 h-2 rounded-sm" :style="{ background: upDown.up }"></i>上漲</span>
          <span class="flex items-center gap-1"><i class="inline-block w-2 h-2 rounded-sm" :style="{ background: upDown.down }"></i>下跌</span>
        </div>

        <v-chart
          v-if="activeWidget && !activeWidget.emptyPlaceholder"
          class="chart-container-stage"
          :option="getOption(activeId)"
          :update-options="{ notMerge: true }"
          autoresize
        />
        <div v-else-if="activeWidget?.emptyPlaceholder" class="chart-container-stage flex items-center justify-center text-center text-surface-500 px-6">
          {{ activeWidget.emptyPlaceholder }}
        </div>

        <ChartExplanationBlock v-if="activeWidget && chartExplanations[activeId]" :explanation="chartExplanations[activeId]" />
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
  DataZoomComponent,
  MarkPointComponent
} from 'echarts/components';
import VChart from 'vue-echarts';

import { useRouter } from 'vue-router';
import { getUpDownColor } from '@/utils/marketColors';
import { buildMovingAverageSeries } from '@/utils/movingAverage';
import { chartExplanations } from '@/utils/chartExplanations';
import { directionVisual, formatDirectionLabel } from '@/utils/alertDirection';
import { alertApi } from '@/service/alertApi';
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
  MarkPointComponent
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
  market: String, // 'tw' | 'us'；未提供時 getUpDownColor 退回台股慣例
  modelValue: { type: String, default: null } // 目前顯示中的圖表 id（v-model，供父層 KPI 卡點選切換）
});

const emit = defineEmits(['update:modelValue']);

const upDown = computed(() => getUpDownColor(props.market));

// id 對應到 chartExplanations.js 的 key，兩邊要一致。panel 對應後端 meta.panels，
// 用來依市場（台股／美股）決定要顯示哪些頁籤——'always' 一律顯示。
const widgetDefinitions = [
  { id: 'kline', title: 'K 線圖 (蠟燭圖)', icon: 'pi-chart-bar', route: 'kline', panel: 'always' },
  { id: 'institutional', title: '三大法人買賣超', icon: 'pi-users', route: 'institutional', panel: 'institutional' },
  { id: 'amount', title: '估算買賣超金額', icon: 'pi-dollar', route: 'amount', panel: 'institutional' },
  { id: 'margin-long', title: '融資餘額', icon: 'pi-chart-line', route: 'margin-long', panel: 'margin' },
  { id: 'margin-short', title: '融券餘額', icon: 'pi-sort-alt', route: 'margin-short', panel: 'margin' },
  { id: 'short-ratio', title: '券資比', icon: 'pi-percentage', route: 'short-ratio', panel: 'margin' },
  { id: 'short', title: '空頭持倉', icon: 'pi-sort-alt', panel: 'short', emptyPlaceholder: '歷史空頭趨勢圖表即將支援' },
  { id: 'holders', title: '機構持股', icon: 'pi-users', panel: 'holders', emptyPlaceholder: '歷史機構持股趨勢圖表即將支援' }
];

const availableWidgets = computed(() => {
  const activePanels = props.chartData?.meta?.panels || ['institutional', 'margin'];
  return widgetDefinitions.filter((w) => w.panel === 'always' || activePanels.includes(w.panel));
});

// 目前顯示中的圖表：優先吃 v-model，若父層沒傳或傳了目前市場沒有的 id，退回第一個可用頁籤。
const activeId = computed({
  get() {
    if (props.modelValue && availableWidgets.value.some((w) => w.id === props.modelValue)) {
      return props.modelValue;
    }
    return availableWidgets.value[0]?.id || 'kline';
  },
  set(id) {
    emit('update:modelValue', id);
  }
});

const activeWidget = computed(() => availableWidgets.value.find((w) => w.id === activeId.value) || null);

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
  if (props.stockId && props.market) {
    router.push({
      path: `/stock/${props.market}/${props.stockId}/chart/${chartType}`,
      query: { period: props.period, months: props.months }
    });
  }
}

const dates = computed(() => props.chartData?.dates || []);

// K 線圖策略觸發標記（均線策略警示系統 設計文件第 9.2 節）。抓該檔近期警示，
// 疊在 candlestick series 上；抓不到（尚未掃描過、API 失敗等）不影響原本圖表渲染。
const stockAlerts = ref([]);

async function loadStockAlerts() {
  if (!props.stockId || !props.market) {
    stockAlerts.value = [];
    return;
  }
  try {
    const res = await alertApi.getAlerts({ symbol: props.stockId, market: props.market, days: 400 });
    stockAlerts.value = res.success ? res.data : [];
  } catch {
    stockAlerts.value = [];
  }
}

watch([() => props.stockId, () => props.market], loadStockAlerts, { immediate: true });

const alertMarkPoints = computed(() => {
  const dateIndex = new Map(dates.value.map((d, i) => [d, i]));
  return stockAlerts.value
    .filter((a) => dateIndex.has(a.trade_date))
    .map((a) => {
      const idx = dateIndex.get(a.trade_date);
      const candle = props.chartData?.kline?.[idx];
      const visual = directionVisual(a.direction);
      const bullish = visual.icon === 'pi-arrow-up';
      // markPoint 座標值只是用來把圖標定位在 K 棒之上/之下，不影響數值座標軸範圍
      const yValue = candle ? (bullish ? candle[3] : candle[2]) : null;
      return {
        name: `${a.strategy_name}：${formatDirectionLabel(a.direction)}`,
        coord: [idx, yValue],
        symbol: 'triangle',
        symbolRotate: bullish ? 0 : 180,
        symbolSize: 10,
        symbolOffset: [0, bullish ? -10 : 10],
        itemStyle: { color: bullish ? upDown.value.up : upDown.value.down }
      };
    })
    .filter((p) => p.coord[1] != null);
});

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
        const [openRaw, closeRaw, lowRaw, highRaw] = candle.data;
        const change = closeRaw - openRaw;
        const color = change >= 0 ? upDown.value.up : upDown.value.down;
        // 美股價格是原始浮點數（可能十幾位小數），統一只顯示到小數 2 位，避免撐爆 tooltip。
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
        },
        // 策略觸發標記（均線策略警示系統 設計文件第 9.2 節）：▲ 綠色=偏多方向，▼ 紅色=偏空方向
        markPoint: {
          symbolSize: 10,
          data: alertMarkPoints.value,
          tooltip: { trigger: 'item', formatter: (p) => p.name }
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
.chart-container-stage {
  width: 100%;
  height: 440px;
}
</style>
