<template>
  <Dialog
    :visible="visible" @update:visible="onVisibleChange" modal :draggable="false"
    :style="{ width: 'min(54rem, 94vw)', maxHeight: '90vh' }" :closable="!busy"
  >
    <template #header>
      <div class="flex flex-1 items-center gap-2.5 min-w-0">
        <span class="text-xl leading-none">🤖</span>
        <span class="font-black text-surface-900 dark:text-surface-0 shrink-0">AI 解析筆記</span>
        <span v-if="note" class="text-sm font-bold text-surface-400 truncate">{{ note.subject }}</span>
      </div>
    </template>

    <!-- ── Stage 1：確認啟用狀態、選擇 Provider／模型，並在花錢前明說費用 ─────────────── -->
    <div v-if="stage === 'select'" class="space-y-5">
      <div v-if="statusLoading" class="flex flex-col items-center justify-center py-10 text-center">
        <i class="pi pi-spin pi-spinner text-primary text-2xl mb-2"></i>
        <p class="text-xs text-surface-400">載入 AI 設定…</p>
      </div>

      <div v-else-if="error" class="flex flex-col items-center justify-center py-8 text-center gap-2">
        <i class="pi pi-exclamation-triangle text-red-400 text-2xl"></i>
        <p class="text-sm font-bold text-red-600 dark:text-red-400">{{ error }}</p>
      </div>

      <div v-else-if="status && !status.enabled" class="flex items-start gap-2.5 text-sm bg-surface-50 dark:bg-surface-800/60 rounded-xl px-4 py-3.5">
        <i class="pi pi-lock mt-0.5 text-surface-400"></i>
        <div>
          <p class="font-bold text-surface-700 dark:text-surface-200">投資筆記 AI 解析尚未啟用</p>
          <p class="text-xs text-surface-500 mt-1">
            需要在 <code>backend/.env</code> 同時設定 <code>AI_ANALYSIS_ENABLED=true</code> 與
            <code>NOTE_AI_ENABLED=true</code>（預設皆為 false，啟用前不會產生任何費用）。
          </p>
        </div>
      </div>

      <template v-else-if="status">
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-2">選擇 AI 服務</label>
          <div class="flex items-center flex-wrap gap-2">
            <button
              v-for="code in providerCodes" :key="code" type="button" @click="selectProvider(code)"
              :class="[
                'px-3.5 py-2 text-sm font-bold rounded-xl border transition-colors',
                provider === code
                  ? 'bg-primary text-primary-contrast border-primary shadow-sm'
                  : 'bg-surface-0 dark:bg-surface-900 text-surface-600 dark:text-surface-300 border-surface-200 dark:border-surface-700 hover:border-primary/60'
              ]"
            >{{ providers[code]?.display_name || code }}</button>
          </div>
        </div>

        <div>
          <label class="block text-xs font-bold text-surface-500 mb-2">選擇模型</label>
          <select
            v-model="model"
            class="w-full bg-surface-0 dark:bg-surface-900 border border-surface-200 dark:border-surface-700 rounded-xl px-3 py-2.5 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-primary/40"
          >
            <option v-for="m in currentModels" :key="m.id" :value="m.id">{{ m.label }}（{{ m.tier }}）</option>
          </select>
        </div>

        <div class="flex items-start gap-2 text-xs text-surface-500 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800/50 rounded-xl px-3 py-2.5">
          <i class="pi pi-info-circle mt-0.5 text-amber-500"></i>
          <span>
            這會呼叫 AI 讀取這篇筆記的文字與圖片（最多 {{ status.max_images }} 張，約 10～60 秒），<strong>會產生實際費用</strong>。
            今日已用 {{ status.used_today ?? '—' }} / {{ status.daily_quota }} 次。
            解析結果只是<strong>提案</strong>，要你逐項確認後才會寫入筆記。
          </span>
        </div>

        <button
          type="button" :disabled="!model || quotaExhausted" @click="run"
          class="w-full px-4 py-2.5 text-sm font-bold bg-primary text-primary-contrast rounded-xl hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
        >
          <i class="pi pi-android"></i>{{ quotaExhausted ? '今日次數已用完' : '開始解析' }}
        </button>
      </template>
    </div>

    <!-- ── Stage 2：分析中 ─────────────────────────────────────────── -->
    <div v-else-if="stage === 'loading'" class="flex flex-col items-center justify-center py-14 text-center" aria-live="polite">
      <i class="pi pi-spin pi-spinner text-primary text-3xl mb-3"></i>
      <p class="text-sm font-bold text-surface-600 dark:text-surface-300">AI 正在解析筆記…</p>
      <p class="text-xs text-surface-400 mt-1">含圖片時通常需要 10～60 秒，請耐心等候</p>
    </div>

    <!-- ── Stage 3：失敗 ─────────────────────────────────────────── -->
    <div v-else-if="stage === 'error'" class="flex flex-col items-center justify-center py-10 text-center gap-3">
      <i class="pi pi-exclamation-triangle text-red-400 text-2xl"></i>
      <p class="text-sm font-bold text-red-600 dark:text-red-400">{{ error }}</p>
      <button type="button" class="px-3 py-1.5 text-xs font-bold text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-800 rounded-lg transition-colors" @click="stage = 'select'">
        <i class="pi pi-arrow-left mr-1"></i>返回重新選擇
      </button>
    </div>

    <!-- ── Stage 4：提案預覽，逐項勾選 ────────────────────────────────── -->
    <div v-else-if="proposal" class="space-y-5">
      <div v-if="proposal.truncated" class="flex items-start gap-2 text-xs font-semibold text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/20 rounded-xl px-3 py-2.5">
        <i class="pi pi-exclamation-triangle mt-0.5"></i><span>AI 回應被截斷，以下內容可能不完整。</span>
      </div>
      <div v-if="proposal.images.skipped > 0" class="flex items-start gap-2 text-xs text-surface-500 bg-surface-50 dark:bg-surface-800/60 rounded-xl px-3 py-2.5">
        <i class="pi pi-info-circle mt-0.5"></i>
        <span>這篇筆記有 {{ proposal.images.found }} 張圖，超過單次上限，只解析了前 {{ proposal.images.sent }} 張。</span>
      </div>

      <section v-if="proposal.suggested_subject" class="note-ai-block">
        <label class="note-ai-row">
          <Checkbox v-model="subjectChecked" binary input-id="ai-subject" />
          <span class="note-ai-title">建議主旨</span>
        </label>
        <p class="text-xs text-surface-400 line-through mt-1.5 ml-7 truncate">{{ note?.subject }}</p>
        <p class="text-sm font-bold text-surface-800 dark:text-surface-100 mt-0.5 ml-7">{{ proposal.suggested_subject }}</p>
      </section>

      <section v-if="proposal.topic_tags.length" class="note-ai-block">
        <div class="note-ai-title mb-2">主題標籤</div>
        <div class="flex flex-wrap gap-2">
          <label v-for="tag in proposal.topic_tags" :key="tag" class="note-ai-chip" :class="checkedTags.includes(tag) ? 'note-ai-chip-on' : ''">
            <Checkbox v-model="checkedTags" :value="tag" />
            <span>{{ tag }}</span>
          </label>
        </div>
      </section>

      <section v-if="symbolRows.length" class="note-ai-block">
        <div class="flex items-center justify-between mb-2">
          <span class="note-ai-title">擷取的個股（{{ symbolRows.length }} 檔）</span>
          <span class="text-[11px] text-surface-400">套用後以「代號」加入標籤</span>
        </div>
        <ul class="divide-y divide-surface-100 dark:divide-surface-800">
          <li v-for="row in symbolRows" :key="row.market + ':' + row.symbol" class="flex items-start gap-3 py-2">
            <Checkbox v-model="row.checked" binary :disabled="!symbolSelectable(row)" class="mt-0.5" />
            <div class="min-w-0 flex-1">
              <div class="flex items-center flex-wrap gap-x-2 gap-y-1">
                <span class="num text-sm font-black text-surface-900 dark:text-surface-0">{{ row.symbol }}</span>
                <span class="text-sm text-surface-700 dark:text-surface-200">{{ row.master_name || row.name }}</span>
                <span class="text-[10px] font-bold text-surface-400 uppercase">{{ row.market }}</span>
                <span class="note-ai-badge" :class="STATUS_BADGE[row.status].cls">{{ STATUS_BADGE[row.status].label }}</span>
                <span v-if="row.corrected_from" class="text-[10px] text-surface-400">（AI 原給 {{ row.corrected_from }}）</span>
              </div>
              <p v-if="row.reason" class="text-[11px] text-surface-500 mt-0.5">{{ row.reason }}</p>
              <p v-if="row.evidence" class="text-[11px] text-surface-400 mt-0.5">依據：{{ row.evidence }}</p>
              <button
                v-if="row.suggestion" type="button" class="mt-1 text-[11px] font-bold text-primary hover:underline"
                @click="takeSuggestion(row)"
              >改用 {{ row.suggestion.symbol }} {{ row.suggestion.name }}</button>
            </div>
          </li>
        </ul>
      </section>

      <section v-if="proposal.transcriptions.length" class="note-ai-block">
        <div class="note-ai-title mb-2">圖片轉錄</div>
        <div v-for="t in proposal.transcriptions" :key="t.ref" class="mb-3 last:mb-0">
          <label class="note-ai-row">
            <Checkbox v-model="checkedRefs" :value="t.ref" :disabled="appliedRefs.has(t.ref)" />
            <span class="text-sm font-bold">圖片 {{ t.ref }}<template v-if="t.title">：{{ t.title }}</template></span>
            <span v-if="appliedRefs.has(t.ref)" class="text-[11px] text-surface-400">（已套用過）</span>
          </label>
          <div class="note-ai-preview mt-2 ml-7">
            <MarkdownPreview class="markdown-content" :source="t.markdown" />
          </div>
        </div>
        <p class="text-[11px] text-surface-400">套用時轉錄會插在原圖下方，原圖不會被移除；數字請與原圖核對。</p>
      </section>

      <section v-if="proposal.summary_markdown" class="note-ai-block">
        <label class="note-ai-row">
          <Checkbox v-model="summaryChecked" binary :disabled="summaryApplied" />
          <span class="note-ai-title">AI 整理</span>
          <span v-if="summaryApplied" class="text-[11px] text-surface-400">（已套用過）</span>
        </label>
        <div class="note-ai-preview mt-2 ml-7"><MarkdownPreview class="markdown-content" :source="proposal.summary_markdown" /></div>
      </section>

      <p v-if="isEmptyProposal" class="text-sm text-surface-400 text-center py-4">AI 沒有從這篇筆記整理出可套用的內容。</p>
    </div>

    <template #footer>
      <div class="w-full flex items-center justify-between gap-3">
        <span class="text-[11px] text-surface-400 min-w-0 truncate">
          <template v-if="proposal">
            {{ proposal.provider }}・{{ proposal.model }}
            <template v-if="proposal.usage.estimated_cost_usd != null">・約 US${{ proposal.usage.estimated_cost_usd.toFixed(4) }}</template>
            ・{{ disclaimer }}
          </template>
        </span>
        <div class="flex items-center gap-2 shrink-0">
          <Button v-if="proposal" label="重新選擇" text :disabled="applying" @click="reset" />
          <Button label="關閉" text :disabled="busy" @click="onVisibleChange(false)" />
          <Button
            v-if="proposal" :label="`套用（${selectedCount} 項）`" icon="pi pi-check"
            :disabled="!selectedCount" :loading="applying" @click="apply"
          />
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { noteAiApi } from '@/service/noteAiApi';
import { aiAnalysisApi } from '@/service/aiAnalysisApi';
import { investmentNoteApi } from '@/service/investmentNoteApi';
import MarkdownPreview from '@/components/portfolio/MarkdownPreview.vue';
import {
  buildApplyPayload, defaultSymbolChecked, symbolSelectable, adoptSuggestion, hasAppliedSummary, hasAppliedTranscription
} from '@/utils/noteAiApply';

