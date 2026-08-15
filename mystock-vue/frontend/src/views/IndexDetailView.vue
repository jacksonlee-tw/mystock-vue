<template>
  <div class="index-dashboard-root">
    <!-- Sticky 控制條，比照 StockDashboard.vue 的版面慣例 -->
    <div class="index-control-bar sticky top-16 z-30 bg-surface-0/95 dark:bg-surface-900/95 backdrop-blur-md border-b border-surface-200 dark:border-surface-700 shadow-sm">
      <div class="max-w-7xl mx-auto px-6 py-4 flex flex-wrap items-center gap-x-4 gap-y-2">
        <button
          @click="router.push('/')"
          class="px-3 py-1.5 text-xs font-bold bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-lg flex items-center gap-1.5 transition-colors shrink-0"
        >
          <i class="pi pi-home"></i> 熱力圖
        </button>

        <!-- 指數切換 -->
        <div class="flex items-center gap-2 shrink-0">
          <Select
            :modelValue="code"
            @update:modelValue="handleIndexChange"
            :options="availableIndices"
            optionLabel="name"
            optionValue="code"
            placeholder="切換指數..."
            class="w-60 sm:w-72 !bg-transparent !border-transparent hover:!bg-surface-100 dark:hover:!bg-surface-800 transition-colors"
          >
            <template #value="slotProps">
              <div v-if="slotProps.value" class="flex items-baseline gap-2.5 min-w-0">
                <span class="num text-2xl font-black text-surface-900 dark:text-surface-0 shrink-0">{{ slotProps.value }}</span>
                <span class="text-lg text-surface-600 dark:text-surface-300 font-bold truncate">{{ currentIndexName }}</span>
              </div>
              <span v-else>{{ slotProps.placeholder }}</span>
            </template>
            <template #option="slotProps">
              <div class="flex items-baseline gap-2">
                <span class="font-bold">{{ slotProps.option.code }}</span>
                <span class="text-sm text-surface-500">{{ slotProps.option.name }}</span>
              </div>
            </template>
          </Select>
        </div>

        <!-- 最新指數 & 漲跌 -->
        <div v-if="summary.close !== undefined" class="flex items-baseline gap-2.5 shrink-0">
          <span class="num text-3xl font-black" :style="{ color: latestChange ? colorForValue(latestChange.diff) : undefined }">
            {{ formatIndexValue(summary.close) }}
          </span>
          <span v-if="latestChange" class="num text-lg font-extrabold" :style="{ color: colorForValue(latestChange.diff) }">
            {{ formatChange(latestChange.diff, latestChange.pct) }}
          </span>
        </div>

        <span v-if="dateRangeText" class="text-sm font-bold text-surface-500 dark:text-surface-400 hidden sm:inline shrink-0">
          <i class="pi pi-calendar mr-1"></i>{{ dateRangeText }}
        </span>

        <div class="flex flex-wrap items-center gap-2 ml-auto">
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

    <div class="p-6 max-w-7xl mx-auto space-y-6">
      <!-- 初次載入中狀態：只有在還沒有任何資料可顯示時才整頁顯示 spinner，比照 CLAUDE.md「Hard rules」與
           StockDashboard.vue 的作法——切換週期/範圍時 chartData 已存在，不能整塊卸載內容，否則頁面變矮，
           瀏覽器會把捲動位置重置到頂部。 -->
      <div v-if="loading && !chartData" class="flex flex-col items-center justify-center p-12 card bg-surface-0 dark:bg-surface-900 rounded-2xl border border-surface-200 dark:border-surface-700">
        <i class="pi pi-spin pi-spinner text-primary text-4xl mb-3"></i>
        <p class="text-sm font-semibold text-surface-600 dark:text-surface-400">正在加載指數數據...</p>
      </div>

      <div v-else-if="error && !chartData" class="card p-6 border border-red-300 bg-red-50 dark:bg-red-900/20 rounded-2xl text-red-700 dark:text-red-300">
        <div class="flex items-center gap-3">
          <i class="pi pi-exclamation-circle text-2xl"></i>
          <div>
            <h4 class="font-bold">資料讀取失敗</h4>
            <p class="text-sm mt-0.5">{{ error }}</p>
          </div>
        </div>
      </div>

      <template v-else-if="chartData">
        <div class="relative">
          <div v-if="loading" class="absolute inset-0 z-10 flex items-start justify-center pt-24 bg-surface-0/60 dark:bg-surface-900/60 rounded-2xl">
            <i class="pi pi-spin pi-spinner text-primary text-3xl"></i>
          </div>
          <div :class="{ 'opacity-50 pointer-events-none transition-opacity duration-150': loading }" class="space-y-6">
            <!-- KPI 卡列（大盤指數功能規劃書 §5.3）
                 !m-0：蓋掉全域 .card { margin-bottom: 2rem; &:last-child { margin-bottom: 0 } }（_utils.scss），
                 否則 grid 裡剛好排到最後的那張卡少了底部留白，stretch 出來會比同列其他卡高，見 CLAUDE.md
                 「Hard rules」。 -->
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-5 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
                <span class="text-xs font-bold tracking-wide uppercase text-surface-400 mb-2">當日區間 ({{ summary.date }})</span>
                <div class="num text-2xl font-black text-surface-900 dark:text-surface-0 mb-1.5">
                  {{ formatIndexValue(summary.low) }} <span class="text-surface-300 dark:text-surface-600 font-normal mx-1">–</span> {{ formatIndexValue(summary.high) }}
                </div>
                <div class="text-xs font-medium text-surface-500">當日最低 / 最高</div>
              </div>

              <div
                v-if="hasTurnover"
                @click="activeChartId = 'index-turnover'"
                class="card !m-0 bg-surface-0 dark:bg-surface-900 p-5 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm hover:shadow-md hover:border-primary/60 hover:-translate-y-0.5 cursor-pointer transition-all duration-200 flex flex-col justify-between"
              >
                <span class="text-xs font-bold tracking-wide uppercase text-surface-400 mb-2">成交金額</span>
                <div class="num text-2xl font-black text-surface-900 dark:text-surface-0 mb-1.5">{{ formatTurnover(latestTurnover) }}</div>
                <div class="text-xs font-medium text-surface-500">{{ market === 'us' ? '估算值' : '全市場合計' }}</div>
              </div>

              <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-5 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
                <span class="text-xs font-bold tracking-wide uppercase text-surface-400 mb-2">距季線 (MA60)</span>
                <div class="num text-2xl font-black mb-1.5" :style="{ color: bias60 !== null ? colorForValue(bias60) : undefined }">
                  {{ bias60 !== null ? formatBias(bias60) : '—' }}
                </div>
                <div class="text-xs font-medium text-surface-500">乖離率</div>
              </div>

              <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-5 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
                <span class="text-xs font-bold tracking-wide uppercase text-surface-400 mb-2">距年線 (MA240)</span>
                <div class="num text-2xl font-black mb-1.5" :style="{ color: bias240 !== null ? colorForValue(bias240) : undefined }">
                  {{ bias240 !== null ? formatBias(bias240) : '—' }}
                </div>
                <div class="text-xs font-medium text-surface-500">乖離率 ・ {{ maPositionLabel }}</div>
              </div>
            </div>

            <div class="flex items-center justify-between border-b border-surface-200 dark:border-surface-700 pb-2">
              <h3 class="font-bold text-sm text-surface-700 dark:text-surface-300 flex items-center gap-2">
                <i class="pi pi-chart-line text-primary"></i> 指數走勢圖表
              </h3>
              <div class="flex items-center gap-3">
                <button
                  @click="exportCSV"
                  class="px-3 py-1.5 text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg flex items-center gap-1.5 transition-colors shadow-sm"
                >
                  <i class="pi pi-file-excel"></i> 匯出 CSV
                </button>
                <span class="text-xs text-surface-500">資料筆數: <span class="num font-bold text-surface-900 dark:text-surface-0">{{ chartData.dates.length }}</span> 筆</span>
              </div>
            </div>

            <StockCharts v-model="activeChartId" :chartData="chartData" :stockId="code" :period="selectedPeriod" :months="selectedMonths" :market="market" kind="index" />

            <!-- 多指數比較（大盤指數功能規劃書 FR-IDX-06） -->
            <IndexCompareWidget :baseCode="code" :baseMarket="market" :period="selectedPeriod" :months="selectedMonths" />
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import Select from 'primevue/select';
import StockCharts from '@/components/StockCharts.vue';
import IndexCompareWidget from '@/components/IndexCompareWidget.vue';
import { indexApi } from '@/service/indexApi';
import { colorForValue as colorForValueRaw } from '@/utils/marketColors';
import { formatChange } from '@/utils/format';
import { useMarket } from '@/composables/useMarket';

