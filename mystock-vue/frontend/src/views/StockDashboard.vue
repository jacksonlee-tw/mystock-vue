<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <!-- 頂部標題與核心控制列 -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div>
        <div class="flex items-center gap-3 mb-2">
          <button 
            @click="router.push('/')" 
            class="px-3 py-1.5 text-xs font-bold bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-lg flex items-center gap-1.5 transition-colors shadow-sm"
          >
            <i class="pi pi-home"></i> 熱力圖
          </button>
        </div>
        <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex flex-wrap items-center gap-3">
          <i class="pi pi-chart-line text-primary text-2xl"></i>
          <span>選股與圖表分析</span>
          <span v-if="currentStockName" class="text-lg font-extrabold text-primary bg-primary-50 dark:bg-primary-900/30 px-3 py-1 rounded-xl border border-primary/20">
            {{ selectedStock }} {{ currentStockName }}
          </span>
        </h1>
        <p class="text-sm text-surface-500 mt-1 flex flex-wrap items-center gap-2">
          <span>即時聚合個股三大法人買賣超、K線圖、融資融券籌碼趨勢</span>
          <span v-if="dateRangeText" class="px-2 py-0.5 text-xs font-bold bg-primary-50 dark:bg-primary-900/30 text-primary rounded-md border border-primary/20">
            <i class="pi pi-calendar mr-1"></i> 資料區間：{{ dateRangeText }}
          </span>
        </p>
      </div>

      <!-- 個股與週期篩選器 -->
      <div class="flex flex-wrap items-center gap-3">
        <!-- 股票選單與管理 -->
        <div class="flex flex-wrap items-center gap-2 border-r border-surface-200 dark:border-surface-700 pr-3">
          <label class="text-xs font-bold text-surface-600 dark:text-surface-400">股票:</label>
          <select 
            v-model="selectedStock" 
            @change="onStockChange"
            class="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-surface-0 dark:bg-surface-800 text-surface-900 dark:text-surface-0 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option v-for="stock in availableStocks" :key="stock.stock_id" :value="stock.stock_id">
              {{ stock.stock_id }} {{ stock.stock_name }}
            </option>
          </select>
          <button @click="removeCurrentStock" class="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors" title="取消追蹤當前股票">
             <i class="pi pi-trash"></i>
          </button>
        </div>

        <!-- 新增股票 -->
        <div class="flex items-center gap-1 border-r border-surface-200 dark:border-surface-700 pr-3">
           <input v-model="newStockId" @keyup.enter="addStock" :disabled="isPolling" placeholder="輸入股號" class="px-3 py-1.5 w-24 border border-surface-300 dark:border-surface-600 rounded-lg bg-surface-0 dark:bg-surface-800 text-sm focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50" />
           <button @click="addStock" :disabled="isPolling || !newStockId.trim()" class="px-3 py-1.5 bg-primary text-primary-contrast rounded-lg text-sm font-bold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
              新增
           </button>
        </div>

        <!-- 聚合週期 -->
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

        <!-- 時間範圍 -->
        <div class="flex items-center gap-1 bg-surface-100 dark:bg-surface-800 p-1 rounded-lg border border-surface-200 dark:border-surface-700">
          <button 
            v-for="m in timeRanges" 
            :key="m.value" 
            @click="setMonths(m.value)"
            :class="[
              'px-3 py-1.5 text-xs font-bold rounded-md transition-colors',
              selectedMonths === m.value 
                ? 'bg-primary text-primary-contrast shadow-sm' 
                : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
            ]"
          >
            {{ m.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- 載入中狀態 -->
    <div v-if="loading" class="flex flex-col items-center justify-center p-12 card bg-surface-0 dark:bg-surface-900 rounded-2xl border border-surface-200 dark:border-surface-700">
      <i class="pi pi-spin pi-spinner text-primary text-4xl mb-3"></i>
      <p class="text-sm font-semibold text-surface-600 dark:text-surface-400">正在加載個股數據與進行週期聚合...</p>
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

    <!-- 主數據視圖 -->
    <template v-else-if="chartData">
      <!-- 頂部指標 KPI 摘要卡片 -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- 最新收盤價 -->
        <div class="card p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center justify-between">
          <div>
            <span class="text-xs font-semibold text-surface-500">最新收盤價 ({{ summary.date }})</span>
            <div class="text-2xl font-black text-surface-900 dark:text-surface-0 mt-1">
              ${{ summary.close }}
            </div>
            <div class="text-xs mt-1 text-surface-500">
              最高: ${{ summary.high }} | 最低: ${{ summary.low }}
            </div>
          </div>
          <div class="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center text-red-500 font-bold">
            <i class="pi pi-dollar text-xl"></i>
          </div>
        </div>

        <!-- 三大法人合計買賣超 -->
        <div class="card p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center justify-between">
          <div>
            <span class="text-xs font-semibold text-surface-500">三大法人合計買賣超</span>
            <div :class="['text-2xl font-black mt-1', summary.total_institutional >= 0 ? 'text-red-500' : 'text-emerald-500']">
              {{ summary.total_institutional >= 0 ? '+' : '' }}{{ summary.total_institutional }} <span class="text-xs font-normal">張</span>
            </div>
            <div class="text-xs mt-1 text-surface-500">
              外資: {{ summary.foreign >= 0 ? '+' : '' }}{{ summary.foreign }} 張
            </div>
          </div>
          <div :class="['w-12 h-12 rounded-full flex items-center justify-center font-bold', summary.total_institutional >= 0 ? 'bg-red-100 dark:bg-red-900/30 text-red-500' : 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-500']">
            <i :class="['pi text-xl', summary.total_institutional >= 0 ? 'pi-arrow-up-right' : 'pi-arrow-down-right']"></i>
          </div>
        </div>

        <!-- 融資融券與券資比 -->
        <div class="card p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center justify-between">
          <div>
            <span class="text-xs font-semibold text-surface-500">融資 / 融券餘額</span>
            <div class="text-xl font-black text-surface-900 dark:text-surface-0 mt-1">
              {{ summary.margin_long }} / {{ summary.margin_short }} <span class="text-xs font-normal text-surface-500">張</span>
            </div>
            <div class="text-xs mt-1 text-orange-500 font-bold">
              券資比: {{ summary.short_ratio !== null ? summary.short_ratio + '%' : '—' }}
            </div>
          </div>
          <div class="w-12 h-12 rounded-full bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center text-orange-500 font-bold">
            <i class="pi pi-percentage text-xl"></i>
          </div>
        </div>

        <!-- 估算買賣超金額 -->
        <div class="card p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center justify-between">
          <div>
            <span class="text-xs font-semibold text-surface-500">估算買賣超金額</span>
            <div :class="['text-2xl font-black mt-1', summary.estimated_amount_wan >= 0 ? 'text-red-500' : 'text-emerald-500']">
              {{ summary.estimated_amount_wan >= 0 ? '+' : '' }}{{ summary.estimated_amount_wan }} <span class="text-xs font-normal">萬元</span>
            </div>
            <div class="text-xs mt-1 text-surface-500">
              投信: {{ summary.trust >= 0 ? '+' : '' }}{{ summary.trust }} 張
            </div>
          </div>
          <div class="w-12 h-12 rounded-full bg-cyan-100 dark:bg-cyan-900/30 flex items-center justify-center text-cyan-500 font-bold">
            <i class="pi pi-chart-pie text-xl"></i>
          </div>
        </div>
      </div>

      <!-- 視圖切換標籤 (圖表 / 表格) -->
      <div class="flex items-center justify-between border-b border-surface-200 dark:border-surface-700 pb-2">
        <div class="flex items-center gap-2">
          <button 
            @click="viewMode = 'charts'"
            :class="[
              'px-4 py-2 font-bold text-sm rounded-lg flex items-center gap-2 transition-colors',
              viewMode === 'charts' 
                ? 'bg-primary text-primary-contrast' 
                : 'bg-surface-100 dark:bg-surface-800 text-surface-700 dark:text-surface-300 hover:bg-surface-200'
            ]"
          >
            <i class="pi pi-th-large"></i> 多維度圖表分析
          </button>
          <button 
            @click="viewMode = 'table'"
            :class="[
              'px-4 py-2 font-bold text-sm rounded-lg flex items-center gap-2 transition-colors',
              viewMode === 'table' 
                ? 'bg-primary text-primary-contrast' 
                : 'bg-surface-100 dark:bg-surface-800 text-surface-700 dark:text-surface-300 hover:bg-surface-200'
            ]"
          >
            <i class="pi pi-table"></i> 精確數據表格
          </button>
        </div>

        <div class="text-xs text-surface-500 flex items-center gap-3">
          <span v-if="dateRangeText" class="font-semibold text-surface-700 dark:text-surface-300">
            <i class="pi pi-calendar text-[10px] mr-1 text-primary"></i>起迄: {{ dateRangeText }}
          </span>
          <span>資料筆數: <span class="font-bold text-surface-900 dark:text-surface-0">{{ chartData.dates.length }}</span> 筆</span>
        </div>
      </div>

      <!-- 圖表視圖 -->
      <StockCharts v-if="viewMode === 'charts'" :chartData="chartData" :stockId="selectedStock" :period="selectedPeriod" :months="selectedMonths" />

      <!-- 明細數據表格視圖 -->
      <div v-else-if="viewMode === 'table'" class="card p-4 shadow-sm border border-surface-200 dark:border-surface-700 rounded-xl bg-surface-0 dark:bg-surface-900">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
            <i class="pi pi-list text-primary"></i> 歷史交易明細數據表 ({{ selectedStock }} <span v-if="currentStockName">{{ currentStockName }}</span>)
            <span v-if="dateRangeText" class="text-xs font-semibold text-surface-500">
              ({{ dateRangeText }})
            </span>
          </h3>
          <button 
            @click="exportCSV" 
            class="px-3 py-1.5 text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg flex items-center gap-1.5 transition-colors shadow-sm"
          >
            <i class="pi pi-file-excel"></i> 匯出 CSV 檔
          </button>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-xs text-left border-collapse">
            <thead>
              <tr class="bg-surface-100 dark:bg-surface-800 text-surface-700 dark:text-surface-300 font-bold border-b border-surface-200 dark:border-surface-700">
                <th class="p-2.5">日期</th>
                <th class="p-2.5">開盤</th>
                <th class="p-2.5">最高</th>
                <th class="p-2.5">最低</th>
                <th class="p-2.5">收盤</th>
                <th class="p-2.5">外資(張)</th>
                <th class="p-2.5">投信(張)</th>
                <th class="p-2.5">自營商(張)</th>
                <th class="p-2.5">合計(張)</th>
                <th class="p-2.5">估算金額(萬)</th>
                <th class="p-2.5">融資餘額</th>
                <th class="p-2.5">融券餘額</th>
                <th class="p-2.5">券資比</th>
              </tr>
            </thead>
            <tbody>
              <tr 
                v-for="row in recordsReversed" 
                :key="row.日期"
                class="border-b border-surface-100 dark:border-surface-800/60 hover:bg-surface-50 dark:hover:bg-surface-800/40 transition-colors"
              >
                <td class="p-2.5 font-semibold text-surface-900 dark:text-surface-0">{{ row.日期 }}</td>
                <td class="p-2.5 text-surface-700 dark:text-surface-300">${{ row.開盤價 }}</td>
                <td class="p-2.5 text-red-500 font-medium">${{ row.最高價 }}</td>
                <td class="p-2.5 text-emerald-500 font-medium">${{ row.最低價 }}</td>
                <td class="p-2.5 font-bold text-surface-900 dark:text-surface-0">${{ row.收盤價 }}</td>
                <td :class="['p-2.5 font-medium', row['外資買賣超(張)'] >= 0 ? 'text-red-500' : 'text-emerald-500']">
                  {{ row['外資買賣超(張)'] >= 0 ? '+' : '' }}{{ row['外資買賣超(張)'] }}
                </td>
                <td :class="['p-2.5 font-medium', row['投信買賣超(張)'] >= 0 ? 'text-red-500' : 'text-emerald-500']">
                  {{ row['投信買賣超(張)'] >= 0 ? '+' : '' }}{{ row['投信買賣超(張)'] }}
                </td>
                <td :class="['p-2.5 font-medium', row['自營商買賣超(張)'] >= 0 ? 'text-red-500' : 'text-emerald-500']">
                  {{ row['自營商買賣超(張)'] >= 0 ? '+' : '' }}{{ row['自營商買賣超(張)'] }}
                </td>
                <td :class="['p-2.5 font-bold', row['合計買賣超(張)'] >= 0 ? 'text-red-500' : 'text-emerald-500']">
                  {{ row['合計買賣超(張)'] >= 0 ? '+' : '' }}{{ row['合計買賣超(張)'] }}
                </td>
                <td :class="['p-2.5 font-medium', row['估算買賣超金額(萬元)'] >= 0 ? 'text-red-500' : 'text-emerald-500']">
                  {{ row['估算買賣超金額(萬元)'] >= 0 ? '+' : '' }}{{ row['估算買賣超金額(萬元)'] }}
                </td>
                <td class="p-2.5 text-pink-500 font-medium">{{ row['融資餘額(張)'] || '—' }}</td>
                <td class="p-2.5 text-emerald-500 font-medium">{{ row['融券餘額(張)'] || '—' }}</td>
                <td class="p-2.5 text-orange-500 font-bold">
                  {{ row['券資比(%)'] !== null && row['券資比(%)'] !== undefined ? row['券資比(%)'] + '%' : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { stockApi } from '@/service/stockApi';
import StockCharts from '@/components/StockCharts.vue';

const route = useRoute();
const router = useRouter();

const availableStocks = ref([]);
const selectedStock = ref(route.params.id || '2330');
const selectedPeriod = ref(route.query.period || 'daily');
const selectedMonths = ref(3);

const loading = ref(true);
const error = ref(null);
const chartData = ref(null);
const viewMode = ref('charts');
const newStockId = ref('');
const isPolling = ref(false);

const periods = [
  { label: '日線', value: 'daily' },
  { label: '週線', value: 'weekly' },
  { label: '月線', value: 'monthly' }
];

const timeRanges = [
  { label: '1個月', value: 1 },
  { label: '3個月', value: 3 },
  { label: '6個月', value: 6 },
  { label: '1年', value: 12 }
];

const dateRangeText = computed(() => {
  if (chartData.value?.start_date && chartData.value?.end_date) {
    return `${chartData.value.start_date} ~ ${chartData.value.end_date}`;
  }
  if (chartData.value?.dates && chartData.value.dates.length > 0) {
    return `${chartData.value.dates[0]} ~ ${chartData.value.dates[chartData.value.dates.length - 1]}`;
  }
  return '';
});

const currentStockName = computed(() => {
  if (chartData.value?.stock_name) return chartData.value.stock_name;
  const match = availableStocks.value.find(s => s.stock_id === selectedStock.value);
  return match ? match.stock_name : '';
});

const summary = computed(() => chartData.value?.latest_summary || {});

const recordsReversed = computed(() => {
  if (!chartData.value?.records) return [];
  return [...chartData.value.records].reverse();
});

onMounted(async () => {
  await fetchAvailableStocks();
  if (route.params.id && route.params.id !== selectedStock.value) {
    selectedStock.value = route.params.id;
  }
  await loadStockData();
});

watch(() => route.params.id, (newId) => {
  if (newId) {
    selectedStock.value = newId;
    loadStockData();
  }
});

async function fetchAvailableStocks() {
  try {
    const res = await stockApi.getAvailableStocks();
    if (res.success && res.data.length > 0) {
      availableStocks.value = res.data;
      // 若當前選擇的股票不在清單中，且無路由參數，預設取第一檔
      if (!route.params.id && !availableStocks.value.some(s => s.stock_id === selectedStock.value)) {
        selectedStock.value = availableStocks.value[0].stock_id;
      }
    }
  } catch (err) {
    console.error('獲取股票清單失敗:', err);
  }
}

function onStockChange() {
  router.push(`/stock/${selectedStock.value}`);
}

async function loadStockData() {
  loading.value = true;
  error.value = null;
  try {
    const res = await stockApi.getChartData(selectedStock.value, selectedPeriod.value, selectedMonths.value);
    if (res.success) {
      chartData.value = res.data;
    } else {
      error.value = '載入資料時發生未知錯誤';
    }
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || '連線後端 API 失敗';
  } finally {
    loading.value = false;
  }
}

function setPeriod(p) {
  if (selectedPeriod.value === p) return;
  selectedPeriod.value = p;
  loadStockData();
}

function setMonths(m) {
  if (selectedMonths.value === m) return;
  selectedMonths.value = m;
  loadStockData();
}

async function addStock() {
  const stockId = newStockId.value.trim();
  if (!stockId) return;

  try {
    await stockApi.addTrackedStock(stockId);
    newStockId.value = '';
    
    // 檢查是否有資料
    const res = await stockApi.getChartData(stockId, 'daily', 3);
    if (res.success && res.data && res.data.records && res.data.records.length > 0) {
      await fetchAvailableStocks();
      router.push(`/stock/${stockId}`);
    } else {
      throw new Error('No data');
    }
  } catch (err) {
    // 若後端回報無數據或錯誤，啟動背景抓取
    triggerFetchStock(stockId);
  }
}

async function triggerFetchStock(stockId) {
  try {
    isPolling.value = true;
    loading.value = true;
    error.value = '正在啟動背景資料抓取...';
    await stockApi.triggerFetch([stockId], 3);
    pollFetchStatus(stockId);
  } catch (err) {
    error.value = '啟動抓取失敗: ' + (err.response?.data?.detail || err.message);
    isPolling.value = false;
    loading.value = false;
  }
}

async function pollFetchStatus(stockId) {
  if (!isPolling.value) return;
  try {
    const res = await stockApi.getFetchStatus();
    if (res.status === 'idle') {
      isPolling.value = false;
      error.value = null;
      await fetchAvailableStocks();
      router.push(`/stock/${stockId}`);
    } else {
      error.value = `資料抓取中，請稍候 (${res.message || '...'})...`;
      setTimeout(() => pollFetchStatus(stockId), 2000);
    }
  } catch (err) {
    setTimeout(() => pollFetchStatus(stockId), 2000);
  }
}

async function removeCurrentStock() {
  if (!confirm(`確定要取消追蹤 ${selectedStock.value} 嗎？\n(已抓取的資料不會被刪除)`)) return;
  try {
    await stockApi.removeTrackedStock(selectedStock.value);
    router.push('/');
  } catch (err) {
    alert('取消追蹤失敗: ' + (err.response?.data?.detail || err.message));
  }
}

function exportCSV() {
  if (!recordsReversed.value.length) return;
  const headers = [
    '日期', '股票名稱', '開盤價', '最高價', '最低價', '收盤價',
    '外資買賣超(張)', '投信買賣超(張)', '自營商買賣超(張)', '合計買賣超(張)',
    '估算買賣超金額(萬元)', '融資餘額(張)', '融券餘額(張)', '券資比(%)'
  ];

  const csvRows = [headers.join(',')];
  for (const row of recordsReversed.value) {
    const values = [
      row.日期,
      row.股票名稱 || '',
      row.開盤價 || 0,
      row.最高價 || 0,
      row.最低價 || 0,
      row.收盤價 || 0,
      row['外資買賣超(張)'] || 0,
      row['投信買賣超(張)'] || 0,
      row['自營商買賣超(張)'] || 0,
      row['合計買賣超(張)'] || 0,
      row['估算買賣超金額(萬元)'] || 0,
      row['融資餘額(張)'] || '',
      row['融券餘額(張)'] || '',
      row['券資比(%)'] || ''
    ];
    csvRows.push(values.join(','));
  }

  const csvString = '\uFEFF' + csvRows.join('\n');
  const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.setAttribute('download', `${selectedStock.value}_籌碼分析數據_${selectedPeriod.value}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
</script>
