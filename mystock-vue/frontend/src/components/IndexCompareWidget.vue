<template>
  <div class="card shadow-sm border border-surface-200 dark:border-surface-700 rounded-xl bg-surface-0 dark:bg-surface-900 overflow-hidden">
    <div class="flex flex-wrap items-center justify-between gap-3 px-4 pt-3 pb-2 border-b border-surface-100 dark:border-surface-800 bg-surface-50/60 dark:bg-surface-800/30">
      <h3 class="font-bold text-sm text-surface-700 dark:text-surface-300 flex items-center gap-2">
        <i class="pi pi-sliders-h text-primary"></i> 多指數比較（Rebase = 100）
      </h3>
      <MultiSelect
        v-model="selectedCodes"
        :options="pickableIndices"
        optionLabel="name"
        optionValue="code"
        placeholder="選擇要疊加比較的指數..."
        display="chip"
        class="w-72 text-xs"
      />
    </div>

    <div class="p-4">
      <div v-if="!selectedCodes.length" class="text-center text-sm text-surface-400 py-10">
        選擇至少一檔其他指數即可疊圖比較相對報酬率
      </div>
      <div v-else-if="loading" class="text-center text-sm text-surface-400 py-10">
        <i class="pi pi-spin pi-spinner mr-1"></i> 載入比較資料中...
      </div>
      <div v-else-if="error" class="text-center text-sm text-red-500 py-10">{{ error }}</div>
      <v-chart v-else class="compare-chart-stage" :option="compareOption" :update-options="{ notMerge: true }" autoresize />

      <ChartExplanationBlock v-if="selectedCodes.length && !loading && !error" :explanation="chartExplanations['index-compare']" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import MultiSelect from 'primevue/multiselect';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart } from 'echarts/charts';
import { TooltipComponent, LegendComponent, GridComponent, DataZoomComponent } from 'echarts/components';
import VChart from 'vue-echarts';
import { indexApi } from '@/service/indexApi';
import { chartExplanations } from '@/utils/chartExplanations';
import ChartExplanationBlock from '@/components/ChartExplanationBlock.vue';

use([CanvasRenderer, LineChart, TooltipComponent, LegendComponent, GridComponent, DataZoomComponent]);

const props = defineProps({
  baseCode: { type: String, required: true },
  baseMarket: { type: String, required: true },
  period: { type: String, default: 'daily' },
  months: { type: Number, default: 12 }
});

const allIndices = ref([]);
const selectedCodes = ref([]);
const compareResult = ref(null);
const loading = ref(false);
const error = ref(null);

// 下拉選單排除目前正在看的這檔指數本身，不然「拿自己跟自己比」沒有意義
const pickableIndices = computed(() => allIndices.value.filter((i) => i.code !== props.baseCode));

onMounted(async () => {
  try {
    const res = await indexApi.getIndices();
    if (res.success) allIndices.value = res.data.map((d) => ({ code: d.stock_id, name: `${d.stock_id} ${d.stock_name}` }));
  } catch (err) {
    // 靜默失敗：只影響下拉選單是否有選項，不影響頁面其他部分
  }
});

async function loadCompare() {
  if (!selectedCodes.value.length) {
    compareResult.value = null;
    return;
  }
  loading.value = true;
  error.value = null;
  try {
    const res = await indexApi.compare([props.baseCode, ...selectedCodes.value], props.period, props.months);
    if (res.success) {
      compareResult.value = res.data;
    } else {
      error.value = '載入比較資料失敗';
    }
  } catch (err) {
    error.value = err.response?.data?.error?.message || err.response?.data?.detail || '載入比較資料失敗';
  } finally {
    loading.value = false;
  }
}

watch(selectedCodes, loadCompare);
watch([() => props.period, () => props.months, () => props.baseCode], () => {
  if (selectedCodes.value.length) loadCompare();
});

const PALETTE = ['#3b82f6', '#f59e0b', '#10b981', '#ec4899', '#8b5cf6', '#06b6d4'];

const compareOption = computed(() => {
  const data = compareResult.value;
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
      lineStyle: { width: code === props.baseCode ? 3 : 2 }
    }))
  };
});
</script>

<style scoped>
.compare-chart-stage {
  width: 100%;
  height: 380px;
}
</style>
