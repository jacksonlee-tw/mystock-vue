<template>
  <div class="card !m-0 rounded-2xl border border-surface-200 dark:border-surface-700/80 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
    <!-- 標頭：一律顯示，讓使用者確定「有沒有警示」本身就是資訊，而不是猜功能是否正常運作 -->
    <div class="flex flex-wrap items-center gap-3 px-5 py-4">
      <div class="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-900/30 text-primary flex items-center justify-center shrink-0">
        <i class="pi pi-bell text-lg"></i>
      </div>
      <div class="min-w-0">
        <div class="font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
          策略警示
          <span class="text-xs font-semibold text-surface-400">近 {{ lookbackDays }} 天</span>
        </div>
        <div class="text-xs text-surface-500">此股票符合的均線／籌碼策略條件</div>
      </div>

      <!-- 方向統計徽章：只在有資料時顯示，呼應 AlertDashboard 的偏多/偏空配色慣例 -->
      <div v-if="!loading && !error && alerts.length > 0" class="flex items-center gap-1.5 ml-auto">
        <span v-if="bullishCount > 0" class="inline-flex items-center gap-1 pl-2 pr-2.5 py-1 text-xs font-bold rounded-full bg-up-soft text-up">
          <i class="pi pi-arrow-up"></i>{{ bullishCount }} 偏多
        </span>
        <span v-if="bearishCount > 0" class="inline-flex items-center gap-1 pl-2 pr-2.5 py-1 text-xs font-bold rounded-full bg-down-soft text-down">
          <i class="pi pi-arrow-down"></i>{{ bearishCount }} 偏空
        </span>
      </div>
      <div v-else-if="!loading && !error" class="ml-auto text-xs font-semibold text-surface-400 flex items-center gap-1.5">
        <i class="pi pi-check-circle"></i>目前無符合的策略警示
      </div>
    </div>

    <!-- 載入中：小型 inline 提示，不做整頁遮罩——這只是主頁面的輔助資訊，載入慢也不該擋住看圖表/表格 -->
    <div v-if="loading" class="px-5 pb-5 flex items-center gap-2 text-sm text-surface-400">
      <i class="pi pi-spin pi-spinner"></i>正在檢查策略警示...
    </div>

    <!-- 載入失敗：同樣走 inline 提示，不擋頁面；使用者仍可正常看圖表 -->
    <div v-else-if="error" class="px-5 pb-5 flex items-center gap-2 text-sm text-red-500">
      <i class="pi pi-exclamation-circle"></i>{{ error }}
      <button type="button" class="font-bold underline hover:no-underline" @click="load">重試</button>
    </div>

    <template v-else-if="alerts.length > 0">
      <div class="px-5 pb-5 pt-1 space-y-3">
        <!-- show-chart-link 開啟（KD指標 設計規格書 §7.5「同場加映」）：早期認為「已經在該股票
             頁面，自我導航連結多餘」而關閉，但「查看圖表」現在會帶 indicator=kd + highlight
             跳去獨立的圖表明細頁（ChartDetailView.vue）並自動開 KD 副圖、標出訊號當天，
             不再是原地打轉的無用連結，兩處（AlertDashboard/StockAlertsPanel）套用同一組 query 契約。 -->
        <AlertTimeline :alerts="visibleAlerts" :strategy-list="strategyList" />
      </div>
      <div v-if="alerts.length > collapsedCount" class="px-5 pb-4 -mt-1">
        <button
          type="button"
          class="w-full text-center text-sm font-bold text-primary hover:underline py-1"
          @click="expanded = !expanded"
        >
          {{ expanded ? '收合' : `顯示全部 ${alerts.length} 筆` }}
          <i class="pi ml-1" :class="expanded ? 'pi-chevron-up' : 'pi-chevron-down'"></i>
        </button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { alertApi } from '@/service/alertApi';
import { classifyDirection } from '@/utils/alertDirection';
import AlertTimeline from '@/components/AlertTimeline.vue';

const props = defineProps({
  stockId: { type: String, required: true },
  market: { type: String, required: true },
  // 與股票頁的圖表時間範圍（月）連動，選越長的區間，警示回溯範圍也跟著放大，不用另外多開一組篩選器
  months: { type: Number, default: 3 }
});

const collapsedCount = 3; // 預設只顯示最新幾筆，避免警示一多就把頁面撐得過長
const expanded = ref(false);
const alerts = ref([]);
const strategyList = ref([]);
const loading = ref(true);
const error = ref(null);

const lookbackDays = computed(() => Math.max(30, props.months * 30));

const visibleAlerts = computed(() => (expanded.value ? alerts.value : alerts.value.slice(0, collapsedCount)));

const bullishCount = computed(() => alerts.value.filter((a) => classifyDirection(a.direction) === 'bullish').length);
const bearishCount = computed(() => alerts.value.filter((a) => classifyDirection(a.direction) === 'bearish').length);

async function loadStrategies() {
  try {
    const res = await alertApi.getStrategies(props.market);
    if (res.success) strategyList.value = res.data;
  } catch {
    // 策略清單只用來顯示分類圖示，載入失敗不影響警示本身的呈現
  }
}

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const res = await alertApi.getAlerts({ market: props.market, symbol: props.stockId, days: lookbackDays.value });
    if (res.success) alerts.value = res.data;
    else error.value = '載入策略警示時發生未知錯誤';
  } catch (err) {
    error.value = err.response?.data?.error?.message || err.response?.data?.detail || err.message || '無法載入策略警示';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadStrategies();
  load();
});

// 切換股票／市場時整組重載；區間（months）改變只需重打警示清單，策略清單與市場無關不必重抓
watch([() => props.stockId, () => props.market], () => {
  expanded.value = false;
  loadStrategies();
  load();
});
watch(() => props.months, () => {
  load();
});
</script>
