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
      <div class="bg-surface-950 text-surface-200 p-4 rounded-xl font-mono text-xs max-h-48 overflow-y-auto space-y-1">
        <div v-if="!fetchStatus.logs || fetchStatus.logs.length === 0" class="text-surface-500 italic">
          目前無運行中的日誌記錄...
        </div>
        <div v-for="(log, idx) in fetchStatus.logs" :key="idx" class="leading-relaxed">
          {{ log }}
        </div>
      </div>
    </div>

    <!-- 追蹤股票清單管理 -->
    <div class="card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900 space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h3 class="text-lg font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
          <i class="pi pi-list text-primary"></i> 追蹤股票號碼設定 (.env)
        </h3>

        <!-- 新增股票輸入框 -->
        <div class="flex items-center gap-2">
          <input
            v-model="newStockId"
            type="text"
            :placeholder="`請輸入股票代號 (例: ${currentMarket === 'tw' ? '2330' : 'AAPL'})`"
            :disabled="isAdding"
            @keyup.enter="addStock"
            class="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-xl bg-surface-0 dark:bg-surface-800 text-surface-900 dark:text-surface-0 text-sm focus:outline-none focus:ring-2 focus:ring-primary w-56 disabled:opacity-50"
          />
          <button
            @click="addStock"
            :disabled="isAdding || !newStockId.trim()"
            class="px-4 py-2 font-bold text-sm bg-primary text-primary-contrast hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl flex items-center gap-1.5 transition-colors shadow-sm"
          >
            <i :class="['pi', isAdding ? 'pi-spin pi-spinner' : 'pi-plus']"></i> 新增
          </button>
        </div>
      </div>

      <!-- 股票清單網格卡片 -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
        <div 
          v-for="stock in trackedCodes" 
          :key="stock.code"
          @click="goToStock(stock.code)"
          class="card h-full p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/40 flex flex-col justify-between hover:shadow-md transition-all cursor-pointer hover:-translate-y-1 hover:border-primary/50"
        >
          <div class="flex items-start justify-between gap-2 mb-3">
            <div class="flex items-center gap-3 w-full">
              <div class="w-12 h-12 shrink-0 rounded-lg bg-primary-100 dark:bg-primary-900/40 text-primary font-black flex items-center justify-center text-sm">
                {{ stock.code }}
              </div>
              <div class="flex-1 min-w-0">
                <div class="font-black text-surface-900 dark:text-surface-0 text-lg">
                  {{ stock.code }}
                </div>
                <div v-if="getStockName(stock.code)" class="text-sm font-bold text-primary leading-snug break-words">
                  {{ getStockName(stock.code) }}
                </div>
              </div>
            </div>
            
            <button 
              @click.stop="removeStock(stock.code)"
              :title="`移除股票 ${stock.code} ${getStockName(stock.code)}`"
              class="shrink-0 text-surface-400 hover:text-red-500 p-2 -mr-2 -mt-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
            >
              <i class="pi pi-trash text-lg"></i>
            </button>
          </div>

          <div class="mt-auto pt-2 border-t border-surface-200 dark:border-surface-700/50">
            <span v-if="pendingStockId === stock.code" class="text-xs font-bold text-amber-500 flex items-center gap-1.5">
              <i class="pi pi-spin pi-spinner"></i> 背景抓取中...
            </span>
            <span v-else-if="stock.start_date" class="text-xs text-surface-500 flex items-center gap-1.5">
              <i class="pi pi-calendar"></i>
              {{ stock.start_date }} ~ {{ stock.end_date }}
            </span>
            <span v-else class="text-xs text-surface-400 flex items-center gap-1.5">
              <i class="pi pi-info-circle"></i> 尚無抓取資料
            </span>
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
import { useCrawlerStatus } from '@/composables/useCrawlerStatus';
import { useMarket } from '@/composables/useMarket';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';

const trackedCodes = ref([]);
const stockNameMap = ref({});
const newStockId = ref('');
const isAdding = ref(false);
const pendingStockId = ref(null); // 正在等待背景抓取完成的股號
const { fetchStatus, isRunning, checkStatus } = useCrawlerStatus();
const { currentMarket, marketMeta } = useMarket();
const toast = useToast();
const confirm = useConfirm();
const router = useRouter();

const statusLabel = computed(() => {
  if (!fetchStatus.value) return '未執行';
  switch (fetchStatus.value.status) {
    case 'running': return '🔄 正在同步中';
    case 'completed': return '✅ 同步完畢';
    case 'error': return '❌ 發生錯誤';
    default: return '靜止中';
  }
});

onMounted(async () => {
  await loadTrackedStocks();
  await checkStatus();
});

watch(currentMarket, () => {
  loadTrackedStocks();
});

function getStockName(code) {
  return stockNameMap.value[code] || '';
}

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

async function addStock() {
  const code = newStockId.value.trim();
  if (!code) return;
  isAdding.value = true;
  try {
    const res = await stockApi.addTrackedStock(code, currentMarket.value);
    if (res.success) {
      trackedCodes.value = res.data;
      newStockId.value = '';
      await loadTrackedStocks();
      toast.add({ severity: 'success', summary: '已加入追蹤', detail: `${code} 已加入追蹤清單`, life: 3000 });

      // 檢查是否已有歷史資料；若無則自動觸發背景抓取，完成後自動刷新清單
      let hasData = false;
      try {
        const chartRes = await stockApi.getChartData(code, 'daily', 3, currentMarket.value);
        hasData = !!(chartRes.success && chartRes.data?.records?.length > 0);
      } catch (checkErr) {
        hasData = false;
      }

      if (!hasData) {
        pendingStockId.value = code;
        await stockApi.triggerFetch([code], 3, currentMarket.value);
        await checkStatus();
        toast.add({
          severity: 'info',
          summary: '背景抓取中',
          detail: `${code} 尚無歷史資料，已啟動背景抓取，完成後會自動更新清單`,
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

// 監控全域抓取狀態：等到自己觸發的背景抓取完成，就自動刷新清單並提示
watch(isRunning, async (running, wasRunning) => {
  if (wasRunning && !running && pendingStockId.value) {
    const done = pendingStockId.value;
    pendingStockId.value = null;
    await loadTrackedStocks();
    toast.add({ severity: 'success', summary: '資料抓取完成', detail: `${done} 的歷史資料已就緒`, life: 3000 });
  }
});
</script>
