<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <!-- 頂部標題 -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div>
        <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-cog text-primary text-2xl"></i>
          股票與爬蟲管理
        </h1>
        <p class="text-sm text-surface-500 mt-1">
          管理追蹤個股清單、手動觸發 {{ marketMeta.exchange }} 法人與籌碼資料同步任務
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
        <div class="flex justify-between text-xs font-semibold text-surface-600 dark:text-surface-400">
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

    <!-- 每日自動排程設定 -->
    <div class="card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900 space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
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

    <!-- 追蹤股票清單管理 -->
    <div class="card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900 space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h3 class="text-lg font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
          <i class="pi pi-list text-primary"></i> 追蹤股票號碼設定 (.env)
        </h3>

        <!-- 新增股票輸入框：支援自動完成（打代號或名稱選建議）與一次輸入多筆（chips），
             未命中建議也可直接打完整代碼按 Enter（AutoComplete 預設 forceSelection=false）。 -->
        <div class="flex items-start gap-2">
          <AutoComplete
            v-model="selectedStocks"
            :suggestions="suggestions"
            optionLabel="label"
            multiple
            display="chip"
            dropdown
            :disabled="isAdding"
            @complete="onAutocomplete"
            :placeholder="`輸入股票代號，可一次輸入多筆 (例: ${currentMarket === 'tw' ? '2330' : 'AAPL'})`"
            class="w-72"
            inputClass="text-sm"
          />
          <button
            @click="addStocks"
            :disabled="isAdding || selectedStocks.length === 0"
            class="px-4 py-2 font-bold text-sm bg-primary text-primary-contrast hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl flex items-center gap-1.5 transition-colors shadow-sm shrink-0"
          >
            <i :class="['pi', isAdding ? 'pi-spin pi-spinner' : 'pi-plus']"></i> 新增
          </button>
        </div>
      </div>

      <!-- 股票清單資料表 -->
      <div class="pt-2 overflow-x-auto">
        <DataTable
          :value="trackedRows"
          dataKey="code"
          sortField="code"
          :sortOrder="1"
          stripedRows
          removableSort
          class="tracked-stocks-table"
        >
          <template #empty>
            <div class="text-center text-surface-400 py-8 text-sm">
              <i class="pi pi-inbox text-2xl mb-2 block"></i>
              尚無追蹤中的股票，請於上方輸入代號新增
            </div>
          </template>

          <Column field="code" header="代號" sortable style="width: 9rem">
            <template #body="{ data }">
              <button
                @click="goToStock(data.code)"
                :title="`查看 ${data.code} ${getStockName(data.code)} 的個股分析`"
                class="font-black text-primary hover:underline"
              >
                {{ data.code }}
              </button>
            </template>
          </Column>

          <Column field="name" header="名稱" sortable>
            <template #body="{ data }">
              <span
                @click="goToStock(data.code)"
                class="font-bold text-surface-900 dark:text-surface-0 cursor-pointer hover:text-primary"
              >
                {{ data.name || '-' }}
              </span>
            </template>
          </Column>

          <Column field="start_date" header="追蹤區間" sortable>
            <template #body="{ data }">
              <span v-if="pendingStockIds.includes(data.code)" class="text-xs font-bold text-amber-500 flex items-center gap-1.5">
                <i class="pi pi-spin pi-spinner"></i> 背景抓取中...
              </span>
              <span v-else-if="data.start_date" class="text-sm text-surface-600 dark:text-surface-300 flex items-center gap-1.5">
                <i class="pi pi-calendar text-surface-400"></i>
                {{ data.start_date }} ~ {{ data.end_date }}
              </span>
              <span v-else class="text-xs text-surface-400 flex items-center gap-1.5">
                <i class="pi pi-info-circle"></i> 尚無抓取資料
              </span>
            </template>
          </Column>

          <Column field="missing_price_days" header="資料缺漏" sortable style="width: 10rem">
            <template #body="{ data }">
              <span
                v-if="data.missing_price_days > 0"
                :title="`有 ${data.missing_price_days} 天沒有開盤/收盤價，請執行重新抓取補齊`"
                class="text-xs font-bold text-amber-600 dark:text-amber-400 flex items-center gap-1"
              >
                <i class="pi pi-exclamation-triangle"></i>
                缺漏 {{ data.missing_price_days }} 天
              </span>
              <span v-else class="text-xs text-surface-400">—</span>
            </template>
          </Column>

          <Column header="操作" style="width: 7rem">
            <template #body="{ data }">
              <div class="flex items-center gap-1">
                <button
                  @click="openRefetch(data)"
                  :disabled="fetchStatus?.is_running"
                  :title="`重新抓取 ${data.code} ${getStockName(data.code)} 的歷史資料`"
                  class="text-surface-400 hover:text-primary p-2 rounded-lg hover:bg-primary-50 dark:hover:bg-primary-900/20 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-surface-400 transition-colors"
                >
                  <i class="pi pi-refresh text-lg"></i>
                </button>
                <button
                  @click="removeStock(data.code)"
                  :title="`移除股票 ${data.code} ${getStockName(data.code)}`"
                  class="text-surface-400 hover:text-red-500 p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                >
                  <i class="pi pi-trash text-lg"></i>
                </button>
              </div>
            </template>
          </Column>
        </DataTable>
      </div>
    </div>

    <!-- 單股重新抓取彈窗 -->
    <RefetchStockDialog
      v-model:visible="refetchVisible"
      :stock-id="refetchTarget?.code || ''"
      :stock-name="refetchTarget ? getStockName(refetchTarget.code) : ''"
      :market="currentMarket"
      :missing-days="refetchTarget?.missing_price_days || 0"
      :busy="isRefetching"
      @confirm="doRefetch"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import RefetchStockDialog from '@/components/RefetchStockDialog.vue';
