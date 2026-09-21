<template>
  <div class="p-4 sm:p-6 max-w-7xl mx-auto space-y-6">
    <!-- 頁面頂部 Header -->
    <div class="flex items-center flex-col md:flex-row md:items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl sm:text-3xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-shield text-primary text-2xl"></i>
          AI 戰情室
        </h1>
        <p class="text-xs sm:text-sm text-surface-500 mt-1">
          監控清單最新 AI 評等總覽<template v-if="data?.trade_date">（交易日 {{ data.trade_date }}）</template>
        </p>
      </div>

      <div class="flex items-center gap-2 self-start md:self-auto shrink-0 flex-wrap">
        <Select v-model="market" :options="MARKET_OPTIONS" optionLabel="label" optionValue="value" class="w-32" @change="onMarketChange" />
        <Button label="重新整理" icon="pi pi-refresh" :loading="loading" text @click="fetchData" />
        <Button
          :label="selectedRows.length ? `分析已選（${selectedRows.length}）` : '分析已選'"
          icon="pi pi-bolt" outlined :disabled="!selectedRows.length || analyzingSymbols.size > 0"
          @click="openManualAnalysis"
        />
        <Button label="批次設定" icon="pi pi-cog" outlined @click="openBatchSettings" />
      </div>
    </div>

    <AiBatchSettingsDialog
      v-model:visible="batchSettingsVisible" :market="market" :symbols="dialogSymbols"
      @started="onManualAnalysisStarted" @executed="onBatchExecuted" @settled="onBatchSettled"
    />

    <!-- 首次載入才顯示整頁 loading；切換市場／篩選一律保留既有內容 + overlay（CLAUDE.md 鐵則 1）-->
    <div v-if="loading && !data" class="flex flex-col items-center justify-center p-12 card bg-surface-0 dark:bg-surface-900 rounded-2xl border border-surface-200 dark:border-surface-700">
      <i class="pi pi-spin pi-spinner text-primary text-4xl mb-3"></i>
      <p class="text-sm font-semibold text-surface-600 dark:text-surface-400">正在載入戰情室資料...</p>
    </div>

    <div v-else-if="error && !data" class="card p-6 border border-red-300 bg-red-50 dark:bg-red-900/20 rounded-2xl text-red-700 dark:text-red-300">
      <div class="flex items-center gap-3">
        <i class="pi pi-exclamation-circle text-2xl"></i>
        <div>
          <h4 class="font-bold">資料讀取失敗</h4>
          <p class="text-sm mt-0.5">{{ error }}</p>
          <p v-if="isUnauthorized" class="text-xs mt-1">戰情室內容即監控清單本身，需先登入擁有者身分才能查看。</p>
        </div>
      </div>
    </div>

    <template v-else-if="data">
      <div class="relative">
        <div v-if="loading" class="absolute inset-0 z-10 flex items-start justify-center pt-24 bg-surface-0/60 dark:bg-surface-900/60 rounded-2xl">
          <i class="pi pi-spin pi-spinner text-primary text-3xl"></i>
        </div>
        <div :class="{ 'opacity-50 pointer-events-none transition-opacity duration-150': loading }" class="space-y-6">
          <!-- 重新整理／切換市場失敗時的行內提示：內容維持掛載（鐵則 1），但不能讓使用者
               把上一個市場的舊資料當成這次的結果，所以錯誤要在原地講清楚 -->
          <div
            v-if="error"
            class="flex items-start gap-2 text-xs font-semibold text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/60 rounded-xl px-3 py-2.5"
          >
            <i class="pi pi-exclamation-triangle mt-0.5"></i>
            <span>{{ error }}（以下為上次成功載入的內容）</span>
          </div>

          <!-- KPI 卡片列：同列等高 + !m-0（CLAUDE.md 鐵則 2）-->
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-5 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
              <span class="text-xs font-bold tracking-wide uppercase text-surface-400">監控標的</span>
              <span class="num text-2xl font-black text-surface-900 dark:text-surface-0 mt-2">{{ data.total }}</span>
              <span class="text-xs text-surface-500 mt-1">{{ data.generated_count }} 檔已產生今日報告</span>
            </div>
            <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-5 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
              <span class="text-xs font-bold tracking-wide uppercase text-surface-400">偏多</span>
              <span class="num text-2xl font-black mt-2" :style="{ color: upColor }">{{ verdictCounts.bullish }}</span>
              <span class="text-xs text-surface-500 mt-1">偏空 {{ verdictCounts.bearish }} ・中性 {{ verdictCounts.neutral }}</span>
            </div>
            <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-5 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
              <span class="text-xs font-bold tracking-wide uppercase text-surface-400">已觸價</span>
              <span class="num text-2xl font-black mt-2" :style="{ color: PRICE_HIT_COLOR }">{{ priceHitCount }}</span>
              <span class="text-xs text-surface-500 mt-1">達目標價或跌破停損</span>
            </div>
            <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-5 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
              <span class="text-xs font-bold tracking-wide uppercase text-surface-400">與規則訊號分歧</span>
              <span class="num text-2xl font-black mt-2" :style="{ color: ALIGNMENT_COLORS.diverged }">{{ divergedCount }}</span>
              <span class="text-xs text-surface-500 mt-1">一致 {{ alignedCount }} 筆</span>
            </div>
          </div>

          <!-- 篩選：全部資料已一次載入，篩選為前端 computed，不重新發請求（AC-P5-15／鐵則 1）-->
          <div class="flex flex-wrap items-center gap-2.5">
            <Select v-model="verdictFilter" :options="VERDICT_FILTER_OPTIONS" optionLabel="label" optionValue="value" class="w-40" />
            <Select v-model="alignmentFilter" :options="ALIGNMENT_FILTER_OPTIONS" optionLabel="label" optionValue="value" class="w-44" />
            <label class="flex items-center gap-1.5 text-sm text-surface-600 dark:text-surface-300 cursor-pointer select-none">
              <Checkbox v-model="priceHitOnly" binary /> 僅顯示已觸價
            </label>
            <button
              v-if="hasActiveFilter"
              @click="resetFilters"
              class="px-3 py-1.5 text-xs font-bold text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-800 rounded-lg transition-colors"
            >
              清除篩選
            </button>
            <div class="ml-auto text-sm text-surface-400">共 {{ filteredRows.length }} / {{ data.total }} 檔</div>
          </div>

          <!-- overflow-x-auto，非 overflow-hidden：手機寬度下表格欄位比視窗寬（代號/名稱/評等/
               目標價/停損/觸價/與規則訊號/來源/交易日 九欄），overflow-hidden 會直接把右側欄位
               裁掉且無法捲動看到，實測 400px 寬度下會看不到「觸價」「與規則訊號」等關鍵欄位 -->
          <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-x-auto">
            <DataTable
              :value="filteredRows"
              v-model:selection="selectedRows"
              dataKey="symbol"
              responsiveLayout="scroll"
              class="p-datatable-sm"
              sortMode="single"
              removableSort
            >
              <template #empty>
                <div class="text-center p-8 text-surface-400">
                  <i class="pi pi-filter-slash text-3xl mb-2 block"></i>沒有符合篩選條件的標的
                </div>
              </template>
              <Column selectionMode="multiple" headerStyle="width: 3rem" />
              <Column field="symbol" header="代號" sortable style="white-space:nowrap;min-width:4.5rem">
                <template #body="{ data: row }">
                  <i v-if="analyzingSymbols.has(row.symbol)" class="pi pi-spin pi-spinner text-primary text-xs mr-1" title="分析中"></i>
                  <router-link :to="`/stock/${market}/${row.symbol}`" class="font-mono font-bold text-primary hover:underline">{{ row.symbol }}</router-link>
                </template>
              </Column>
              <Column field="stock_name" header="名稱" sortable style="min-width:7rem" />
              <Column field="verdict" header="評等" sortable style="white-space:nowrap;min-width:6rem">
                <template #body="{ data: row }">
                  <!-- 已送交這次多選手動觸發、結果尚未回來的標的：蓋過原本的評等／未產生狀態，
                       避免使用者誤以為勾了沒反應而重複送出（觸發請求是同步阻塞，逐檔依序執行，
                       沒有逐檔進度可回報，因此整批已送出的標的會同時顯示分析中，見
                       AiBatchSettingsDialog.vue 的 started／settled 事件） -->
                  <span v-if="analyzingSymbols.has(row.symbol)" class="px-2.5 py-1 rounded-full font-bold text-xs inline-flex items-center gap-1 bg-primary-50 dark:bg-primary-900/30 text-primary">
                    <i class="pi pi-spin pi-spinner"></i>分析中
                  </span>
                  <span v-else-if="row.verdict" class="px-2.5 py-1 rounded-full font-black text-xs inline-flex items-center gap-1"
                        :style="{ backgroundColor: verdictColor(row.verdict) + '1a', color: verdictColor(row.verdict) }">
                    <i :class="['pi', VERDICT_ICONS[row.verdict]]"></i>{{ VERDICT_LABELS[row.verdict] }}
                  </span>
                  <span v-else class="px-2.5 py-1 rounded-full font-bold text-xs bg-surface-100 dark:bg-surface-800 text-surface-400" :title="row.reason">未產生</span>
                </template>
              </Column>
              <!-- 目標價／停損拆成兩行標註：擠在同一行的「目 1200 ／ 損 1050」在手機寬度下會折行
                   成無法對齊的兩段，且「目／損」單字縮寫需要猜。兩行各自帶標籤反而更窄也更好讀 -->
              <Column header="目標價／停損" sortable sortField="target_price" style="white-space:nowrap;min-width:6.5rem">
                <template #body="{ data: row }">
                  <div v-if="row.target_price != null || row.stop_loss != null" class="num text-xs leading-snug">
                    <div v-if="row.target_price != null" :style="{ color: upColor }">
                      <span class="text-[10px] text-surface-400 font-bold mr-1">目標</span>{{ row.target_price }}
                    </div>
                    <div v-if="row.stop_loss != null" :style="{ color: PRICE_HIT_COLOR }">
                      <span class="text-[10px] text-surface-400 font-bold mr-1">停損</span>{{ row.stop_loss }}
                    </div>
                  </div>
                  <span v-else class="text-surface-300">—</span>
                </template>
              </Column>
              <Column field="is_price_hit" header="觸價" sortable style="white-space:nowrap;min-width:4.5rem">
                <template #body="{ data: row }">
                  <span v-if="row.is_price_hit" class="inline-flex items-center gap-1 text-xs font-bold" :style="{ color: PRICE_HIT_COLOR }" title="收盤已達目標價或跌破停損">
                    <i class="pi pi-bolt"></i>觸價
                  </span>
                  <span v-else class="text-surface-300">—</span>
                </template>
              </Column>
              <Column field="rule_signal_alignment" header="與規則訊號" sortable style="white-space:nowrap;min-width:7.5rem">
                <template #body="{ data: row }">
                  <span
                    v-if="ALIGNMENT_LABELS[row.rule_signal_alignment]"
                    class="px-2.5 py-1 rounded-full font-bold text-xs inline-flex items-center gap-1"
                    :style="{
                      backgroundColor: ALIGNMENT_COLORS[row.rule_signal_alignment] + '1a',
                      color: ALIGNMENT_COLORS[row.rule_signal_alignment]
                    }"
                  >
                    <i :class="['pi', row.rule_signal_alignment === 'diverged' ? 'pi-exclamation-circle' : 'pi-check-circle']"></i>
                    {{ ALIGNMENT_LABELS[row.rule_signal_alignment] }}
                  </span>
                  <span v-else class="text-surface-300">—</span>
                </template>
              </Column>
              <Column field="trigger_type" header="來源" sortable style="white-space:nowrap;min-width:4.5rem">
                <template #body="{ data: row }">
                  <span v-if="row.trigger_type === 'batch'" class="text-[11px] text-surface-400" title="排程批次產生，僅憑量化數值推理，未含圖表型態判讀">
                    批次<i class="pi pi-info-circle ml-1 text-[9px]"></i>
                  </span>
                  <span v-else-if="row.trigger_type === 'manual'" class="text-[11px] text-surface-400">手動</span>
                  <span v-else class="text-surface-300">—</span>
                </template>
              </Column>
              <!-- 未產生原因是一段完整說明句，直接塞進儲存格會把該列撐成三四行、破壞同列等高
                   （鐵則 2 的精神）。截斷 + title 保留完整內容 -->
              <Column field="generated_at" header="交易日／原因" sortable style="min-width:9rem">
                <template #body="{ data: row }">
                  <!-- 落後於本批最新交易日的報告要看得出來，否則使用者會把上週的判讀當成今天的 -->
                  <span
                    v-if="row.status === 'generated'"
                    class="text-[11px]"
                    style="white-space:nowrap"
                    :class="isStale(row) ? 'text-amber-600 font-bold' : 'text-surface-400'"
                    :title="`交易日 ${row.trade_date}・產生於 ${formatTime(row.generated_at)}` + (isStale(row) ? '（非本批最新交易日）' : '')"
                  >
                    <i v-if="isStale(row)" class="pi pi-clock text-[9px] mr-1"></i>{{ row.trade_date }}
                  </span>
                  <span v-else class="block max-w-[14rem] truncate text-[11px] text-amber-600" :title="row.reason">{{ row.reason }}</span>
                </template>
              </Column>
              <Column header="" style="white-space:nowrap;min-width:3rem">
                <template #body="{ data: row }">
                  <Button
                    v-if="row.report_id" icon="pi pi-eye" size="small" text
                    title="檢視完整報告" @click="showDetail(row)"
                  />
                </template>
              </Column>
            </DataTable>
          </div>
        </div>
      </div>
    </template>

    <!-- 詳情：與個股頁即時產生報告共用同一個呈現元件（規格書 §7.4），資料來源為 /reports/{id}，
         比照 AiReportHistory.vue 的既有作法，不另外做一套報告呈現 -->
    <AiAnalysisDialog
      v-model:visible="detailVisible"
      stage="result"
      :loading="detailLoading"
      :error="detailError"
      :report="detailReport"
      :market="market"
      :allow-reselect="false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import AiAnalysisDialog from '@/components/AiAnalysisDialog.vue';
