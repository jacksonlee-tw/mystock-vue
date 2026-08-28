<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div>
        <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-book text-primary text-2xl"></i>投資筆記
        </h1>
        <p class="text-sm text-surface-500 mt-1">把當下的判斷留下來，讓未來的你看見決策是怎麼形成的；不會覆寫交易紀錄或觀察名單。</p>
      </div>
      <Button label="新增筆記" icon="pi pi-plus" @click="openCreate" />
    </div>

    <!-- 首次載入且無資料時才顯示整頁 loading；篩選/分頁切換一律保留既有內容 + overlay
         （CLAUDE.md 硬規則：切換控制項不得整頁 refresh 跳回頂端）。 -->
    <div v-if="loading && !hasLoadedOnce" class="flex items-center gap-2 text-surface-500 text-sm py-10 justify-center">
      <i class="pi pi-spin pi-spinner"></i> 載入中...
    </div>

    <template v-else>
      <div class="relative">
        <div v-if="loading" class="absolute inset-0 bg-surface-0/60 dark:bg-surface-900/60 backdrop-blur-[1px] z-10 rounded-xl flex items-start justify-center pt-16">
          <i class="pi pi-spin pi-spinner text-2xl text-primary"></i>
        </div>

        <div class="space-y-6">
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center gap-3">
              <div class="w-12 h-12 rounded-xl bg-primary-50 dark:bg-primary-500/10 text-primary flex items-center justify-center text-xl shrink-0"><i class="pi pi-book"></i></div>
              <div><div class="text-xs font-bold text-surface-400 uppercase tracking-wide">符合篩選</div><div class="text-2xl font-black text-surface-900 dark:text-surface-0 num">{{ total }}</div></div>
            </div>
            <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center gap-3">
              <div class="w-12 h-12 rounded-xl bg-sky-50 dark:bg-sky-500/10 text-sky-600 flex items-center justify-center text-xl shrink-0"><i class="pi pi-tag"></i></div>
              <div><div class="text-xs font-bold text-surface-400 uppercase tracking-wide">最常記錄</div><div class="text-2xl font-black text-sky-600 truncate max-w-[8rem]">{{ topTag }}</div></div>
            </div>
            <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center gap-3 col-span-2 sm:col-span-1">
              <div class="w-12 h-12 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 flex items-center justify-center text-xl shrink-0"><i class="pi pi-sparkles"></i></div>
              <div class="text-xs text-surface-500 leading-snug">記錄理由，比記錄結果更有價值。</div>
            </div>
          </div>

          <div class="note-filter-bar rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-3 shadow-sm">
            <IconField class="w-full">
              <InputIcon class="pi pi-search" />
              <InputText v-model="keyword" placeholder="搜尋主旨或內容" aria-label="搜尋主旨或內容" class="w-full" />
            </IconField>
            <DatePicker v-model="monthFilter" view="month" dateFormat="yy-mm" showIcon placeholder="依月份篩選" aria-label="依月份篩選" showButtonBar class="w-full" />
            <Select v-model="tagFilter" :options="tagSelectOptions" optionLabel="label" optionValue="value" placeholder="所有標籤" aria-label="標籤篩選" showClear class="w-full" />
            <Select v-model="marketFilter" :options="marketFilterOptions" optionLabel="label" optionValue="value" aria-label="市場篩選" class="w-full" />
            <Select v-model="statusFilter" :options="statusFilterOptions" optionLabel="label" optionValue="value" aria-label="狀態篩選" class="w-full" />
            <Button class="filter-reset-button" style="height: 32px" label="清除篩選" icon="pi pi-filter-slash" text size="small" :disabled="!hasActiveFilters" @click="resetFilters" />
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_240px] gap-6">
            <div>
              <div class="flex items-center gap-2 mb-3 text-sm">
                <span class="font-extrabold text-surface-800 dark:text-surface-100">{{ hasActiveFilters ? '篩選結果' : '全部筆記' }}</span>
                <span class="text-surface-400 text-xs">{{ total }} 篇</span>
              </div>

              <div v-if="!notes.length" class="border border-dashed border-surface-300 dark:border-surface-700 rounded-xl py-16 px-6 text-center text-surface-400">
                <i class="pi pi-search text-2xl text-primary"></i>
                <h3 class="text-surface-700 dark:text-surface-200 font-bold mt-3 mb-1">沒有找到筆記</h3>
                <p class="text-sm">試試看調整搜尋條件，或寫下今天的第一筆觀察。</p>
              </div>

              <div v-else class="space-y-2.5">
                <article
                  v-for="note in notes" :key="note.id"
                  class="group flex gap-5 p-5 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm hover:shadow-md hover:border-primary-200 dark:hover:border-primary-500/40 transition-all"
                >
                  <div class="w-16 shrink-0 text-center pt-0.5">
                    <div class="text-lg font-black text-surface-800 dark:text-surface-100 num leading-tight">{{ dateParts(note.note_date).day }}</div>
                    <div class="text-[11px] text-surface-400 num">{{ dateParts(note.note_date).year }}</div>
                    <div class="text-[11px] font-bold text-primary num mt-0.5">#{{ note.sequence_no }}</div>
                  </div>

                  <div class="flex-1 min-w-0">
                    <h2 class="text-base font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2 mb-1">
                      <span class="truncate">{{ note.subject }}</span>
                      <span v-if="note.status === 'draft'" class="shrink-0 px-1.5 py-0.5 text-[10px] font-bold rounded bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300">草稿</span>
                      <span v-else-if="note.status === 'archived'" class="shrink-0 px-1.5 py-0.5 text-[10px] font-bold rounded bg-surface-100 dark:bg-surface-800 text-surface-500">已封存</span>
                    </h2>
                    <p class="text-sm text-surface-500 mb-2.5 line-clamp-2">{{ note.content_excerpt }}</p>
                    <div class="flex flex-wrap items-center gap-1.5">
                      <button
                        v-for="t in note.tags" :key="t.id" type="button" @click="tagFilter = tagFilter === t.name ? '' : t.name"
                        class="px-2 py-0.5 text-[11px] font-bold rounded bg-teal-50 dark:bg-teal-500/10 text-teal-700 dark:text-teal-300 hover:opacity-75"
                      >{{ t.name }}</button>
                      <span v-if="note.symbol" class="px-2 py-0.5 text-[11px] font-medium rounded border border-amber-200 dark:border-amber-500/30 text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/10 num">
                        {{ note.market?.toUpperCase() }} · {{ note.symbol }}<span v-if="note.symbol_name">（{{ note.symbol_name }}）</span>
                      </span>
                    </div>
                  </div>

                  <div class="shrink-0 flex items-start gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
                    <button @click="openEdit(note)" title="編輯" class="w-8 h-8 grid place-items-center rounded-lg text-surface-400 hover:text-primary hover:bg-surface-100 dark:hover:bg-surface-800"><i class="pi pi-pencil"></i></button>
                    <button @click="confirmDelete(note)" title="刪除" class="w-8 h-8 grid place-items-center rounded-lg text-surface-400 hover:text-red-500 hover:bg-surface-100 dark:hover:bg-surface-800"><i class="pi pi-trash"></i></button>
                  </div>
                </article>
              </div>

              <Paginator
                v-if="total > pageSize"
                class="mt-4 bg-transparent border-0"
                :rows="pageSize" :totalRecords="total" :first="(page - 1) * pageSize"
                :rowsPerPageOptions="[10, 20, 50]" @page="onPage"
              />
            </div>

            <aside class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4 h-fit">
              <div class="flex items-center justify-between mb-3 text-sm font-extrabold text-surface-800 dark:text-surface-100">
                <span>標籤索引</span><i class="pi pi-tag text-primary"></i>
              </div>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="t in tags" :key="t.id" type="button" @click="tagFilter = tagFilter === t.name ? '' : t.name"
                  :class="tagFilter === t.name ? 'border-primary-300 text-primary bg-primary-50 dark:bg-primary-500/10' : 'border-surface-200 dark:border-surface-700 text-surface-500'"
                  class="px-2 py-1 text-[11px] font-medium rounded-md border hover:opacity-75"
                >{{ t.name }} <em class="not-italic text-surface-300 ml-0.5">{{ t.usage_count }}</em></button>
                <span v-if="!tags.length" class="text-surface-300 text-xs">尚無標籤</span>
              </div>
              <div class="flex items-start gap-2 mt-4 pt-3.5 border-t border-surface-200 dark:border-surface-700 text-surface-400 text-[11px] leading-relaxed">
                <i class="pi pi-info-circle mt-0.5"></i><p>列表只顯示內容摘要，點選「編輯」可查看完整內容。</p>
              </div>
            </aside>
          </div>
        </div>
      </div>
    </template>

    <InvestmentNoteEditor v-model:visible="editorVisible" :note="editingNote" :tag-options="tags" @saved="onSaved" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';
