<template>
  <div class="stock-dashboard-root">
    <!-- ══════════════════════════════════════════════════
         Sticky 控制條：貼附在 AppTopbar (4rem) 正下方
         使用 backdrop-blur 玻璃效果，不遮擋閱讀體驗
    ═══════════════════════════════════════════════════ -->
    <div class="stock-control-bar sticky top-16 z-30 bg-surface-0/95 dark:bg-surface-900/95 backdrop-blur-md border-b border-surface-200 dark:border-surface-700 shadow-sm">
      <div class="max-w-7xl mx-auto px-6 py-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <!-- 返回按鈕 -->
        <button
          @click="router.push('/')"
          class="px-3 py-1.5 text-xs font-bold bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-lg flex items-center gap-1.5 transition-colors shrink-0"
        >
          <i class="pi pi-home"></i> 熱力圖
        </button>

        <!-- 股票代號 & 名稱 -->
        <div class="flex items-center gap-2 shrink-0">
          <Select 
            :modelValue="selectedStock" 
            @update:modelValue="handleStockChange"
            :options="availableStocks" 
            optionLabel="stock_name"
            optionValue="stock_id"
            placeholder="切換股票..." 
            class="w-48 sm:w-64 !bg-transparent !border-transparent hover:!bg-surface-100 dark:hover:!bg-surface-800 transition-colors"
          >
            <template #value="slotProps">
              <div v-if="slotProps.value" class="flex items-baseline gap-2">
                <span class="num text-xl font-black text-surface-900 dark:text-surface-0">{{ slotProps.value }}</span>
                <span class="text-sm text-surface-500 font-semibold">{{ currentStockName }}</span>
              </div>
              <span v-else>{{ slotProps.placeholder }}</span>
            </template>
            <template #option="slotProps">
              <div class="flex items-baseline gap-2">
                <span class="font-bold">{{ slotProps.option.stock_id }}</span>
                <span class="text-sm text-surface-500">{{ slotProps.option.stock_name }}</span>
              </div>
            </template>
          </Select>
        </div>

        <!-- 最新收盤價 & 漲跌 -->
        <div v-if="summary.close !== undefined" class="flex items-baseline gap-2 shrink-0">
          <span class="num text-xl font-black" :style="{ color: latestChange ? colorForValue(latestChange.diff) : undefined }">
            ${{ summary.close }}
          </span>
          <span v-if="latestChange" class="num text-xs font-bold" :style="{ color: colorForValue(latestChange.diff) }">
            {{ latestChange.diff >= 0 ? '+' : '' }}{{ latestChange.diff.toFixed(2) }} ({{ latestChange.pct >= 0 ? '+' : '' }}{{ latestChange.pct.toFixed(2) }}%)
          </span>
        </div>

        <!-- 日期區間 -->
        <span v-if="dateRangeText" class="text-xs font-semibold text-surface-400 hidden sm:inline shrink-0">
          <i class="pi pi-calendar mr-1"></i>{{ dateRangeText }}
        </span>

        <!-- 右側控制群 -->
        <div class="flex flex-wrap items-center gap-2 ml-auto">
          <!-- 追蹤狀態 -->
          <div class="flex items-center gap-1 border-r border-surface-200 dark:border-surface-700 pr-2">
            <button
              @click="removeCurrentStock"
              class="px-2.5 py-1 text-xs font-bold bg-primary-50 dark:bg-primary-900/30 text-primary rounded-lg flex items-center gap-1 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-900/20 transition-colors"
              title="取消追蹤當前股票"
            >
              <i class="pi pi-star-fill"></i> 追蹤中
            </button>
            <button
              @click="router.push('/stocks')"
              class="p-1.5 text-surface-400 hover:text-primary hover:bg-surface-100 dark:hover:bg-surface-800 rounded-lg transition-colors"
              title="新增或管理追蹤股票清單"
            >
              <i class="pi pi-cog"></i>
            </button>
          </div>

          <!-- 聚合週期 -->
          <div class="flex items-center gap-0.5 bg-surface-100 dark:bg-surface-800 p-0.5 rounded-lg border border-surface-200 dark:border-surface-700">
            <button
              v-for="p in periods"
              :key="p.value"
              @click="setPeriod(p.value)"
              :class="[
                'px-2.5 py-1 text-xs font-bold rounded-md transition-all duration-150',
                selectedPeriod === p.value
                  ? 'bg-primary text-primary-contrast shadow-sm'
                  : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
              ]"
            >
              {{ p.label }}
            </button>
          </div>

          <!-- 時間範圍 -->
          <div class="flex items-center gap-0.5 bg-surface-100 dark:bg-surface-800 p-0.5 rounded-lg border border-surface-200 dark:border-surface-700">
            <button
              v-for="m in timeRanges"
              :key="m.value"
              @click="setMonths(m.value)"
              :class="[
                'px-2.5 py-1 text-xs font-bold rounded-md transition-all duration-150',
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
    </div>

    <!-- ══════════════════════════════════════════════════
         主頁面內容區（在 sticky bar 下方正常捲動）
    ═══════════════════════════════════════════════════ -->
    <div class="p-6 max-w-7xl mx-auto space-y-6">

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
      <!-- 指標盤：由後端回傳的 metrics 驅動動態渲染 -->
      <div v-if="chartData.metrics && chartData.metrics.length > 0" class="grid grid-cols-2 lg:grid-cols-5 gap-px bg-surface-200 dark:bg-surface-700 border border-surface-200 dark:border-surface-700 rounded-xl overflow-hidden">
        <!-- 當日區間 (固定顯示) -->
        <div class="bg-surface-0 dark:bg-surface-900 p-3.5">
          <span class="text-[10.5px] font-bold tracking-wide uppercase text-surface-400">當日區間 ({{ summary.date }})</span>
          <div class="num text-lg font-black text-surface-900 dark:text-surface-0 mt-1">
            {{ chartData.meta.currency_symbol }}{{ summary.low }} <span class="text-surface-300 dark:text-surface-600 font-normal">–</span> {{ chartData.meta.currency_symbol }}{{ summary.high }}
          </div>
          <div class="text-[11px] mt-0.5 text-surface-500">最高 / 最低</div>
        </div>

        <!-- 動態指標 (依照 metrics 定義) -->
        <div v-for="metric in chartData.metrics" :key="metric.key" class="bg-surface-0 dark:bg-surface-900 p-3.5">
          <span class="text-[10.5px] font-bold tracking-wide uppercase text-surface-400">{{ metric.label }}</span>
          <div class="num text-lg font-black mt-1 text-surface-900 dark:text-surface-0" :style="{ color: metric.format === 'number_colored' || metric.format === 'currency_colored' ? colorForValue(summary[metric.key]) : undefined }">
            {{ formatMetricValue(summary[metric.key], metric, chartData.meta) }} <span class="text-[11px] font-normal text-surface-500" v-if="metric.unit">{{ metric.unit }}</span>
          </div>
          <div v-if="metric.key === 'short_balance' && summary.short_ratio !== undefined" class="num text-[11px] mt-0.5 text-orange-500 font-bold">
            券資比 {{ summary.short_ratio !== null ? summary.short_ratio + '%' : '—' }}
          </div>
          <div v-else-if="metric.key === 'institutional_total' && summary.foreign_buy_sell !== undefined" class="num text-[11px] mt-0.5 text-surface-500">
            外資 {{ summary.foreign_buy_sell >= 0 ? '+' : '' }}{{ summary.foreign_buy_sell }}
          </div>
          <div v-else-if="metric.key === 'institutional_amount_est' && summary.trust_buy_sell !== undefined" class="num text-[11px] mt-0.5 text-surface-500">
            投信 {{ summary.trust_buy_sell >= 0 ? '+' : '' }}{{ summary.trust_buy_sell }}
          </div>
          <div v-else class="text-[11px] mt-0.5 text-surface-500">{{ metric.label }}</div>
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
          <span>資料筆數: <span class="num font-bold text-surface-900 dark:text-surface-0">{{ chartData.dates.length }}</span> 筆</span>
        </div>
      </div>

      <!-- 圖表視圖 -->
      <StockCharts v-if="viewMode === 'charts'" :chartData="chartData" :stockId="selectedStock" :period="selectedPeriod" :months="selectedMonths" :market="market" />

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
          <table class="num w-full text-xs text-left border-collapse">
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
                <td class="p-2.5 text-surface-700 dark:text-surface-300 font-medium">${{ row.最高價 }}</td>
                <td class="p-2.5 text-surface-700 dark:text-surface-300 font-medium">${{ row.最低價 }}</td>
                <td class="p-2.5 font-bold" :style="{ color: colorForValue(row.收盤價 - row.開盤價) }">${{ row.收盤價 }}</td>
                <td class="p-2.5 font-medium" :style="{ color: colorForValue(row['外資買賣超(張)']) }">
                  {{ row['外資買賣超(張)'] >= 0 ? '+' : '' }}{{ row['外資買賣超(張)'] }}
                </td>
                <td class="p-2.5 font-medium" :style="{ color: colorForValue(row['投信買賣超(張)']) }">
                  {{ row['投信買賣超(張)'] >= 0 ? '+' : '' }}{{ row['投信買賣超(張)'] }}
                </td>
                <td class="p-2.5 font-medium" :style="{ color: colorForValue(row['自營商買賣超(張)']) }">
                  {{ row['自營商買賣超(張)'] >= 0 ? '+' : '' }}{{ row['自營商買賣超(張)'] }}
                </td>
                <td class="p-2.5 font-bold" :style="{ color: colorForValue(row['合計買賣超(張)']) }">
                  {{ row['合計買賣超(張)'] >= 0 ? '+' : '' }}{{ row['合計買賣超(張)'] }}
                </td>
                <td class="p-2.5 font-medium" :style="{ color: colorForValue(row['估算買賣超金額(萬元)']) }">
                  {{ row['估算買賣超金額(萬元)'] >= 0 ? '+' : '' }}{{ row['估算買賣超金額(萬元)'] }}
                </td>
                <td class="p-2.5 text-surface-700 dark:text-surface-300 font-medium">{{ row['融資餘額(張)'] || '—' }}</td>
                <td class="p-2.5 text-surface-700 dark:text-surface-300 font-medium">{{ row['融券餘額(張)'] || '—' }}</td>
                <td class="p-2.5 text-orange-500 font-bold">
                  {{ row['券資比(%)'] !== null && row['券資比(%)'] !== undefined ? row['券資比(%)'] + '%' : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
    </div><!-- /內容區 -->
  </div><!-- /stock-dashboard-root -->
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';
import { stockApi } from '@/service/stockApi';
import { colorForValue as colorForValueRaw } from '@/utils/marketColors';
import StockCharts from '@/components/StockCharts.vue';
import { useMarket } from '@/composables/useMarket';

const route = useRoute();
const router = useRouter();
const toast = useToast();
const confirm = useConfirm();
const { currentMarket } = useMarket();

const availableStocks = ref([]);
const selectedStock = ref(route.params.id || '2330');
const selectedPeriod = ref(route.query.period || 'daily');
const selectedMonths = ref(Number(route.query.months) || 3);

const loading = ref(true);
const error = ref(null);
const chartData = ref(null);
const viewMode = ref('charts');

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

// 身分列的漲跌幅：後端 latest_summary 沒有現成欄位，故用最新兩筆明細自行計算。
const latestChange = computed(() => {
  const records = chartData.value?.records;
  if (!records || records.length < 2) return null;
  const latest = records[records.length - 1];
  const prev = records[records.length - 2];
  if (!latest || !prev || prev.收盤價 == null || latest.收盤價 == null) return null;
  const diff = latest.收盤價 - prev.收盤價;
  const pct = prev.收盤價 !== 0 ? (diff / prev.收盤價) * 100 : 0;
  return { diff, pct };
});

// 目前後端僅支援台股，chart-data 尚未回傳 market 欄位；
// 這裡預先讀取（若未來 API 補上）以便漲跌配色自動切換，缺省時退回台股慣例。
const market = computed(() => chartData.value?.market || 'tw');

function colorForValue(value) {
  return colorForValueRaw(value, market.value);
}

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

watch(currentMarket, () => {
  fetchAvailableStocks();
});

// URL query 是週期／範圍狀態的唯一來源：可重整、可分享、可上一頁返回。
watch(() => route.query.period, (v) => {
  const p = v || 'daily';
  if (p !== selectedPeriod.value) selectedPeriod.value = p;
});
watch(() => route.query.months, (v) => {
  const m = Number(v) || 3;
  if (m !== selectedMonths.value) selectedMonths.value = m;
});
watch([selectedPeriod, selectedMonths], () => {
  loadStockData();
});

async function fetchAvailableStocks() {
  try {
    const res = await stockApi.getAvailableStocks(currentMarket.value);
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

async function loadStockData() {
  loading.value = true;
  error.value = null;
  try {
    const res = await stockApi.getChartData(selectedStock.value, selectedPeriod.value, selectedMonths.value, currentMarket.value);
    if (res.success) {
      chartData.value = res.data;
    } else {
      error.value = '載入資料時發生未知錯誤';
    }
  } catch (err) {
    error.value = err.response?.data?.error?.message || err.response?.data?.detail || err.message || '連線後端 API 失敗';
  } finally {
    loading.value = false;
  }
}

function formatMetricValue(value, metric, meta) {
  if (value === undefined || value === null) return '—';
  let formatted = Number(value).toFixed(2).replace(/\.00$/, ''); // simple formatting
  if (metric.format === 'number_colored' || metric.format === 'currency_colored') {
    formatted = (value >= 0 ? '+' : '') + formatted;
  }
  if (metric.format === 'currency' || metric.format === 'currency_colored') {
    formatted = (meta.currency_symbol || '$') + formatted;
  }
  if (metric.format === 'percent' || metric.format === 'percent_colored') {
    formatted = formatted + '%';
  }
  return formatted;
}

function setPeriod(p) {
  if (selectedPeriod.value === p) return;
  router.replace({ query: { ...route.query, period: p } });
}

function setMonths(m) {
  if (selectedMonths.value === m) return;
  router.replace({ query: { ...route.query, months: m } });
}

function handleStockChange(newStockId) {
  if (newStockId && newStockId !== selectedStock.value) {
    router.push({
      path: `/stock/${market.value}/${newStockId}`,
      query: { ...route.query }
    });
  }
}

function removeCurrentStock() {
  const id = selectedStock.value;
  confirm.require({
    message: `確定要取消追蹤 ${id} 嗎？已抓取的資料不會被刪除。`,
    header: '取消追蹤確認',
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: '取消追蹤',
    rejectLabel: '保留',
    acceptProps: { severity: 'danger' },
    accept: async () => {
      try {
        await stockApi.removeTrackedStock(id, currentMarket.value);
        toast.add({ severity: 'success', summary: '已取消追蹤', detail: `${id} 已從追蹤清單移除`, life: 3000 });
        router.push('/');
      } catch (err) {
        toast.add({
          severity: 'error',
          summary: '取消追蹤失敗',
          detail: err.response?.data?.error?.message || err.response?.data?.detail || err.message,
          life: 4000
        });
      }
    }
  });
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