import { stockApi } from '@/service/stockApi';
import { useCrawlerStatus } from '@/composables/useCrawlerStatus';
import { useMarket } from '@/composables/useMarket';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';

const trackedCodes = ref([]);
const stockNameMap = ref({});
const selectedStocks = ref([]); // AutoComplete v-model：字串或 {symbol,name,label,...} 建議物件混合陣列
const suggestions = ref([]);
const isAdding = ref(false);
const isSyncingSymbols = ref(false);
const pendingStockIds = ref([]); // 正在等待背景抓取完成的股號（批次新增/單股重抓共用）
const refetchVisible = ref(false);
const refetchTarget = ref(null);
const isRefetching = ref(false);
const { fetchStatus, isRunning, checkStatus } = useCrawlerStatus();
const { currentMarket, marketMeta } = useMarket();
const toast = useToast();
const confirm = useConfirm();
const router = useRouter();
const logContainerEl = ref(null);

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

onMounted(async () => {
  await loadTrackedStocks();
  await checkStatus();
  await loadSchedule();
});

watch(currentMarket, () => {
  loadTrackedStocks();
});

watch(() => fetchStatus.value?.logs?.length, async () => {
  await nextTick();
  if (logContainerEl.value) {
    logContainerEl.value.scrollTop = logContainerEl.value.scrollHeight;
  }
});

function getStockName(code) {
  return stockNameMap.value[code] || '';
}

// 表格用資料：合併股名，供欄位排序/顯示使用
const trackedRows = computed(() =>
  trackedCodes.value.map(stock => ({
    ...stock,
    name: getStockName(stock.code)
  }))
);

function goToStock(code) {
  router.push(`/stock/${currentMarket.value}/${code}`);
}

async function loadTrackedStocks() {
  try {
    const [trackedRes, availRes] = await Promise.allSettled([
      stockApi.getTrackedStocks(currentMarket.value),
      stockApi.getAvailableStocks(currentMarket.value)
    ]);

    if (availRes.status === 'fulfilled' && availRes.value.success) {
      const map = {};
      availRes.value.data.forEach(s => {
        map[s.stock_id] = s.stock_name;
      });
      stockNameMap.value = map;
    }

    if (trackedRes.status === 'fulfilled' && trackedRes.value.success) {
      trackedCodes.value = trackedRes.value.data;
    }
  } catch (err) {
    console.error('取得追蹤清單失敗:', err);
  }
}

// AutoComplete 的 @complete：依輸入字串向後端要建議清單，附上 label 供 optionLabel 顯示「代號 名稱」
async function onAutocomplete(event) {
  try {
    const res = await stockApi.suggestSymbols(event.query, currentMarket.value, 15);
    suggestions.value = res.success
      ? res.data.map(s => ({ ...s, label: s.name ? `${s.symbol} ${s.name}` : s.symbol }))
      : [];
  } catch (err) {
    suggestions.value = [];
  }
}

