<template>
  <Dialog v-model:visible="state.visible" :header="state.editId ? '編輯追蹤設定' : '加入追蹤與觀察名單'" modal style="width: 26rem">
    <div class="space-y-4">
      <div class="flex items-center gap-2 p-3 rounded-lg bg-surface-50 dark:bg-surface-800 border border-surface-200 dark:border-surface-700">
        <span class="px-2 py-0.5 text-xs font-bold rounded bg-surface-100 dark:bg-surface-900 text-surface-600 dark:text-surface-300">{{ marketMeta[state.market]?.label || state.market }}</span>
        <span class="font-black text-surface-900 dark:text-surface-0">{{ state.symbol }}</span>
        <span class="text-surface-500 truncate">{{ state.name }}</span>
      </div>
      <div>
        <label class="block text-xs font-bold text-surface-500 mb-1">目標買進價（選填）</label>
        <InputNumber v-model="targetPrice" mode="decimal" :minFractionDigits="0" :maxFractionDigits="2" class="w-full" placeholder="留空＝純追蹤，不計算到價提醒" />
        <p v-if="state.price != null" class="text-xs text-surface-400 mt-1">目前股價 {{ state.price.toFixed(2) }}，可作為目標價參考。</p>
      </div>
      <div>
        <label class="block text-xs font-bold text-surface-500 mb-1">追蹤原因（選填）</label>
        <Textarea v-model="note" rows="2" class="w-full" placeholder="例如：等季報公布、法人連買、等回檔至月線" />
      </div>
      <div>
        <label class="block text-xs font-bold text-surface-500 mb-1">標籤（選填，可輸入新標籤自動建立）</label>
        <AutoComplete v-model="tagInputs" :suggestions="tagSuggestions" multiple display="chip" dropdown @complete="onTagComplete" class="w-full" inputClass="text-sm" placeholder="輸入或選擇標籤" />
      </div>
    </div>
    <template #footer>
      <Button label="取消" text @click="state.visible = false" />
      <Button :label="state.editId ? '儲存變更' : '加入清單'" icon="pi pi-check" :loading="saving" @click="save" />
    </template>
  </Dialog>
</template>

<script setup>
import { ref, watch } from 'vue';
import { useToast } from 'primevue/usetoast';
import { portfolioApi } from '@/service/portfolioApi';
import { useWatchlistQuickAdd } from '@/composables/useWatchlistQuickAdd';
import { useWatchlistTags } from '@/composables/useWatchlistTags';
import { useTrackingList } from '@/composables/useTrackingList';
import { marketMeta } from '@/composables/usePortfolioFormat';

const { state } = useWatchlistQuickAdd();
const { tags: knownTags, refresh: refreshTags } = useWatchlistTags();
const { refresh: refreshTrackingList } = useTrackingList();
const toast = useToast();

const targetPrice = ref(null);
const note = ref('');
const tagInputs = ref([]); // AutoComplete v-model：標籤名稱字串陣列
const tagSuggestions = ref([]);
const saving = ref(false);

// 每次開啟都重新帶入目前的值（新增＝現價/空白；編輯＝該項目既有的目標價/原因/標籤），
// 避免殘留上一次操作的殘值
watch(
  () => state.visible,
  async (visible) => {
    if (visible) {
      await refreshTags();
      targetPrice.value = state.price;
      note.value = state.note || '';
      tagInputs.value = [...(state.tags || [])];
    }
  }
);

function onTagComplete(event) {
  const q = (event.query || '').trim().toLowerCase();
  tagSuggestions.value = knownTags.value
    .map((t) => t.name)
    .filter((name) => !tagInputs.value.includes(name) && (!q || name.toLowerCase().includes(q)));
}

async function save() {
  saving.value = true;
  try {
    let res;
    if (state.editId) {
      res = await portfolioApi.updateWatchlist(state.editId, {
        target_price: targetPrice.value || null,
        note: note.value || null,
        tags: tagInputs.value
      });
    } else {
      res = await portfolioApi.addWatchlist({
        market: state.market,
        symbol: state.symbol,
        name: state.name,
        target_price: targetPrice.value || null,
        note: note.value || null,
        tags: tagInputs.value
      });
    }
    toast.add({ severity: 'success', summary: res.message || '已儲存', life: 2500 });
    if (res.fetch_triggered?.length) {
      toast.add({ severity: 'info', summary: '背景抓取中', detail: `${res.fetch_triggered.join(', ')} 尚無歷史資料，已自動啟動背景抓取`, life: 4000 });
    }
    state.visible = false;
    await refreshTrackingList(state.market);
  } catch (err) {
    toast.add({ severity: 'error', summary: '儲存失敗', detail: err?.response?.data?.detail || err.message, life: 5000 });
  } finally {
    saving.value = false;
  }
}
</script>
