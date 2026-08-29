<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <Toast />

    <div>
      <h1 class="text-3xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
        <i class="pi pi-history text-primary text-3xl"></i>
        LLM 執行歷史
      </h1>
      <p class="text-base text-surface-500 mt-1">
        查詢每一次呼叫 AI 模型的紀錄，含觸發功能、Provider／模型、Token 用量、耗時與預估成本
        （docs/16.AI技術分析/執行歷史頁面開發計劃.md）
      </p>
    </div>

    <!-- ══════════════════════ 用量彙總卡片 ══════════════════════ -->
    <div>
      <p class="text-xs text-surface-400 mb-2">
        彙總卡片僅套用「建立日期區間」篩選（對應 <code>GET /ai/usage</code> 的參數），不受下方 Provider／模型／狀態等其他篩選影響，且一律排除試跑列
      </p>
      <!-- !m-0：蓋掉全域 .card { margin-bottom: 2rem; &:last-child { margin-bottom: 0 } }（_utils.scss，
           設計給直向堆疊的單欄卡片用），版面間距一律交給 grid 的 gap-4 處理（比照 StockDashboard.vue 的
           KPI 卡片矩陣，CLAUDE.md 鐵則 2：同列卡片高度需一致）。 -->
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-4 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
          <span class="text-[11px] font-bold tracking-wide uppercase text-surface-400">總呼叫次數</span>
          <span class="text-2xl font-black text-surface-900 dark:text-surface-0 mt-2">{{ usage.call_count ?? '—' }}</span>
          <span class="text-[11px] text-surface-400 mt-1">含失敗，是「花錢的次數」</span>
        </div>
        <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-4 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
          <span class="text-[11px] font-bold tracking-wide uppercase text-surface-400">成功</span>
          <span class="text-2xl font-black text-emerald-600 mt-2">{{ usage.success_count ?? '—' }}</span>
          <span class="text-[11px] text-surface-400 mt-1">{{ successRateLabel }}</span>
        </div>
        <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-4 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
          <span class="text-[11px] font-bold tracking-wide uppercase text-surface-400">失敗</span>
          <span class="text-2xl font-black text-red-600 mt-2">{{ usage.failed_count ?? '—' }}</span>
          <span class="text-[11px] text-surface-400 mt-1">持續偏高需優先排查</span>
        </div>
        <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-4 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
          <span class="text-[11px] font-bold tracking-wide uppercase text-surface-400">快取命中（省下）</span>
          <span class="text-2xl font-black text-surface-900 dark:text-surface-0 mt-2">{{ usage.cached_hit_count ?? '—' }}</span>
          <span class="text-[11px] text-surface-400 mt-1">當日已有報告，省下的呼叫</span>
        </div>
        <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-4 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
          <span class="text-[11px] font-bold tracking-wide uppercase text-surface-400">總 Token 用量</span>
          <span class="text-2xl font-black text-primary mt-2">{{ formatTokens(usage.total_tokens) }}</span>
          <span class="text-[11px] text-surface-400 mt-1">輸入＋輸出</span>
        </div>
        <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-4 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
          <span class="text-[11px] font-bold tracking-wide uppercase text-surface-400">預估總成本</span>
          <span class="text-2xl font-black text-primary mt-2">{{ formatCost(usage.estimated_cost_usd) }}</span>
          <span class="text-[11px] text-surface-400 mt-1">已排除試跑列</span>
        </div>
      </div>
    </div>

    <!-- ══════════════════════ 篩選列 + 資料表 ══════════════════════ -->
    <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
      <div class="flex flex-wrap items-end gap-3 p-4 border-b border-surface-100 dark:border-surface-800">
        <div class="flex flex-col gap-1">
          <label class="text-[11px] font-bold text-surface-400 uppercase">功能</label>
          <Select v-model="filters.viewId" :options="FEATURE_OPTIONS" optionLabel="label" optionValue="value" placeholder="全部功能" showClear class="w-56" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[11px] font-bold text-surface-400 uppercase">Provider</label>
          <Select v-model="filters.provider" :options="PROVIDER_OPTIONS" optionLabel="label" optionValue="value" placeholder="全部" showClear class="w-32" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[11px] font-bold text-surface-400 uppercase">模型</label>
          <Select v-model="filters.model" :options="modelOptions" optionLabel="label" optionValue="value" placeholder="全部模型" showClear class="w-52" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[11px] font-bold text-surface-400 uppercase">狀態</label>
          <Select v-model="filters.status" :options="STATUS_OPTIONS" optionLabel="label" optionValue="value" placeholder="全部狀態" showClear class="w-32" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[11px] font-bold text-surface-400 uppercase">市場</label>
          <Select v-model="filters.market" :options="MARKET_OPTIONS" optionLabel="label" optionValue="value" placeholder="全部市場" showClear class="w-28" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[11px] font-bold text-surface-400 uppercase">股票代號</label>
          <input
            v-model.trim="filters.symbol"
            @keyup.enter="applyFilters"
            placeholder="例：2330"
            class="bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg px-2.5 py-1.5 text-xs w-28 focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[11px] font-bold text-surface-400 uppercase">建立日期（起）</label>
          <input v-model="filters.dateFrom" type="date" class="bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[11px] font-bold text-surface-400 uppercase">建立日期（迄）</label>
          <input v-model="filters.dateTo" type="date" class="bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary" />
        </div>
        <div class="flex items-center gap-2 pb-1.5">
          <Checkbox v-model="filters.includeDryRun" binary inputId="includeDryRun" />
          <label for="includeDryRun" class="text-xs font-semibold text-surface-500">包含試跑</label>
        </div>
        <button @click="applyFilters" class="px-3 py-1.5 text-xs font-bold bg-primary text-primary-contrast rounded-lg hover:bg-primary-600 transition-colors">
          <i class="pi pi-search mr-1"></i>查詢
        </button>
        <button @click="resetFilters" class="px-3 py-1.5 text-xs font-bold text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-800 rounded-lg transition-colors">
          清除
        </button>
        <div class="ml-auto text-sm text-surface-400">共 {{ total }} 筆</div>
      </div>

      <DataTable
        :value="rows"
        :loading="loading"
        lazy
        paginator
        :rows="pageSize"
        :totalRecords="total"
        :first="first"
        @page="onPage"
        :rowsPerPageOptions="[10, 20, 50]"
        size="small"
      >
        <template #empty>
          <div class="flex flex-col items-center justify-center py-16 text-surface-400">
            <i class="pi pi-inbox text-5xl mb-3 opacity-40"></i>
            <p class="text-lg">尚無查詢結果</p>
            <p class="text-sm">請調整篩選條件後重新查詢</p>
          </div>
        </template>

        <Column header="操作" style="width:56px">
          <template #body="{ data }">
            <Button icon="pi pi-info-circle" text size="small" v-tooltip.top="'明細'" @click="openDetail(data)" />
          </template>
        </Column>
        <Column field="created_at" header="建立時間" style="white-space:nowrap">
          <template #body="{ data }">{{ formatDateTime(data.created_at) }}</template>
        </Column>
        <Column header="標的">
          <template #body="{ data }">
            <span class="font-bold">{{ data.symbol }}</span>
            <span class="ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-surface-100 dark:bg-surface-800 text-surface-500">{{ MARKET_LABEL[data.market_type] || data.market_type }}</span>
          </template>
        </Column>
        <Column header="功能">
          <template #body="{ data }">
            <span class="text-xs" :class="data.view_id ? 'text-surface-700 dark:text-surface-200' : 'text-surface-400 italic'">{{ featureLabel(data.view_id) }}</span>
          </template>
        </Column>
        <Column header="Provider／模型">
          <template #body="{ data }">
            <div class="text-xs font-bold">{{ PROVIDER_LABEL[data.provider] || data.provider }}</div>
            <div class="text-[11px] text-surface-400">{{ data.model }}</div>
          </template>
        </Column>
        <Column header="呼叫模式">
          <template #body="{ data }">
            <span class="text-xs">{{ CALL_MODE_LABEL[data.call_mode] || data.call_mode }}</span>
          </template>
        </Column>
        <Column header="狀態">
          <template #body="{ data }">
            <Tag :value="STATUS_META[data.status]?.label || data.status" :severity="STATUS_META[data.status]?.severity || 'secondary'" />
            <Tag v-if="data.is_dry_run" value="試跑" severity="secondary" class="ml-1" />
          </template>
        </Column>
        <Column header="耗時">
          <template #body="{ data }">{{ formatElapsed(data.elapsed_ms) }}</template>
        </Column>
        <Column header="Tokens">
          <template #body="{ data }">
            <div class="font-bold text-xs">{{ formatTokens(data.total_tokens) }}</div>
            <div v-if="data.input_tokens != null" class="text-[11px] text-surface-400">入 {{ formatTokens(data.input_tokens) }}・出 {{ formatTokens(data.output_tokens) }}</div>
          </template>
        </Column>
        <Column header="預估成本">
          <template #body="{ data }">
            <span :title="data.estimated_cost_usd == null ? '找不到該模型定價，無法估算成本' : undefined">{{ formatCost(data.estimated_cost_usd) }}</span>
          </template>
        </Column>
        <Column header="UUID">
          <template #body="{ data }">
            <span class="text-xs font-mono" v-tooltip.top="data.execution_uuid">{{ data.execution_uuid?.slice(0, 18) }}…</span>
          </template>
        </Column>
      </DataTable>
    </div>

    <!-- ══════════════════════ 執行紀錄詳情 Dialog ══════════════════════ -->
    <Dialog v-model:visible="detailVisible" header="執行紀錄詳情" modal :style="{ width: '760px' }" dismissableMask>
      <template v-if="detailRow">
        <div class="text-[11px] font-bold uppercase text-surface-400 mb-2">基本資訊</div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div class="surface-ground border-round p-3 md:col-span-2 bg-surface-50 dark:bg-surface-800 rounded-lg">
            <div class="text-color-secondary text-[10px] uppercase mb-1">UUID</div>
            <div class="font-mono text-xs" style="word-break: break-all">{{ detailRow.execution_uuid }}</div>
          </div>
          <div class="bg-surface-50 dark:bg-surface-800 rounded-lg p-3">
            <div class="text-[10px] uppercase text-surface-400 mb-1">觸發功能</div>
            <div class="text-sm font-bold" :class="detailRow.view_id ? '' : 'text-surface-400 italic'">{{ featureLabel(detailRow.view_id) }}</div>
          </div>
          <div class="bg-surface-50 dark:bg-surface-800 rounded-lg p-3">
            <div class="text-[10px] uppercase text-surface-400 mb-1">狀態</div>
            <Tag :value="STATUS_META[detailRow.status]?.label || detailRow.status" :severity="STATUS_META[detailRow.status]?.severity || 'secondary'" />
          </div>
          <div class="bg-surface-50 dark:bg-surface-800 rounded-lg p-3">
            <div class="text-[10px] uppercase text-surface-400 mb-1">Provider／模型</div>
            <div class="text-sm font-bold">{{ PROVIDER_LABEL[detailRow.provider] || detailRow.provider }}</div>
            <div class="text-xs text-surface-400">{{ detailRow.model }}</div>
          </div>
          <div class="bg-surface-50 dark:bg-surface-800 rounded-lg p-3">
            <div class="text-[10px] uppercase text-surface-400 mb-1">標的</div>
            <div class="text-sm">{{ detailRow.symbol }}（{{ MARKET_LABEL[detailRow.market_type] || detailRow.market_type }}）</div>
          </div>
          <div class="bg-surface-50 dark:bg-surface-800 rounded-lg p-3">
            <div class="text-[10px] uppercase text-surface-400 mb-1">交易日</div>
            <div class="text-sm">{{ detailRow.trade_date || '-' }}</div>
          </div>
          <div class="bg-surface-50 dark:bg-surface-800 rounded-lg p-3">
            <div class="text-[10px] uppercase text-surface-400 mb-1">呼叫模式</div>
            <div class="text-sm">{{ CALL_MODE_LABEL[detailRow.call_mode] || detailRow.call_mode }}</div>
          </div>
          <div class="bg-surface-50 dark:bg-surface-800 rounded-lg p-3">
            <div class="text-[10px] uppercase text-surface-400 mb-1">嘗試次數／Prompt 版本</div>
            <div class="text-sm">第 {{ detailRow.attempt_no }} 次・{{ detailRow.prompt_version || '-' }}</div>
          </div>
        </div>

        <div class="text-[11px] font-bold uppercase text-surface-400 mb-2">用量與成本</div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div class="bg-surface-50 dark:bg-surface-800 rounded-lg p-3">
            <div class="text-[10px] uppercase text-surface-400 mb-1">輸入 Tokens</div>
            <div class="text-sm font-bold">{{ formatTokens(detailRow.input_tokens) }}</div>
          </div>
          <div class="bg-surface-50 dark:bg-surface-800 rounded-lg p-3">
            <div class="text-[10px] uppercase text-surface-400 mb-1">輸出 Tokens</div>
            <div class="text-sm font-bold">{{ formatTokens(detailRow.output_tokens) }}</div>
          </div>
          <div class="bg-surface-50 dark:bg-surface-800 rounded-lg p-3">
            <div class="text-[10px] uppercase text-surface-400 mb-1">總 Tokens</div>
            <div class="text-sm font-bold">{{ formatTokens(detailRow.total_tokens) }}</div>
          </div>
          <div class="bg-surface-50 dark:bg-surface-800 rounded-lg p-3">
            <div class="text-[10px] uppercase text-surface-400 mb-1">預估成本</div>
            <div class="text-sm font-bold">{{ formatCost(detailRow.estimated_cost_usd) }}</div>
          </div>
          <template v-if="detailRow.cache_read_tokens != null || detailRow.cache_write_tokens != null">
            <div class="bg-surface-50 dark:bg-surface-800 rounded-lg p-3">
              <div class="text-[10px] uppercase text-surface-400 mb-1">快取讀取 Tokens</div>
              <div class="text-sm font-bold">{{ formatTokens(detailRow.cache_read_tokens) }}</div>
            </div>
            <div class="bg-surface-50 dark:bg-surface-800 rounded-lg p-3">
              <div class="text-[10px] uppercase text-surface-400 mb-1">快取寫入 Tokens</div>
              <div class="text-sm font-bold">{{ formatTokens(detailRow.cache_write_tokens) }}</div>
            </div>
          </template>
          <div class="bg-surface-50 dark:bg-surface-800 rounded-lg p-3">
            <div class="text-[10px] uppercase text-surface-400 mb-1">送出圖片大小</div>
            <div class="text-sm font-bold">{{ formatBytes(detailRow.image_bytes) }}</div>
          </div>
          <div class="bg-surface-50 dark:bg-surface-800 rounded-lg p-3">
            <div class="text-[10px] uppercase text-surface-400 mb-1">耗時</div>
            <div class="text-sm font-bold">{{ formatElapsed(detailRow.elapsed_ms) }}</div>
          </div>
        </div>

        <Message v-if="detailRow.error_message" severity="error" :closable="false" class="mb-4">
          <span class="font-bold mr-1">{{ detailRow.error_code }}</span>{{ detailRow.error_message }}
        </Message>

        <div class="text-[11px] font-bold uppercase text-surface-400 mb-2">執行時間軸</div>
        <div class="grid grid-cols-3 gap-2 text-xs mb-4">
          <div><span class="text-surface-400">建立：</span>{{ formatDateTime(detailRow.created_at) }}</div>
          <div><span class="text-surface-400">開始：</span>{{ formatDateTime(detailRow.started_at) }}</div>
          <div><span class="text-surface-400">完成：</span>{{ formatDateTime(detailRow.completed_at) }}</div>
        </div>

        <div class="flex gap-2 flex-wrap">
          <Button
            icon="pi pi-sign-in" label="request_meta JSON" severity="info" outlined size="small"
            @click="openJson('request_meta 中繼資料', detailRow.request_meta)"
            :disabled="!detailRow.request_meta || Object.keys(detailRow.request_meta).length === 0"
          />
          <Button
            icon="pi pi-sign-out" label="response_meta JSON" severity="success" outlined size="small"
            @click="openJson('response_meta 中繼資料', detailRow.response_meta)"
            :disabled="!detailRow.response_meta || Object.keys(detailRow.response_meta).length === 0"
          />
          <router-link v-if="detailRow.report_id" :to="{ name: 'ai-report-detail', params: { reportId: detailRow.report_id } }">
            <Button icon="pi pi-external-link" label="查看對應診股報告" severity="secondary" outlined size="small" />
          </router-link>
        </div>
      </template>
      <template #footer>
        <Button label="關閉" icon="pi pi-times" text @click="detailVisible = false" />
      </template>
    </Dialog>

    <!-- ══════════════════════ JSON Preview Dialog ══════════════════════ -->
    <Dialog v-model:visible="jsonVisible" :header="jsonTitle" modal :style="{ width: '640px' }" dismissableMask>
      <pre class="bg-surface-900 text-surface-50 rounded-lg p-4 text-xs overflow-auto" style="max-height:46vh">{{ jsonContent }}</pre>
      <template #footer>
        <Button label="複製" icon="pi pi-copy" text size="small" @click="copyJson" />
        <Button label="關閉" icon="pi pi-times" text size="small" @click="jsonVisible = false" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted, watch } from 'vue';
