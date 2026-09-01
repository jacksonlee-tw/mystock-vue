<template>
  <Dialog v-model:visible="visible" header="待核對清單（人工核對介面）" modal style="width: 46rem" :breakpoints="{ '900px': '92vw' }">
    <div class="space-y-3">
      <div class="flex items-center justify-between gap-2">
        <p class="text-xs text-surface-500">
          {{ chainName || chainId }}・LLM 萃取的邊一律先標記為
          <code class="px-1 py-0.5 rounded bg-surface-100 dark:bg-surface-800">未核對</code>（ADR-IC-14）。
          「確認核可」把該邊標記為已核可；「判定錯誤」則軟刪除下架（ADR-IC-15，資料庫仍保留稽核軌跡，不會物理刪除）。
        </p>
        <Button icon="pi pi-refresh" text size="small" :loading="loading" @click="load" />
      </div>

      <div v-if="loading && !items.length" class="flex items-center gap-2 text-surface-500 text-sm py-10 justify-center">
        <i class="pi pi-spin pi-spinner"></i> 載入中...
      </div>

      <div v-else-if="error" class="p-4 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-300 text-sm">
        {{ error }}
      </div>

      <div v-else-if="!items.length" class="p-10 text-center text-surface-400">
        <i class="pi pi-check-circle text-2xl mb-2"></i>
        <p class="text-sm">目前沒有待核對的邊</p>
      </div>

      <!-- 單欄清單（非卡片 Grid），不涉及 CLAUDE.md 硬規則 2 的同列等高問題；
           清單本身在 Dialog 內捲動，動作只更新本地陣列，不整批重新 fetch -->
      <div v-else class="border border-surface-200 dark:border-surface-700 rounded-xl divide-y divide-surface-100 dark:divide-surface-800 max-h-[28rem] overflow-y-auto">
        <div v-for="edge in items" :key="edgeKey(edge)" class="p-3">
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <div class="text-sm">
              <span class="font-bold num text-surface-800 dark:text-surface-100">{{ edge.upstream_symbol }}</span>
              <span class="text-surface-500">{{ edge.upstream_name }}</span>
              <i class="pi pi-arrow-right text-[10px] text-surface-400 mx-1.5"></i>
              <span class="font-bold num text-surface-800 dark:text-surface-100">{{ edge.downstream_symbol }}</span>
              <span class="text-surface-500">{{ edge.downstream_name }}</span>
            </div>
            <div class="flex items-center gap-1.5 flex-wrap">
              <Tag :value="`Tier ${edge.relation_tier}`" severity="secondary" />
              <Tag :value="edge.source" severity="info" />
              <Tag
                v-if="edge.extra_data?.llm_confidence"
                :value="CONFIDENCE_LABEL[edge.extra_data.llm_confidence] || edge.extra_data.llm_confidence"
                :severity="CONFIDENCE_SEVERITY[edge.extra_data.llm_confidence] || 'secondary'"
              />
              <Tag v-if="edge.extra_data?.concept_tag_match" value="概念標籤吻合" severity="success" />
            </div>
          </div>

          <p v-if="edge.component_type" class="text-xs text-surface-500 mt-1.5">供應內容：{{ edge.component_type }}</p>
          <p v-if="edge.extra_data?.llm_evidence" class="text-xs text-surface-500 mt-1 flex items-start gap-1">
            <i class="pi pi-comment text-[10px] mt-0.5 shrink-0"></i>
            <span>{{ edge.extra_data.llm_evidence }}</span>
          </p>
          <a
            v-if="edge.extra_data?.evidence_url"
            :href="edge.extra_data.evidence_url"
            target="_blank"
            rel="noopener noreferrer"
            class="text-xs text-primary hover:underline inline-flex items-center gap-1 mt-1"
          >
            <i class="pi pi-external-link text-[10px]"></i>查看佐證來源
          </a>

          <div class="flex items-center gap-2 mt-2.5">
            <Button
              label="確認核可" icon="pi pi-check" size="small" severity="success" outlined
              :loading="isActing(edge, 'verify')" :disabled="!!acting"
              @click="onVerify(edge)"
            />
            <Button
              label="判定錯誤" icon="pi pi-times" size="small" severity="danger" outlined
              :loading="isActing(edge, 'deactivate')" :disabled="!!acting"
              @click="onDeactivate(edge)"
            />
            <span class="text-[10px] text-surface-400 ml-auto">首次出現 {{ edge.first_seen_date || '—' }}</span>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <Button label="關閉" text @click="close" />
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';
import { industryChainApi } from '@/service/industryChainApi';

