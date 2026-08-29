<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex items-center flex-col md:flex-row md:items-center justify-between gap-4 card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div>
        <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-eye text-primary text-2xl"></i>追蹤與觀察名單
        </h1>
        <p class="text-sm text-surface-500 mt-1">追蹤候選股與觀察標的；加入後自動納入每日爬蟲抓取範圍，可選填目標買進價、追蹤原因與標籤</p>
      </div>
      <Button label="加入追蹤" icon="pi pi-plus" @click="openAddModal" />
    </div>

    <div class="p-4 rounded-xl bg-primary-50 dark:bg-primary-500/10 border border-primary-200 dark:border-primary-500/30 text-primary-800 dark:text-primary-300 text-sm flex items-start gap-2.5">
      <i class="pi pi-info-circle mt-0.5"></i>
      <span>到價推播通知（串接整合訊息通知平台）尚未串接，目前僅頁面即時顯示距目標價；此功能規劃於後續擴充。</span>
    </div>

    <!-- 首次載入且無資料時才顯示整頁 loading；篩選切換／背景重新整理一律保留既有內容 + overlay
         （CLAUDE.md 硬規則：切換控制項不得整頁 refresh 跳回頂端）。 -->
    <div v-if="loading && !hasLoadedOnce" class="flex items-center gap-2 text-surface-500 text-sm py-10 justify-center">
      <i class="pi pi-spin pi-spinner"></i> 載入中...
    </div>

    <template v-else>
      <div class="relative">
        <div v-if="loading" class="absolute inset-0 bg-surface-0/60 dark:bg-surface-900/60 backdrop-blur-[1px] z-10 rounded-xl flex items-start justify-center pt-16">
          <i class="pi pi-spin pi-spinner text-2xl text-primary"></i>
        </div>

        <div class="space-y-6">
          <div class="grid grid-cols-2 sm:grid-cols-5 gap-4">
            <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center gap-3">
              <div class="w-12 h-12 rounded-xl bg-primary-50 dark:bg-primary-500/10 text-primary flex items-center justify-center text-xl shrink-0"><i class="pi pi-eye"></i></div>
              <div><div class="text-xs font-bold text-surface-400 uppercase tracking-wide">追蹤中</div><div class="text-2xl font-black text-surface-900 dark:text-surface-0 num">{{ watchlist.length }}</div></div>
            </div>
            <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center gap-3">
              <div class="w-12 h-12 rounded-xl bg-sky-50 dark:bg-sky-500/10 text-sky-600 flex items-center justify-center text-xl shrink-0"><i class="pi pi-flag"></i></div>
              <div><div class="text-xs font-bold text-surface-400 uppercase tracking-wide">已設目標價</div><div class="text-2xl font-black text-sky-600 num">{{ withTargetCount }}</div></div>
            </div>
            <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center gap-3">
              <div class="w-12 h-12 rounded-xl bg-amber-50 dark:bg-amber-500/10 text-amber-600 flex items-center justify-center text-xl shrink-0"><i class="pi pi-bell"></i></div>
              <div><div class="text-xs font-bold text-surface-400 uppercase tracking-wide">接近目標價</div><div class="text-2xl font-black text-amber-600 num">{{ nearTargetCount }}</div></div>
            </div>
            <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center gap-3">
              <div class="w-12 h-12 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 flex items-center justify-center text-xl shrink-0"><i class="pi pi-check-circle"></i></div>
              <div><div class="text-xs font-bold text-surface-400 uppercase tracking-wide">已達價</div><div class="text-2xl font-black text-emerald-600 num">{{ reachedCount }}</div></div>
            </div>
            <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center gap-3">
              <div class="w-12 h-12 rounded-xl bg-rose-50 dark:bg-rose-500/10 text-rose-600 flex items-center justify-center text-xl shrink-0"><i class="pi pi-exclamation-triangle"></i></div>
              <div><div class="text-xs font-bold text-surface-400 uppercase tracking-wide">資料缺漏</div><div class="text-2xl font-black text-rose-600 num">{{ missingCount }}</div></div>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2.5">
            <Select v-model="marketFilter" :options="marketFilterOptions" optionLabel="label" optionValue="value" class="w-36" />
            <MultiSelect v-model="tagFilter" :options="tags" optionLabel="name" optionValue="id" display="chip" placeholder="篩選標籤" class="w-56" />
            <InputText v-model="keyword" placeholder="搜尋代號或名稱" class="w-56" />
            <label class="flex items-center gap-1.5 text-sm text-surface-600 dark:text-surface-300 cursor-pointer select-none">
              <Checkbox v-model="hasTargetOnly" binary /> 僅顯示有目標價
            </label>
          </div>

          <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
            <div class="overflow-x-auto">
              <table class="w-full text-left border-collapse text-sm">
                <thead>
                  <tr class="bg-surface-50 dark:bg-surface-800 text-surface-400 text-xs uppercase tracking-wide">
                    <th class="p-3">股票</th><th class="p-3">市場</th><th class="p-3">標籤</th><th class="p-3">追蹤原因</th>
                    <th class="p-3">加入日期</th><th class="p-3 text-right">股價</th><th class="p-3 text-right">目標價</th>
                    <th class="p-3 text-right">距目標</th><th class="p-3">資料</th><th class="p-3 text-center">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="w in watchlist" :key="w.id" class="border-t border-surface-100 dark:border-surface-800" :class="[w.is_near_target ? 'bg-amber-50/50 dark:bg-amber-500/5' : '', !w.is_crawl_enabled ? 'opacity-60' : '']">
                    <td class="p-3">
                      <div class="font-bold text-surface-800 dark:text-surface-100 flex items-center gap-1.5">
                        <a :href="stockChartHref(w)" target="_blank" rel="noopener" title="在新分頁開啟「選股與圖表分析」" class="hover:text-primary hover:underline">{{ w.symbol }}</a>
                        <span v-if="w.is_reached" class="px-1.5 py-0.5 text-[10px] font-bold rounded bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300">已達價</span>
                        <span v-else-if="w.is_near_target" class="px-1.5 py-0.5 text-[10px] font-bold rounded bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300">到價提醒</span>
                        <span v-if="!w.is_crawl_enabled" title="已暫停抓取，設定仍保留" class="px-1.5 py-0.5 text-[10px] font-bold rounded bg-surface-100 dark:bg-surface-800 text-surface-500">已暫停</span>
                      </div>
                      <div class="text-xs text-surface-400">{{ w.name }}</div>
                    </td>
                    <td class="p-3"><span class="px-2 py-0.5 text-xs font-bold rounded bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300">{{ marketMeta[w.market].label }}</span></td>
                    <td class="p-3">
                      <div class="flex items-center flex-wrap gap-1 max-w-[150px]">
                        <button v-for="tag in w.tags" :key="tag.id" @click="toggleTagFilter(tag.id)" :title="`篩選標籤：${tag.name}`" :class="tagColorClass(tag.color)" class="px-1.5 py-0.5 text-[10px] font-bold rounded hover:opacity-75 transition-opacity">{{ tag.name }}</button>
                        <span v-if="!w.tags.length" class="text-surface-300 text-xs">—</span>
                      </div>
                    </td>
                    <td class="p-3 text-surface-400 text-xs max-w-[160px] truncate" :title="w.note">{{ w.note || '—' }}</td>
                    <td class="p-3 text-surface-500 num">{{ w.added_date }}</td>
                    <td class="p-3 text-right num font-medium">
                      <span v-if="w.price != null">{{ w.price.toFixed(2) }}</span>
                      <span v-else class="text-surface-300" title="尚無最新報價資料">待報價</span>
                    </td>
                    <td class="p-3 text-right num">{{ w.target_price != null ? w.target_price.toFixed(2) : '—' }}</td>
                    <td class="p-3 text-right num font-bold" :class="w.gap_pct == null ? 'text-surface-300' : (w.gap_pct <= 0 ? 'text-emerald-600' : 'text-surface-500')">
                      {{ w.gap_pct == null ? '—' : fmtPct(w.gap_pct) }}
                    </td>
                    <td class="p-3 text-xs whitespace-nowrap">
                      <span v-if="pendingRefetchId === w.id" class="text-amber-500 font-bold flex items-center gap-1"><i class="pi pi-spin pi-spinner"></i> 抓取中</span>
                      <span v-else-if="!w.coverage || !w.coverage.count" class="text-surface-400 flex items-center gap-1"><i class="pi pi-info-circle"></i> 尚無資料</span>
                      <span v-else-if="w.coverage.missing_price_days > 0" :title="`缺漏 ${w.coverage.missing_price_days} 天`" class="text-amber-600 font-bold flex items-center gap-1"><i class="pi pi-exclamation-triangle"></i> 缺漏</span>
                      <span v-else class="text-emerald-600 flex items-center gap-1"><i class="pi pi-check"></i> 完整</span>
                    </td>
                    <td class="p-3 text-center whitespace-nowrap">
                      <a :href="stockChartHref(w)" target="_blank" rel="noopener" title="在新分頁開啟「選股與圖表分析」" class="text-surface-400 hover:text-primary mx-1 inline-block align-middle"><i class="pi pi-chart-bar"></i></a>
                      <button @click="convertToTransaction(w)" title="登錄買進" class="text-primary hover:text-primary-700 mx-1"><i class="pi pi-shopping-cart"></i></button>
                      <button @click="openRefetch(w)" :disabled="fetchStatus?.is_running" title="重新抓取歷史資料" class="text-surface-400 hover:text-primary mx-1 disabled:opacity-40 disabled:cursor-not-allowed"><i class="pi pi-refresh"></i></button>
                      <button @click="openEditModal(w)" title="編輯" class="text-surface-400 hover:text-primary mx-1"><i class="pi pi-pencil"></i></button>
                      <button @click="confirmRemove(w)" title="移除" class="text-surface-400 hover:text-red-500 mx-1"><i class="pi pi-trash"></i></button>
                    </td>
                  </tr>
                  <tr v-if="!watchlist.length"><td colspan="10" class="p-8 text-center text-surface-400 text-sm">{{ hasActiveFilters ? '沒有符合篩選條件的項目' : '清單目前是空的' }}</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </template>

    <Dialog v-model:visible="showModal" :header="editingId ? '編輯清單項目' : '加入追蹤與觀察名單'" modal style="width: 26rem">
      <div class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">市場</label>
            <Select v-model="form.market" :options="marketOptions" optionLabel="label" optionValue="value" :disabled="!!editingId" class="w-full" />
          </div>
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">股票代碼</label>
            <div class="flex items-center gap-1.5">
              <InputText v-model="form.symbol" :disabled="!!editingId" class="w-full" placeholder="例如: 2317" />
              <Button v-if="!editingId" icon="pi pi-search" outlined @click="lookupName" title="查詢名稱" />
            </div>
          </div>
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">股票名稱</label>
          <InputText v-model="form.name" class="w-full" placeholder="查詢後自動帶出，亦可手動輸入" />
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">目標買進價（選填）</label>
          <InputNumber v-model="form.target_price" mode="decimal" :maxFractionDigits="2" class="w-full" placeholder="留空＝純追蹤，不計算到價提醒" />
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">追蹤原因（選填）</label>
          <Textarea v-model="form.note" rows="2" class="w-full" placeholder="例如：等季報公布、等回檔至月線" />
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">標籤（選填，可輸入新標籤自動建立）</label>
          <AutoComplete v-model="form.tags" :suggestions="tagSuggestions" multiple display="chip" dropdown @complete="onTagComplete" class="w-full" inputClass="text-sm" placeholder="輸入或選擇標籤" />
        </div>
        <label v-if="editingId" class="flex items-center gap-1.5 text-sm text-surface-600 dark:text-surface-300 cursor-pointer select-none">
          <Checkbox v-model="form.is_crawl_enabled" binary /> 納入每日爬蟲抓取範圍
        </label>
      </div>
      <template #footer>
        <Button label="取消" text @click="showModal = false" />
        <Button :label="editingId ? '儲存變更' : '加入清單'" icon="pi pi-check" :loading="saving" @click="save" />
      </template>
    </Dialog>

    <RefetchStockDialog
      v-model:visible="refetchVisible"
      :stock-id="refetchTarget?.symbol || ''"
      :stock-name="refetchTarget?.name || ''"
      :market="refetchTarget?.market || 'tw'"
      :missing-days="refetchTarget?.coverage?.missing_price_days || 0"
      :busy="isRefetching"
      @confirm="doRefetch"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';
