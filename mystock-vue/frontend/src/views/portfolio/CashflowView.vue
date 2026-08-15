<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div>
        <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-sync text-primary text-2xl"></i>現金流 / 股利
        </h1>
        <p class="text-sm text-surface-500 mt-1">股息收入、本金出入金與真實報酬率（TWR／IRR）</p>
      </div>
      <Button label="新增紀錄" icon="pi pi-plus" @click="openAddModal" />
    </div>

    <div v-if="loading" class="flex items-center gap-2 text-surface-500 text-sm py-10 justify-center"><i class="pi pi-spin pi-spinner"></i> 載入中...</div>

    <template v-else>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide mb-1 flex items-center gap-1">
            時間加權報酬率 (TWR)
            <i class="pi pi-question-circle text-surface-300 text-xs" title="以 Modified Dietz 近似，正式 TWR 需要每日淨值快照，目前尚未提供"></i>
          </div>
          <div class="text-2xl font-black num" :class="returns.twr_pct_approx >= 0 ? 'text-emerald-600' : 'text-red-600'">{{ fmtPct(returns.twr_pct_approx) }}</div>
          <div class="text-[11px] text-amber-600 font-bold mt-1">近似值</div>
        </div>
        <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide mb-1">內部報酬率 (IRR)</div>
          <div class="text-2xl font-black num" :class="(returns.irr_pct ?? 0) >= 0 ? 'text-emerald-600' : 'text-red-600'">{{ returns.irr_pct == null ? '—' : fmtPct(returns.irr_pct) }}</div>
          <div class="text-[11px] text-surface-400 mt-1">年化，由實際出入金試算</div>
        </div>
        <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide mb-1">累計現金股利</div>
          <div class="text-2xl font-black text-surface-800 dark:text-surface-100 num">NT$ {{ fmtNum(totalCashDividendTwd) }}</div>
          <div class="text-[11px] text-surface-400 mt-1">{{ dividendModeLabel }}</div>
        </div>
        <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide mb-1">出入金淨額</div>
          <div class="text-2xl font-black text-surface-800 dark:text-surface-100 num">NT$ {{ fmtNum(netCashflow) }}</div>
        </div>
      </div>

      <div class="flex items-center gap-1 bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg p-1 w-fit">
        <button v-for="opt in subTabOptions" :key="opt.value" @click="subTab = opt.value"
          class="px-3.5 py-1.5 text-xs font-bold rounded-md transition-colors"
          :class="subTab === opt.value ? 'bg-primary text-primary-contrast shadow-sm' : 'text-surface-500 hover:text-surface-800 dark:hover:text-surface-200'">{{ opt.label }}</button>
      </div>

      <div v-if="subTab === 'dividend'" class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-sm">
            <thead>
              <tr class="bg-surface-50 dark:bg-surface-800 text-surface-400 text-xs uppercase tracking-wide">
                <th class="p-3">發放日期</th><th class="p-3">市場</th><th class="p-3">股票</th><th class="p-3">類型</th>
                <th class="p-3 text-right">金額 / 股數</th><th class="p-3">備註</th><th class="p-3 text-center">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in dividends" :key="d.id" class="border-t border-surface-100 dark:border-surface-800">
                <td class="p-3 text-surface-500 num">{{ d.pay_date }}</td>
                <td class="p-3"><span class="px-2 py-0.5 text-xs font-bold rounded bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300">{{ marketMeta[d.market].label }}</span></td>
                <td class="p-3 font-medium text-surface-800 dark:text-surface-100">{{ d.symbol }} <span class="text-surface-400 font-normal">{{ d.name }}</span></td>
                <td class="p-3"><span class="px-2 py-0.5 text-xs font-bold rounded bg-primary-50 dark:bg-primary-500/10 text-primary-700 dark:text-primary-300">{{ d.type === 'cash' ? '現金股利' : '股票股利' }}</span></td>
                <td class="p-3 text-right num font-bold text-emerald-600">{{ d.type === 'cash' ? marketMeta[d.market].symbol + ' ' + fmtAmt(d.amount, d.market) : '+' + fmtNum(d.shares) + ' 股' }}</td>
                <td class="p-3 text-surface-400 text-xs">{{ d.note }}</td>
                <td class="p-3 text-center text-surface-400"><button @click="confirmDeleteDividend(d)" class="hover:text-red-500"><i class="pi pi-trash"></i></button></td>
              </tr>
              <tr v-if="!dividends.length"><td colspan="7" class="p-8 text-center text-surface-400 text-sm">尚無股利紀錄</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="subTab === 'cash'" class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-sm">
            <thead>
              <tr class="bg-surface-50 dark:bg-surface-800 text-surface-400 text-xs uppercase tracking-wide">
                <th class="p-3">日期</th><th class="p-3">類型</th><th class="p-3 text-right">金額</th><th class="p-3">備註</th><th class="p-3 text-center">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in cashflows" :key="c.id" class="border-t border-surface-100 dark:border-surface-800">
                <td class="p-3 text-surface-500 num">{{ c.flow_date }}</td>
                <td class="p-3"><span class="px-2 py-0.5 text-xs font-bold rounded" :class="c.type === 'deposit' ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600' : 'bg-amber-50 dark:bg-amber-500/10 text-amber-600'">{{ c.type === 'deposit' ? '入金' : '出金' }}</span></td>
                <td class="p-3 text-right num font-bold" :class="c.type === 'deposit' ? 'text-emerald-600' : 'text-amber-600'">{{ c.type === 'deposit' ? '+' : '-' }}{{ fmtNum(c.amount) }}</td>
                <td class="p-3 text-surface-400 text-xs">{{ c.note }}</td>
                <td class="p-3 text-center text-surface-400"><button @click="confirmDeleteCashflow(c)" class="hover:text-red-500"><i class="pi pi-trash"></i></button></td>
              </tr>
              <tr v-if="!cashflows.length"><td colspan="5" class="p-8 text-center text-surface-400 text-sm">尚無出入金紀錄</td></tr>
            </tbody>
          </table>
        </div>
        <p class="px-4 py-3 border-t border-surface-100 dark:border-surface-800 text-xs text-surface-400">出入金不分市場，一律以 TWD 記帳。</p>
      </div>
    </template>

    <Dialog v-model:visible="showModal" header="新增現金流／股利紀錄" modal style="width: 28rem">
      <div class="space-y-4">
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">紀錄類型</label>
          <Select v-model="form.kind" :options="kindOptions" optionLabel="label" optionValue="value" class="w-full" />
        </div>
        <div v-if="isDividendKind" class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">市場</label>
            <Select v-model="form.market" :options="marketOptions" optionLabel="label" optionValue="value" class="w-full" />
          </div>
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">股票代碼</label>
            <InputText v-model="form.symbol" class="w-full" />
          </div>
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">日期</label>
          <DatePicker v-model="form.date" dateFormat="yy-mm-dd" showIcon class="w-full" />
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">{{ form.kind === 'stock_dividend' ? '股票股利股數' : '金額' }}</label>
          <InputNumber v-model="form.amount" mode="decimal" :maxFractionDigits="2" class="w-full" />
          <p v-if="isDividendKind" class="text-xs text-surface-400 mt-1">現金股利目前設定為<b>{{ dividendModeLabel }}</b>（可於設定頁切換）。</p>
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">備註</label>
          <InputText v-model="form.note" class="w-full" />
        </div>
      </div>
      <template #footer>
        <Button label="取消" text @click="showModal = false" />
        <Button label="儲存紀錄" icon="pi pi-check" :loading="saving" @click="save" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';
