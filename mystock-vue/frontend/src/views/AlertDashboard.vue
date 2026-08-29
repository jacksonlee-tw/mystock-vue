<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <Toast />

    <!-- 標題列 -->
    <div class="flex items-center flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h1 class="text-3xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-bell text-primary text-3xl"></i>
          策略警示看板
        </h1>
        <p class="text-base text-surface-500 mt-1">均線策略觸發事件清單，依市場、策略、強度篩選</p>
      </div>

      <div class="flex items-center gap-2">
        <div class="flex items-center gap-1 bg-surface-100 dark:bg-surface-800 p-1 rounded-lg border border-surface-200 dark:border-surface-700">
          <button
            v-for="m in marketOptions"
            :key="m.value"
            @click="setMarket(m.value)"
            :class="[
              'px-3 py-1.5 text-sm font-bold rounded-md transition-colors',
              currentMarket === m.value ? 'bg-primary text-primary-contrast shadow-sm' : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
            ]"
          >
            {{ m.label }}
          </button>
        </div>
        <Button label="立即掃描" icon="pi pi-search" :loading="scanning" size="small" @click="runScan" />
      </div>
    </div>

    <!-- 統計 × 篩選整合面板：統計與清單共用同一個「區間」，
         避免出現「上方統計看當天、下方清單看 14 天」這種兩套區間並存的狀況。
         注意：這裡刻意不套全域 .card class —— layout.scss 的 .card 排在 tailwind utilities 之後，
         會蓋掉 p-*/bg-* utility，導致選中狀態的底色與內距失效。 -->
    <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
      <!-- 區間控制列：整個面板（統計＋清單）的資料範圍 -->
      <div class="flex flex-wrap items-center gap-3 px-4 py-3 bg-surface-50 dark:bg-surface-800/40 border-b border-surface-100 dark:border-surface-800">
        <label class="text-sm font-bold text-surface-600 dark:text-surface-300 flex items-center gap-1.5">
          <i class="pi pi-calendar text-primary"></i>統計區間
        </label>
        <Select v-model="filters.days" :options="dayOptions" optionLabel="label" optionValue="value" class="w-36" />
        <span v-if="dateRangeLabel" class="text-sm text-surface-500 num">{{ dateRangeLabel }}</span>
        <span class="ml-auto text-xs text-surface-400">下方統計與清單皆以此區間計算</span>
      </div>

      <!-- 摘要磚：點選可連動篩選下方清單 -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 p-4">
        <div
          role="button"
          tabindex="0"
          class="p-3 rounded-xl border text-left flex items-center gap-3 transition-all cursor-pointer select-none hover:-translate-y-0.5 hover:shadow-md"
          :class="isAllActive ? 'border-primary ring-2 ring-primary/40 bg-primary-50 dark:bg-primary-900/20' : 'border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900'"
          @click="resetQuickFilters"
          @keydown.enter="resetQuickFilters"
          @keydown.space.prevent="resetQuickFilters"
        >
          <div class="w-12 h-12 rounded-xl bg-primary-50 dark:bg-primary-900/30 text-primary flex items-center justify-center shrink-0 text-xl">
            <i class="pi pi-bell"></i>
          </div>
          <div class="min-w-0">
            <div class="text-xs font-bold text-surface-400 uppercase tracking-wide">區間警示總數</div>
            <div class="text-3xl font-black text-surface-900 dark:text-surface-0 num leading-tight">{{ summaryStats.total }}</div>
            <div class="text-xs text-surface-400">{{ isAllActive ? '未套用篩選' : '點擊清除篩選' }}</div>
          </div>
        </div>

        <div
          role="button"
          tabindex="0"
          class="p-3 rounded-xl border text-left flex items-center gap-3 transition-all cursor-pointer select-none hover:-translate-y-0.5 hover:shadow-md"
          :class="directionFilter === 'bullish' ? 'border-up ring-2 ring-up bg-up-soft' : 'border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900'"
          @click="toggleDirection('bullish')"
          @keydown.enter="toggleDirection('bullish')"
          @keydown.space.prevent="toggleDirection('bullish')"
        >
          <div class="w-12 h-12 rounded-xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center shrink-0 text-xl text-up">
            <i class="pi pi-arrow-up"></i>
          </div>
          <div class="min-w-0">
            <div class="text-xs font-bold text-surface-400 uppercase tracking-wide">偏多訊號</div>
            <div class="text-3xl font-black text-up num leading-tight">{{ summaryStats.bullish }}</div>
            <div class="text-xs text-surface-400">{{ directionFilter === 'bullish' ? '篩選中，點擊取消' : '點擊篩選' }}</div>
          </div>
        </div>

        <div
          role="button"
          tabindex="0"
          class="p-3 rounded-xl border text-left flex items-center gap-3 transition-all cursor-pointer select-none hover:-translate-y-0.5 hover:shadow-md"
          :class="directionFilter === 'bearish' ? 'border-down ring-2 ring-down bg-down-soft' : 'border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900'"
          @click="toggleDirection('bearish')"
          @keydown.enter="toggleDirection('bearish')"
          @keydown.space.prevent="toggleDirection('bearish')"
        >
          <div class="w-12 h-12 rounded-xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center shrink-0 text-xl text-down">
            <i class="pi pi-arrow-down"></i>
          </div>
          <div class="min-w-0">
            <div class="text-xs font-bold text-surface-400 uppercase tracking-wide">偏空訊號</div>
            <div class="text-3xl font-black text-down num leading-tight">{{ summaryStats.bearish }}</div>
            <div class="text-xs text-surface-400">{{ directionFilter === 'bearish' ? '篩選中，點擊取消' : '點擊篩選' }}</div>
          </div>
        </div>

        <div
          role="button"
          :tabindex="topStrategyId ? 0 : -1"
          class="p-3 rounded-xl border text-left flex items-center gap-3 transition-all select-none"
          :class="[
            topStrategyId ? 'cursor-pointer hover:-translate-y-0.5 hover:shadow-md' : 'opacity-50 cursor-not-allowed',
            isTopStrategyActive ? 'border-primary ring-2 ring-primary/40 bg-primary-50 dark:bg-primary-900/20' : 'border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900'
          ]"
          :aria-disabled="!topStrategyId"
          @click="toggleTopStrategy"
          @keydown.enter="toggleTopStrategy"
          @keydown.space.prevent="toggleTopStrategy"
        >
          <div class="w-12 h-12 rounded-xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center shrink-0 text-xl text-surface-500">
            <i class="pi pi-chart-line"></i>
          </div>
          <div class="min-w-0">
            <div class="text-xs font-bold text-surface-400 uppercase tracking-wide">觸發最多策略</div>
            <div class="text-base font-black text-surface-900 dark:text-surface-0 truncate">{{ topStrategyLabel }}</div>
            <div class="text-xs text-surface-400">{{ isTopStrategyActive ? '篩選中，點擊取消' : (topStrategyId ? '點擊篩選' : '—') }}</div>
          </div>
        </div>
      </div>

      <!-- 細部篩選：在同一區間內再依策略／強度縮小範圍 -->
      <div class="flex flex-wrap items-center gap-3 px-4 py-3 border-t border-surface-100 dark:border-surface-800">
        <div class="flex items-center gap-2">
          <label class="text-sm font-bold text-surface-500 flex items-center gap-1"><i class="pi pi-sliders-h text-xs"></i>策略</label>
          <Select
            v-model="filters.strategy"
            :options="strategyOptions"
            optionGroupLabel="label"
            optionGroupChildren="items"
            optionLabel="name"
            optionValue="id"
            placeholder="全部策略"
            showClear
            class="w-56"
          >
            <template #optiongroup="{ option }">
              <div class="flex items-center gap-2 text-xs font-bold text-surface-500">
                <i :class="option.icon"></i>
                <span>{{ option.label }}</span>
              </div>
            </template>
          </Select>
        </div>
        <div class="flex items-center gap-2">
          <label class="text-sm font-bold text-surface-500 flex items-center gap-1"><i class="pi pi-bolt text-xs"></i>強度</label>
          <Select v-model="filters.strength" :options="strengthOptions" optionLabel="label" optionValue="value" placeholder="全部強度" showClear class="w-32" />
        </div>

        <div class="ml-auto flex items-center gap-2">
          <span
            v-if="directionFilter"
            class="inline-flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 text-sm font-bold rounded-full"
            :class="directionFilter === 'bullish' ? 'bg-up-soft text-up' : 'bg-down-soft text-down'"
          >
            <i class="pi" :class="directionFilter === 'bullish' ? 'pi-arrow-up' : 'pi-arrow-down'"></i>
            {{ directionFilter === 'bullish' ? '偏多訊號' : '偏空訊號' }}
            <i class="pi pi-times-circle cursor-pointer opacity-70 hover:opacity-100" @click="directionFilter = null" title="清除篩選"></i>
          </span>
          <span class="text-sm font-bold text-surface-600 dark:text-surface-300">
            共 <span class="num text-primary">{{ displayedAlerts.length }}</span> 筆
            <span v-if="displayedAlerts.length !== summaryStats.total" class="text-surface-400 font-normal">／{{ summaryStats.total }}</span>
          </span>
        </div>
      </div>
    </div>

    <!-- 載入中 -->
    <div v-if="loading" class="flex flex-col items-center justify-center p-12 card bg-surface-0 dark:bg-surface-900 rounded-2xl border border-surface-200 dark:border-surface-700">
      <i class="pi pi-spin pi-spinner text-primary text-4xl mb-3"></i>
      <p class="text-base font-semibold text-surface-600 dark:text-surface-400">載入警示資料中...</p>
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
    <AlertTimeline v-else :alerts="displayedAlerts" :strategy-list="strategyList" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { useToast } from 'primevue/usetoast';