import AiBatchSettingsDialog from '@/components/AiBatchSettingsDialog.vue';
import { aiAnalysisApi } from '@/service/aiAnalysisApi';
import { getUpDownColor } from '@/utils/marketColors';

const MARKET_OPTIONS = [
  { label: '台股', value: 'tw' },
  { label: '美股', value: 'us' }
];
const VERDICT_FILTER_OPTIONS = [
  { label: '全部評等', value: null },
  { label: '偏多', value: 'bullish' },
  { label: '偏空', value: 'bearish' },
  { label: '中性', value: 'neutral' },
  { label: '未產生', value: 'not_generated' }
];
const ALIGNMENT_FILTER_OPTIONS = [
  { label: '全部', value: null },
  { label: '與規則訊號一致', value: 'aligned' },
  { label: '與規則訊號分歧', value: 'diverged' }
];
const VERDICT_LABELS = { bullish: '偏多', bearish: '偏空', neutral: '中性' };
const VERDICT_ICONS = { bullish: 'pi-arrow-up-right', bearish: 'pi-arrow-down-right', neutral: 'pi-minus' };
// 一致／分歧的色碼與 AiAnalysisDialog.vue 的徽章完全相同（cyan-600／amber-600）——同一個語意
// 在彈窗與戰情室之間不得換色，否則使用者要重新學一次配色。
const ALIGNMENT_LABELS = { aligned: '一致', diverged: '分歧' };
const ALIGNMENT_COLORS = { aligned: '#0891b2', diverged: '#d97706' };
// 觸價／停損沿用彈窗位階卡片的停損色（orange-500），與漲跌紅綠、分歧的 amber 都區分得開。
const PRICE_HIT_COLOR = '#f97316';

