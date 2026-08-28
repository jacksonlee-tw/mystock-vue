<template>
  <Dialog :visible="visible" @update:visible="$emit('update:visible', $event)" modal :header="isEditing ? '編輯投資筆記' : '新增投資筆記'" :style="{ width: 'min(52rem, 94vw)' }" :closable="!saving">
    <div class="space-y-4">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">日期</label>
          <DatePicker v-model="form.note_date" dateFormat="yy-mm-dd" showIcon class="w-full" />
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">狀態</label>
          <Select v-model="form.status" :options="statusOptions" optionLabel="label" optionValue="value" class="w-full" />
        </div>
      </div>

      <div>
        <label class="flex items-center justify-between text-xs font-bold text-surface-500 mb-1">
          <span>主旨</span><span class="font-normal text-surface-300">{{ form.subject.length }}/200</span>
        </label>
        <InputText v-model="form.subject" maxlength="200" class="w-full" placeholder="這筆筆記想留下什麼？" />
      </div>

      <div>
        <div class="flex items-center justify-between gap-3 mb-1.5">
          <label class="text-xs font-bold text-surface-500">內容</label>
          <span class="text-[11px] text-surface-400"><i class="pi pi-file mr-1"></i>Markdown (.md)</span>
        </div>
        <div class="markdown-editor rounded-lg border border-surface-200 dark:border-surface-700 overflow-hidden">
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
            rows="8"
            class="markdown-source w-full"
            spellcheck="false"
            aria-label="原始 Markdown 內容"
            placeholder="# 今日觀察&#10;&#10;記下你的觀察、判斷依據與下一步..."
          />
          <div v-else class="markdown-preview" aria-live="polite">
            <div v-if="form.content.trim()" class="markdown-content" v-html="renderedContent"></div>
            <div v-else class="h-full min-h-64 grid place-items-center text-center text-surface-400">
              <div><i class="pi pi-file-edit text-2xl"></i><p class="mt-2 text-sm">尚無內容，請回到「原始 Markdown」開始輸入。</p></div>
            </div>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">
            標籤<span class="font-normal text-surface-300 ml-1">選填，可輸入新標籤自動建立</span>
          </label>
          <AutoComplete v-model="form.tags" :suggestions="tagSuggestions" multiple display="chip" dropdown @complete="onTagComplete" class="w-full" inputClass="text-sm" placeholder="輸入或選擇標籤" />
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">關聯標的<span class="font-normal text-surface-300 ml-1">選填</span></label>
          <div class="flex gap-1.5">
            <Select v-model="form.market" :options="marketOptions" optionLabel="label" optionValue="value" showClear placeholder="市場" class="w-28" />
            <InputText v-model="form.symbol" placeholder="例如 2330" class="flex-1 min-w-0" />
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="w-full flex items-center justify-between">
        <span class="text-xs text-surface-400 flex items-center gap-1">
          <i class="pi pi-hashtag"></i>
          {{ isEditing ? `當日流水號 #${note.sequence_no}` : '儲存後自動取得當日流水號' }}
        </span>
        <div class="flex gap-2">
          <Button label="取消" text :disabled="saving" @click="$emit('update:visible', false)" />
          <Button :label="isEditing ? '儲存變更' : '儲存筆記'" icon="pi pi-check" :loading="saving" @click="save" />
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { reactive, computed, watch, ref } from 'vue';
import { useToast } from 'primevue/usetoast';
import MarkdownIt from 'markdown-it';
import { investmentNoteApi } from '@/service/investmentNoteApi';
import { toIsoDate, fromIsoDate, todayDate } from '@/composables/usePortfolioFormat';

const props = defineProps({
  visible: { type: Boolean, default: false },
  note: { type: Object, default: null }, // null = 新增；非 null = 編輯（需含完整內容，來自 getNote()）
  tagOptions: { type: Array, default: () => [] }
});
const emit = defineEmits(['update:visible', 'saved']);

const toast = useToast();
const isEditing = computed(() => !!props.note);
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
const editorMode = ref('source');
const markdown = new MarkdownIt({ html: false, linkify: true, breaks: true });
const renderedContent = computed(() => markdown.render(form.content || ''));

// 每次開啟（新增或切換編輯目標）都重新灌值，避免殘留上一次的表單內容
watch(
  () => [props.visible, props.note],
  ([visible, note]) => {
    if (!visible) return;
    editorMode.value = 'source';
    if (note) {
      Object.assign(form, {
        note_date: fromIsoDate(note.note_date), status: note.status, subject: note.subject, content: note.content,
        tags: (note.tags || []).map((t) => t.name), market: note.market || null, symbol: note.symbol || ''
      });
    } else {
      Object.assign(form, blankForm());
    }
  },
  { immediate: true }
);

function onTagComplete(event) {
  const q = (event.query || '').trim();
  const qLower = q.toLowerCase();
  const matches = props.tagOptions.map((t) => t.name).filter((name) => !form.tags.includes(name) && (!qLower || name.toLowerCase().includes(qLower)));
  // PrimeVue AutoComplete 沒有比對到任何 suggestion 時，Enter 不會把純文字提交成 chip（下拉選單顯示
  // 「No results found」）。找不到完全相符的既有標籤時，把使用者輸入本身當作「新增標籤」選項附加在
  // 候選清單最後，讓使用者仍可從下拉選單選取／建立全新標籤（設計文件：標籤可輸入新標籤自動建立）。
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
  if (!!form.market !== !!form.symbol.trim()) {
    toast.add({ severity: 'error', summary: '市場與股票代碼必須同時填寫或同時留空', life: 3500 });
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
      symbol: form.market ? form.symbol.trim().toUpperCase() : null
    };
    const res = isEditing.value ? await investmentNoteApi.updateNote(props.note.id, payload) : await investmentNoteApi.createNote(payload);
    toast.add({ severity: 'success', summary: res.message, life: 2500 });
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
  max-height: 20rem;
  overflow: auto;
  padding: 1.25rem 1.5rem;
  background: var(--p-surface-0);
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
.markdown-content :deep(blockquote) {
  margin: 0.9rem 0;
  padding: 0.15rem 1rem;
  border-left: 3px solid var(--p-primary-color);
  color: var(--p-text-muted-color);
  background: var(--p-surface-50);
}
.markdown-content :deep(code) {
  padding: 0.12rem 0.32rem;
  border-radius: 0.3rem;
  background: var(--p-surface-100);
  font-family: ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace;
  font-size: 0.85em;
}
.markdown-content :deep(pre) {
  margin: 0.9rem 0;
  padding: 1rem;
  overflow-x: auto;
  border-radius: 0.5rem;
  background: var(--p-surface-100);
}
.markdown-content :deep(pre code) { padding: 0; background: transparent; }
.markdown-content :deep(a) { color: var(--p-primary-color); text-decoration: underline; }
.markdown-content :deep(hr) { margin: 1.25rem 0; border: 0; border-top: 1px solid var(--p-content-border-color); }
.markdown-content :deep(table) { width: 100%; margin: 1rem 0; border-collapse: collapse; }
.markdown-content :deep(th),
.markdown-content :deep(td) { padding: 0.55rem 0.7rem; border: 1px solid var(--p-content-border-color); text-align: left; }
.markdown-content :deep(th) { background: var(--p-surface-50); font-weight: 700; }
</style>