import { investmentNoteApi } from '@/service/investmentNoteApi';
import { toIsoDate } from '@/composables/usePortfolioFormat';
import InvestmentNoteEditor from '@/components/portfolio/InvestmentNoteEditor.vue';

const toast = useToast();
const confirm = useConfirm();

const marketFilterOptions = [
  { label: '全部市場', value: '' },
  { label: '台股', value: 'tw' },
  { label: '美股', value: 'us' }
];
const statusFilterOptions = [
  { label: '已發布', value: 'published' },
  { label: '含草稿', value: 'all' },
  { label: '草稿', value: 'draft' },
  { label: '已封存', value: 'archived' }
];

const loading = ref(true);
const hasLoadedOnce = ref(false);
const notes = ref([]);
const total = ref(0);
const tags = ref([]);

const page = ref(1);
const pageSize = ref(10);
const keyword = ref('');
const monthFilter = ref(null);
const tagFilter = ref('');
const marketFilter = ref('');
const statusFilter = ref('published');

const hasActiveFilters = computed(
  () => !!(keyword.value || monthFilter.value || tagFilter.value || marketFilter.value || statusFilter.value !== 'published')
);
const tagSelectOptions = computed(() => tags.value.map((t) => ({ label: `${t.name} (${t.usage_count})`, value: t.name })));
const topTag = computed(() => {
  if (!tags.value.length) return '—';
  return tags.value.slice().sort((a, b) => b.usage_count - a.usage_count)[0].name;
});