const market = ref('tw');
const batchSettingsVisible = ref(false);
const dialogSymbols = ref([]); // 開對話框當下決定：[] 為整份監控清單批次，非空為多選手動觸發
const selectedRows = ref([]);
// 已送出這次多選手動觸發、結果尚未回來的標的（分析中圖示，見 AiBatchSettingsDialog.vue 的
// started／settled 事件）。只有多選手動觸發（symbols 非空）才會標記——整份監控清單批次沒有
// 前端已知的確切候選清單（ETF 排除等規則在後端才算出），標不出是哪幾檔。
const analyzingSymbols = ref(new Set());
const data = ref(null);
const loading = ref(false);
const error = ref(null);
const isUnauthorized = ref(false);

const verdictFilter = ref(null);
const alignmentFilter = ref(null);
const priceHitOnly = ref(false);

const detailVisible = ref(false);
const detailLoading = ref(false);
const detailError = ref(null);
const detailReport = ref(null);

const upColor = computed(() => getUpDownColor(market.value).up);
function verdictColor(verdict) {
  const { up, down } = getUpDownColor(market.value);
  if (verdict === 'bullish') return up;
  if (verdict === 'bearish') return down;
  return '#64748b';
}

function openBatchSettings() {
  dialogSymbols.value = [];
  batchSettingsVisible.value = true;
}
function openManualAnalysis() {
  dialogSymbols.value = selectedRows.value.map((r) => r.symbol);
  batchSettingsVisible.value = true;
}
function onManualAnalysisStarted({ symbols } = {}) {
  if (symbols?.length) analyzingSymbols.value = new Set(symbols);
}
function onBatchExecuted() {
  selectedRows.value = [];
  fetchData();
}
function onBatchSettled() {
  analyzingSymbols.value = new Set();
}
function onMarketChange() {
  selectedRows.value = [];
  analyzingSymbols.value = new Set();
  fetchData();
}

