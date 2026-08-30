<template>
  <Dialog v-model:visible="visible" header="批次匯入追蹤與觀察名單" modal style="width: 56rem" :breakpoints="{ '1200px': '92vw' }">
    <div class="space-y-4">
      <div class="p-3 rounded-lg bg-surface-50 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 text-xs text-surface-500 leading-relaxed">
        貼上表格文字（支援 Excel／Google Sheets 複製的 Tab 分隔、Markdown 表格、逗號分隔），固定欄位順序為
        <b class="text-surface-700 dark:text-surface-300">股號、名稱、主要分類、主要業務與產業角色、核心題材與受惠邏輯</b>。
        解析後「主要分類」會設成標籤，「主要業務與產業角色」＋「核心題材與受惠邏輯」以逗號合併成追蹤原因，送出前可逐列調整或排除。
      </div>

      <template v-if="!parsed.length">
        <div class="flex items-center gap-3">
          <label class="text-xs font-bold text-surface-500 shrink-0">市場</label>
          <Select v-model="market" :options="marketOptions" optionLabel="label" optionValue="value" class="w-40" />
        </div>
        <Textarea v-model="pasteText" rows="12" class="w-full font-mono text-xs" placeholder="貼上表格內容...&#10;例如：3017&#9;奇鋐&#9;散熱&#9;散熱模組／液冷解決方案龍頭&#9;受惠次世代 AI 伺服器全面導入液冷散熱…" />
      </template>

      <template v-else>
        <div class="flex items-center justify-between">
          <div class="text-sm text-surface-500">共解析出 <b class="text-surface-700 dark:text-surface-300">{{ parsed.length }}</b> 檔，取消勾選可排除該列</div>
          <Button label="重新貼上" text size="small" icon="pi pi-replay" @click="resetParse" />
        </div>
        <div class="border border-surface-200 dark:border-surface-700 rounded-xl overflow-hidden">
          <div class="overflow-x-auto overflow-y-auto" style="max-height: 26rem">
            <table class="w-full text-left border-collapse text-xs">
              <thead class="sticky top-0 bg-surface-50 dark:bg-surface-800 text-surface-400 uppercase tracking-wide z-10">
                <tr>
                  <th class="p-2 w-8"></th>
                  <th class="p-2 w-24">股號</th>
                  <th class="p-2 w-28">名稱</th>
                  <th class="p-2 w-40">標籤（主要分類）</th>
                  <th class="p-2">追蹤原因</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in parsed" :key="row._id" class="border-t border-surface-100 dark:border-surface-800" :class="!row.included ? 'opacity-40' : ''">
                  <td class="p-2 align-top pt-3"><Checkbox v-model="row.included" binary /></td>
                  <td class="p-2 align-top"><InputText v-model="row.symbol" class="w-full text-xs" /></td>
                  <td class="p-2 align-top"><InputText v-model="row.name" class="w-full text-xs" /></td>
                  <td class="p-2 align-top"><InputText v-model="row.tag" class="w-full text-xs" /></td>
                  <td class="p-2 align-top"><Textarea v-model="row.note" rows="2" class="w-full text-xs" /></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </div>
    <template #footer>
      <Button label="取消" text @click="close" />
      <Button v-if="!parsed.length" label="解析" icon="pi pi-search" :disabled="!pasteText.trim()" @click="doParse" />
      <Button v-else :label="`確認匯入（${includedCount} 檔）`" icon="pi pi-check" :loading="importing" :disabled="!includedCount" @click="doImport" />
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useToast } from 'primevue/usetoast';
import { portfolioApi } from '@/service/portfolioApi';
import { useWatchlistTags } from '@/composables/useWatchlistTags';
import { useTrackingList } from '@/composables/useTrackingList';
import { parsePastedStockTable } from '@/utils/parsePastedStockTable';

const props = defineProps({ visible: Boolean });
const emit = defineEmits(['update:visible', 'imported']);

const visible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v)
});

const { refresh: refreshTags } = useWatchlistTags();
const { refresh: refreshTrackingList } = useTrackingList();
const toast = useToast();

const marketOptions = [
  { label: '台股 TWSE', value: 'tw' },
  { label: '美股 NASDAQ', value: 'us' }
];
const market = ref('tw');
const pasteText = ref('');
const parsed = ref([]);
const importing = ref(false);
let seq = 0;

const includedCount = computed(() => parsed.value.filter((r) => r.included).length);

function resetParse() {
  parsed.value = [];
}

function doParse() {
  const rows = parsePastedStockTable(pasteText.value);
  if (!rows.length) {
    toast.add({ severity: 'warn', summary: '沒有解析出任何列，請確認貼上內容含股票代碼欄', life: 3500 });
    return;
  }
  parsed.value = rows.map((r) => ({
    _id: ++seq,
    included: true,
    symbol: r.symbol,
    name: r.name,
    tag: r.category,
    note: [r.business, r.theme].filter(Boolean).join(',')
  }));
}

function close() {
  visible.value = false;
}

// 關閉（含匯入完成後自動關閉）就重置，避免下次打開殘留上一次的貼上內容/解析結果
watch(visible, (v) => {
  if (!v) {
    pasteText.value = '';
    parsed.value = [];
  }
});

async function doImport() {
  const items = parsed.value
    .filter((r) => r.included && r.symbol.trim())
    .map((r) => ({
      symbol: r.symbol.trim(),
      name: r.name.trim() || undefined,
      tags: r.tag.trim() ? [r.tag.trim()] : [],
      note: r.note.trim() || undefined
    }));
  if (!items.length) return;

  importing.value = true;
  try {
    const res = await portfolioApi.addWatchlistBatch({ market: market.value, items });
    const { failed } = res.data;
    toast.add({ severity: failed?.length ? 'warn' : 'success', summary: res.message, life: 4000 });
    if (failed?.length) {
      toast.add({
        severity: 'error',
        summary: '部分匯入失敗',
        detail: failed.map((f) => `${f.symbol}：${f.error}`).join('；'),
        life: 6000
      });
    }
    if (res.fetch_triggered?.length) {
      toast.add({ severity: 'info', summary: '背景抓取中', detail: `${res.fetch_triggered.join(', ')} 尚無歷史資料，已自動啟動背景抓取`, life: 4000 });
    }
    await Promise.all([refreshTags(), refreshTrackingList(market.value)]);
    emit('imported');
    visible.value = false;
  } catch (err) {
    toast.add({ severity: 'error', summary: '匯入失敗', detail: err?.response?.data?.detail || err.message, life: 5000 });
  } finally {
    importing.value = false;
  }
}
</script>