import { portfolioApi } from '@/service/portfolioApi';
import { stockApi } from '@/service/stockApi';
import { usePortfolioPrefill } from '@/composables/usePortfolioPrefill';
import { marketMeta, fmtPct } from '@/composables/usePortfolioFormat';
import { useWatchlistTags, tagColorClass } from '@/composables/useWatchlistTags';
import { useTrackingList } from '@/composables/useTrackingList';
import { useCrawlerStatus } from '@/composables/useCrawlerStatus';
import RefetchStockDialog from '@/components/RefetchStockDialog.vue';

const router = useRouter();
const toast = useToast();
const confirm = useConfirm();
const { setPendingTransaction } = usePortfolioPrefill();
const { tags, refresh: refreshTags } = useWatchlistTags();
const { refresh: refreshTrackingList } = useTrackingList();
const { fetchStatus, isRunning, checkStatus } = useCrawlerStatus();

const marketOptions = [{ label: '台股 TWSE', value: 'tw' }, { label: '美股 NASDAQ', value: 'us' }];
const marketFilterOptions = [{ label: '全部市場', value: '' }, ...marketOptions];

const loading = ref(true);
const hasLoadedOnce = ref(false);
const watchlist = ref([]);

const marketFilter = ref('');
const tagFilter = ref([]);
const keyword = ref('');
const hasTargetOnly = ref(false);
const hasActiveFilters = computed(() => !!(marketFilter.value || tagFilter.value.length || keyword.value || hasTargetOnly.value));

