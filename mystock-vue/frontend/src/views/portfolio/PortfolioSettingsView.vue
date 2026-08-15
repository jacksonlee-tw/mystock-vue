<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <div class="card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
        <i class="pi pi-cog text-primary text-2xl"></i>記帳設定
      </h1>
      <p class="text-sm text-surface-500 mt-1">交易成本費率、匯率與計算規則；改動只影響「之後」新增/試算的手續費，已存的歷史交易不會被回頭改動</p>
    </div>

    <div v-if="loading" class="flex items-center gap-2 text-surface-500 text-sm py-10 justify-center"><i class="pi pi-spin pi-spinner"></i> 載入中...</div>

    <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="p-5 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm space-y-4">
        <h2 class="text-sm font-bold text-surface-700 dark:text-surface-200 pb-2 border-b border-surface-100 dark:border-surface-800">台股交易成本</h2>
        <div class="flex items-center justify-between gap-3">
          <label class="text-sm text-surface-600 dark:text-surface-300">手續費率</label>
          <InputNumber v-model="form.tw_fee_rate" :minFractionDigits="4" :maxFractionDigits="6" class="w-36 min-w-0 shrink-0" inputClass="text-right w-full min-w-0" />
        </div>
        <div class="flex items-center justify-between gap-3">
          <label class="text-sm text-surface-600 dark:text-surface-300">券商折讓 <span class="text-xs text-surface-400">（0.6 ＝ 6 折）</span></label>
          <InputNumber v-model="form.tw_fee_discount" :minFractionDigits="2" :maxFractionDigits="3" class="w-36 min-w-0 shrink-0" inputClass="text-right w-full min-w-0" />
        </div>
        <div class="flex items-center justify-between gap-3">
          <label class="text-sm text-surface-600 dark:text-surface-300">最低手續費</label>
          <InputNumber v-model="form.tw_fee_min" class="w-36 min-w-0 shrink-0" inputClass="text-right w-full min-w-0" />
        </div>
        <div class="flex items-center justify-between gap-3">
          <label class="text-sm text-surface-600 dark:text-surface-300">證交稅率（一般股票）</label>
          <InputNumber v-model="form.tw_tax_rate" :minFractionDigits="3" :maxFractionDigits="4" class="w-36 min-w-0 shrink-0" inputClass="text-right w-full min-w-0" />
        </div>
        <div class="flex items-center justify-between gap-3">
          <label class="text-sm text-surface-600 dark:text-surface-300">證交稅率（ETF/ETN）</label>
          <InputNumber v-model="form.tw_tax_rate_etf" :minFractionDigits="3" :maxFractionDigits="4" class="w-36 min-w-0 shrink-0" inputClass="text-right w-full min-w-0" />
        </div>
      </div>

      <div class="p-5 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm space-y-4">
        <h2 class="text-sm font-bold text-surface-700 dark:text-surface-200 pb-2 border-b border-surface-100 dark:border-surface-800">美股交易成本與匯率</h2>
        <div class="flex items-center justify-between gap-3">
          <label class="text-sm text-surface-600 dark:text-surface-300">手續費率 <span class="text-xs text-surface-400">（0 ＝ 免佣）</span></label>
          <InputNumber v-model="form.us_fee_rate" :minFractionDigits="2" :maxFractionDigits="4" class="w-36 min-w-0 shrink-0" inputClass="text-right w-full min-w-0" />
        </div>
        <div class="flex items-center justify-between gap-3">
          <label class="text-sm text-surface-600 dark:text-surface-300">SEC 規費率（賣出）</label>
          <InputNumber v-model="form.us_sec_fee_rate" :minFractionDigits="6" :maxFractionDigits="8" class="w-36 min-w-0 shrink-0" inputClass="text-right w-full min-w-0" />
        </div>
        <div class="flex items-center justify-between gap-3">
          <label class="text-sm text-surface-600 dark:text-surface-300">USD → TWD 匯率</label>
          <InputNumber v-model="form.fx_rate" :minFractionDigits="2" :maxFractionDigits="4" class="w-36 min-w-0 shrink-0" inputClass="text-right w-full min-w-0" />
        </div>
        <Message severity="secondary" :closable="false">
          目前採單一可調匯率換算所有美股金額；逐筆歷史匯率（依交易當日實際匯率換算）留待後續擴充。
        </Message>
      </div>

      <div class="p-5 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm space-y-4">
        <h2 class="text-sm font-bold text-surface-700 dark:text-surface-200 pb-2 border-b border-surface-100 dark:border-surface-800">計算規則</h2>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1.5">預設成本計算法</label>
          <div class="flex items-center gap-1 bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg p-1 w-fit">
            <button v-for="o in costMethodOptions" :key="o.value" @click="form.cost_method = o.value"
              class="px-3 py-1.5 text-xs font-bold rounded-md transition-colors"
              :class="form.cost_method === o.value ? 'bg-primary text-primary-contrast' : 'text-surface-500'">{{ o.label }}</button>
          </div>
          <p class="text-xs text-surface-400 mt-1.5">持股／已實現損益頁可個別覆寫檢視，但此為預設值。</p>
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1.5">現金股利處理方式</label>
          <div class="flex items-center gap-1 bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg p-1 w-fit">
            <button v-for="o in dividendModeOptions" :key="o.value" @click="form.dividend_mode = o.value"
              class="px-3 py-1.5 text-xs font-bold rounded-md transition-colors"
              :class="form.dividend_mode === o.value ? 'bg-primary text-primary-contrast' : 'text-surface-500'">{{ o.label }}</button>
          </div>
        </div>
        <div class="flex items-center justify-between gap-3">
          <label class="text-sm text-surface-600 dark:text-surface-300">觀察名單到價提醒門檻（±%）</label>
          <InputNumber v-model="form.near_target_pct" :minFractionDigits="1" :maxFractionDigits="2" class="w-36 min-w-0 shrink-0" inputClass="text-right w-full min-w-0" />
        </div>
      </div>

      <div class="p-5 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex flex-col justify-between">
        <div>
          <h2 class="text-sm font-bold text-surface-700 dark:text-surface-200 pb-2 border-b border-surface-100 dark:border-surface-800 mb-3">儲存變更</h2>
          <p class="text-sm text-surface-500">調整完成後點擊「儲存設定」套用；成本法／股利處理法會立即影響持股與已實現損益頁的計算結果。</p>
        </div>
        <Button label="儲存設定" icon="pi pi-check" class="mt-4 w-fit" :loading="saving" @click="save" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { useToast } from 'primevue/usetoast';
