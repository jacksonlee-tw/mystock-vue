<template>
  <Dialog v-model:visible="state.visible" header="加入觀察名單" modal style="width: 24rem">
    <div class="space-y-4">
      <div class="flex items-center gap-2 p-3 rounded-lg bg-surface-50 dark:bg-surface-800 border border-surface-200 dark:border-surface-700">
        <span class="px-2 py-0.5 text-xs font-bold rounded bg-surface-100 dark:bg-surface-900 text-surface-600 dark:text-surface-300">{{ marketMeta[state.market]?.label || state.market }}</span>
        <span class="font-black text-surface-900 dark:text-surface-0">{{ state.symbol }}</span>
        <span class="text-surface-500 truncate">{{ state.name }}</span>
      </div>
      <div>
        <label class="block text-xs font-bold text-surface-500 mb-1">目標買進價</label>
        <InputNumber v-model="targetPrice" mode="decimal" :minFractionDigits="0" :maxFractionDigits="2" class="w-full" />
        <p v-if="state.price != null" class="text-xs text-surface-400 mt-1">目前股價 {{ state.price.toFixed(2) }}，預設帶入現價，可自行調整。</p>
      </div>
      <div>
        <label class="block text-xs font-bold text-surface-500 mb-1">備註（選填）</label>
        <InputText v-model="note" class="w-full" placeholder="例如：等季報公布、等回檔至月線" />
      </div>
    </div>
    <template #footer>
      <Button label="取消" text @click="state.visible = false" />
      <Button label="加入觀察" icon="pi pi-eye" :loading="saving" @click="save" />
    </template>
  </Dialog>
</template>

<script setup>
import { ref, watch } from 'vue';
import { useToast } from 'primevue/usetoast';
import { portfolioApi } from '@/service/portfolioApi';
import { useWatchlistQuickAdd } from '@/composables/useWatchlistQuickAdd';
import { marketMeta } from '@/composables/usePortfolioFormat';

const { state } = useWatchlistQuickAdd();
const toast = useToast();

const targetPrice = ref(null);
const note = ref('');
const saving = ref(false);

// 每次開啟都重新帶入現價當預設目標價，避免殘留上一檔股票填過的值
watch(
  () => state.visible,
  (visible) => {
    if (visible) {
      targetPrice.value = state.price;
      note.value = '';
    }
  }
);

async function save() {
  if (!targetPrice.value || targetPrice.value <= 0) {
    toast.add({ severity: 'error', summary: '請填寫目標買進價', life: 3000 });
    return;
  }
  saving.value = true;
  try {
    const res = await portfolioApi.addWatchlist({
      market: state.market,
      symbol: state.symbol,
      name: state.name,
      target_price: targetPrice.value,
      note: note.value || null
    });
    toast.add({ severity: 'success', summary: res.message || '已加入觀察名單', life: 2500 });
    state.visible = false;
  } catch (err) {
    toast.add({ severity: 'error', summary: '加入失敗', detail: err?.response?.data?.detail || err.message, life: 5000 });
  } finally {
    saving.value = false;
  }
}
</script>