import { useToast } from 'primevue/usetoast';
import { aiAnalysisApi } from '@/service/aiAnalysisApi';

const toast = useToast();

// ── 選項 ────────────────────────────────────────────────────────
// 「功能」目前只有一個真實來源（個股頁手動觸發）；Phase5-三層式 AI 決策引擎與戰情室.md
// 已確認戰情室批次掃描會沿用同一套 API，上線時在這裡加一行即可（見 §2.1）。
// 不放「全部」這個假選項——PrimeVue Select 把 value:null 視為「未選擇」，即使選項清單裡
// 有一筆 value:null 也不會顯示它的 label（實測證實）。改用 placeholder + showClear，
// 比照既有慣例（見 AlertDashboard.vue 的「全部策略」／「全部強度」）。
const FEATURE_OPTIONS = [
  { label: '個股 AI 診股報告', value: 'stock_dashboard' }
];
const PROVIDER_OPTIONS = [
  { label: 'Claude', value: 'claude' },
  { label: 'Gemini', value: 'gemini' }
];
const STATUS_OPTIONS = [
  { label: '成功', value: 'succeeded' },
  { label: '失敗', value: 'failed' },
  { label: '處理中', value: 'pending' }
];
const MARKET_OPTIONS = [
  { label: '台股', value: 'tw' },
  { label: '美股', value: 'us' }
];

