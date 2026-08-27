<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <Toast />

    <div>
      <h1 class="text-3xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
        <i class="pi pi-android text-primary text-3xl"></i>
        AI 診股報告紀錄
      </h1>
      <p class="text-base text-surface-500 mt-1">歷史 AI 技術分析報告查詢（AI 技術分析報告 系統開發規格書 §7.4）</p>
    </div>

    <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
      <!-- 篩選列 -->
      <div class="flex flex-wrap items-end gap-3 p-4 border-b border-surface-100 dark:border-surface-800">
        <div class="flex flex-col gap-1">
          <label class="text-[11px] font-bold text-surface-400 uppercase">市場</label>
          <SelectButton v-model="filters.market" :options="MARKET_OPTIONS" optionLabel="label" optionValue="value" @change="load" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[11px] font-bold text-surface-400 uppercase">研判</label>
          <SelectButton v-model="filters.verdict" :options="VERDICT_OPTIONS" optionLabel="label" optionValue="value" @change="load" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[11px] font-bold text-surface-400 uppercase">股票代號</label>
          <input
            v-model.trim="filters.symbol"
            @keyup.enter="load"
            placeholder="例：2330"
            class="bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg px-2.5 py-1.5 text-xs w-28 focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[11px] font-bold text-surface-400 uppercase">交易日（起）</label>
          <input
            v-model="filters.dateFrom"
            type="date"
            class="bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[11px] font-bold text-surface-400 uppercase">交易日（迄）</label>
          <input
            v-model="filters.dateTo"
            type="date"
            class="bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <button
          @click="load"
          class="px-3 py-1.5 text-xs font-bold bg-primary text-primary-contrast rounded-lg hover:bg-primary-600 transition-colors"
        >
          <i class="pi pi-search mr-1"></i>查詢
        </button>
        <button
          @click="resetFilters"
          class="px-3 py-1.5 text-xs font-bold text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-800 rounded-lg transition-colors"
        >
          清除
        </button>
        <div class="ml-auto text-sm text-surface-400">共 {{ reports.length }} 筆</div>
      </div>

      <DataTable :value="reports" :loading="loading" paginator :rows="20" size="small">
        <Column field="trade_date" header="交易日" style="white-space:nowrap" />
        <Column header="標的">
          <template #body="{ data }">
            <span class="font-bold">{{ data.symbol }}</span>
            <span v-if="data.stock_name" class="text-surface-400 ml-1">{{ data.stock_name }}</span>
          </template>
        </Column>
        <Column header="研判">
          <template #body="{ data }">
            <span
              class="px-2 py-0.5 rounded-full text-[11px] font-black"
              :style="{ backgroundColor: verdictColor(data.verdict, data.market_type) + '1a', color: verdictColor(data.verdict, data.market_type) }"
            >
              {{ VERDICT_LABEL[data.verdict] || '—' }}
            </span>
          </template>
        </Column>
        <Column header="結論">
          <template #body="{ data }"><span class="text-xs">{{ (data.headline || '').slice(0, 40) }}</span></template>
        </Column>
        <Column field="provider" header="Provider" style="white-space:nowrap" />
        <Column header="信心">
          <template #body="{ data }">{{ CONFIDENCE_LABEL[data.confidence] || data.confidence || '—' }}</template>
        </Column>
        <Column header="">
          <template #body="{ data }">
            <Button icon="pi pi-eye" size="small" text @click="showDetail(data)" title="檢視完整報告" />
            <Button icon="pi pi-trash" size="small" text severity="danger" @click="confirmDelete(data)" title="刪除" />
          </template>
        </Column>
      </DataTable>
    </div>

    <!-- 詳情：與即時產生報告共用同一個呈現元件（規格書 §7.4），資料來源改為 /reports/{id} -->
    <AiAnalysisDialog
      v-model:visible="detailVisible"
      stage="result"
      :loading="detailLoading"
      :error="detailError"
      :report="detailReport"
      :market="detailReport?.market || 'tw'"
    />
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';
import AiAnalysisDialog from '@/components/AiAnalysisDialog.vue';
import { aiAnalysisApi } from '@/service/aiAnalysisApi';
import { getUpDownColor } from '@/utils/marketColors';

const toast = useToast();
const confirm = useConfirm();

const MARKET_OPTIONS = [
  { label: '全部', value: null },
  { label: '台股', value: 'tw' },
  { label: '美股', value: 'us' }
];
const VERDICT_OPTIONS = [
  { label: '全部', value: null },
  { label: '偏多', value: 'bullish' },
  { label: '偏空', value: 'bearish' },
  { label: '中性', value: 'neutral' }
];
const VERDICT_LABEL = { bullish: '偏多', bearish: '偏空', neutral: '中性' };
const CONFIDENCE_LABEL = { high: '高', medium: '中', low: '低' };

const filters = reactive({ market: null, verdict: null, symbol: '', dateFrom: null, dateTo: null });

const reports = ref([]);
const loading = ref(true);

function verdictColor(verdict, market) {
  const { up, down } = getUpDownColor(market);
  if (verdict === 'bullish') return up;
  if (verdict === 'bearish') return down;
  return '#64748b';
}

async function load() {
  loading.value = true;
  try {
    const res = await aiAnalysisApi.listReports({
      market: filters.market,
      symbol: filters.symbol || undefined,
      dateFrom: filters.dateFrom || undefined,
      dateTo: filters.dateTo || undefined,
      verdict: filters.verdict,
      limit: 100
    });
    reports.value = res.data?.items || [];
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: '載入失敗',
      detail: err.response?.data?.error?.message || err.message,
      life: 4000
    });
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  filters.market = null;
  filters.verdict = null;
  filters.symbol = '';
  filters.dateFrom = null;
  filters.dateTo = null;
  load();
}

// 詳情彈窗：與 StockDashboard.vue 觸發的即時報告共用 AiAnalysisDialog.vue，
// 只是資料來源改為既有的 GET /ai/reports/{id}（規格書 §7.4）
const detailVisible = ref(false);
const detailLoading = ref(false);
const detailError = ref(null);
const detailReport = ref(null);

async function showDetail(row) {
  detailVisible.value = true;
  detailError.value = null;
  detailReport.value = null;
  detailLoading.value = true;
  try {
    const res = await aiAnalysisApi.getReport(row.id);
    detailReport.value = res.data;
  } catch (err) {
    detailError.value = err.response?.data?.error?.message || err.message || '讀取報告失敗';
  } finally {
    detailLoading.value = false;
  }
}

function confirmDelete(row) {
  confirm.require({
    message: `確定要刪除 ${row.symbol}（${row.trade_date}）的 AI 報告嗎？`,
    header: '刪除確認',
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: '刪除',
    rejectLabel: '取消',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await aiAnalysisApi.deleteReport(row.id);
        toast.add({ severity: 'success', summary: '已刪除', life: 2500 });
        await load();
      } catch (err) {
        toast.add({
          severity: 'error',
          summary: '刪除失敗',
          detail: err.response?.data?.error?.message || err.message,
          life: 4000
        });
      }
    }
  });
}

onMounted(load);
</script>