const route = useRoute();
const router = useRouter();
const toast = useToast();
const { currentMarket } = useMarket();

const availableIndices = ref([]);
const code = ref(route.params.code || 'TWII');
const market = computed(() => chartData.value?.market || route.params.market || currentMarket.value);
const selectedPeriod = ref(route.query.period || 'daily');
const selectedMonths = ref(Number(route.query.months) || 3);

const loading = ref(true);
const error = ref(null);
const chartData = ref(null);
const activeChartId = ref(null);

const periods = [
  { label: '日線', value: 'daily' },
  { label: '週線', value: 'weekly' },
  { label: '月線', value: 'monthly' }
];

const timeRanges = [
  { label: '1個月', value: 1 },
  { label: '3個月', value: 3 },
  { label: '6個月', value: 6 },
  { label: '1年', value: 12 },
  { label: '3年', value: 36 }
];

const dateRangeText = computed(() => {
  if (chartData.value?.start_date && chartData.value?.end_date) {
    return `${chartData.value.start_date} ~ ${chartData.value.end_date}`;
  }
  return '';
});

const currentIndexName = computed(() => {
  if (chartData.value?.stock_name) return chartData.value.stock_name;
  const match = availableIndices.value.find((i) => i.code === code.value);
  return match ? match.name : '';
});

