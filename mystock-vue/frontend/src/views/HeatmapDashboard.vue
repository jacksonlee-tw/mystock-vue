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
    <div v-else class="space-y-8">
      <div v-for="category in categories" :key="category.name" v-show="category.stocks.length > 0">
        <h2 class="text-xl font-bold text-surface-900 dark:text-surface-0 mb-4 flex items-center gap-2">
          <i :class="['pi text-primary', category.icon]"></i>
          {{ category.name }}
        </h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          <div 
            v-for="stock in category.stocks" 
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
                  <span class="px-1.5 py-0.5 text-[10px] font-bold bg-primary text-primary-contrast rounded border border-primary">
                    {{ marketMeta.exchange }}
                  </span>
                </div>
                <div class="text-xs text-surface-500 font-medium">{{ stock.stock_id }}</div>
              </div>
              <div class="text-right">
                <div class="text-lg font-black" :class="getPriceColorClass(stock)">{{ marketMeta.currency_symbol }}{{ stock.latest_close.toFixed(2) }}</div>
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
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { stockApi } from '@/service/stockApi';
import { useMarket } from '@/composables/useMarket';
import { getUpDownColorFromCSS } from '@/utils/marketColors';
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

const etfStocks = computed(() => stocks.value.filter(isEtf));
const generalStocks = computed(() => stocks.value.filter(s => !isEtf(s)));

const categories = computed(() => [
  { name: 'ETF', icon: 'pi-chart-pie', stocks: etfStocks.value },
  { name: '一般個股', icon: 'pi-building', stocks: generalStocks.value }
]);

function isEtf(stock) {
  if (stock.market === 'tw') {
    // 台股 ETF 通常以 00 開頭
    return stock.stock_id.startsWith('00');
  } else if (stock.market === 'us') {
    // 美股常見 ETF 列表
    const usEtfs = ['SPY', 'QQQ', 'DIA', 'IWM', 'VOO', 'VTI', 'IVV', 'SOXX', 'ARKK', 'VT', 'VEA', 'VWO', 'BND', 'TQQQ', 'SQQQ'];
    return usEtfs.includes(stock.stock_id.toUpperCase());
  }
  return false;
}

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

const { currentMarket, marketMeta } = useMarket();

watch(currentMarket, () => {
  loadHeatmapData();
});

async function loadHeatmapData() {
  loading.value = true;
  error.value = null;
  try {
    const res = await stockApi.getHeatmapData(selectedPeriod.value, currentMarket.value);
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
    path: `/stock/${currentMarket.value}/${id}`,
    query: { period: selectedPeriod.value }
  });
}

function getPriceColorClass(stock) {
  if (stock.change > 0) return 'text-up';
  if (stock.change < 0) return 'text-down';
  return 'text-surface-500';
}

function getCardBorderClass(stock) {
  if (stock.change > 0) return 'border-up hover:border-up';
  if (stock.change < 0) return 'border-down hover:border-down';
  return 'border-surface-200 dark:border-surface-700 hover:border-primary/50';
}

function getSparklineOption(stock) {
  const isUp = stock.change >= 0;
  const { up, down } = getUpDownColorFromCSS();
  const color = isUp ? up : down;
  
  // ECharts 支援 rgba() 語法，但如果 up/down 變數是 HEX 色碼，
  // 我們可以簡單用 echarts 漸層，或者需要 HEX 轉 RGBA。
  // 為簡化，使用 color 加上 ECharts 內建 opacity 處理，
  // 或是自己寫個 hex to rgba，這裡偷懶直接用 colorStops 0.4 和 0。
  
  // 簡易 hexToRgba
  const hexToRgba = (hex, alpha) => {
    const r = parseInt(hex.slice(1, 3), 16) || 0;
    const g = parseInt(hex.slice(3, 5), 16) || 0;
    const b = parseInt(hex.slice(5, 7), 16) || 0;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };

  const color04 = color.startsWith('#') ? hexToRgba(color, 0.4) : color;
  const color00 = color.startsWith('#') ? hexToRgba(color, 0.0) : 'transparent';

  
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
              { offset: 0, color: color04 },
              { offset: 1, color: color00 }
            ]
          }
        }
      }
    ]
  };
}
</script>
