<template>
  <Dialog
    :visible="visible" @update:visible="$emit('update:visible', $event)" modal maximizable
    header="轉為投資筆記" :style="{ width: 'min(52rem, 94vw)' }" :closable="!saving"
    @maximize="isMaximized = true" @unmaximize="isMaximized = false"
  >
    <!-- FR-21（docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §4.5、§8，v2.6 新增）：
         整鏈快照／單一關聯／節點路徑三種匯出範圍共用同一個轉換 Modal，欄位比照既有
         InvestmentNoteEditor.vue（日期／狀態／主旨／內容兩分頁／標籤／關聯標的），
         差異只在開啟前由呼叫端（IndustryChainView.vue）帶入的 initial 內容不同。
         本對話框永遠是「新增」語意，直接呼叫既有 investmentNoteApi.createNote()，
         不新增任何後端端點、不擴充 investment_note 的 schema（ADR-IC-20）。-->
    <div class="space-y-4" :class="isMaximized ? 'h-full flex flex-col' : ''">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 shrink-0">
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">日期</label>
          <DatePicker v-model="form.note_date" dateFormat="yy-mm-dd" showIcon class="w-full" />
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">狀態</label>
          <Select v-model="form.status" :options="statusOptions" optionLabel="label" optionValue="value" class="w-full" />
        </div>
      </div>

      <div class="shrink-0">
        <label class="flex items-center justify-between text-xs font-bold text-surface-500 mb-1">
          <span>主旨</span><span class="font-normal text-surface-300">{{ form.subject.length }}/200</span>
        </label>
        <InputText v-model="form.subject" maxlength="200" class="w-full" placeholder="這筆筆記想留下什麼？" />
      </div>

      <div :class="isMaximized ? 'flex-1 min-h-0 flex flex-col' : ''">
        <div class="flex items-center justify-between gap-3 mb-1.5 shrink-0">
          <label class="text-xs font-bold text-surface-500">內容</label>
          <span class="text-[11px] text-surface-400"><i class="pi pi-file mr-1"></i>Markdown (.md) ・ 支援 Mermaid 圖表</span>
        </div>
        <div class="markdown-editor rounded-lg border border-surface-200 dark:border-surface-700 overflow-hidden" :class="isMaximized ? 'flex-1 min-h-0 flex flex-col' : ''">
          <div class="flex items-center gap-1 p-1.5 border-b border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800">
            <button
              type="button"
              class="markdown-tab"
              :class="editorMode === 'source' ? 'markdown-tab-active' : ''"
              :aria-pressed="editorMode === 'source'"
              @click="editorMode = 'source'"
            >
              <i class="pi pi-code"></i>原始 Markdown
            </button>
            <button
              type="button"
              class="markdown-tab"
              :class="editorMode === 'preview' ? 'markdown-tab-active' : ''"
              :aria-pressed="editorMode === 'preview'"
              @click="editorMode = 'preview'"
            >
              <i class="pi pi-eye"></i>渲染檢視
            </button>
          </div>

          <Textarea
            v-if="editorMode === 'source'"
            v-model="form.content"
            :rows="isMaximized ? 24 : 12"
            class="markdown-source w-full"
            :class="isMaximized ? 'flex-1 editor-maximized-textarea' : ''"
            spellcheck="false"
            aria-label="原始 Markdown 內容"
          />
          <div v-else class="markdown-preview" :class="isMaximized ? 'flex-1 editor-maximized-preview' : ''" aria-live="polite">
            <MarkdownPreview v-if="form.content.trim()" class="markdown-content" :source="form.content" />
            <div v-else class="h-full min-h-64 grid place-items-center text-center text-surface-400">
              <div><i class="pi pi-file-edit text-2xl"></i><p class="mt-2 text-sm">尚無內容。</p></div>
            </div>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 shrink-0">
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">
            標籤<span class="font-normal text-surface-300 ml-1">選填，可輸入新標籤自動建立</span>
          </label>
          <AutoComplete v-model="form.tags" :suggestions="tagSuggestions" multiple display="chip" dropdown @complete="onTagComplete" class="w-full" inputClass="text-sm" placeholder="輸入或選擇標籤" />
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">
            關聯標的<span class="font-normal text-surface-300 ml-1">單一錨點標的，其餘標的已寫在內文（ADR-IC-20）</span>
          </label>
          <div class="flex items-center gap-1.5">
            <Select v-model="form.market" :options="marketOptions" optionLabel="label" optionValue="value" showClear placeholder="市場" class="w-32 shrink-0" />
            <InputText v-model="form.symbol" placeholder="例如 2330" class="flex-1 min-w-0" />
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="w-full flex items-center justify-end gap-2">
        <Button label="取消" text :disabled="saving" @click="$emit('update:visible', false)" />
        <Button label="儲存為投資筆記" icon="pi pi-check" :loading="saving" @click="save" />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { reactive, watch, ref } from 'vue';