import { useMarket } from '@/composables/useMarket';
import { alertApi } from '@/service/alertApi';
import { classifyDirection } from '@/utils/alertDirection';
import { CATEGORY_GROUPS, OTHER_CATEGORY } from '@/utils/alertCategory';
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
// 方向快篩（偏多／偏空）純前端篩選：後端 /alerts 沒有 direction 參數。
const directionFilter = ref(null); // null | 'bullish' | 'bearish'
// rangeAlerts＝該市場、該區間內的全部警示（只帶 market/days 打後端）。
// 策略／強度／方向一律在前端篩，好處是摘要磚的統計基準固定為「整個區間」，
// 不會因為點了某張磚而讓其他磚的數字跟著跳動；區間筆數本來就只有數十到數百筆，前端篩很輕。
const rangeAlerts = ref([]);
const strategyList = ref([]);
const loading = ref(true);
const error = ref(null);
const scanning = ref(false);

// 依 CATEGORY_GROUPS 把策略清單分組給 Select 的 optionGroup 用；
// 只顯示「有策略」的分組，避免空分類顯示成一個空標題。
const strategyOptions = computed(() => {
  const groups = CATEGORY_GROUPS.map((g) => ({
    ...g,
    items: strategyList.value.filter((s) => s.category === g.category)
  }));
  const known = new Set(CATEGORY_GROUPS.map((g) => g.category));
  const others = strategyList.value.filter((s) => !known.has(s.category));
  if (others.length) groups.push({ ...OTHER_CATEGORY, items: others });
  return groups.filter((g) => g.items.length);
});

