<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <!-- 頂部標題 -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div>
        <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-table text-primary text-2xl"></i>
          全市場代碼查詢
        </h1>
        <p class="text-sm text-surface-500 mt-1">
          瀏覽／查詢 {{ marketMeta.label }} 全市場代碼主檔（含 ETF），可依代號、名稱或產業別篩選
        </p>
      </div>

      <button
        @click="syncSymbolMaster"
        :disabled="isSyncing"
        :title="`從 ${currentMarket === 'tw' ? 'TWSE／TPEx' : 'SEC EDGAR'} 重新抓取全市場代碼與名稱`"
        class="px-4 py-2.5 font-bold text-surface-700 dark:text-surface-200 bg-surface-100 dark:bg-surface-800 hover:bg-surface-200 dark:hover:bg-surface-700 disabled:opacity-50 rounded-xl flex items-center gap-2 transition-all shrink-0"
      >
        <i :class="['pi text-lg', isSyncing ? 'pi-spin pi-spinner' : 'pi-database']"></i>
        {{ isSyncing ? '同步代碼清單中...' : `同步${marketMeta.label}代碼清單` }}
      </button>
    </div>

    <!-- 篩選列 -->
    <div class="card p-4 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div class="flex flex-col sm:flex-row gap-3">
        <span class="relative flex-1">
          <i class="pi pi-search absolute left-3 top-1/2 -translate-y-1/2 text-surface-400 text-sm"></i>
          <InputText
            v-model="keyword"
            @input="onKeywordInput"
            :placeholder="`輸入代號或名稱關鍵字搜尋 (例: ${currentMarket === 'tw' ? '2330 / 台積電' : 'AAPL / Apple'})`"
            class="w-full pl-9"
          />
        </span>
        <Select
          v-model="industryCode"
          :options="industryOptions"
          optionLabel="label"
          optionValue="industry_code"
          placeholder="全部產業別"
          showClear
          class="w-full sm:w-64"
          @change="reload(1)"
        />
      </div>
      <p v-if="currentMarket === 'us' && industryOptions.length === 0" class="text-xs text-surface-400 mt-2">
        <i class="pi pi-info-circle"></i> 美股產業別目前只涵蓋已追蹤的股票，尚未有完整全市場分類資料
      </p>
    </div>

    <!-- 代碼主檔資料表 -->
    <div class="card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div class="overflow-x-auto">
        <DataTable
          :value="items"
          lazy
          paginator
          :rows="pageSize"
          :rowsPerPageOptions="[20, 50, 100]"
          :totalRecords="total"
          :loading="loading"
          :first="(page - 1) * pageSize"
          @page="onPage"
          dataKey="symbol"
          stripedRows
        >
          <template #empty>
            <div class="text-center text-surface-400 py-8 text-sm">
              <i class="pi pi-inbox text-2xl mb-2 block"></i>
              找不到符合條件的代碼{{ total === 0 && !keyword && !industryCode ? '，請先點右上角「同步代碼清單」' : '' }}
            </div>
          </template>

          <Column field="symbol" header="代號" style="width: 9rem">
            <template #body="{ data }">
              <button
                @click="goToStock(data.symbol)"
                :title="`查看 ${data.symbol} ${data.name || ''} 的個股分析`"
                class="font-black text-primary hover:underline"
              >
                {{ data.symbol }}
              </button>
            </template>
          </Column>

          <Column field="name" header="名稱">
            <template #body="{ data }">
              <span
                @click="goToStock(data.symbol)"
                class="font-bold text-surface-900 dark:text-surface-0 cursor-pointer hover:text-primary"
              >
                {{ data.name || '-' }}
              </span>
            </template>
          </Column>

          <Column field="exchange" header="交易所" style="width: 8rem">
            <template #body="{ data }">
              <span v-if="data.exchange" class="text-xs font-bold bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300 px-2 py-1 rounded">
                {{ data.exchange }}
              </span>
              <span v-else class="text-xs text-surface-400">—</span>
            </template>
          </Column>

          <Column field="industry_name" header="產業別">
            <template #body="{ data }">
              <span v-if="data.industry_name" class="text-sm text-surface-600 dark:text-surface-300">{{ data.industry_name }}</span>
              <span v-else class="text-xs text-surface-400">未分類</span>
            </template>
          </Column>

          <Column header="操作" style="width: 8rem">
            <template #body="{ data }">
              <button
                v-if="!trackedSet.has(data.symbol)"
                @click="addToTracked(data.symbol)"
                :disabled="addingSymbol === data.symbol"
                title="加入追蹤清單"
                class="px-2.5 py-1.5 text-xs font-bold bg-primary-50 dark:bg-primary-500/10 text-primary hover:bg-primary-100 dark:hover:bg-primary-500/20 rounded-lg flex items-center gap-1 disabled:opacity-50"
              >
                <i :class="['pi', addingSymbol === data.symbol ? 'pi-spin pi-spinner' : 'pi-plus']"></i> 追蹤
              </button>
              <span v-else class="px-2.5 py-1.5 text-xs font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                <i class="pi pi-check"></i> 已追蹤
              </span>
            </template>
          </Column>
        </DataTable>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash/debounce';
