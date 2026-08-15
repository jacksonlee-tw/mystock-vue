<template>
  <div class="card shadow-sm border border-surface-200 dark:border-surface-700 rounded-xl bg-surface-0 dark:bg-surface-900 overflow-hidden">
    <div class="flex flex-wrap items-center justify-between gap-3 px-4 pt-3 pb-2 border-b border-surface-100 dark:border-surface-800 bg-surface-50/60 dark:bg-surface-800/30">
      <h3 class="font-bold text-sm text-surface-700 dark:text-surface-300 flex items-center gap-2">
        <i class="pi pi-chart-line text-primary"></i> {{ stockId }} vs 大盤（Rebase = 100）
      </h3>
      <Select
        v-if="market === 'us'"
        v-model="benchmark"
        :options="usBenchmarks"
        optionLabel="label"
        optionValue="code"
        class="w-40 text-xs"
      />
      <span v-else class="text-xs font-bold text-surface-500">基準：加權指數 (TWII)</span>
    </div>

    <div class="p-4">
      <div v-if="loading" class="text-center text-sm text-surface-400 py-10">
        <i class="pi pi-spin pi-spinner mr-1"></i> 載入比較資料中...
      </div>
      <div v-else-if="error" class="text-center text-sm text-red-500 py-10">{{ error }}</div>
      <template v-else-if="result">
        <div class="flex items-center gap-4 mb-2 text-xs font-bold">
          <span :style="{ color: PALETTE[0] }">超額報酬（相對大盤）：</span>
          <span :style="{ color: alpha >= 0 ? upColor : downColor }">{{ alpha >= 0 ? '+' : '' }}{{ alpha.toFixed(2) }}%</span>
        </div>
        <v-chart class="vs-index-chart-stage" :option="chartOption" :update-options="{ notMerge: true }" autoresize />
        <ChartExplanationBlock :explanation="chartExplanations['vs-index']" />
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import Select from 'primevue/select';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart } from 'echarts/charts';
import { TooltipComponent, LegendComponent, GridComponent, DataZoomComponent } from 'echarts/components';
import VChart from 'vue-echarts';
import { stockApi } from '@/service/stockApi';
import { getUpDownColor } from '@/utils/marketColors';
import { chartExplanations } from '@/utils/chartExplanations';
import ChartExplanationBlock from '@/components/ChartExplanationBlock.vue';

use([CanvasRenderer, LineChart, TooltipComponent, LegendComponent, GridComponent, DataZoomComponent]);

const props = defineProps({
  stockId: { type: String, required: true },
  market: { type: String, required: true },
  period: { type: String, default: 'daily' },
  months: { type: Number, default: 12 }
});

const usBenchmarks = [
  { label: 'S&P 500', code: 'GSPC' },
  { label: '道瓊', code: 'DJI' },
  { label: '那斯達克', code: 'IXIC' },
  { label: '費城半導體', code: 'SOX' }
];

const benchmark = ref('GSPC');
const result = ref(null);
const loading = ref(false);
const error = ref(null);

const upDown = computed(() => getUpDownColor(props.market));
const upColor = computed(() => upDown.value.up);
const downColor = computed(() => upDown.value.down);

const PALETTE = ['#3b82f6', '#94a3b8'];

// Alpha（超額報酬）＝個股 rebase 終值 - 大盤 rebase 終值（兩者皆以同一起點為 100 的簡化版，
// 非嚴謹的 Jensen's Alpha 迴歸計算——規劃書 §6 保留給投資組合績效模組做完整版）。
const alpha = computed(() => {
  if (!result.value) return 0;
  const stockSeries = result.value.series[props.stockId] || [];
  const benchSeries = result.value.series[benchmarkCode.value] || [];
  const lastValid = (arr) => {
    for (let i = arr.length - 1; i >= 0; i--) {
      if (arr[i] != null) return arr[i];
    }
    return null;
  };
  const s = lastValid(stockSeries);
  const b = lastValid(benchSeries);
  if (s == null || b == null) return 0;
  return s - b;
});

const benchmarkCode = computed(() => (props.market === 'us' ? benchmark.value : 'TWII'));

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const res = await stockApi.getVsIndex(props.stockId, props.market, benchmarkCode.value, props.period, props.months);
    if (res.success) {
      result.value = res.data;
    } else {
      error.value = '載入比較資料失敗';
    }
  } catch (err) {
    error.value = err.response?.data?.error?.message || err.response?.data?.detail || '載入比較資料失敗（可能該市場尚無對應基準指數資料）';
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch([() => props.stockId, () => props.market, () => props.period, () => props.months, benchmark], load);

const chartOption = computed(() => {
  const data = result.value;
  if (!data) return {};
  const codes = Object.keys(data.series);
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: codes.map((c) => data.labels[c] || c), top: 0 },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, height: 16, bottom: 4 }
    ],
    grid: { left: '3%', right: '4%', bottom: '18%', top: '15%', containLabel: true },
    xAxis: { type: 'category', data: data.dates },
    yAxis: { type: 'value', name: '相對報酬 (基期=100)', scale: true },
    series: codes.map((code, idx) => ({
      name: data.labels[code] || code,
      type: 'line',
      data: data.series[code],
      showSymbol: false,
      connectNulls: false,
      itemStyle: { color: PALETTE[idx % PALETTE.length] },
      lineStyle: { width: code === props.stockId ? 3 : 2 }
    }))
  };
});
</script>

<style scoped>
.vs-index-chart-stage {
  width: 100%;
  height: 340px;
}
</style>
