<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
      <div>
        <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-th-large text-primary text-2xl"></i>
          全市場個股動態熱力圖
        </h1>
        <p class="text-sm text-surface-500 mt-1 flex flex-wrap items-center gap-2">
          <span>點擊卡片深入檢視個股分析與籌碼動向</span>
          <span v-if="overallDateRange" class="px-2 py-0.5 text-xs font-semibold bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300 rounded-md border border-surface-200 dark:border-surface-700">
            <i class="pi pi-calendar text-xs mr-1 text-primary"></i>
            資料區間：{{ overallDateRange }} ({{ selectedPeriodLabel }})
          </span>
        </p>
      </div>

      <!-- 聚合週期切換 -->
      <div class="flex items-center gap-1 bg-surface-100 dark:bg-surface-800 p-1 rounded-lg border border-surface-200 dark:border-surface-700">
        <button 
          v-for="p in periods" 
          :key="p.value" 
          @click="setPeriod(p.value)"
          :class="[
            'px-3 py-1.5 text-xs font-bold rounded-md transition-colors',
            selectedPeriod === p.value 
              ? 'bg-primary text-primary-contrast shadow-sm' 
              : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
          ]"
        >
          {{ p.label }}
        </button>
      </div>
    </div>

    <!-- 載入中狀態 -->
    <div v-if="loading" class="flex flex-col items-center justify-center p-12 card bg-surface-0 dark:bg-surface-900 rounded-2xl border border-surface-200 dark:border-surface-700">
      <i class="pi pi-spin pi-spinner text-primary text-4xl mb-3"></i>
      <p class="text-sm font-semibold text-surface-600 dark:text-surface-400">加載股票熱力圖數據中...</p>
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

    <!-- 熱力圖網格 -->
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      <div 
        v-for="stock in stocks" 
        :key="stock.stock_id + '-' + selectedPeriod"
        @click="goToStock(stock.stock_id)"
        class="card p-4 rounded-xl border bg-surface-0 dark:bg-surface-900 shadow-sm cursor-pointer hover:-translate-y-1 hover:shadow-lg transition-all"
        :class="getCardBorderClass(stock)"
      >
        <div class="flex justify-between items-start mb-2">
          <div>
            <div class="flex items-center gap-1.5">
              <span class="text-lg font-bold text-surface-900 dark:text-surface-0">{{ stock.stock_name }}</span>
              <span class="px-1.5 py-0.5 text-[10px] font-bold bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300 rounded border border-surface-200 dark:border-surface-700">
                {{ selectedPeriodLabel }}
              </span>
            </div>
            <div class="text-xs text-surface-500 font-medium">{{ stock.stock_id }}</div>
          </div>
          <div class="text-right">
            <div class="text-lg font-black" :class="getPriceColorClass(stock)">${{ stock.latest_close.toFixed(2) }}</div>
            <div class="text-xs font-bold" :class="getPriceColorClass(stock)">
              {{ stock.change > 0 ? '+' : '' }}{{ stock.change.toFixed(2) }} 
              ({{ stock.change > 0 ? '+' : '' }}{{ stock.change_percent.toFixed(2) }}%)
            </div>
          </div>
        </div>
        
        <div class="h-16 mb-2">
          <v-chart :key="stock.stock_id + '-' + selectedPeriod" :option="getSparklineOption(stock)" :update-options="{ notMerge: true }" autoforesize />
        </div>
        
        <div class="flex items-center justify-between text-xs text-surface-500 border-t border-surface-100 dark:border-surface-800 pt-2">
          <span class="font-medium" title="資料起迄日期">
            <i class="pi pi-calendar text-[10px] mr-1 text-primary"></i>
            {{ stock.start_date ? stock.start_date + ' ~ ' + stock.end_date : stock.latest_date }}
          </span>
          <i class="pi pi-arrow-right" :class="getPriceColorClass(stock)"></i>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { stockApi } from '@/service/stockApi';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import VChart from 'vue-echarts';

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent]);

const router = useRouter();
const stocks = ref([]);
const loading = ref(true);
const error = ref(null);
const selectedPeriod = ref('daily');

const periods = [
  { label: '日線', value: 'daily' },
  { label: '週線', value: 'weekly' },
  { label: '月線', value: 'monthly' }
];

const selectedPeriodLabel = computed(() => {
  const p = periods.find(item => item.value === selectedPeriod.value);
  return p ? p.label : '';
});

const overallDateRange = computed(() => {
  if (!stocks.value || stocks.value.length === 0) return '';
  const startDates = stocks.value.map(s => s.start_date).filter(Boolean);
  const endDates = stocks.value.map(s => s.end_date || s.latest_date).filter(Boolean);
  if (!startDates.length || !endDates.length) return '';
  const earliest = startDates.slice().sort()[0];
  const latest = endDates.slice().sort().reverse()[0];
  return `${earliest} ~ ${latest}`;
});

onMounted(() => {
  loadHeatmapData();
});

async function loadHeatmapData() {
  loading.value = true;
  error.value = null;
  try {
    const res = await stockApi.getHeatmapData(selectedPeriod.value);
    if (res.success) {
      stocks.value = res.data;
    }
  } catch (err) {
    error.value = '無法載入股票熱力圖資料';
  } finally {
    loading.value = false;
  }
}

function setPeriod(p) {
  if (selectedPeriod.value === p) return;
  selectedPeriod.value = p;
  loadHeatmapData();
}

function goToStock(id) {
  router.push({
    path: `/stock/${id}`,
    query: { period: selectedPeriod.value }
  });
}

function getPriceColorClass(stock) {
  if (stock.change > 0) return 'text-red-500';
  if (stock.change < 0) return 'text-emerald-500';
  return 'text-surface-500';
}

function getCardBorderClass(stock) {
  if (stock.change > 0) return 'border-red-200 dark:border-red-900/50 hover:border-red-500';
  if (stock.change < 0) return 'border-emerald-200 dark:border-emerald-900/50 hover:border-emerald-500';
  return 'border-surface-200 dark:border-surface-700 hover:border-primary/50';
}

function getSparklineOption(stock) {
  const isUp = stock.change >= 0;
  const color = isUp ? '#ef4444' : '#10b981';
  
  return {
    grid: { left: 0, right: 0, top: 5, bottom: 5 },
    xAxis: { type: 'category', show: false, boundaryGap: false },
    yAxis: { type: 'value', show: false, min: 'dataMin', max: 'dataMax' },
    series: [
      {
        type: 'line',
        data: stock.sparkline,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 2, color: color },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: isUp ? 'rgba(239, 68, 68, 0.4)' : 'rgba(16, 185, 129, 0.4)' },
              { offset: 1, color: isUp ? 'rgba(239, 68, 68, 0.0)' : 'rgba(16, 185, 129, 0.0)' }
            ]
          }
        }
      }
    ]
  };
}
</script>