function monthRange(date) {
  if (!date) return { dateFrom: undefined, dateTo: undefined };
  const y = date.getFullYear();
  const m = date.getMonth();
  return { dateFrom: toIsoDate(new Date(y, m, 1)), dateTo: toIsoDate(new Date(y, m + 1, 0)) };
}

function dateParts(iso) {
  const [y, m, d] = iso.split('-');
  return { day: `${m}.${d}`, year: y };
}

async function load() {
  loading.value = true;
  try {
    const { dateFrom, dateTo } = monthRange(monthFilter.value);
    const res = await investmentNoteApi.getNotes({
      page: page.value, pageSize: pageSize.value, dateFrom, dateTo,
      q: keyword.value || undefined, tag: tagFilter.value || undefined,
      market: marketFilter.value || undefined, status: statusFilter.value
    });
    notes.value = res.data.items;
    total.value = res.data.total;
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: err?.response?.data?.detail || err.message, life: 4000 });
  } finally {
    loading.value = false;
    hasLoadedOnce.value = true;
  }
}

async function loadTags() {
  try {
    const res = await investmentNoteApi.getTags();
    tags.value = res.data;
  } catch {
    // 標籤索引載入失敗不影響主要列表，靜默略過
  }
}

onMounted(() => {
  load();
  loadTags();
});

// 篩選切換即時重查（切回第 1 頁）；關鍵字搜尋做輕量 debounce，避免每次按鍵都打一次 API
let keywordTimer = null;
watch(keyword, () => {
  clearTimeout(keywordTimer);
  keywordTimer = setTimeout(() => {
    page.value = 1;
    load();
  }, 350);
});
watch([monthFilter, tagFilter, marketFilter, statusFilter], () => {
  page.value = 1;
  load();
});

function onPage(event) {
  page.value = event.page + 1;
  pageSize.value = event.rows;
  load();
}

function resetFilters() {
  keyword.value = '';
  monthFilter.value = null;
  tagFilter.value = '';
  marketFilter.value = '';
  statusFilter.value = 'published';
}

const editorVisible = ref(false);
const editingNote = ref(null);

function openCreate() {
  editingNote.value = null;
  editorVisible.value = true;
}

async function openEdit(note) {
  try {
    const res = await investmentNoteApi.getNote(note.id);
    editingNote.value = res.data;
    editorVisible.value = true;
  } catch (err) {
    toast.add({ severity: 'error', summary: '讀取筆記內容失敗', detail: err?.response?.data?.detail || err.message, life: 4000 });
  }
}

async function onSaved() {
  await Promise.all([load(), loadTags()]);
}

function confirmDelete(note) {
  confirm.require({
    message: `確定要刪除「${note.subject}」（${note.note_date} #${note.sequence_no}）嗎？此動作無法復原，且不影響任何交易紀錄或觀察名單。`,
    header: '刪除投資筆記',
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: '確定刪除',
    rejectLabel: '取消',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await investmentNoteApi.deleteNote(note.id);
        toast.add({ severity: 'success', summary: '筆記已刪除', life: 2500 });
        if (notes.value.length === 1 && page.value > 1) page.value -= 1;
        await Promise.all([load(), loadTags()]);
      } catch (err) {
        toast.add({ severity: 'error', summary: '刪除失敗', detail: err?.response?.data?.detail || err.message, life: 4000 });
      }
    }
  });
}
</script>

<style scoped>
.note-filter-bar {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
  align-items: center;
}

.filter-reset-button {
  justify-self: stretch;
  white-space: nowrap;
}

@media (min-width: 640px) {
  .note-filter-bar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .note-filter-bar > :first-child {
    grid-column: 1 / -1;
  }

  .filter-reset-button {
    grid-column: 1 / -1;
  }
}

@media (min-width: 1024px) {
  .note-filter-bar {
    grid-template-columns: minmax(240px, 1fr) repeat(4, minmax(120px, 150px)) auto;
  }

  .note-filter-bar > :first-child {
    grid-column: auto;
  }

  .filter-reset-button {
    grid-column: auto;
    justify-self: end;
  }
}

.num {
  font-family: ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
</style>
