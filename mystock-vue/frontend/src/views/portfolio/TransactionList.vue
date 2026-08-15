<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div>
        <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-list text-primary text-2xl"></i>交易紀錄
        </h1>
        <p class="text-sm text-surface-500 mt-1">新增／編輯／刪除任一筆交易，持股均價、已實現損益與勝率都會即時重算</p>
      </div>
      <div class="flex items-center gap-2">
        <Button label="匯入" icon="pi pi-upload" severity="secondary" outlined @click="importDialog = true" />
        <Button label="匯出 CSV" icon="pi pi-download" severity="secondary" outlined @click="exportCsv" />
        <Button label="新增交易" icon="pi pi-plus" @click="openAddModal" />
      </div>
    </div>

    <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
      <div class="flex flex-wrap gap-3 items-center">
        <InputText v-model="filters.keyword" placeholder="搜尋代碼或名稱..." class="w-48" />
        <Select v-model="filters.market" :options="marketOptions" optionLabel="label" optionValue="value" placeholder="全部市場" showClear class="w-32" />
        <Select v-model="filters.side" :options="sideOptions" optionLabel="label" optionValue="value" placeholder="全部類型" showClear class="w-32" />
        <DatePicker v-model="filters.from" placeholder="起始日期" dateFormat="yy-mm-dd" showIcon showButtonBar class="w-40" />
        <span class="text-surface-400 text-sm">至</span>
        <DatePicker v-model="filters.to" placeholder="結束日期" dateFormat="yy-mm-dd" showIcon showButtonBar class="w-40" />
        <Button label="清除篩選" icon="pi pi-filter-slash" text size="small" @click="resetFilters" />
      </div>
    </div>

    <div v-if="loading" class="flex items-center gap-2 text-surface-500 text-sm py-10 justify-center"><i class="pi pi-spin pi-spinner"></i> 載入中...</div>

    <div v-else class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="bg-surface-50 dark:bg-surface-800 text-surface-400 text-xs uppercase tracking-wide">
              <th class="p-3">交易日期</th>
              <th class="p-3">市場</th>
              <th class="p-3">類型</th>
              <th class="p-3">股票</th>
              <th class="p-3 text-right">股數</th>
              <th class="p-3 text-right">單價</th>
              <th class="p-3 text-right">手續費/稅</th>
              <th class="p-3 text-right">淨收付</th>
              <th class="p-3 text-center">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="tx in pagedTransactions" :key="tx.id" class="border-t border-surface-100 dark:border-surface-800 hover:bg-surface-50 dark:hover:bg-surface-800/60">
              <td class="p-3 text-surface-500 num">
                {{ tx.trade_date }}
                <div v-if="tx.trade_time" class="text-[11px] text-surface-400">{{ tx.trade_time }}</div>
              </td>
              <td class="p-3"><span class="px-2 py-0.5 text-xs font-bold rounded bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300">{{ marketMeta[tx.market].label }}</span></td>
              <td class="p-3">
                <span class="px-2 py-1 text-xs font-bold rounded whitespace-nowrap" :class="tx.side === 'buy' ? 'bg-red-50 dark:bg-red-500/10 text-red-600' : 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600'">
                  {{ (tx.odd_lot ? '零股' : '') + (tx.side === 'buy' ? '買進' : '賣出') }}
                </span>
              </td>
              <td class="p-3 font-medium text-surface-800 dark:text-surface-100">
                {{ tx.symbol }} <span class="text-surface-400 font-normal">{{ tx.name }}</span>
                <span v-if="isTwEtfSymbol(tx.symbol) && tx.market === 'tw'" class="ml-1 px-1.5 py-0.5 text-[10px] font-bold rounded bg-primary-50 dark:bg-primary-500/10 text-primary-700 dark:text-primary-300">ETF</span>
              </td>
              <td class="p-3 text-right num">
                {{ fmtNum(tx.shares) }}
                <div v-if="lotLabel(tx.shares, tx.market)" class="text-[11px] text-surface-400">{{ lotLabel(tx.shares, tx.market) }}</div>
              </td>
              <td class="p-3 text-right num">{{ tx.price.toFixed(2) }}</td>
              <td class="p-3 text-right num text-surface-400 text-xs">
                {{ fmtAmt(tx.fee, tx.market) }} / {{ fmtAmt(tx.tax, tx.market) }}
                <div v-if="tx.fee_is_manual || tx.tax_is_manual" class="text-[10px] text-amber-600 font-bold">手動</div>
              </td>
              <td class="p-3 text-right font-bold num" :class="tx.side === 'buy' ? 'text-surface-800 dark:text-surface-100' : 'text-primary-700 dark:text-primary-300'">
                {{ tx.side === 'buy' ? '-' : '+' }}{{ fmtAmt(tx.net, tx.market) }}
              </td>
              <td class="p-3 text-center text-surface-400 whitespace-nowrap">
                <button @click="openEditModal(tx)" title="編輯" class="hover:text-primary mx-1 transition-colors"><i class="pi pi-pencil"></i></button>
                <button @click="confirmDelete(tx)" title="刪除" class="hover:text-red-500 mx-1 transition-colors"><i class="pi pi-trash"></i></button>
              </td>
            </tr>
            <tr v-if="!filteredTransactions.length">
              <td colspan="9" class="p-8 text-center text-surface-400 text-sm">沒有符合篩選條件的交易紀錄</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="flex items-center justify-between px-4 py-3 border-t border-surface-100 dark:border-surface-800 text-xs text-surface-400">
        <span>共 {{ filteredTransactions.length }} 筆，第 {{ page }} / {{ pageCount }} 頁</span>
        <div class="flex items-center gap-1">
          <Button label="上一頁" size="small" text :disabled="page <= 1" @click="page--" />
          <Button label="下一頁" size="small" text :disabled="page >= pageCount" @click="page++" />
        </div>
      </div>
    </div>

    <!-- ══════ 新增／編輯交易 ══════ -->
    <Dialog v-model:visible="showModal" :header="editingId ? '編輯交易紀錄' : '新增交易紀錄'" modal style="width: 34rem">
      <div class="space-y-4">
        <div class="flex gap-3">
          <label class="flex-1 flex items-center justify-center gap-2 cursor-pointer font-bold px-4 py-2.5 rounded-lg border-2 transition-colors"
            :class="form.side === 'buy' ? 'text-red-600 bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/30' : 'text-surface-400 border-surface-200 dark:border-surface-700'">
            <RadioButton v-model="form.side" value="buy" /> 買進
          </label>
          <label class="flex-1 flex items-center justify-center gap-2 cursor-pointer font-bold px-4 py-2.5 rounded-lg border-2 transition-colors"
            :class="form.side === 'sell' ? 'text-emerald-600 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/30' : 'text-surface-400 border-surface-200 dark:border-surface-700'">
            <RadioButton v-model="form.side" value="sell" /> 賣出
          </label>
        </div>

        <label v-if="form.market === 'tw'" class="flex items-center gap-2 text-sm text-surface-600 dark:text-surface-300 bg-surface-50 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg px-3 py-2">
          <Checkbox v-model="form.odd_lot" binary />
          <span>零股交易<span class="text-xs text-surface-400 ml-1">（未滿 1 張 ＝ {{ marketMeta.tw.lotSize }} 股；勾選後股數不受整張限制）</span></span>
        </label>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">市場</label>
            <Select v-model="form.market" :options="marketOptions" optionLabel="label" optionValue="value" class="w-full" />
          </div>
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">交易日期 / 時間</label>
            <div class="flex gap-1.5">
              <DatePicker v-model="form.trade_date" dateFormat="yy-mm-dd" showIcon class="w-full" />
              <InputText v-model="form.trade_time" placeholder="HH:MM" class="w-24" />
            </div>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">股票代碼</label>
            <div class="flex gap-1.5">
              <InputText v-model="form.symbol" @blur="lookupName" :placeholder="form.market === 'tw' ? '例如: 2330' : '例如: AAPL'" class="w-full" />
              <Button icon="pi pi-search" outlined @click="lookupName" title="查詢名稱" />
            </div>
          </div>
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">股票名稱</label>
            <InputText v-model="form.name" placeholder="自動帶出或手動輸入" class="w-full" />
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">成交單價</label>
            <InputNumber v-model="form.price" mode="decimal" :minFractionDigits="0" :maxFractionDigits="4" class="w-full" />
          </div>
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">成交股數</label>
            <InputNumber v-model="form.shares" class="w-full" />
          </div>
        </div>

        <div class="bg-surface-50 dark:bg-surface-800 p-4 rounded-lg border border-surface-100 dark:border-surface-700 space-y-2">
          <label class="flex items-center gap-2 text-xs font-bold text-surface-500">
            <Checkbox v-model="form.manualOverride" binary /> 手動調整手續費 / 稅金
          </label>
          <div class="flex justify-between items-center">
            <span class="text-sm text-surface-600 dark:text-surface-300">手續費{{ form.manualOverride ? '' : '（自動試算）' }}</span>
            <InputNumber v-model="form.fee" mode="decimal" :maxFractionDigits="2" :disabled="!form.manualOverride" class="w-32 min-w-0 shrink-0" inputClass="text-right w-full min-w-0" />
          </div>
          <div class="flex justify-between items-center">
            <span class="text-sm text-surface-600 dark:text-surface-300">{{ form.market === 'tw' ? '證交稅' : 'SEC 規費' }}{{ form.manualOverride ? '' : '（自動試算）' }}</span>
            <InputNumber v-model="form.tax" mode="decimal" :maxFractionDigits="2" :disabled="!form.manualOverride" class="w-32 min-w-0 shrink-0" inputClass="text-right w-full min-w-0" />
          </div>
          <p class="text-[11px] text-surface-400">留空未覆寫時，儲存當下會依目前設定頁費率自動試算並凍結；之後調整設定不會回頭改動這筆紀錄。</p>
        </div>

        <Message v-if="sellPreview" :severity="sellPreview.ok ? 'success' : 'error'" :closable="false">{{ sellPreview.message }}</Message>
      </div>
      <template #footer>
        <Button label="取消" text @click="showModal = false" />
        <Button label="儲存紀錄" icon="pi pi-check" :loading="saving" @click="saveTx" />
      </template>
    </Dialog>

    <!-- ══════ 匯入 ══════ -->
    <Dialog v-model:visible="importDialog" header="批次匯入交易紀錄" modal style="width: 40rem">
      <div class="space-y-4">
        <div class="p-3 rounded-lg bg-surface-50 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 text-xs text-surface-500 dark:text-surface-400">
          <div class="font-bold text-surface-700 dark:text-surface-200 mb-1">CSV 範本欄位</div>
          <code class="block whitespace-pre-wrap">date,time,market,side,symbol,name,shares,price,odd_lot,fee,tax</code>
          <div class="mt-1.5">market：tw / us；side：buy / sell；odd_lot：1 為零股；fee、tax 留空則依設定頁費率自動試算。</div>
        </div>
        <input ref="fileInputEl" type="file" accept=".csv,text/csv" @change="onFileSelected"
          class="text-sm file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-primary file:text-white file:font-bold file:cursor-pointer" />
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">或直接貼上 CSV 內容</label>
          <Textarea v-model="importText" rows="6" class="w-full font-mono text-xs" placeholder="date,time,market,side,symbol,name,shares,price,odd_lot,fee,tax" />
        </div>
        <div v-if="importResult">
          <Message :severity="importResult.errors.length ? 'warn' : 'success'" :closable="false">
            已匯入 {{ importResult.committed }} 筆{{ importResult.errors.length ? `，${importResult.errors.length} 筆有問題` : '' }}
          </Message>
          <ul v-if="importResult.errors.length" class="mt-2 text-xs text-red-600 dark:text-red-400 space-y-0.5 max-h-32 overflow-y-auto">
            <li v-for="(e, i) in importResult.errors" :key="i">{{ e.line ? `第 ${e.line} 行：` : '' }}{{ e.message }}</li>
          </ul>
        </div>
      </div>
      <template #footer>
        <Button label="關閉" text @click="importDialog = false" />
        <Button label="開始匯入" icon="pi pi-upload" :loading="importing" :disabled="!importText && !selectedFile" @click="doImport" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';
