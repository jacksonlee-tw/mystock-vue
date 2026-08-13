<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <Toast />

    <!-- 標題列 -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-bell text-primary text-2xl"></i>
          策略警示看板
        </h1>
        <p class="text-sm text-surface-500 mt-1">均線策略觸發事件清單，依市場、策略、強度篩選</p>
      </div>

      <div class="flex items-center gap-2">
        <div class="flex items-center gap-1 bg-surface-100 dark:bg-surface-800 p-1 rounded-lg border border-surface-200 dark:border-surface-700">
          <button
            v-for="m in marketOptions"
            :key="m.value"
            @click="setMarket(m.value)"
            :class="[
              'px-3 py-1.5 text-xs font-bold rounded-md transition-colors',
              currentMarket === m.value ? 'bg-primary text-primary-contrast shadow-sm' : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
            ]"
          >
            {{ m.label }}
          </button>
        </div>
        <Button label="立即掃描" icon="pi pi-search" :loading="scanning" size="small" @click="runScan" />
      </div>
    </div>

    <!-- 摘要卡片 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="card p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-primary-50 dark:bg-primary-900/30 text-primary flex items-center justify-center shrink-0">
          <i class="pi pi-bell"></i>
        </div>
        <div class="min-w-0">
          <div class="text-[11px] font-bold text-surface-400 uppercase">今日警示總數</div>
          <div class="text-xl font-black text-surface-900 dark:text-surface-0 num">{{ summary.total_alerts ?? 0 }}</div>
          <div class="text-[11px] text-surface-400">{{ summary.scan_date || '—' }}</div>
        </div>
      </div>

      <div class="card p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-surface-100 dark:bg-surface-800 flex items-center justify-center shrink-0 text-up">
          <i class="pi pi-arrow-up"></i>
        </div>
        <div class="min-w-0">
          <div class="text-[11px] font-bold text-surface-400 uppercase">偏多訊號</div>
          <div class="text-xl font-black text-up num">{{ summary.by_direction?.bullish ?? 0 }}</div>
        </div>
      </div>

      <div class="card p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-surface-100 dark:bg-surface-800 flex items-center justify-center shrink-0 text-down">
          <i class="pi pi-arrow-down"></i>
        </div>
        <div class="min-w-0">
          <div class="text-[11px] font-bold text-surface-400 uppercase">偏空訊號</div>
          <div class="text-xl font-black text-down num">{{ summary.by_direction?.bearish ?? 0 }}</div>
        </div>
      </div>

      <div class="card p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-surface-100 dark:bg-surface-800 flex items-center justify-center shrink-0 text-surface-500">
          <i class="pi pi-chart-line"></i>
        </div>
        <div class="min-w-0">
          <div class="text-[11px] font-bold text-surface-400 uppercase">觸發最多策略</div>
          <div class="text-sm font-black text-surface-900 dark:text-surface-0 truncate">{{ topStrategyLabel }}</div>
        </div>
      </div>
    </div>

    <!-- 篩選列 -->
    <div class="flex flex-wrap items-center gap-3 card p-3 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900">
      <div class="flex items-center gap-2">
        <label class="text-xs font-bold text-surface-500">策略</label>
        <Select v-model="filters.strategy" :options="strategyOptions" optionLabel="name" optionValue="id" placeholder="全部策略" showClear class="w-48" />
      </div>
      <div class="flex items-center gap-2">
        <label class="text-xs font-bold text-surface-500">強度</label>
        <Select v-model="filters.strength" :options="strengthOptions" optionLabel="label" optionValue="value" placeholder="全部強度" showClear class="w-32" />
      </div>
      <div class="flex items-center gap-2">
        <label class="text-xs font-bold text-surface-500">區間</label>
        <Select v-model="filters.days" :options="dayOptions" optionLabel="label" optionValue="value" class="w-32" />
      </div>
      <div class="ml-auto text-xs text-surface-400">共 {{ alerts.length }} 筆</div>
    </div>

    <!-- 載入中 -->
    <div v-if="loading" class="flex flex-col items-center justify-center p-12 card bg-surface-0 dark:bg-surface-900 rounded-2xl border border-surface-200 dark:border-surface-700">
      <i class="pi pi-spin pi-spinner text-primary text-4xl mb-3"></i>
      <p class="text-sm font-semibold text-surface-600 dark:text-surface-400">載入警示資料中...</p>
    </div>

    <!-- 錯誤 -->
    <div v-else-if="error" class="card p-6 border border-red-300 bg-red-50 dark:bg-red-900/20 rounded-2xl text-red-700 dark:text-red-300">
      <div class="flex items-center gap-3">
        <i class="pi pi-exclamation-circle text-2xl"></i>
        <div>
          <h4 class="font-bold">資料讀取失敗</h4>
          <p class="text-sm mt-0.5">{{ error }}</p>
        </div>
      </div>
    </div>

    <!-- 警示清單 -->
    <AlertTimeline v-else :alerts="alerts" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { useToast } from 'primevue/usetoast';