// 摘要磚統計：一律以 rangeAlerts（整個區間）為基準，與下方清單同一個區間
const summaryStats = computed(() => {
  const stats = { total: rangeAlerts.value.length, bullish: 0, bearish: 0, byStrategy: {} };
  for (const a of rangeAlerts.value) {
    if (classifyDirection(a.direction) === 'bullish') stats.bullish += 1;
    else stats.bearish += 1;
    stats.byStrategy[a.strategy_id] = (stats.byStrategy[a.strategy_id] || 0) + 1;
  }
  return stats;
});

// 區間內實際有資料的頭尾交易日，讓「近 N 天」不只是個抽象數字
const dateRangeLabel = computed(() => {
  const dates = rangeAlerts.value.map((a) => a.trade_date).filter(Boolean);
  if (!dates.length) return '';
  const min = dates.reduce((m, d) => (d < m ? d : m));
  const max = dates.reduce((m, d) => (d > m ? d : m));
  return min === max ? min : `${min} ~ ${max}`;
});

// 點選「區間警示總數」磚＝清空全部篩選，回到整個區間的未篩選狀態
const isAllActive = computed(() => !directionFilter.value && !filters.strategy && !filters.strength);

const topStrategyId = computed(() => {
  const entries = Object.entries(summaryStats.value.byStrategy);
  if (!entries.length) return null;
  entries.sort((a, b) => b[1] - a[1]);
  return entries[0][0];
});

const topStrategyLabel = computed(() => {
  if (!topStrategyId.value) return '—';
  const count = summaryStats.value.byStrategy[topStrategyId.value] ?? 0;
  const found = strategyList.value.find((s) => s.id === topStrategyId.value);
  return `${found?.name || topStrategyId.value}（${count}）`;
});

const isTopStrategyActive = computed(() => !!topStrategyId.value && filters.strategy === topStrategyId.value);

// 顯示用清單：在區間資料上疊加策略／強度／方向三層前端篩選
const displayedAlerts = computed(() =>
  rangeAlerts.value.filter((a) => {
    if (filters.strategy && a.strategy_id !== filters.strategy) return false;
    if (filters.strength && a.signal_strength !== filters.strength) return false;
    if (directionFilter.value && classifyDirection(a.direction) !== directionFilter.value) return false;
    return true;
  })
);

function resetQuickFilters() {
  directionFilter.value = null;
  filters.strategy = null;
  filters.strength = null;
}

function toggleDirection(dir) {
  directionFilter.value = directionFilter.value === dir ? null : dir;
  // 方向快篩與策略快篩是兩個不同維度，切換其中一個時清空另一個，避免疊加出「篩到沒有資料」的死角
  filters.strategy = null;
}

function toggleTopStrategy() {
  if (!topStrategyId.value) return;
  filters.strategy = filters.strategy === topStrategyId.value ? null : topStrategyId.value;
  directionFilter.value = null;
}

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
    const res = await alertApi.getAlerts({ market: currentMarket.value, days: filters.days });
    if (res.success) rangeAlerts.value = res.data;
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
  resetQuickFilters();
  loadStrategies();
  loadAlerts();
});

// 只有區間會改變要跟後端拿的資料；策略／強度／方向都是前端篩，不需重打 API
watch(() => filters.days, loadAlerts);
</script>
