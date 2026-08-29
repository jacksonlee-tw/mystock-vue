<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <!-- 頂部標題 -->
    <div class="flex items-center flex-col md:flex-row md:items-center justify-between gap-4 card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div>
        <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-cog text-primary text-2xl"></i>
          股票與爬蟲管理
        </h1>
        <p class="text-sm text-surface-500 mt-1">
          手動觸發 {{ marketMeta.exchange }} 法人與籌碼資料同步任務、管理每日排程與匯率資料
        </p>
      </div>

      <div class="flex items-center gap-2">
        <!-- 同步全市場代碼主檔：餵給下方追蹤股票輸入框與 Ctrl+K 搜尋的自動完成建議用 -->
        <button
          @click="syncSymbolMaster"
          :disabled="isSyncingSymbols"
          :title="`從 ${currentMarket === 'tw' ? 'TWSE／TPEx' : 'SEC EDGAR'} 抓取全市場代碼與名稱，寫入資料庫供代號自動完成使用`"
          class="px-4 py-2.5 font-bold text-surface-700 dark:text-surface-200 bg-surface-100 dark:bg-surface-800 hover:bg-surface-200 dark:hover:bg-surface-700 disabled:opacity-50 rounded-xl flex items-center gap-2 transition-all"
        >
          <i :class="['pi text-lg', isSyncingSymbols ? 'pi-spin pi-spinner' : 'pi-database']"></i>
          {{ isSyncingSymbols ? '同步代碼清單中...' : `同步${marketMeta.label}代碼清單` }}
        </button>

        <!-- 觸發抓取按鈕 -->
        <button
          @click="triggerFetch"
          :disabled="fetchStatus?.is_running"
          class="px-5 py-2.5 font-bold text-white bg-primary hover:bg-primary-600 disabled:opacity-50 rounded-xl flex items-center gap-2 transition-all shadow-md"
        >
          <i :class="['pi text-lg', fetchStatus?.is_running ? 'pi-spin pi-spinner' : 'pi-cloud-download']"></i>
          {{ fetchStatus?.is_running ? '同步資料執行中...' : `立即同步 ${marketMeta.exchange} 資料` }}
        </button>
      </div>
    </div>

    <!-- 抓取狀態與實時進度面板 -->
    <div v-if="fetchStatus" class="card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900 space-y-4">
      <div class="flex items-center justify-between">
        <h3 class="text-lg font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
          <i class="pi pi-sync text-primary"></i> 爬蟲任務執行狀態
        </h3>
        <span 
          :class="[
            'px-3 py-1 text-xs font-bold rounded-full',
            fetchStatus.status === 'running' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300' :
            fetchStatus.status === 'completed' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' :
            fetchStatus.status === 'error' ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' :
            'bg-surface-100 text-surface-600 dark:bg-surface-800 dark:text-surface-400'
          ]"
        >
          {{ statusLabel }}
        </span>
      </div>

      <!-- 進度條 -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between text-xs font-semibold text-surface-600 dark:text-surface-400">
          <span>{{ fetchStatus.message || '準備就緒' }}</span>
          <span>{{ fetchStatus.progress_percent }}%</span>
        </div>
        <div class="w-full h-3 bg-surface-100 dark:bg-surface-800 rounded-full overflow-hidden">
          <div 
            class="h-full bg-primary transition-all duration-300 rounded-full"
            :style="{ width: `${fetchStatus.progress_percent}%` }"
          ></div>
        </div>
      </div>

      <!-- 執行日誌控制框 -->
      <div ref="logContainerEl" class="bg-surface-950 text-surface-200 p-4 rounded-xl font-mono text-xs max-h-48 overflow-y-auto space-y-1">
        <div v-if="!fetchStatus.logs || fetchStatus.logs.length === 0" class="text-surface-500 italic">
          目前無運行中的日誌記錄...
        </div>
        <div v-for="(log, idx) in fetchStatus.logs" :key="idx" class="leading-relaxed">
          {{ log }}
        </div>
      </div>
    </div>

    <!-- 每日匯率資料（USD/JPY/CNY，供個人記帳模組交易紀錄頁「折算台幣」欄位使用） -->
    <div class="card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900 space-y-4">
      <div class="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h3 class="text-lg font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
            <i class="pi pi-dollar text-primary"></i> 每日匯率資料
          </h3>
          <p class="text-xs text-surface-500 mt-1">
            來源：公開市場參考匯率（非台灣銀行牌告價，該來源需執行 JS 驗證無法自動抓取），啟動時與每日排程都會自動抓取一次
          </p>
        </div>
        <button
          @click="triggerExchangeRateFetch"
          :disabled="isFetchingRates"
          class="px-4 py-2 font-bold text-sm text-surface-700 dark:text-surface-200 bg-surface-100 dark:bg-surface-800 hover:bg-surface-200 dark:hover:bg-surface-700 disabled:opacity-50 rounded-xl flex items-center gap-2 transition-all"
        >
          <i :class="['pi text-sm', isFetchingRates ? 'pi-spin pi-spinner' : 'pi-refresh']"></i>
          {{ isFetchingRates ? '更新中...' : '立即更新匯率' }}
        </button>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div v-for="c in ['USD', 'JPY', 'CNY']" :key="c" class="p-3 rounded-xl border border-surface-200 dark:border-surface-700">
          <div class="text-xs font-bold text-surface-400">{{ c }} / TWD</div>
          <template v-if="exchangeRates[c]">
            <div class="text-lg font-black text-surface-900 dark:text-surface-0 num">{{ exchangeRates[c].rate.toFixed(4) }}</div>
            <div class="text-[11px] text-surface-400 mt-1"><i class="pi pi-calendar"></i> {{ exchangeRates[c].rate_date }}</div>
          </template>
          <div v-else class="text-sm text-surface-400 mt-1">尚無資料</div>
        </div>
      </div>
    </div>

    <!-- 每日自動排程設定 -->
    <div class="card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900 space-y-4">
      <div class="flex items-center flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 class="text-lg font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
            <i class="pi pi-clock text-primary"></i> 每日自動排程
          </h3>
          <p class="text-sm text-surface-500 mt-1">
            設定每日自動抓取＋策略掃描的執行時間；儲存後<b>立即生效</b>，不需重啟服務。
          </p>
        </div>
        <div class="flex items-center gap-2">
          <span
            v-if="schedule"
            class="px-2.5 py-1 rounded-lg text-xs font-bold"
            :class="schedule.scheduler_running
              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
              : 'bg-surface-200 text-surface-600 dark:bg-surface-700 dark:text-surface-300'"
          >
            {{ schedule.scheduler_running ? '排程器運行中' : '排程器未啟動' }}
          </span>
          <span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-surface-100 dark:bg-surface-800 text-surface-500">
            <i class="pi pi-globe"></i> {{ schedule?.timezone || 'Asia/Taipei' }}
          </span>
        </div>
      </div>

      <div v-if="scheduleLoading" class="flex items-center gap-2 text-surface-500 text-sm py-4">
        <i class="pi pi-spin pi-spinner"></i> 載入排程設定...
      </div>

      <div v-else-if="scheduleError" class="p-4 rounded-xl bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-sm flex items-center justify-between gap-3">
        <span><i class="pi pi-exclamation-triangle"></i> 排程設定載入失敗：{{ scheduleError }}</span>
        <button @click="loadSchedule" class="px-3 py-1.5 rounded-lg bg-red-100 dark:bg-red-900/40 font-bold text-xs">重試</button>
      </div>

      <div v-else-if="schedule" class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div
          v-for="m in SCHEDULE_MARKETS"
          :key="m.key"
          class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 space-y-3"
          :class="scheduleForm[m.key].enabled ? '' : 'opacity-60'"
        >
          <div class="flex items-center justify-between gap-3">
            <div class="font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
              <i :class="m.icon" class="text-primary"></i> {{ m.label }}
            </div>
            <label class="flex items-center gap-2 cursor-pointer">
              <span class="text-xs text-surface-500">{{ scheduleForm[m.key].enabled ? '啟用' : '停用' }}</span>
              <input type="checkbox" v-model="scheduleForm[m.key].enabled" class="w-9 h-5 accent-primary cursor-pointer" />
            </label>
          </div>

          <div class="flex items-center gap-3">
            <input
              type="time"
              v-model="scheduleForm[m.key].time"
              :disabled="!scheduleForm[m.key].enabled"
              class="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-xl bg-surface-0 dark:bg-surface-800 text-surface-900 dark:text-surface-0 text-lg font-mono font-bold focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
            />
            <div class="text-xs text-surface-500 leading-relaxed">
              <div>{{ m.hint }}</div>
              <div v-if="scheduleForm[m.key].enabled && schedule.health_check_delay_minutes">
                健康檢查 {{ healthCheckTime(m.key) }}
              </div>
            </div>
          </div>

          <div class="text-xs text-surface-500 flex items-center gap-1.5 pt-1 border-t border-surface-100 dark:border-surface-800">
            <i class="pi pi-calendar-clock"></i>
            <span v-if="!scheduleForm[m.key].enabled">已停用，不會自動執行</span>
            <span v-else-if="scheduleDirty">設定已變更，儲存後計算下次執行時間</span>
            <span v-else-if="schedule.markets[m.key].next_run_at">
              下次執行：{{ formatNextRun(schedule.markets[m.key].next_run_at) }}
            </span>
            <span v-else>尚未排定</span>
          </div>
        </div>
      </div>

      <div v-if="schedule && !scheduleLoading" class="flex items-center justify-between gap-3 flex-wrap pt-1">
        <p class="text-xs text-surface-500">
          <i class="pi pi-info-circle"></i>
          抓取完成後會自動接著執行策略掃描；若當下已有抓取任務進行中，該次排程會直接跳過而非排隊等待。
        </p>
        <div class="flex items-center gap-2">
          <button
            v-if="scheduleDirty"
            @click="resetSchedule"
            class="px-4 py-2 rounded-xl border border-surface-300 dark:border-surface-600 text-sm font-bold text-surface-600 dark:text-surface-300"
          >
            還原
          </button>
          <button
            @click="saveSchedule"
            :disabled="!scheduleDirty || scheduleSaving"
            class="px-5 py-2 font-bold text-white bg-primary hover:bg-primary-600 disabled:opacity-50 rounded-xl flex items-center gap-2 transition-all"
          >
            <i :class="['pi', scheduleSaving ? 'pi-spin pi-spinner' : 'pi-check']"></i>
            {{ scheduleSaving ? '儲存中...' : '儲存排程' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 追蹤股票清單：已整合至「追蹤與觀察名單」單一頁面（見規劃書 §6.1 方案 A），
         這裡只留摘要卡與導向按鈕，不再管理清單內容 -->
    <div class="card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900 space-y-4">
      <div class="flex items-center flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 class="text-lg font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
            <i class="pi pi-list text-primary"></i> 追蹤股票清單
          </h3>
          <p class="text-xs text-surface-500 mt-1">
            清單已整合至「追蹤與觀察名單」，可在該頁新增／編輯股票、目標買進價、追蹤原因與標籤
          </p>
        </div>
        <router-link
          to="/portfolio/watchlist"
          class="px-4 py-2 font-bold text-sm bg-primary text-primary-contrast hover:bg-primary-600 rounded-xl flex items-center gap-1.5 transition-colors shadow-sm shrink-0"
        >
          <i class="pi pi-arrow-right"></i> 前往管理
        </router-link>
      </div>

      <div v-if="trackingSummaryLoading" class="flex items-center gap-2 text-surface-400 text-xs py-2">
        <i class="pi pi-spin pi-spinner"></i> 載入中...
      </div>
      <div v-else class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div class="p-3 rounded-xl border border-surface-200 dark:border-surface-700">
          <div class="text-xs font-bold text-surface-400">追蹤中</div>
          <div class="text-xl font-black text-surface-900 dark:text-surface-0 num">{{ trackingSummary.total }}</div>
        </div>
        <div class="p-3 rounded-xl border border-surface-200 dark:border-surface-700">
          <div class="text-xs font-bold text-surface-400">已設目標價</div>
          <div class="text-xl font-black text-surface-900 dark:text-surface-0 num">{{ trackingSummary.withTarget }}</div>
        </div>
        <div class="p-3 rounded-xl border border-surface-200 dark:border-surface-700">
          <div class="text-xs font-bold text-surface-400">資料缺漏</div>
          <div class="text-xl font-black num" :class="trackingSummary.missing > 0 ? 'text-amber-600' : 'text-surface-900 dark:text-surface-0'">{{ trackingSummary.missing }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import { stockApi } from '@/service/stockApi';
import { portfolioApi } from '@/service/portfolioApi';
import { exchangeRateApi } from '@/service/exchangeRateApi';
import { useCrawlerStatus } from '@/composables/useCrawlerStatus';
import { useMarket } from '@/composables/useMarket';
import { useToast } from 'primevue/usetoast';

const isSyncingSymbols = ref(false);
const { fetchStatus, isRunning, checkStatus } = useCrawlerStatus();
const { currentMarket, marketMeta } = useMarket();
const toast = useToast();
const logContainerEl = ref(null);

// 追蹤股票清單摘要（清單管理已整合至「追蹤與觀察名單」，見規劃書 §6.1 方案 A）：
// 這裡只讀 GET /watchlist 帶 with_coverage 算出三個計數，不再自己維護整份清單資料
const trackingSummaryLoading = ref(true);
const trackingSummary = ref({ total: 0, withTarget: 0, missing: 0 });

async function loadTrackingSummary() {
  trackingSummaryLoading.value = true;
  try {
    const res = await portfolioApi.getWatchlist({ market: currentMarket.value, withCoverage: true });
    if (res.success) {
      const items = res.data;
      trackingSummary.value = {
        total: items.length,
        withTarget: items.filter((w) => w.target_price != null).length,
        missing: items.filter((w) => w.coverage && w.coverage.count && w.coverage.missing_price_days > 0).length
      };
    }
  } catch (err) {
    // 摘要卡是輔助資訊，載入失敗不影響本頁其餘爬蟲/排程/匯率功能
  } finally {
    trackingSummaryLoading.value = false;
  }
}

const statusLabel = computed(() => {
  if (!fetchStatus.value) return '未執行';
  switch (fetchStatus.value.status) {
    case 'running': return '🔄 正在同步中';
    case 'completed': return '✅ 同步完畢';
    case 'error': return '❌ 發生錯誤';
    default: return '靜止中';
  }
});

// ── 每日自動排程設定 ──────────────────────────────────────────
const SCHEDULE_MARKETS = [
  { key: 'tw', label: '台股', icon: 'pi pi-chart-line', hint: '建議設在台股盤後（14:30 以後）' },
  { key: 'us', label: '美股', icon: 'pi pi-globe', hint: '美股收盤後的隔日台北時間（預設 06:00）' }
];

const schedule = ref(null);
const scheduleLoading = ref(true);
const scheduleSaving = ref(false);
const scheduleError = ref('');
const scheduleForm = ref({ tw: { time: '14:30', enabled: true }, us: { time: '06:00', enabled: true } });
let scheduleSaved = JSON.stringify(scheduleForm.value);

const scheduleDirty = computed(() => JSON.stringify(scheduleForm.value) !== scheduleSaved);

function applyScheduleData(data) {
  schedule.value = data;
  scheduleForm.value = {
    tw: { time: data.markets.tw.time, enabled: data.markets.tw.enabled },
    us: { time: data.markets.us.time, enabled: data.markets.us.enabled }
  };
  scheduleSaved = JSON.stringify(scheduleForm.value);
}

async function loadSchedule() {
  scheduleLoading.value = true;
  scheduleError.value = '';
  try {
    const res = await stockApi.getSchedule();
    if (!res.success) throw new Error(res.error?.message || '未知錯誤');
    applyScheduleData(res.data);
  } catch (err) {
    scheduleError.value = err.message;
  } finally {
    scheduleLoading.value = false;
  }
}

async function saveSchedule() {
  scheduleSaving.value = true;
  try {
    const res = await stockApi.saveSchedule({
      tw: { time: scheduleForm.value.tw.time, enabled: scheduleForm.value.tw.enabled },
      us: { time: scheduleForm.value.us.time, enabled: scheduleForm.value.us.enabled }
    });
    if (!res.success) throw new Error(res.error?.message || '未知錯誤');
    applyScheduleData(res.data);
    toast.add({ severity: 'success', summary: '排程已更新', detail: '設定已立即套用，不需重啟服務', life: 3000 });
  } catch (err) {
    toast.add({ severity: 'error', summary: '排程儲存失敗', detail: err.message, life: 5000 });
  } finally {
    scheduleSaving.value = false;
  }
}

function resetSchedule() {
  scheduleForm.value = JSON.parse(scheduleSaved);
}

/** 健康檢查時間＝抓取時間 + 後端的延遲分鐘數（跨日會繞回） */
function healthCheckTime(market) {
  const [h, m] = (scheduleForm.value[market].time || '00:00').split(':').map(Number);
  const total = h * 60 + m + (schedule.value?.health_check_delay_minutes || 0);
  return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

function formatNextRun(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// ── 每日匯率資料（USD/JPY/CNY）──────────────────────────────
const exchangeRates = ref({});
const isFetchingRates = ref(false);

async function loadExchangeRates() {
  try {
    const res = await exchangeRateApi.getLatest();
    if (res.success) exchangeRates.value = res.data;
  } catch (err) { /* 匯率卡片是輔助資訊，載入失敗不影響主流程 */ }
}

async function triggerExchangeRateFetch() {
  isFetchingRates.value = true;
  try {
    const res = await exchangeRateApi.trigger();
    if (res.success) {
      toast.add({ severity: 'success', summary: '匯率已更新', detail: res.message, life: 3000 });
      await loadExchangeRates();
    } else {
      toast.add({ severity: 'warn', summary: '匯率更新失敗', detail: res.error?.message || res.message, life: 5000 });
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '更新失敗', detail: '啟動匯率抓取失敗', life: 4000 });
  } finally {
    isFetchingRates.value = false;
  }
}

onMounted(async () => {
  await loadTrackingSummary();
  await checkStatus();
  await loadSchedule();
  await loadExchangeRates();
});

watch(currentMarket, () => {
  loadTrackingSummary();
});

watch(() => fetchStatus.value?.logs?.length, async () => {
  await nextTick();
  if (logContainerEl.value) {
    logContainerEl.value.scrollTop = logContainerEl.value.scrollHeight;
  }
});

// 手動觸發全市場代碼主檔同步：讓 Ctrl+K 搜尋等其他頁面的代號自動完成建議有資料可查
async function syncSymbolMaster() {
  isSyncingSymbols.value = true;
  try {
    const res = await stockApi.syncSymbolMaster(currentMarket.value);
    if (res.success) {
      toast.add({ severity: 'success', summary: '已啟動同步', detail: res.message, life: 3000 });
    } else {
      toast.add({ severity: 'warn', summary: '無法啟動', detail: res.error?.message || res.message, life: 4000 });
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '啟動失敗', detail: '啟動代碼清單同步失敗', life: 4000 });
  } finally {
    isSyncingSymbols.value = false;
  }
}

async function triggerFetch() {
  try {
    const res = await stockApi.triggerFetch(null, null, currentMarket.value);
    if (res.success) {
      await checkStatus();
    } else {
      toast.add({ severity: 'warn', summary: '無法啟動', detail: res.message, life: 4000 });
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '啟動失敗', detail: '啟動爬蟲失敗', life: 4000 });
  }
}

// 全域抓取完成後，摘要卡的資料涵蓋範圍可能已改變，順便重新整理一次
watch(isRunning, async (running, wasRunning) => {
  if (wasRunning && !running) {
    await loadTrackingSummary();
  }
});
</script>