// 批次新增：selectedStocks 裡的項目可能是建議物件（有 .symbol）或使用者手動打完直接 Enter 的純字串
async function addStocks() {
  const codes = [...new Set(
    selectedStocks.value
      .map(s => (typeof s === 'string' ? s.trim() : s.symbol))
      .filter(Boolean)
  )];
  if (!codes.length) return;

  isAdding.value = true;
  try {
    const res = await stockApi.addTrackedStocks(codes, currentMarket.value);
    if (res.success) {
      trackedCodes.value = res.data;
      selectedStocks.value = [];
      await loadTrackedStocks();
      toast.add({ severity: 'success', summary: '已加入追蹤', detail: res.message, life: 3000 });

      if (res.unknown?.length) {
        toast.add({
          severity: 'warn',
          summary: '部分代號未能驗證',
          detail: `在台股代碼清單中找不到：${res.unknown.join(', ')}，仍已加入追蹤清單`,
          life: 5000
        });
      }

      // 針對新加入的代號，並行檢查是否已有歷史資料；沒有的一次性觸發背景抓取（而非逐檔各打一次）
      const addedCodes = res.added || [];
      const needFetch = [];
      await Promise.allSettled(addedCodes.map(async code => {
        try {
          const chartRes = await stockApi.getChartData(code, 'daily', 3, currentMarket.value);
          if (!(chartRes.success && chartRes.data?.records?.length > 0)) needFetch.push(code);
        } catch (checkErr) {
          needFetch.push(code);
        }
      }));

      if (needFetch.length) {
        pendingStockIds.value = [...pendingStockIds.value, ...needFetch];
        await stockApi.triggerFetch(needFetch, 3, currentMarket.value);
        await checkStatus();
        toast.add({
          severity: 'info',
          summary: '背景抓取中',
          detail: `${needFetch.length} 檔尚無歷史資料，已啟動背景抓取，完成後會自動更新清單`,
          life: 4000
        });
      }
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '新增失敗', detail: err.response?.data?.detail || '新增股票失敗', life: 4000 });
  } finally {
    isAdding.value = false;
  }
}

// 手動觸發全市場代碼主檔同步：讓上面的自動完成建議清單有資料可查
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

function removeStock(code) {
  const name = getStockName(code);
  const displayName = name ? `${code} (${name})` : code;
  confirm.require({
    message: `確定要將股票 ${displayName} 從追蹤清單中移除嗎？`,
    header: '取消追蹤確認',
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: '移除',
    rejectLabel: '取消',
    acceptProps: { severity: 'danger' },
    accept: async () => {
      try {
        const res = await stockApi.removeTrackedStock(code, currentMarket.value);
        if (res.success) {
          trackedCodes.value = res.data;
          toast.add({ severity: 'success', summary: '已移除', detail: `已取消追蹤 ${displayName}`, life: 3000 });
        }
      } catch (err) {
        toast.add({ severity: 'error', summary: '移除失敗', detail: err.response?.data?.detail || '移除股票失敗', life: 4000 });
      }
    }
  });
}

function openRefetch(stock) {
  refetchTarget.value = stock;
  refetchVisible.value = true;
}

// 單股重抓：以 repair 模式送出，後端會忽略增量邏輯改用完整區間，才補得到中間的缺漏
async function doRefetch({ stockId, months }) {
  isRefetching.value = true;
  try {
    const res = await stockApi.triggerFetch([stockId], months, currentMarket.value, 'repair');
    if (res.success) {
      pendingStockIds.value = [...pendingStockIds.value, stockId];
      refetchVisible.value = false;
      await checkStatus();
      toast.add({
        severity: 'info',
        summary: '背景抓取中',
        detail: `已開始重新抓取 ${stockId} 近 ${months} 個月的資料`,
        life: 4000
      });
    } else {
      toast.add({
        severity: 'warn',
        summary: '無法啟動',
        detail: res.error?.message || res.message || '已有抓取任務執行中',
        life: 4000
      });
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '啟動失敗', detail: '啟動重新抓取失敗', life: 4000 });
  } finally {
    isRefetching.value = false;
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

// 監控全域抓取狀態：等到自己觸發的背景抓取完成，就自動刷新清單並提示（批次新增/單股重抓共用同一個陣列）
watch(isRunning, async (running, wasRunning) => {
  if (wasRunning && !running && pendingStockIds.value.length) {
    const done = pendingStockIds.value;
    pendingStockIds.value = [];
    await loadTrackedStocks();
    const detail = done.length === 1 ? `${done[0]} 的歷史資料已就緒` : `${done.length} 檔股票的歷史資料已就緒`;
    toast.add({ severity: 'success', summary: '資料抓取完成', detail, life: 3000 });
  }
});
</script>