const FEATURE_LABEL = { stock_dashboard: '個股 AI 診股報告' };
function featureLabel(viewId) {
  if (!viewId) return '（未記錄）';
  return FEATURE_LABEL[viewId] || viewId;
}

const STATUS_META = {
  succeeded: { label: '成功', severity: 'success' },
  failed: { label: '失敗', severity: 'danger' },
  pending: { label: '處理中', severity: 'warn' }
};
const CALL_MODE_LABEL = { blocking: '同步 Blocking', streaming: '串流 Streaming' };
const MARKET_LABEL = { tw: '台股', us: '美股' };
const PROVIDER_LABEL = { claude: 'Claude', gemini: 'Gemini' };

// ── 篩選狀態（僅在按下「查詢」或分頁時才實際觸發請求，見 applyFilters／onPage）──
const filters = reactive({
  viewId: null, provider: null, model: null, status: null, market: null,
  symbol: '', dateFrom: null, dateTo: null, includeDryRun: false
});

// 切換 Provider 時，先前選的模型可能不屬於新 Provider，清空避免送出無效組合
watch(() => filters.provider, () => { filters.model = null; });

// ── 模型下拉（依 Provider 連動，來源為既有 GET /ai/models，非硬編）──
const providerModels = ref({}); // { claude: { models: [...] }, gemini: { models: [...] } }
const modelOptions = computed(() => {
  const pool = filters.provider
    ? providerModels.value[filters.provider]?.models || []
    : Object.values(providerModels.value).flatMap((p) => p.models || []);
  return pool.map((m) => ({ label: m.id, value: m.id }));
});