import { portfolioApi } from '@/service/portfolioApi';
import { usePortfolioPrefill } from '@/composables/usePortfolioPrefill';
import { marketMeta, fmtNum, fmtAmt, lotLabel, isTwEtfSymbol, toIsoDate, fromIsoDate, todayDate } from '@/composables/usePortfolioFormat';

const toast = useToast();
const confirm = useConfirm();
const { consumePendingTransaction } = usePortfolioPrefill();

const marketOptions = [{ label: '台股 TWSE', value: 'tw' }, { label: '美股 NASDAQ', value: 'us' }];
const sideOptions = [{ label: '買進', value: 'buy' }, { label: '賣出', value: 'sell' }];

const loading = ref(true);
const transactions = ref([]);
const holdingsBySymbol = ref({}); // 'tw:2330' -> shares，供賣出防呆提示（實際防呆仍由後端驗證）

const filters = reactive({ keyword: '', market: null, side: null, from: null, to: null });
function resetFilters() { Object.assign(filters, { keyword: '', market: null, side: null, from: null, to: null }); }

const filteredTransactions = computed(() => {
  return transactions.value.filter((tx) => {
    if (filters.market && tx.market !== filters.market) return false;
    if (filters.side && tx.side !== filters.side) return false;
    if (filters.keyword) {
      const k = filters.keyword.toLowerCase();
      if (!tx.symbol.toLowerCase().includes(k) && !(tx.name || '').toLowerCase().includes(k)) return false;
    }
    if (filters.from && tx.trade_date < toIsoDate(filters.from)) return false;
    if (filters.to && tx.trade_date > toIsoDate(filters.to)) return false;
    return true;
  });
});

