<template>
  <Dialog :visible="visible" @update:visible="$emit('update:visible', $event)" modal :header="isEditing ? '編輯投資筆記' : '新增投資筆記'" style="width: 36rem" :closable="!saving">
    <div class="space-y-4">
      <div class="grid grid-cols-2 gap-4">
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
        <label class="block text-xs font-bold text-surface-500 mb-1">內容</label>
        <Textarea v-model="form.content" rows="8" class="w-full" placeholder="記下你的觀察、判斷依據與下一步..." />
      </div>

      <div class="grid grid-cols-2 gap-4">
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

// 每次開啟（新增或切換編輯目標）都重新灌值，避免殘留上一次的表單內容
watch(
  () => [props.visible, props.note],
  ([visible, note]) => {
    if (!visible) return;
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