async function loadModels() {
  try {
    const res = await aiAnalysisApi.getModels();
    providerModels.value = res.data?.providers || {};
  } catch (e) {
    // 非關鍵功能：模型選單抓不到就只留「全部」，不影響查詢功能本身
  }
}

// ── 用量彙總卡片（GET /ai/usage，僅套用日期區間，見計劃文件 §3.3）──
const usage = ref({});
const successRateLabel = computed(() => {
  const total = usage.value.call_count;
  const success = usage.value.success_count;
  if (!total) return '—';
  return `${Math.round((success / total) * 100)}% 成功率`;
});

async function loadUsage() {
  try {
    const res = await aiAnalysisApi.getUsage({ dateFrom: filters.dateFrom, dateTo: filters.dateTo });
    usage.value = res.data?.totals || {};
  } catch (err) {
    toast.add({ severity: 'error', summary: '用量彙總載入失敗', detail: err.response?.data?.error?.message || err.message, life: 4000 });
  }
}

// ── 執行紀錄列表（GET /ai/executions，後端分頁）──
const rows = ref([]);
const total = ref(0);
const loading = ref(true);
const pageSize = ref(20);
const first = ref(0);

async function loadExecutions() {
  loading.value = true;
  try {
    const res = await aiAnalysisApi.listExecutions({
      viewId: filters.viewId,
      provider: filters.provider,
      model: filters.model,
      status: filters.status,
      symbol: filters.symbol || undefined,
      market: filters.market,
      dateFrom: filters.dateFrom,
      dateTo: filters.dateTo,
      includeDryRun: filters.includeDryRun,
      limit: pageSize.value,
      offset: first.value
    });
    rows.value = res.data?.items || [];
    total.value = res.data?.total || 0;
  } catch (err) {
    toast.add({ severity: 'error', summary: '查詢失敗', detail: err.response?.data?.error?.message || err.message, life: 4000 });
  } finally {
    loading.value = false;
  }
}