const withTargetCount = computed(() => watchlist.value.filter((w) => w.target_price != null).length);
const nearTargetCount = computed(() => watchlist.value.filter((w) => w.is_near_target).length);
const reachedCount = computed(() => watchlist.value.filter((w) => w.is_reached).length);
const missingCount = computed(() => watchlist.value.filter((w) => w.coverage && w.coverage.count && w.coverage.missing_price_days > 0).length);

async function load() {
  loading.value = true;
  try {
    const res = await portfolioApi.getWatchlist({
      market: marketFilter.value || undefined,
      tags: tagFilter.value.length ? tagFilter.value : undefined,
      q: keyword.value || undefined,
      hasTarget: hasTargetOnly.value ? true : undefined,
      withCoverage: true
    });
    watchlist.value = res.data;
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: err?.response?.data?.detail || err.message, life: 4000 });
  } finally {
    loading.value = false;
    hasLoadedOnce.value = true;
  }
}
onMounted(() => Promise.all([load(), refreshTags()]));

// 篩選切換即時重查；關鍵字搜尋做輕量 debounce，避免每次按鍵都打一次 API
let keywordTimer = null;
watch(keyword, () => {
  clearTimeout(keywordTimer);
  keywordTimer = setTimeout(load, 350);
});
watch([marketFilter, tagFilter, hasTargetOnly], load, { deep: true });