import { portfolioApi } from '@/service/portfolioApi';
import { marketMeta, fmtNum, fmtAmt, fmtPct, toIsoDate, todayDate } from '@/composables/usePortfolioFormat';

const toast = useToast();
const confirm = useConfirm();

const marketOptions = [{ label: '台股 TWSE', value: 'tw' }, { label: '美股 NASDAQ', value: 'us' }];
const kindOptions = [
  { label: '現金股利', value: 'cash_dividend' }, { label: '股票股利', value: 'stock_dividend' },
  { label: '資金入金', value: 'deposit' }, { label: '資金出金', value: 'withdraw' }
];
const subTabOptions = [{ value: 'dividend', label: '股利紀錄' }, { value: 'cash', label: '資金出入金' }];
const subTab = ref('dividend');

const loading = ref(true);
const dividends = ref([]);
const cashflows = ref([]);
const returns = ref({ irr_pct: null, twr_pct_approx: 0 });
const dividendMode = ref('income');

const dividendModeLabel = computed(() => (dividendMode.value === 'income' ? '計入已實現收益' : '沖抵持股成本'));
const totalCashDividendTwd = computed(() => dividends.value.reduce((s, d) => (d.type === 'cash' ? s + (d.market === 'us' ? d.amount * fxRate.value : d.amount) : s), 0));
const netCashflow = computed(() => cashflows.value.reduce((s, c) => s + (c.type === 'deposit' ? c.amount : -c.amount), 0));
const fxRate = ref(32.5);