function applyFilters() {
  first.value = 0;
  loadExecutions();
  loadUsage(); // 只有日期區間會影響彙總卡片，但重新查詢時一併刷新較直覺
}

function resetFilters() {
  Object.assign(filters, {
    viewId: null, provider: null, model: null, status: null, market: null,
    symbol: '', dateFrom: null, dateTo: null, includeDryRun: false
  });
  first.value = 0;
  loadExecutions();
  loadUsage();
}

function onPage(event) {
  first.value = event.first;
  pageSize.value = event.rows;
  loadExecutions();
}

// ── 明細 Dialog ────────────────────────────────────────────────
const detailVisible = ref(false);
const detailRow = ref(null);
function openDetail(row) {
  detailRow.value = row;
  detailVisible.value = true;
}

// ── JSON Preview Dialog ────────────────────────────────────────
const jsonVisible = ref(false);
const jsonTitle = ref('');
const jsonContent = ref('');
function openJson(title, obj) {
  jsonTitle.value = title;
  jsonContent.value = JSON.stringify(obj, null, 2);
  jsonVisible.value = true;
}
async function copyJson() {
  try {
    await navigator.clipboard.writeText(jsonContent.value);
    toast.add({ severity: 'info', summary: '已複製到剪貼簿', life: 2000 });
  } catch (e) {
    toast.add({ severity: 'error', summary: '複製失敗，請手動選取複製', life: 2500 });
  }
}

// ── 格式化工具 ──────────────────────────────────────────────────
function formatDateTime(iso) {
  if (!iso) return '-';
  return String(iso).replace('T', ' ').substring(0, 19);
}
function formatElapsed(ms) { return ms == null ? '-' : (ms / 1000).toFixed(2) + 's'; }
function formatTokens(n) { return n == null ? '-' : Number(n).toLocaleString('en-US'); }
function formatCost(v) { return v == null ? '—' : '$' + Number(v).toFixed(4); }
function formatBytes(v) { return v == null ? '-' : (v / 1024 / 1024).toFixed(2) + ' MB'; }

onMounted(() => {
  loadModels();
  loadExecutions();
  loadUsage();
});
</script>