import { useToast } from 'primevue/usetoast';
import { investmentNoteApi } from '@/service/investmentNoteApi';
import { toIsoDate, todayDate } from '@/composables/usePortfolioFormat';
import MarkdownPreview from '@/components/portfolio/MarkdownPreview.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  // { subject, market, symbol, tagNames, content }，由 IndustryChainView.vue 依三種匯出範圍組出
  // （見 utils/industryChainExport.js）。開啟對話框當下若為 null，表單維持空白（防守用，正常
  // 流程下呼叫端一定會在打開對話框前算好內容）。
  initial: { type: Object, default: null }
});
const emit = defineEmits(['update:visible', 'saved']);

const toast = useToast();
const marketOptions = [
  { label: '台股', value: 'tw' },
  { label: '美股', value: 'us' }
];
const statusOptions = [
  { label: '已發布', value: 'published' },
  { label: '草稿', value: 'draft' },
  { label: '已封存', value: 'archived' }
];

function blankForm() {
  return { note_date: todayDate(), status: 'published', subject: '', content: '', tags: [], market: null, symbol: '' };
}
const form = reactive(blankForm());
const saving = ref(false);
const tagSuggestions = ref([]);
const tagOptions = ref([]);
const editorMode = ref('source');
const isMaximized = ref(false);

// 每次開啟都用 initial 重新灌值，避免殘留上一次匯出的內容
watch(
  () => [props.visible, props.initial],
  ([visible, initial]) => {
    if (!visible) return;
    editorMode.value = 'source';
    isMaximized.value = false;
    Object.assign(form, blankForm());
    if (initial) {
      Object.assign(form, {
        subject: initial.subject || '',
        content: initial.content || '',
        tags: initial.tagNames || [],
        market: initial.market || null,
        symbol: initial.symbol || ''
      });
    }
    investmentNoteApi.getTags().then((res) => { tagOptions.value = res.data || []; }).catch(() => {});
  },
  { immediate: true }
);

function onTagComplete(event) {
  const q = (event.query || '').trim();
  const qLower = q.toLowerCase();
  const matches = tagOptions.value.map((t) => t.name).filter((name) => !form.tags.includes(name) && (!qLower || name.toLowerCase().includes(qLower)));
  // 同既有 InvestmentNoteEditor.vue 慣例：找不到完全相符的既有標籤時，把使用者輸入本身當作
  // 「新增標籤」選項附加在候選清單最後，讓使用者仍可從下拉選單選取／建立全新標籤
  if (q && !form.tags.includes(q) && !matches.some((name) => name.toLowerCase() === qLower)) {
    matches.push(q);
  }
  tagSuggestions.value = matches;
}