async function fetchData() {
  loading.value = true;
  error.value = null;
  try {
    const res = await aiAnalysisApi.getWarRoom(market.value);
    data.value = res.data;
    isUnauthorized.value = false;
  } catch (e) {
    isUnauthorized.value = e?.response?.status === 401;
    error.value = e?.response?.data?.error?.message || e?.message || '載入失敗';
  } finally {
    loading.value = false;
  }
}

async function showDetail(row) {
  detailVisible.value = true;
  detailError.value = null;
  detailReport.value = null;
  detailLoading.value = true;
  try {
    const res = await aiAnalysisApi.getReport(row.report_id);
    detailReport.value = res.data;
  } catch (e) {
    detailError.value = e?.response?.data?.error?.message || e?.message || '讀取報告失敗';
  } finally {
    detailLoading.value = false;
  }
}

const hasActiveFilter = computed(() => !!verdictFilter.value || !!alignmentFilter.value || priceHitOnly.value);
function resetFilters() {
  verdictFilter.value = null;
  alignmentFilter.value = null;
  priceHitOnly.value = false;
}

const filteredRows = computed(() => {
  if (!data.value) return [];
  return data.value.items.filter((row) => {
    if (verdictFilter.value) {
      if (verdictFilter.value === 'not_generated' ? row.status !== 'not_generated' : row.verdict !== verdictFilter.value) return false;
    }
    if (alignmentFilter.value && row.rule_signal_alignment !== alignmentFilter.value) return false;
    if (priceHitOnly.value && !row.is_price_hit) return false;
    return true;
  });
});

const verdictCounts = computed(() => {
  const counts = { bullish: 0, bearish: 0, neutral: 0 };
  (data.value?.items || []).forEach((r) => {
    if (r.verdict && counts[r.verdict] !== undefined) counts[r.verdict]++;
  });
  return counts;
});
const priceHitCount = computed(() => (data.value?.items || []).filter((r) => r.is_price_hit).length);
const alignedCount = computed(() => (data.value?.items || []).filter((r) => r.rule_signal_alignment === 'aligned').length);
const divergedCount = computed(() => (data.value?.items || []).filter((r) => r.rule_signal_alignment === 'diverged').length);

function formatTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('zh-TW', { hour: '2-digit', minute: '2-digit', month: '2-digit', day: '2-digit' });
}

// 該列的報告不是本批最新交易日產生的（例如批次當天對這檔失敗、只剩前一個交易日的舊報告）
function isStale(row) {
  return !!row.trade_date && !!data.value?.trade_date && row.trade_date < data.value.trade_date;
}

onMounted(fetchData);
</script>