const summary = computed(() => chartData.value?.latest_summary || {});

const latestChange = computed(() => {
  const records = chartData.value?.records;
  if (!records || records.length < 2) return null;
  const latest = records[records.length - 1];
  const prev = records[records.length - 2];
  if (!latest || !prev || prev.close == null || latest.close == null) return null;
  const diff = latest.close - prev.close;
  const pct = prev.close !== 0 ? (diff / prev.close) * 100 : 0;
  return { diff, pct };
});

const hasTurnover = computed(() => (chartData.value?.records || []).some((r) => r.amount));
const latestTurnover = computed(() => {
  const records = chartData.value?.records || [];
  return records.length ? records[records.length - 1].amount || 0 : 0;
});

// 距季線／年線乖離率（大盤指數功能規劃書 FR-IDX-40）：均線已由後端統一算好
// （見 services/stock_service.py 的 compute_ma_set），這裡只取最後一筆做乖離率計算，
// 不重新實作均線邏輯（均線策略警示系統 設計文件的既有原則：指標只在後端算一次）。
function lastMaValue(period) {
  const series = chartData.value?.moving_averages?.[`MA${period}`];
  if (!Array.isArray(series) || !series.length) return null;
  for (let i = series.length - 1; i >= 0; i--) {
    if (series[i] != null) return series[i];
  }
  return null;
}

function biasFor(period) {
  const ma = lastMaValue(period);
  const close = summary.value.close;
  if (ma == null || close == null || ma === 0) return null;
  return ((close - ma) / ma) * 100;
}

const bias60 = computed(() => biasFor(60));
const bias240 = computed(() => biasFor(240));

