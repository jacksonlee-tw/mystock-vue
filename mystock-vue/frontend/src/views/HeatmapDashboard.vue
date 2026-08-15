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
            @click="goToItem(stock)"
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
                  <span
                    class="px-1.5 py-0.5 text-[10px] font-bold rounded border"
                    :class="stock.is_index
                      ? 'bg-amber-500 text-white border-amber-500'
                      : 'bg-primary text-primary-contrast border-primary'"
                  >
                    {{ stock.is_index ? '指數' : marketMeta.exchange }}
                  </span>
                </div>
                <div class="text-xs text-surface-500 font-medium">{{ stock.stock_id }}</div>
              </div>
              <div class="text-right">
                <div class="text-lg font-black" :class="getPriceColorClass(stock)">
                  <span v-if="!stock.is_index">{{ marketMeta.currency_symbol }}</span>{{ formatCardPrice(stock.latest_close) }}
                </div>
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
import { indexApi } from '@/service/indexApi';
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
const indexOverview = ref([]); // 指數分類資料（/api/v1/indices/overview），與個股清單分開抓取
const industries = ref({}); // 產業標籤對照表（/api/v1/stocks/industries，大盤指數功能規劃書 §8.2）
const loading = ref(true);
const error = ref(null);
const selectedPeriod = ref('daily');

const etfStocks = computed(() => stocks.value.filter(isEtf));
const generalStocks = computed(() => stocks.value.filter(s => !isEtf(s)));
// 尚未抓過資料的指數（has_data === false）不顯示卡片，比照個股熱力圖「沒資料就整檔略過」的既有慣例，
// 避免出現一張空 Sparkline 的壞卡片（見大盤指數功能規劃書 ADR-I8／services/index_service.py 的註解）。
const indexStocks = computed(() => indexOverview.value.filter(s => s.has_data !== false));

// 一般個股依產業分組（大盤指數功能規劃書 §8.2）：查不到產業標籤的股票（例如尚未跑過
// scripts/init_industries.py，或美股未在追蹤清單內時抓不到 sector）歸類到「未分類」，
// 而不是整個功能因為缺資料而不顯示——分組是錦上添花，缺資料不該讓熱力圖本體不能用。
const generalStocksByIndustry = computed(() => {
  const groups = new Map();
  for (const stock of generalStocks.value) {
    const info = industries.value[stock.stock_id];
    const name = info?.industry_name || '未分類';
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(stock);
  }
  // 未分類排最後，其餘依股數多到少排序，方便先看規模大的產業
  const entries = [...groups.entries()];
  entries.sort((a, b) => {
    if (a[0] === '未分類') return 1;
    if (b[0] === '未分類') return -1;
    return b[1].length - a[1].length;
  });
  return entries.map(([name, list]) => ({ name, icon: 'pi-building', stocks: list }));
});

// 指數放在最前面：先看大盤，再看 ETF，最後才是依產業分組的一般個股（見大盤指數功能規劃書 §5.2/§8.2）。
// 產業對照表尚未載入或全查不到資料時，退回單一「一般個股」分類，不讓分組邏輯阻擋既有行為。
const categories = computed(() => {
  const hasIndustryData = Object.keys(industries.value).length > 0;
  const generalCategories = hasIndustryData
    ? generalStocksByIndustry.value
    : [{ name: '一般個股', icon: 'pi-building', stocks: generalStocks.value }];

  return [
    { name: '指數', icon: 'pi-globe', stocks: indexStocks.value },
    { name: 'ETF', icon: 'pi-chart-pie', stocks: etfStocks.value },
    ...generalCategories
  ];
});

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
  loadIndexOverview();
  loadIndustries();
});

const { currentMarket, marketMeta } = useMarket();

watch(currentMarket, () => {
  loadHeatmapData();
  loadIndexOverview();
  loadIndustries();
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

// 指數概況獨立一支請求，失敗只讓「指數」分類空白，不影響個股熱力圖主流程
// （大盤指數功能規劃書 P-4：指數抓取失敗絕不能拖垮既有功能）。
async function loadIndexOverview() {
  try {
    const res = await indexApi.getOverview(selectedPeriod.value, currentMarket.value);
    if (res.success) {
      indexOverview.value = res.data;
    }
  } catch (err) {
    indexOverview.value = [];
  }
}

// 產業標籤是相對靜態的中繼資料（季度更新即可），失敗只讓分組退回「一般個股」單一分類，
// 不影響熱力圖本體（大盤指數功能規劃書 §8.2）。
async function loadIndustries() {
  try {
    const res = await stockApi.getIndustries(currentMarket.value);
    if (res.success) industries.value = res.data;
  } catch (err) {
    industries.value = {};
  }
}

function setPeriod(p) {
  if (selectedPeriod.value === p) return;
  selectedPeriod.value = p;
  loadHeatmapData();
  loadIndexOverview();
}

function goToItem(stock) {
  const base = stock.is_index ? '/index' : '/stock';
  router.push({
    path: `${base}/${currentMarket.value}/${stock.stock_id}`,
    query: { period: selectedPeriod.value }
  });
}

// 指數點數常是 4~5 位數（如 45,811.01），加千分位才不會擠成一串數字看不清楚；
// 個股價格通常較小，加千分位對它無害，統一處理不需要另外分支。
function formatCardPrice(value) {
  return Number(value).toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
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