function toggleTagFilter(tagId) {
  const idx = tagFilter.value.indexOf(tagId);
  if (idx >= 0) tagFilter.value.splice(idx, 1);
  else tagFilter.value.push(tagId);
}

const showModal = ref(false);
const editingId = ref(null);
const saving = ref(false);
const tagSuggestions = ref([]);
const originalCrawlEnabled = ref(true); // 開啟編輯彈窗時記錄，供 save() 判斷是否為「暫停抓取」動作（ADR-11）
function blankForm() { return { market: 'tw', symbol: '', name: '', target_price: null, note: '', tags: [], is_crawl_enabled: true }; }
const form = reactive(blankForm());

function onTagComplete(event) {
  const q = (event.query || '').trim().toLowerCase();
  tagSuggestions.value = tags.value
    .map((t) => t.name)
    .filter((name) => !form.tags.includes(name) && (!q || name.toLowerCase().includes(q)));
}

function openAddModal() { Object.assign(form, blankForm()); editingId.value = null; showModal.value = true; }
function openEditModal(w) {
  Object.assign(form, {
    market: w.market, symbol: w.symbol, name: w.name, target_price: w.target_price, note: w.note || '',
    tags: (w.tags || []).map((t) => t.name), is_crawl_enabled: w.is_crawl_enabled
  });
  editingId.value = w.id;
  originalCrawlEnabled.value = w.is_crawl_enabled;
  showModal.value = true;
}