const maPositionLabel = computed(() => {
  const close = summary.value.close;
  if (close == null) return '';
  const periods = [5, 10, 20, 60, 120, 240];
  const above = periods.filter((p) => {
    const ma = lastMaValue(p);
    return ma != null && close >= ma;
  });
  return `站上 ${above.length}/${periods.length} 條均線`;
});

function colorForValue(value) {
  return colorForValueRaw(value, market.value);
}

function formatIndexValue(value) {
  if (value === undefined || value === null) return '—';
  return Number(value).toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatBias(value) {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function formatTurnover(amount) {
  if (!amount) return '—';
  if (market.value === 'us') {
    return `$${(amount / 1e6).toLocaleString('zh-TW', { maximumFractionDigits: 1 })}M`;
  }
  return `${(amount / 1e8).toLocaleString('zh-TW', { maximumFractionDigits: 2 })} 億元`;
}

async function fetchAvailableIndices() {
  try {
    const res = await indexApi.getIndices(market.value);
    if (res.success) availableIndices.value = res.data;
  } catch (err) {
    // 靜默失敗：不影響主圖表載入，只是切換下拉選單會缺清單
  }
}

async function loadIndexData() {
  loading.value = true;
  error.value = null;
  // 切換週期/範圍時畫面會保留舊的 chartData 原地顯示（見 template，比照 StockDashboard.vue 與 CLAUDE.md
  // 「Hard rules」），所以背景刷新失敗時走 toast 提示，不能只靠 error && !chartData 的整頁錯誤畫面。
  const isBackgroundRefresh = chartData.value !== null;
  try {
    const res = await indexApi.getChartData(code.value, selectedPeriod.value, selectedMonths.value, route.params.market || currentMarket.value);
    if (res.success) {
      chartData.value = res.data;
    } else {
      error.value = '載入資料時發生未知錯誤';
    }
  } catch (err) {
    error.value = err.response?.data?.error?.message || err.response?.data?.detail || err.message || '連線後端 API 失敗';
  } finally {
    loading.value = false;
    if (error.value && isBackgroundRefresh) {
      toast.add({ severity: 'error', summary: '刷新資料失敗', detail: error.value, life: 4000 });
    }
  }
}

onMounted(async () => {
  await fetchAvailableIndices();
  await loadIndexData();
});

watch(() => route.params.code, (newCode) => {
  if (newCode && newCode !== code.value) {
    code.value = newCode;
    loadIndexData();
  }
});

watch(() => route.query.period, (v) => {
  const p = v || 'daily';
  if (p !== selectedPeriod.value) selectedPeriod.value = p;
});
watch(() => route.query.months, (v) => {
  const m = Number(v) || 3;
  if (m !== selectedMonths.value) selectedMonths.value = m;
});
watch([selectedPeriod, selectedMonths], () => {
  loadIndexData();
});

function setPeriod(p) {
  if (selectedPeriod.value === p) return;
  router.replace({ query: { ...route.query, period: p } });
}

function setMonths(m) {
  if (selectedMonths.value === m) return;
  router.replace({ query: { ...route.query, months: m } });
}

function handleIndexChange(newCode) {
  if (!newCode || newCode === code.value) return;
  const target = availableIndices.value.find((i) => i.code === newCode);
  router.push({
    path: `/index/${target ? target.market : currentMarket.value}/${newCode}`,
    query: { ...route.query }
  });
}

function exportCSV() {
  const records = chartData.value?.records || [];
  if (!records.length) return;
  const headers = ['日期', '開盤', '最高', '最低', '收盤', '成交量', '成交金額'];
  const rows = [headers.join(',')];
  for (const r of records) {
    rows.push([r.date, r.open ?? '', r.high ?? '', r.low ?? '', r.close ?? '', r.volume ?? '', r.amount ?? ''].join(','));
  }
  const csvString = '﻿' + rows.join('\n');
  const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.setAttribute('download', `${code.value}_指數資料_${selectedPeriod.value}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
</script>