async function save() {
  if (!form.subject.trim()) {
    toast.add({ severity: 'error', summary: '請填寫主旨', life: 3000 });
    return;
  }
  if (!form.content.trim()) {
    toast.add({ severity: 'error', summary: '請填寫內容', life: 3000 });
    return;
  }
  if (form.symbol.trim() && !form.market) {
    toast.add({ severity: 'error', summary: '請先選擇市場，才能填寫股票代碼', life: 3500 });
    return;
  }

  saving.value = true;
  try {
    const payload = {
      subject: form.subject.trim(),
      content: form.content.trim(),
      status: form.status,
      note_date: toIsoDate(form.note_date),
      tag_names: form.tags,
      market: form.market || null,
      symbol: form.symbol.trim() ? form.symbol.trim().toUpperCase() : null
    };
    const res = await investmentNoteApi.createNote(payload);
    toast.add({ severity: 'success', summary: res.message || '已建立投資筆記', life: 2500 });
    emit('saved', res.data);
    emit('update:visible', false);
  } catch (err) {
    toast.add({ severity: 'error', summary: '儲存失敗', detail: err?.response?.data?.detail || err.message, life: 5000 });
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.markdown-tab {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.45rem 0.75rem;
  border-radius: 0.4rem;
  color: var(--p-text-muted-color);
  font-size: 0.8rem;
  font-weight: 700;
  transition: background-color 150ms, color 150ms;
}

.markdown-tab:hover {
  background: var(--p-surface-100);
  color: var(--p-text-color);
}

.markdown-tab-active {
  background: var(--p-surface-0);
  color: var(--p-primary-color);
  box-shadow: 0 1px 3px rgb(15 23 42 / 0.12);
}

.markdown-source {
  display: block;
  min-height: 12rem;
  border: 0;
  border-radius: 0;
  resize: vertical;
  font-family: ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace;
  line-height: 1.65;
}

.markdown-source:focus {
  box-shadow: none;
}

.markdown-preview {
  min-height: 12rem;
  max-height: 24rem;
  overflow: auto;
  padding: 1.25rem 1.5rem;
  background: var(--p-surface-0);
}

/* var(--p-surface-*) 是固定色階、不隨主題切換，深色模式需另外覆寫，理由與寫法同既有
   InvestmentNoteEditor.vue：不能寫成 :global(.app-dark) ...，scoped 編譯會把 .app-dark
   整段吃掉，.app-dark 本來就掛在 <html> 上、在本元件範圍外，直接寫後代選擇器即可。 */
.app-dark .markdown-preview {
  background: var(--p-surface-900);
}

.editor-maximized-textarea {
  min-height: 0;
  resize: none;
}

.editor-maximized-preview {
  max-height: none;
}

.markdown-content {
  color: var(--p-text-color);
  font-size: 0.9rem;
  line-height: 1.75;
  overflow-wrap: anywhere;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3) {
  margin: 1.25em 0 0.55em;
  color: var(--p-text-color);
  font-weight: 800;
  line-height: 1.3;
}

.markdown-content :deep(h1:first-child),
.markdown-content :deep(h2:first-child),
.markdown-content :deep(h3:first-child) {
  margin-top: 0;
}

.markdown-content :deep(h1) { font-size: 1.5rem; }
.markdown-content :deep(h2) { font-size: 1.25rem; }
.markdown-content :deep(h3) { font-size: 1.05rem; }
.markdown-content :deep(p) { margin: 0.7em 0; }
.markdown-content :deep(ul),
.markdown-content :deep(ol) { margin: 0.7em 0; padding-left: 1.5rem; }
.markdown-content :deep(ul) { list-style: disc; }
.markdown-content :deep(ol) { list-style: decimal; }
.markdown-content :deep(table) { width: 100%; margin: 1rem 0; border-collapse: collapse; }
.markdown-content :deep(th),
.markdown-content :deep(td) { padding: 0.55rem 0.7rem; border: 1px solid var(--p-content-border-color); text-align: left; }
.markdown-content :deep(th) { background: var(--p-surface-50); font-weight: 700; }

.app-dark .markdown-content :deep(th) { background: var(--p-surface-800); }
</style>