async function lookupName() {
  if (!form.symbol) return;
  try {
    const res = await portfolioApi.searchSymbol(form.symbol, form.market);
    const found = res.data?.[form.symbol.toUpperCase()];
    if (found?.name) {
      form.name = found.name;
      toast.add({ severity: 'success', summary: '已帶入股票名稱', life: 2000 });
    } else {
      toast.add({ severity: 'warn', summary: '查無此代碼，請手動輸入名稱', life: 2500 });
    }
  } catch {
    toast.add({ severity: 'warn', summary: '查無此代碼，請手動輸入名稱', life: 2500 });
  }
}

// 有非零持股時，暫停抓取／移除清單前先確認（規劃書 §12.9 ADR-11）；查詢失敗不阻擋操作，
// 由後端二次防呆補上同樣的提醒（回應中的 had_position）。回傳 shares（無持股或查詢失敗為 0）。
async function checkHolding(id) {
  try {
    const res = await portfolioApi.getWatchlistPosition(id);
    return res.data?.has_position ? res.data.shares : 0;
  } catch {
    return 0;
  }
}

function confirmPauseCrawl(shares) {
  return new Promise((resolve) => {
    confirm.require({
      message: `這檔股票目前持有 ${shares} 股。暫停追蹤後，明日起不會再更新每日價格，也不會出現在熱力圖與持股列表的即時報價中。確定要繼續嗎？`,
      header: '暫停抓取確認', icon: 'pi pi-exclamation-triangle', acceptLabel: '確定暫停', rejectLabel: '取消',
      accept: () => resolve(true),
      reject: () => resolve(false)
    });
  });
}

async function save() {
  if (!form.symbol) {
    toast.add({ severity: 'error', summary: '請填寫股票代碼', life: 3000 });
    return;
  }
  if (editingId.value && originalCrawlEnabled.value && !form.is_crawl_enabled) {
    const shares = await checkHolding(editingId.value);
    if (shares > 0 && !(await confirmPauseCrawl(shares))) return;
  }
  saving.value = true;
  try {
    let res;
    if (editingId.value) {
      res = await portfolioApi.updateWatchlist(editingId.value, {
        target_price: form.target_price ?? null,
        note: form.note || null,
        name: form.name || undefined,
        tags: form.tags,
        is_crawl_enabled: form.is_crawl_enabled
      });
      toast.add({ severity: 'success', summary: '已更新清單項目', life: 2500 });
    } else {
      res = await portfolioApi.addWatchlist({
        market: form.market, symbol: form.symbol, name: form.name || undefined,
        target_price: form.target_price ?? null, note: form.note || null, tags: form.tags
      });
      toast.add({ severity: 'success', summary: res.message, life: 2500 });
    }
    if (res.mirror_warning) {
      toast.add({ severity: 'warn', summary: '爬蟲設定檔同步失敗', detail: res.mirror_warning, life: 6000 });
    }
    if (res.fetch_triggered?.length) {
      toast.add({ severity: 'info', summary: '背景抓取中', detail: `${res.fetch_triggered.join(', ')} 尚無歷史資料，已自動啟動背景抓取`, life: 4000 });
    }
    showModal.value = false;
    await Promise.all([load(), refreshTags(), refreshTrackingList(form.market)]);
  } catch (err) {
    toast.add({ severity: 'error', summary: '儲存失敗', detail: err?.response?.data?.detail || err.message, life: 5000 });
  } finally {
    saving.value = false;
  }
}