import { portfolioApi } from '@/service/portfolioApi';

const toast = useToast();
const costMethodOptions = [{ value: 'fifo', label: '先進先出 FIFO' }, { value: 'average', label: '加權平均法' }];
const dividendModeOptions = [{ value: 'income', label: '計入已實現收益' }, { value: 'reduce_cost', label: '沖抵持股成本' }];

const loading = ref(true);
const saving = ref(false);
const form = reactive({
  tw_fee_rate: 0.001425, tw_fee_discount: 0.6, tw_fee_min: 20, tw_tax_rate: 0.003, tw_tax_rate_etf: 0.001,
  us_fee_rate: 0, us_sec_fee_rate: 0.0000278, fx_rate: 32.5, cost_method: 'fifo', dividend_mode: 'income', near_target_pct: 3
});

async function load() {
  loading.value = true;
  try {
    const res = await portfolioApi.getSettings();
    Object.assign(form, res.data);
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: err?.response?.data?.detail || err.message, life: 4000 });
  } finally {
    loading.value = false;
  }
}
onMounted(load);

async function save() {
  saving.value = true;
  try {
    const res = await portfolioApi.updateSettings({ ...form });
    Object.assign(form, res.data);
    toast.add({ severity: 'success', summary: '設定已更新', life: 2500 });
  } catch (err) {
    toast.add({ severity: 'error', summary: '儲存失敗', detail: err?.response?.data?.detail || err.message, life: 5000 });
  } finally {
    saving.value = false;
  }
}
</script>
