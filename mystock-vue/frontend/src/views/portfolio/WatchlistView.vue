<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div>
        <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-eye text-primary text-2xl"></i>觀察名單
        </h1>
        <p class="text-sm text-surface-500 mt-1">追蹤候選股，設定目標買進價，取消或移除不影響任何已存在的交易紀錄</p>
      </div>
      <Button label="加入觀察" icon="pi pi-eye" @click="openAddModal" />
    </div>

    <div class="p-4 rounded-xl bg-primary-50 dark:bg-primary-500/10 border border-primary-200 dark:border-primary-500/30 text-primary-800 dark:text-primary-300 text-sm flex items-start gap-2.5">
      <i class="pi pi-info-circle mt-0.5"></i>
      <span>到價推播通知（串接整合訊息通知平台）尚未串接，目前僅頁面即時顯示距目標價；此功能規劃於後續擴充。</span>
    </div>

    <div v-if="loading" class="flex items-center gap-2 text-surface-500 text-sm py-10 justify-center"><i class="pi pi-spin pi-spinner"></i> 載入中...</div>

    <template v-else>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center gap-3">
          <div class="w-12 h-12 rounded-xl bg-primary-50 dark:bg-primary-500/10 text-primary flex items-center justify-center text-xl shrink-0"><i class="pi pi-eye"></i></div>
          <div><div class="text-xs font-bold text-surface-400 uppercase tracking-wide">觀察中檔數</div><div class="text-2xl font-black text-surface-900 dark:text-surface-0 num">{{ watchlist.length }}</div></div>
        </div>
        <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center gap-3">
          <div class="w-12 h-12 rounded-xl bg-amber-50 dark:bg-amber-500/10 text-amber-600 flex items-center justify-center text-xl shrink-0"><i class="pi pi-bell"></i></div>
          <div><div class="text-xs font-bold text-surface-400 uppercase tracking-wide">接近目標價</div><div class="text-2xl font-black text-amber-600 num">{{ nearTargetCount }}</div></div>
        </div>
        <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center gap-3">
          <div class="w-12 h-12 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 flex items-center justify-center text-xl shrink-0"><i class="pi pi-check-circle"></i></div>
          <div><div class="text-xs font-bold text-surface-400 uppercase tracking-wide">已跌破目標價</div><div class="text-2xl font-black text-emerald-600 num">{{ reachedCount }}</div></div>
        </div>
      </div>

      <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-sm">
            <thead>
              <tr class="bg-surface-50 dark:bg-surface-800 text-surface-400 text-xs uppercase tracking-wide">
                <th class="p-3">股票</th><th class="p-3">市場</th><th class="p-3">加入日期</th>
                <th class="p-3 text-right">目前股價</th><th class="p-3 text-right">目標買進價</th><th class="p-3 text-right">距目標</th>
                <th class="p-3">備註</th><th class="p-3 text-center">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="w in watchlist" :key="w.id" class="border-t border-surface-100 dark:border-surface-800" :class="w.is_near_target ? 'bg-amber-50/50 dark:bg-amber-500/5' : ''">
                <td class="p-3">
                  <div class="font-bold text-surface-800 dark:text-surface-100 flex items-center gap-1.5">
                    <a :href="stockChartHref(w)" target="_blank" rel="noopener" title="在新分頁開啟「選股與圖表分析」" class="hover:text-primary hover:underline">{{ w.symbol }}</a>
                    <span v-if="w.is_reached" class="px-1.5 py-0.5 text-[10px] font-bold rounded bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300">已達價</span>
                    <span v-else-if="w.is_near_target" class="px-1.5 py-0.5 text-[10px] font-bold rounded bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300">到價提醒</span>
                  </div>
                  <div class="text-xs text-surface-400">{{ w.name }}</div>
                </td>
                <td class="p-3"><span class="px-2 py-0.5 text-xs font-bold rounded bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300">{{ marketMeta[w.market].label }}</span></td>
                <td class="p-3 text-surface-500 num">{{ w.added_date }}</td>
                <td class="p-3 text-right num font-medium">
                  <span v-if="w.price != null">{{ w.price.toFixed(2) }}</span>
                  <span v-else class="text-surface-300" title="尚無最新報價資料">待報價</span>
                </td>
                <td class="p-3 text-right num">{{ w.target_price.toFixed(2) }}</td>
                <td class="p-3 text-right num font-bold" :class="w.price == null ? 'text-surface-300' : (w.gap_pct <= 0 ? 'text-emerald-600' : 'text-surface-500')">
                  {{ w.price == null ? '—' : fmtPct(w.gap_pct) }}
                </td>
                <td class="p-3 text-surface-400 text-xs max-w-[160px] truncate" :title="w.note">{{ w.note }}</td>
                <td class="p-3 text-center whitespace-nowrap">
                  <a :href="stockChartHref(w)" target="_blank" rel="noopener" title="在新分頁開啟「選股與圖表分析」" class="text-surface-400 hover:text-primary mx-1 inline-block align-middle"><i class="pi pi-chart-bar"></i></a>
                  <button @click="convertToTransaction(w)" title="登錄買進" class="text-primary hover:text-primary-700 mx-1"><i class="pi pi-shopping-cart"></i></button>
                  <button @click="openEditModal(w)" title="編輯" class="text-surface-400 hover:text-primary mx-1"><i class="pi pi-pencil"></i></button>
                  <button @click="confirmRemove(w)" title="移除" class="text-surface-400 hover:text-red-500 mx-1"><i class="pi pi-trash"></i></button>
                </td>
              </tr>
              <tr v-if="!watchlist.length"><td colspan="8" class="p-8 text-center text-surface-400 text-sm">觀察名單目前是空的</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <Dialog v-model:visible="showModal" :header="editingId ? '編輯觀察紀錄' : '加入觀察名單'" modal style="width: 26rem">
      <div class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">市場</label>
            <Select v-model="form.market" :options="marketOptions" optionLabel="label" optionValue="value" :disabled="!!editingId" class="w-full" />
          </div>
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">股票代碼</label>
            <div class="flex gap-1.5">
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
          <label class="block text-xs font-bold text-surface-500 mb-1">目標買進價</label>
          <InputNumber v-model="form.target_price" mode="decimal" :maxFractionDigits="2" class="w-full" />
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">備註</label>
          <Textarea v-model="form.note" rows="2" class="w-full" placeholder="例如：等季報公布、等回檔至月線" />
        </div>
      </div>
      <template #footer>
        <Button label="取消" text @click="showModal = false" />
        <Button :label="editingId ? '儲存變更' : '加入觀察'" icon="pi pi-check" :loading="saving" @click="save" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';