const PAGE_SIZE = 12;
const page = ref(1);
const pageCount = computed(() => Math.max(1, Math.ceil(filteredTransactions.value.length / PAGE_SIZE)));
const pagedTransactions = computed(() => filteredTransactions.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE));
watch([filteredTransactions, pageCount], () => { if (page.value > pageCount.value) page.value = pageCount.value; });

async function loadTransactions() {
  loading.value = true;
  try {
    const res = await portfolioApi.getTransactions();
    transactions.value = res.data;
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: err?.response?.data?.detail || err.message, life: 4000 });
  } finally {
    loading.value = false;
  }
}
async function loadHoldingsMap() {
  try {
    const res = await portfolioApi.getHoldings();
    holdingsBySymbol.value = Object.fromEntries(res.data.map((h) => [`${h.market}:${h.symbol}`, h.shares]));
  } catch { /* 賣出防呆提示是輔助資訊，載入失敗不影響主流程 */ }
}

// ── 新增／編輯 Modal ──────────────────────────────────────────
const showModal = ref(false);
const editingId = ref(null);
const saving = ref(false);
function blankForm() {
  return {
    side: 'buy', market: 'tw', symbol: '', name: '', trade_date: todayDate(), trade_time: '',
    price: null, shares: null, odd_lot: false, fee: 0, tax: 0, manualOverride: false, pendingWatchId: null
  };
}
const form = reactive(blankForm());