import { useMarket } from '@/composables/useMarket';
import { alertApi } from '@/service/alertApi';
import AlertTimeline from '@/components/AlertTimeline.vue';

const { currentMarket, setMarket } = useMarket();
const toast = useToast();

const marketOptions = [
  { label: '台股', value: 'tw' },
  { label: '美股', value: 'us' }
];
const strengthOptions = [
  { label: '強', value: 'strong' },
  { label: '中', value: 'moderate' },
  { label: '弱', value: 'weak' }
];
const dayOptions = [
  { label: '近 7 天', value: 7 },
  { label: '近 14 天', value: 14 },
  { label: '近 30 天', value: 30 },
  { label: '近 90 天', value: 90 }
];

const filters = reactive({ strategy: null, strength: null, days: 14 });
const alerts = ref([]);
const summary = ref({});
const strategyList = ref([]);
const loading = ref(true);
const error = ref(null);
const scanning = ref(false);

const strategyOptions = computed(() => strategyList.value);

const topStrategyLabel = computed(() => {
  const entries = Object.entries(summary.value.by_strategy || {});
  if (!entries.length) return '—';
  entries.sort((a, b) => b[1] - a[1]);
  const [id, count] = entries[0];
  const found = strategyList.value.find((s) => s.id === id);
  return `${found?.name || id}（${count}）`;
});

async function loadStrategies() {
  try {
    const res = await alertApi.getStrategies(currentMarket.value);
    if (res.success) strategyList.value = res.data;
  } catch {
    // 策略清單只是篩選器的輔助資訊，載入失敗不影響警示清單本身
  }
}

async function loadAlerts() {
  loading.value = true;
  error.value = null;
  try {
    const [alertsRes, summaryRes] = await Promise.all([
      alertApi.getAlerts({
        market: currentMarket.value,
        days: filters.days,
        strategy: filters.strategy,
        strength: filters.strength
      }),
      alertApi.getAlertsSummary({ market: currentMarket.value })
    ]);
    if (alertsRes.success) alerts.value = alertsRes.data;
    if (summaryRes.success) summary.value = summaryRes.data;
  } catch (err) {
    error.value = '無法載入警示資料，請確認後端服務是否啟動';
  } finally {
    loading.value = false;
  }
}

async function runScan() {
  scanning.value = true;
  try {
    const res = await alertApi.triggerScan(currentMarket.value);
    if (res.success) {
      const { alerts_generated, scanned_stocks, scan_duration_ms } = res.data;
      toast.add({
        severity: alerts_generated > 0 ? 'success' : 'info',
        summary: '掃描完成',
        detail: `掃描 ${scanned_stocks} 檔標的，新增 ${alerts_generated} 筆警示（耗時 ${scan_duration_ms}ms）`,
        life: 4000
      });
      await loadAlerts();
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '掃描失敗', detail: '請確認後端服務是否啟動', life: 4000 });
  } finally {
    scanning.value = false;
  }
}

onMounted(() => {
  loadStrategies();
  loadAlerts();
});

watch(currentMarket, () => {
  filters.strategy = null;
  loadStrategies();
  loadAlerts();
});

watch(() => [filters.strategy, filters.strength, filters.days], loadAlerts);
</script>