const props = defineProps({
  visible: { type: Boolean, default: false },
  note: { type: Object, default: null } // 列表中的筆記（只需 id／subject；完整內容於套用時另取）
});
const emit = defineEmits(['update:visible', 'applied']);

const toast = useToast();
const router = useRouter();
const route = useRoute();

const STATUS_BADGE = {
  verified: { label: '已驗證', cls: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300' },
  name_mismatch: { label: '名稱不符', cls: 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300' },
  not_found: { label: '查無此代號', cls: 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-300' },
  unverified: { label: '未驗證', cls: 'bg-surface-100 text-surface-500 dark:bg-surface-800 dark:text-surface-400' }
};

const stage = ref('select'); // select | loading | error | result（result 以 proposal 是否存在判斷）
const error = ref('');
const status = ref(null);
const statusLoading = ref(false);
const providers = ref({});
const provider = ref('');
const model = ref('');

const proposal = ref(null);
const disclaimer = ref('');
const subjectChecked = ref(true);
const checkedTags = ref([]);
const symbolRows = ref([]);
const checkedRefs = ref([]);
const summaryChecked = ref(false);
const appliedRefs = ref(new Set());
const summaryApplied = ref(false);
const applying = ref(false);

const busy = computed(() => stage.value === 'loading' || applying.value);
const providerCodes = computed(() => Object.keys(providers.value));
const currentModels = computed(() => providers.value[provider.value]?.models || []);
const quotaExhausted = computed(() => status.value?.used_today != null && status.value.used_today >= status.value.daily_quota);

const selectedSymbols = computed(() => symbolRows.value.filter((r) => r.checked && symbolSelectable(r)));
const selectedCount = computed(() =>
  (subjectChecked.value && proposal.value?.suggested_subject ? 1 : 0)
  + checkedTags.value.length + selectedSymbols.value.length + checkedRefs.value.length
  + (summaryChecked.value && !summaryApplied.value ? 1 : 0)
);
const isEmptyProposal = computed(() => {
  const p = proposal.value;
  return !p.suggested_subject && !p.topic_tags.length && !p.symbols.length && !p.transcriptions.length && !p.summary_markdown;
});

function selectProvider(code) {
  provider.value = code;
  model.value = providers.value[code]?.default_model || providers.value[code]?.models?.[0]?.id || '';
}

function reset() {
  stage.value = 'select';
  proposal.value = null;
  error.value = '';
}

function onVisibleChange(v) {
  if (!v && busy.value) return; // 分析中／套用中不可關閉，避免看不到結果或中斷寫入
  emit('update:visible', v);
}

async function loadSetup() {
  statusLoading.value = true;
  error.value = '';
  try {
    const [statusRes, modelsRes] = await Promise.all([noteAiApi.getStatus(), aiAnalysisApi.getModels()]);
    status.value = statusRes.data;
    providers.value = modelsRes.data?.providers || {};
    selectProvider(providers.value[status.value.default_provider] ? status.value.default_provider : Object.keys(providers.value)[0] || '');
    if (providers.value[provider.value] && providers.value[provider.value].models.some((m) => m.id === status.value.default_model)) {
      model.value = status.value.default_model;
    }
  } catch (err) {
    if (await redirectIfUnauthorized(err)) return;
    error.value = err.message || '載入 AI 設定失敗';
  } finally {
    statusLoading.value = false;
  }
}

async function redirectIfUnauthorized(err) {
  if (err?.status !== 401) return false;
  emit('update:visible', false);
  await router.push({ name: 'owner-login', query: { redirect: route.fullPath } });
  return true;
}

watch(
  () => props.visible,
  (v) => {
    if (!v) return;
    reset();
    loadSetup();
  },
  { immediate: true }
);

async function run() {
  stage.value = 'loading';
  error.value = '';
  try {
    const res = await noteAiApi.analyzeNote(props.note.id, { provider: provider.value, model: model.value });
    disclaimer.value = res.disclaimer || '';
    await showProposal(res.data);
  } catch (err) {
    if (await redirectIfUnauthorized(err)) return;
    error.value = err.message || 'AI 解析失敗';
    stage.value = 'error';
  }
}

async function showProposal(p) {
  // 取完整內容判斷哪些轉錄／整理已套用過（列表只有摘要，沒有 content）
  let fullNote = null;
  try {
    fullNote = (await investmentNoteApi.getNote(props.note.id)).data;
  } catch { /* 取不到就當作都沒套用過，不擋預覽 */ }
  const content = fullNote?.content || '';

  proposal.value = p;
  appliedRefs.value = new Set(p.transcriptions.filter((t) => hasAppliedTranscription(content, t.ref)).map((t) => t.ref));
  summaryApplied.value = hasAppliedSummary(content);
  subjectChecked.value = !!p.suggested_subject;
  checkedTags.value = [...p.topic_tags];
  symbolRows.value = p.symbols.map((s) => ({ ...s, checked: defaultSymbolChecked(s) }));
  checkedRefs.value = p.transcriptions.map((t) => t.ref).filter((ref) => !appliedRefs.value.has(ref));
  summaryChecked.value = false;
  stage.value = 'result';
}

function takeSuggestion(row) {
  const i = symbolRows.value.indexOf(row);
  if (i < 0) return;
  const swapped = adoptSuggestion(row);
  // 建議代號若跟清單中另一列相同，直接併掉這一列，避免同一檔出現兩次
  const dup = symbolRows.value.some((r, j) => j !== i && r.market === swapped.market && r.symbol === swapped.symbol);
  if (dup) symbolRows.value.splice(i, 1);
  else symbolRows.value[i] = { ...swapped, checked: true };
}

async function apply() {
  applying.value = true;
  try {
    // 以最新內容為基準：分析期間使用者可能又改過這篇筆記
    const fullNote = (await investmentNoteApi.getNote(props.note.id)).data;
    const payload = buildApplyPayload({
      note: fullNote,
      proposal: proposal.value,
      choices: {
        subject: subjectChecked.value,
        topicTags: checkedTags.value,
        symbols: selectedSymbols.value,
        transcriptions: checkedRefs.value,
        summary: summaryChecked.value
      }
    });
    if (!Object.keys(payload).length) {
      toast.add({ severity: 'info', summary: '沒有需要套用的變更', life: 2500 });
      return;
    }
    await investmentNoteApi.updateNote(props.note.id, payload);
    toast.add({ severity: 'success', summary: '已套用 AI 解析結果', life: 2500 });
    emit('applied');
    emit('update:visible', false);
  } catch (err) {
    if (await redirectIfUnauthorized(err)) return;
    toast.add({ severity: 'error', summary: '套用失敗', detail: err.message, life: 5000 });
  } finally {
    applying.value = false;
  }
}
</script>

<style scoped>
.note-ai-block {
  padding: 0.9rem 1rem;
  border: 1px solid var(--p-content-border-color);
  border-radius: 0.75rem;
}

.note-ai-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  cursor: pointer;
}

.note-ai-title {
  font-size: 0.8rem;
  font-weight: 800;
  color: var(--p-text-muted-color);
}

.note-ai-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.6rem;
  font-size: 0.8rem;
  font-weight: 700;
  border: 1px solid var(--p-content-border-color);
  border-radius: 0.5rem;
  cursor: pointer;
  color: var(--p-text-muted-color);
}

.note-ai-chip-on {
  border-color: var(--p-primary-color);
  color: var(--p-primary-color);
}

.note-ai-badge {
  padding: 0.05rem 0.4rem;
  font-size: 10px;
  font-weight: 800;
  border-radius: 0.3rem;
}

.note-ai-preview {
  max-height: 14rem;
  overflow: auto;
  padding: 0.6rem 0.8rem;
  border-radius: 0.5rem;
  background: var(--p-surface-50);
}

.app-dark .note-ai-preview {
  background: var(--p-surface-900);
}

.markdown-content { font-size: 0.85rem; line-height: 1.6; color: var(--p-text-color); }
.markdown-content :deep(table) { width: 100%; border-collapse: collapse; }
.markdown-content :deep(th),
.markdown-content :deep(td) { padding: 0.3rem 0.5rem; border: 1px solid var(--p-content-border-color); text-align: left; font-size: 0.8rem; }
.markdown-content :deep(th) { font-weight: 700; background: var(--p-surface-100); }
.app-dark .markdown-content :deep(th) { background: var(--p-surface-800); }
.markdown-content :deep(h3) { margin: 0.6rem 0 0.3rem; font-weight: 800; }
.markdown-content :deep(p) { margin: 0.4rem 0; }
</style>
