<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
      <div>
        <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-sync text-primary text-2xl"></i>
          台股類股輪動
        </h1>
        <p class="text-sm text-surface-500 mt-1">依當日漲跌幅排序，觀察資金往哪個板塊集中（大盤指數功能規劃書 FR-IDX-30/31）</p>
      </div>
      <button
        @click="router.push('/')"
        class="px-3 py-1.5 text-xs font-bold bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-lg flex items-center gap-1.5 transition-colors shrink-0 self-start"
      >
        <i class="pi pi-home"></i> 回熱力圖
      </button>
    </div>

    <div v-if="loading" class="flex flex-col items-center justify-center p-12 card bg-surface-0 dark:bg-surface-900 rounded-2xl border border-surface-200 dark:border-surface-700">
      <i class="pi pi-spin pi-spinner text-primary text-4xl mb-3"></i>
      <p class="text-sm font-semibold text-surface-600 dark:text-surface-400">載入類股輪動資料中...</p>
    </div>

    <div v-else-if="error" class="card p-6 border border-red-300 bg-red-50 dark:bg-red-900/20 rounded-2xl text-red-700 dark:text-red-300">
      <div class="flex items-center gap-3">
        <i class="pi pi-exclamation-circle text-2xl"></i>
        <div>
          <h4 class="font-bold">資料讀取失敗</h4>
          <p class="text-sm mt-0.5">{{ error }}</p>
        </div>
      </div>
    </div>

    <div v-else-if="!withData.length" class="card p-8 text-center text-surface-500 rounded-2xl border border-surface-200 dark:border-surface-700">
      <i class="pi pi-info-circle text-3xl mb-2 block"></i>
      類股指數資料尚未累積（每日快照，需等排程執行過至少一次）。
    </div>

    <template v-else>
      <!-- 橫向排行 Bar（FR-IDX-30） -->
      <div class="card p-4 rounded-2xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
        <v-chart class="rank-chart-stage" :option="rankOption" :update-options="{ notMerge: true }" autoresize @click="onBarClick" />
      </div>

      <!-- 輪動熱力圖網格（FR-IDX-31）：重用個股熱力圖的卡片版型概念 -->
      <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        <div
          v-for="sector in withData"
          :key="sector.stock_id"
          @click="goToSector(sector)"
          class="card p-4 rounded-xl border bg-surface-0 dark:bg-surface-900 shadow-sm cursor-pointer hover:-translate-y-1 hover:shadow-lg transition-all"
          :class="getCardBorderClass(sector)"
        >
          <div class="flex justify-between items-start mb-2">
            <div>
              <span class="text-base font-bold text-surface-900 dark:text-surface-0">{{ sector.stock_name }}</span>
              <div class="text-xs text-surface-500 font-medium">{{ sector.industry_code }}</div>
            </div>
            <div class="text-right">
              <div class="num text-lg font-black" :class="getPriceColorClass(sector)">{{ formatIndexValue(sector.latest_close) }}</div>
              <div class="num text-xs font-bold" :class="getPriceColorClass(sector)">
                {{ sector.change_percent > 0 ? '+' : '' }}{{ sector.change_percent.toFixed(2) }}%
              </div>
            </div>
          </div>
          <div class="h-12">
            <v-chart :option="getSparklineOption(sector)" :update-options="{ notMerge: true }" autoresize />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { indexApi } from '@/service/indexApi';
import { getUpDownColorFromCSS } from '@/utils/marketColors';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart, LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import VChart from 'vue-echarts';

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent]);

const router = useRouter();
const sectors = ref([]);
const loading = ref(true);
const error = ref(null);

const withData = computed(() => sectors.value.filter((s) => s.has_data));

onMounted(async () => {
  try {
    const res = await indexApi.getSectors('tw');
    if (res.success) sectors.value = res.data;
  } catch (err) {
    error.value = '無法載入類股輪動資料';
  } finally {
    loading.value = false;
  }
});

function formatIndexValue(value) {
  return Number(value).toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function getPriceColorClass(s) {
  if (s.change > 0) return 'text-up';
  if (s.change < 0) return 'text-down';
  return 'text-surface-500';
}

function getCardBorderClass(s) {
  if (s.change > 0) return 'border-up hover:border-up';
  if (s.change < 0) return 'border-down hover:border-down';
  return 'border-surface-200 dark:border-surface-700 hover:border-primary/50';
}

function goToSector(sector) {
  router.push(`/index/tw/${sector.stock_id}`);
}

function getSparklineOption(sector) {
  const isUp = sector.change >= 0;
  const { up, down } = getUpDownColorFromCSS();
  const color = isUp ? up : down;
  return {
    grid: { left: 0, right: 0, top: 4, bottom: 4 },
    xAxis: { type: 'category', show: false, boundaryGap: false },
    yAxis: { type: 'value', show: false, min: 'dataMin', max: 'dataMax' },
    series: [{ type: 'line', data: sector.sparkline, showSymbol: false, smooth: true, lineStyle: { width: 2, color } }]
  };
}

// 排行 Bar：依漲跌幅排序（後端已排序，這裡直接沿用順序）
const rankOption = computed(() => {
  const list = withData.value;
  const { up, down } = getUpDownColorFromCSS();
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '6%', bottom: '3%', top: '3%', containLabel: true },
    xAxis: { type: 'value', name: '漲跌幅 %' },
    yAxis: { type: 'category', data: list.map((s) => s.stock_name).reverse(), axisLabel: { fontSize: 11 } },
    series: [
      {
        type: 'bar',
        data: list.map((s) => ({ value: s.change_percent, itemStyle: { color: s.change_percent >= 0 ? up : down } })).reverse(),
        barMaxWidth: 16
      }
    ]
  };
});

function onBarClick(params) {
  const list = [...withData.value].reverse();
  const sector = list[params.dataIndex];
  if (sector) goToSector(sector);
}
</script>

<style scoped>
.rank-chart-stage {
  width: 100%;
  height: 720px;
}
</style>