const props = defineProps({
  visible: Boolean,
  chainId: { type: String, default: null },
  chainName: { type: String, default: '' }
});
const emit = defineEmits(['update:visible', 'changed']);

const visible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v)
});

const toast = useToast();
const confirm = useConfirm();

const items = ref([]);
const loading = ref(false);
const error = ref(null);
// 目前正在處理中的動作，格式 `${upstream}-${downstream}:verify|deactivate`；非 null 時鎖住
// 整張清單的動作按鈕，避免同一筆（或不同筆）邊被重複送出
const acting = ref(null);
let didChange = false; // 這次開啟期間是否至少成功動作過一次，關閉時才據此通知父層刷新

const CONFIDENCE_LABEL = { high: '信心：高', medium: '信心：中', low: '信心：低' };
const CONFIDENCE_SEVERITY = { high: 'success', medium: 'warn', low: 'danger' };

function edgeKey(edge) {
  return `${edge.upstream_symbol}-${edge.downstream_symbol}`;
}
function isActing(edge, type) {
  return acting.value === `${edgeKey(edge)}:${type}`;
}

async function load() {
  if (!props.chainId) return;
  loading.value = true;
  error.value = null;
  try {
    // 只取待核對清單（verified=false）——本對話框的職責就是 §8 定義的最小可用核對介面，
    // 已核可的邊仍在主頁面的力導向圖與節點清單看得到，不重複列在這裡
    const res = await industryChainApi.listChainEdges(props.chainId, false);
    items.value = res.data.items;
  } catch (err) {
    error.value = err?.response?.data?.error?.message || err.message;
  } finally {
    loading.value = false;
  }
}

// 開啟時重新讀一次待核對清單並重置「是否已變更」旗標；關閉時若曾經動作過，通知父層刷新
// 圖譜（is_verified 改變會影響力導向圖邊的樣式與「已核可比例」KPI 卡片）——刻意不在每次
// 單筆動作後就刷新父層，那會讓底下主頁面在核對過程中一直重繪，體感更卡
watch(() => props.visible, (v, prevV) => {
  if (v) {
    didChange = false;
    load();
  } else if (prevV && didChange) {
    emit('changed');
  }
});

async function onVerify(edge) {
  acting.value = `${edgeKey(edge)}:verify`;
  try {
    await industryChainApi.verifyChainEdge(props.chainId, {
      upstreamSymbol: edge.upstream_symbol, downstreamSymbol: edge.downstream_symbol
    });
    // 區域性更新：從本地清單移除該筆，不整批重新 fetch
    items.value = items.value.filter((e) => edgeKey(e) !== edgeKey(edge));
    didChange = true;
    toast.add({ severity: 'success', summary: `已核可 ${edge.upstream_symbol} → ${edge.downstream_symbol}`, life: 3000 });
  } catch (err) {
    toast.add({ severity: 'error', summary: '核可失敗', detail: err?.response?.data?.error?.message || err.message, life: 5000 });
  } finally {
    acting.value = null;
  }
}

function onDeactivate(edge) {
  confirm.require({
    header: '判定為錯誤邊',
    message: `確定要將「${edge.upstream_symbol} → ${edge.downstream_symbol}」判定為錯誤並下架？此動作為軟刪除（is_active=false），資料庫仍保留稽核軌跡，需要時可再改判恢復，不會物理刪除。`,
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: '判定錯誤並下架',
    rejectLabel: '取消',
    acceptProps: { severity: 'danger' },
    accept: () => doDeactivate(edge)
  });
}

async function doDeactivate(edge) {
  acting.value = `${edgeKey(edge)}:deactivate`;
  try {
    await industryChainApi.deactivateChainEdge(props.chainId, {
      upstreamSymbol: edge.upstream_symbol, downstreamSymbol: edge.downstream_symbol
    });
    items.value = items.value.filter((e) => edgeKey(e) !== edgeKey(edge));
    didChange = true;
    toast.add({ severity: 'success', summary: `已下架 ${edge.upstream_symbol} → ${edge.downstream_symbol}`, life: 3000 });
  } catch (err) {
    toast.add({ severity: 'error', summary: '下架失敗', detail: err?.response?.data?.error?.message || err.message, life: 5000 });
  } finally {
    acting.value = null;
  }
}

function close() {
  visible.value = false;
}
</script>