async function confirmRemove(w) {
  const shares = await checkHolding(w.id);
  const holdingHint = shares > 0 ? `此股票目前持有 ${shares} 股，移除後不會再更新每日價格與熱力圖顯示。` : '';
  confirm.require({
    message: `${holdingHint}確定要將 ${w.symbol} ${w.name} 從清單移除嗎？將同時停止每日抓取；此動作不影響任何交易紀錄或已抓取的歷史資料。`,
    header: '移除清單項目', icon: 'pi pi-exclamation-triangle', acceptLabel: '確定移除', rejectLabel: '取消', acceptClass: 'p-button-danger',
    accept: async () => {
      const res = await portfolioApi.removeWatchlist(w.id);
      toast.add({ severity: 'success', summary: '已從清單移除', life: 2500 });
      if (res.mirror_warning) {
        toast.add({ severity: 'warn', summary: '爬蟲設定檔同步失敗', detail: res.mirror_warning, life: 6000 });
      }
      await Promise.all([load(), refreshTrackingList(w.market)]);
    }
  });
}

function convertToTransaction(w) {
  setPendingTransaction({ market: w.market, symbol: w.symbol, name: w.name, price: w.price ?? w.target_price ?? null, watchId: w.id });
  router.push({ name: 'portfolio-transactions' });
}

// ── 重新抓取（自 StockManagement.vue 移入，見規劃書 §6.3）─────────────
const refetchVisible = ref(false);
const refetchTarget = ref(null);
const isRefetching = ref(false);
const pendingRefetchId = ref(null);

function openRefetch(w) {
  refetchTarget.value = w;
  refetchVisible.value = true;
}

async function doRefetch({ stockId, months }) {
  isRefetching.value = true;
  try {
    const res = await stockApi.triggerFetch([stockId], months, refetchTarget.value.market, 'repair');
    if (res.success) {
      pendingRefetchId.value = refetchTarget.value.id;
      refetchVisible.value = false;
      await checkStatus();
      toast.add({ severity: 'info', summary: '背景抓取中', detail: `已開始重新抓取 ${stockId} 近 ${months} 個月的資料`, life: 4000 });
    } else {
      toast.add({ severity: 'warn', summary: '無法啟動', detail: res.error?.message || res.message || '已有抓取任務執行中', life: 4000 });
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '啟動失敗', detail: '啟動重新抓取失敗', life: 4000 });
  } finally {
    isRefetching.value = false;
  }
}

// 監控全域抓取狀態：等到自己觸發的重抓完成，就自動刷新清單並提示
watch(isRunning, async (running, wasRunning) => {
  if (wasRunning && !running && pendingRefetchId.value) {
    pendingRefetchId.value = null;
    await load();
    toast.add({ severity: 'success', summary: '資料抓取完成', detail: '該股票的歷史資料已就緒', life: 3000 });
  }
});

// 代號／操作圖示都用真的 <a target="_blank"> 開新分頁到「選股與圖表分析」（stock-dashboard，預設就是
// K 線圖），不要用 @click + router.push——那樣只會在目前分頁跳轉，蓋掉使用者正在看的清單頁。
// router.resolve() 才能拿到正確的 href（尊重 base path），純字串接容易在部署路徑不同時壞掉。
function stockChartHref(w) {
  return router.resolve({ path: `/stock/${w.market}/${w.symbol}` }).href;
}
</script>

<style scoped>
.num {
  font-family: ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
</style>