async function loadAll() {
  loading.value = true;
  try {
    const [divRes, cashRes, returnsRes, settingsRes] = await Promise.all([
      portfolioApi.getDividends(), portfolioApi.getCashflows(), portfolioApi.getReturns(), portfolioApi.getSettings()
    ]);
    dividends.value = divRes.data;
    cashflows.value = cashRes.data;
    returns.value = returnsRes.data;
    dividendMode.value = settingsRes.data.dividend_mode;
    fxRate.value = settingsRes.data.fx_rate;
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: err?.response?.data?.detail || err.message, life: 4000 });
  } finally {
    loading.value = false;
  }
}
onMounted(loadAll);

const isDividendKind = computed(() => form.kind === 'cash_dividend' || form.kind === 'stock_dividend');
const showModal = ref(false);
const saving = ref(false);
function blankForm() {
  return { kind: 'cash_dividend', market: 'tw', symbol: '', date: todayDate(), amount: null, note: '' };
}
const form = reactive(blankForm());
function openAddModal() { Object.assign(form, blankForm()); showModal.value = true; }

async function save() {
  saving.value = true;
  try {
    if (isDividendKind.value) {
      if (!form.symbol || form.amount == null) { toast.add({ severity: 'error', summary: '請填寫股票代碼與金額/股數', life: 3000 }); return; }
      await portfolioApi.createDividend({
        market: form.market, symbol: form.symbol, pay_date: toIsoDate(form.date),
        type: form.kind === 'cash_dividend' ? 'cash' : 'stock',
        amount: form.kind === 'cash_dividend' ? form.amount : null,
        shares: form.kind === 'stock_dividend' ? form.amount : null,
        note: form.note || null
      });
    } else {
      if (form.amount == null) { toast.add({ severity: 'error', summary: '請填寫金額', life: 3000 }); return; }
      await portfolioApi.createCashflow({ flow_date: toIsoDate(form.date), type: form.kind, amount: form.amount, note: form.note || null });
    }
    toast.add({ severity: 'success', summary: '已新增紀錄', life: 2500 });
    showModal.value = false;
    await loadAll();
  } catch (err) {
    toast.add({ severity: 'error', summary: '儲存失敗', detail: err?.response?.data?.detail || err.message, life: 5000 });
  } finally {
    saving.value = false;
  }
}

function confirmDeleteDividend(d) {
  confirm.require({
    message: `確定要刪除 ${d.symbol} 於 ${d.pay_date} 的股利紀錄嗎？`, header: '刪除股利紀錄', icon: 'pi pi-exclamation-triangle', acceptLabel: '確定刪除', rejectLabel: '取消', acceptClass: 'p-button-danger',
    accept: async () => {
      await portfolioApi.deleteDividend(d.id);
      toast.add({ severity: 'success', summary: '已刪除股利紀錄', life: 2500 });
      await loadAll();
    }
  });
}
function confirmDeleteCashflow(c) {
  confirm.require({
    message: `確定要刪除 ${c.flow_date} 的資金出入金紀錄嗎？`, header: '刪除出入金紀錄', icon: 'pi pi-exclamation-triangle', acceptLabel: '確定刪除', rejectLabel: '取消', acceptClass: 'p-button-danger',
    accept: async () => {
      await portfolioApi.deleteCashflow(c.id);
      toast.add({ severity: 'success', summary: '已刪除紀錄', life: 2500 });
      await loadAll();
    }
  });
}
</script>

<style scoped>
.num {
  font-family: ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
</style>