function openAddModal() {
  Object.assign(form, blankForm());
  editingId.value = null;
  showModal.value = true;
}
function openEditModal(tx) {
  Object.assign(form, {
    side: tx.side, market: tx.market, symbol: tx.symbol, name: tx.name,
    trade_date: fromIsoDate(tx.trade_date), trade_time: tx.trade_time ? tx.trade_time.slice(0, 5) : '',
    price: tx.price, shares: tx.shares, odd_lot: tx.odd_lot, fee: tx.fee, tax: tx.tax,
    manualOverride: tx.fee_is_manual || tx.tax_is_manual, pendingWatchId: null
  });
  editingId.value = tx.id;
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
    }
  } catch { /* 查無代號時保留手動輸入，不阻擋流程 */ }
}

const sellPreview = computed(() => {
  if (form.side !== 'sell' || !form.symbol) return null;
  const key = `${form.market}:${String(form.symbol).toUpperCase()}`;
  let available = holdingsBySymbol.value[key] || 0;
  const want = form.shares || 0;
  if (!want) return { ok: true, message: `目前 ${form.symbol} 可賣庫存約 ${available.toLocaleString()} 股` };
  return want <= available
    ? { ok: true, message: `可賣庫存約 ${available.toLocaleString()} 股，儲存後由後端做最終確認` }
    : { ok: false, message: `庫存可能不足：目前約 ${available.toLocaleString()} 股，實際結果以儲存時後端驗證為準` };
});