import { stockApi } from '@/service/stockApi';
import { useMarket } from '@/composables/useMarket';
import { useToast } from 'primevue/usetoast';

const { currentMarket, marketMeta } = useMarket();
const router = useRouter();
const toast = useToast();

const items = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(50);
const loading = ref(false);

const keyword = ref('');
const industryCode = ref(null);
const industryOptionsRaw = ref([]);
const industryOptions = computed(() =>
  industryOptionsRaw.value.map(o => ({ ...o, label: `${o.industry_name} (${o.industry_code})` }))
);

const isSyncing = ref(false);
const trackedSet = ref(new Set());
const addingSymbol = ref(null);

async function load() {
  loading.value = true;
  try {
    const res = await stockApi.listSymbols(currentMarket.value, {
      q: keyword.value.trim() || undefined,
      industryCode: industryCode.value || undefined,
      page: page.value,
      pageSize: pageSize.value,
    });
    if (res.success) {
      items.value = res.data.items;
      total.value = res.data.total;
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: '取得代碼清單失敗', life: 4000 });
  } finally {
    loading.value = false;
  }
}

function reload(toPage = 1) {
  page.value = toPage;
  load();
}

const onKeywordInput = debounce(() => reload(1), 300);

function onPage(event) {
  page.value = event.page + 1;
  pageSize.value = event.rows;
  load();
}

async function loadIndustryOptions() {
  try {
    const res = await stockApi.getSymbolIndustryOptions(currentMarket.value);
    industryOptionsRaw.value = res.success ? res.data : [];
  } catch (err) {
    industryOptionsRaw.value = [];
  }
}

async function loadTracked() {
  try {
    const res = await stockApi.getTrackedStocks(currentMarket.value);
    trackedSet.value = new Set(res.success ? res.data.map(s => s.code) : []);
  } catch (err) {
    trackedSet.value = new Set();
  }
}

async function addToTracked(symbol) {
  addingSymbol.value = symbol;
  try {
    const res = await stockApi.addTrackedStocks([symbol], currentMarket.value);
    if (res.success) {
      trackedSet.value = new Set([...trackedSet.value, symbol]);
      toast.add({ severity: 'success', summary: '已加入追蹤', detail: `${symbol} 已加入追蹤清單`, life: 3000 });
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '加入失敗', detail: err.response?.data?.detail || '加入追蹤清單失敗', life: 4000 });
  } finally {
    addingSymbol.value = null;
  }
}

async function syncSymbolMaster() {
  isSyncing.value = true;
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
    isSyncing.value = false;
  }
}

function goToStock(symbol) {
  router.push(`/stock/${currentMarket.value}/${symbol}`);
}

function resetAndLoad() {
  keyword.value = '';
  industryCode.value = null;
  page.value = 1;
  load();
  loadIndustryOptions();
  loadTracked();
}

onMounted(resetAndLoad);
watch(currentMarket, resetAndLoad);
</script>