import { portfolioApi } from '@/service/portfolioApi';
import { usePortfolioPrefill } from '@/composables/usePortfolioPrefill';
import { marketMeta, fmtPct } from '@/composables/usePortfolioFormat';

const router = useRouter();
const toast = useToast();
const confirm = useConfirm();
const { setPendingTransaction } = usePortfolioPrefill();

const marketOptions = [{ label: '台股 TWSE', value: 'tw' }, { label: '美股 NASDAQ', value: 'us' }];

const loading = ref(true);
const watchlist = ref([]);
const nearTargetCount = computed(() => watchlist.value.filter((w) => w.is_near_target).length);
const reachedCount = computed(() => watchlist.value.filter((w) => w.is_reached).length);

async function load() {
  loading.value = true;
  try {
    const res = await portfolioApi.getWatchlist();
    watchlist.value = res.data;
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: err?.response?.data?.detail || err.message, life: 4000 });
  } finally {
    loading.value = false;
  }
}
onMounted(load);

const showModal = ref(false);
const editingId = ref(null);
const saving = ref(false);
function blankForm() { return { market: 'tw', symbol: '', name: '', target_price: null, note: '' }; }
const form = reactive(blankForm());

function openAddModal() { Object.assign(form, blankForm()); editingId.value = null; showModal.value = true; }
function openEditModal(w) {
  Object.assign(form, { market: w.market, symbol: w.symbol, name: w.name, target_price: w.target_price, note: w.note || '' });
  editingId.value = w.id;
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

async function save() {
  if (!form.symbol || form.target_price == null) {
    toast.add({ severity: 'error', summary: '請填寫股票代碼與目標買進價', life: 3000 });
    return;
  }
  saving.value = true;
  try {
    if (editingId.value) {
      await portfolioApi.updateWatchlist(editingId.value, { target_price: form.target_price, note: form.note, name: form.name || undefined });
      toast.add({ severity: 'success', summary: '已更新觀察紀錄', life: 2500 });
    } else {
      const res = await portfolioApi.addWatchlist({ market: form.market, symbol: form.symbol, name: form.name || undefined, target_price: form.target_price, note: form.note || null });
      toast.add({ severity: 'success', summary: res.message, life: 2500 });
    }
    showModal.value = false;
    await load();
  } catch (err) {
    toast.add({ severity: 'error', summary: '儲存失敗', detail: err?.response?.data?.detail || err.message, life: 5000 });
  } finally {
    saving.value = false;
  }
}

function confirmRemove(w) {
  confirm.require({
    message: `確定要將 ${w.symbol} ${w.name} 從觀察名單移除嗎？此動作不影響任何交易紀錄。`,
    header: '移除觀察紀錄', icon: 'pi pi-exclamation-triangle', acceptLabel: '確定移除', rejectLabel: '取消', acceptClass: 'p-button-danger',
    accept: async () => {
      await portfolioApi.removeWatchlist(w.id);
      toast.add({ severity: 'success', summary: '已從觀察名單移除', life: 2500 });
      await load();
    }
  });
}

function convertToTransaction(w) {
  setPendingTransaction({ market: w.market, symbol: w.symbol, name: w.name, price: w.price ?? w.target_price, watchId: w.id });
  router.push({ name: 'portfolio-transactions' });
}

// 代號／操作圖示都用真的 <a target="_blank"> 開新分頁到「選股與圖表分析」（stock-dashboard，預設就是
// K 線圖），不要用 @click + router.push——那樣只會在目前分頁跳轉，蓋掉使用者正在看的觀察名單。
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