async function saveTx() {
  if (!form.symbol || !form.price || !form.shares) {
    toast.add({ severity: 'error', summary: '請完整填寫股票代碼、單價與股數', life: 3000 });
    return;
  }
  const payload = {
    market: form.market, symbol: form.symbol, name: form.name || form.symbol, side: form.side,
    trade_date: toIsoDate(form.trade_date), trade_time: form.trade_time || null,
    shares: form.shares, price: form.price, odd_lot: form.odd_lot,
    fee: form.manualOverride ? form.fee : null, tax: form.manualOverride ? form.tax : null
  };
  saving.value = true;
  try {
    if (editingId.value) {
      await portfolioApi.updateTransaction(editingId.value, payload);
      toast.add({ severity: 'success', summary: '交易紀錄已更新', life: 2500 });
    } else {
      await portfolioApi.createTransaction(payload);
      toast.add({ severity: 'success', summary: '交易紀錄已新增', life: 2500 });
    }
    showModal.value = false;
    await Promise.all([loadTransactions(), loadHoldingsMap()]);
  } catch (err) {
    toast.add({ severity: 'error', summary: '儲存失敗', detail: err?.response?.data?.detail || err.message, life: 5000 });
  } finally {
    saving.value = false;
  }
}

function confirmDelete(tx) {
  confirm.require({
    message: `確定要刪除 ${tx.symbol} ${tx.name} 於 ${tx.trade_date} 的交易紀錄嗎？刪除後持股成本、已實現損益與勝率都會重新計算。`,
    header: '刪除交易紀錄',
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: '確定刪除',
    rejectLabel: '取消',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await portfolioApi.deleteTransaction(tx.id);
        toast.add({ severity: 'success', summary: '已刪除交易紀錄', life: 2500 });
        await Promise.all([loadTransactions(), loadHoldingsMap()]);
      } catch (err) {
        toast.add({ severity: 'error', summary: '刪除失敗', detail: err?.response?.data?.detail || err.message, life: 5000 });
      }
    }
  });
}

// ── 匯入／匯出 ────────────────────────────────────────────────
const importDialog = ref(false);
const importText = ref('');
const selectedFile = ref(null);
const fileInputEl = ref(null);
const importing = ref(false);
const importResult = ref(null);

function onFileSelected(e) {
  selectedFile.value = e.target.files?.[0] || null;
}
async function doImport() {
  importing.value = true;
  importResult.value = null;
  try {
    const res = await portfolioApi.importTransactions({ file: selectedFile.value, csvText: selectedFile.value ? null : importText.value });
    importResult.value = res.data;
    if (res.data.committed > 0) {
      toast.add({ severity: 'success', summary: `已匯入 ${res.data.committed} 筆`, life: 3000 });
      await Promise.all([loadTransactions(), loadHoldingsMap()]);
    }
    importText.value = '';
    selectedFile.value = null;
    if (fileInputEl.value) fileInputEl.value.value = '';
  } catch (err) {
    toast.add({ severity: 'error', summary: '匯入失敗', detail: err?.response?.data?.detail || err.message, life: 5000 });
  } finally {
    importing.value = false;
  }
}

async function exportCsv() {
  try {
    const response = await portfolioApi.exportTransactionsBlob({
      market: filters.market, side: filters.side, keyword: filters.keyword,
      dateFrom: filters.from ? toIsoDate(filters.from) : null, dateTo: filters.to ? toIsoDate(filters.to) : null
    });
    const url = URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `transactions_${toIsoDate(todayDate())}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    toast.add({ severity: 'error', summary: '匯出失敗', detail: err?.response?.data?.detail || err.message, life: 4000 });
  }
}

onMounted(async () => {
  await Promise.all([loadTransactions(), loadHoldingsMap()]);
  // 從觀察名單「登錄買進」捷徑帶資料過來（設計文件 §五）
  const pending = consumePendingTransaction();
  if (pending) {
    Object.assign(form, blankForm(), {
      side: 'buy', market: pending.market, symbol: pending.symbol, name: pending.name,
      price: pending.price, shares: pending.market === 'tw' ? marketMeta.tw.lotSize : 1,
      pendingWatchId: pending.watchId
    });
    editingId.value = null;
    showModal.value = true;
  }
});
</script>

<style scoped>
.num {
  font-family: ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
</style>
