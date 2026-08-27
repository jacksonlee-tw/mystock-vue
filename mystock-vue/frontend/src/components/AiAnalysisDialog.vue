<template>
  <Dialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    modal
    :draggable="false"
    :style="{ width: '54rem', maxHeight: '88vh' }"
    :breakpoints="{ '960px': '92vw' }"
    content-class="!p-0"
  >
    <!-- 自訂 header：帶標的名稱，比純文字標題更好定位「這是哪一檔的報告」 -->
    <template #header>
      <div class="flex items-center gap-2.5 min-w-0">
        <span class="text-xl leading-none">🤖</span>
        <span class="font-black text-surface-900 dark:text-surface-0">AI 診股報告</span>
        <span v-if="report" class="num text-sm font-bold text-surface-400 truncate">
          {{ report.symbol }}<template v-if="report.stock_name"> {{ report.stock_name }}</template>
        </span>
      </div>
    </template>

    <!-- ── Stage 1：選擇 Provider／Model（v3.4 新增，§7.1）─────────────────────── -->
    <div v-if="stage === 'select'" class="px-6 py-5 space-y-5">
      <div v-if="modelsLoading" class="flex flex-col items-center justify-center py-12 text-center">
        <i class="pi pi-spin pi-spinner text-primary text-2xl mb-2"></i>
        <p class="text-xs text-surface-400">載入可選模型清單…</p>
      </div>

      <div v-else-if="error" class="flex flex-col items-center justify-center py-10 text-center gap-2">
        <i class="pi pi-exclamation-triangle text-red-400 text-2xl"></i>
        <p class="text-sm font-bold text-red-600 dark:text-red-400">{{ error }}</p>
      </div>

      <template v-else>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-2">選擇 AI 服務</label>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="code in providerCodes"
              :key="code"
              @click="$emit('select-provider', code)"
              :class="[
                'px-3.5 py-2 text-sm font-bold rounded-xl border transition-colors',
                selectedProvider === code
                  ? 'bg-primary text-primary-contrast border-primary shadow-sm'
                  : 'bg-surface-0 dark:bg-surface-900 text-surface-600 dark:text-surface-300 border-surface-200 dark:border-surface-700 hover:border-primary/60'
              ]"
            >
              {{ availableModels[code]?.display_name || code }}
            </button>
          </div>
        </div>

        <div>
          <label class="block text-xs font-bold text-surface-500 mb-2">選擇模型</label>
          <select
            :value="selectedModel"
            @change="$emit('update:selectedModel', $event.target.value)"
            class="w-full bg-surface-0 dark:bg-surface-900 border border-surface-200 dark:border-surface-700 rounded-xl px-3 py-2.5 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-primary/40"
          >
            <option v-for="m in currentModels" :key="m.id" :value="m.id">{{ m.label }}（{{ m.tier }}）</option>
          </select>
        </div>

        <!-- 今日是否已有此模型組合的報告：讓使用者按下去之前就知道會不會計費（§7.3） -->
        <div v-if="checkingLatest" class="flex items-center gap-1.5 text-xs text-surface-400">
          <i class="pi pi-spin pi-spinner"></i>檢查今日是否已有報告…
        </div>
        <div
          v-else-if="latestForSelection"
          class="flex items-start gap-2 text-xs font-semibold text-primary bg-primary-50 dark:bg-primary-900/20 border border-primary-100 dark:border-primary-800/60 rounded-xl px-3 py-2.5"
        >
          <i class="pi pi-history mt-0.5"></i>
          <span>今日已用此模型產生過報告，點擊下方按鈕直接讀取，<strong>不會再計費</strong>。</span>
        </div>
        <div v-else class="flex items-start gap-2 text-xs text-surface-400 bg-surface-50 dark:bg-surface-800/60 rounded-xl px-3 py-2.5">
          <i class="pi pi-info-circle mt-0.5"></i>
          <span>今日尚未用此模型產生過報告，點擊下方按鈕將擷取目前 K 線圖並呼叫 AI（約 10～40 秒，會產生實際費用）。</span>
        </div>

        <button
          @click="$emit('confirm')"
          :disabled="!selectedModel"
          class="w-full px-4 py-2.5 text-sm font-bold bg-primary text-primary-contrast rounded-xl hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
        >
          <i :class="['pi', latestForSelection ? 'pi-eye' : 'pi-android']"></i>
          {{ latestForSelection ? '檢視今日報告' : '產生報告' }}
        </button>
      </template>
    </div>

    <!-- ── Stage 2：載入中／錯誤／報告內容（沿用既有三態邏輯）───────────────────── -->
    <template v-else>
      <div v-if="loading && !report" class="flex flex-col items-center justify-center py-16 text-center px-6">
        <i class="pi pi-spin pi-spinner text-primary text-3xl mb-3"></i>
        <p class="text-sm font-bold text-surface-600 dark:text-surface-300">AI 正在分析中…</p>
        <p class="text-xs text-surface-400 mt-1">通常需要 10～40 秒，請耐心等候</p>
      </div>

      <div v-if="error && !report" class="flex flex-col items-center justify-center py-14 text-center gap-3 px-6">
        <i class="pi pi-exclamation-triangle text-red-400 text-2xl"></i>
        <p class="text-sm font-bold text-red-600 dark:text-red-400">{{ error }}</p>
        <button
          v-if="allowReselect"
          @click="$emit('back')"
          class="px-3 py-1.5 text-xs font-bold text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-800 rounded-lg transition-colors"
        >
          <i class="pi pi-arrow-left mr-1"></i>返回重新選擇
        </button>
      </div>

      <!-- 報告內容：單一捲動區（Dialog 自身的 content 區塊），避免內層再開一個捲軸 -->
      <div v-if="report" class="px-6 py-5 space-y-5" :class="{ 'opacity-60 pointer-events-none': loading }">
        <div
          v-if="error"
          class="flex items-start gap-2 text-xs font-semibold text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/60 rounded-xl px-3 py-2.5"
        >
          <i class="pi pi-exclamation-triangle mt-0.5"></i>
          <span>{{ error }}</span>
        </div>

        <!-- 狀態列：研判、信心、來源、是否讀取自快取 -->
        <div class="flex flex-wrap items-center gap-2 text-xs">
          <span
            class="px-2.5 py-1 rounded-full font-black flex items-center gap-1"
            :style="{ backgroundColor: verdictColor + '1a', color: verdictColor }"
          >
            <i :class="['pi', verdictIcon]"></i>{{ verdictLabel }}
          </span>
          <span v-if="report.confidence" class="px-2.5 py-1 rounded-full font-bold bg-surface-100 dark:bg-surface-800 text-surface-500">
            信心度：{{ confidenceLabel }}
          </span>
          <span v-if="report.cached" class="px-2.5 py-1 rounded-full font-bold bg-primary-50 dark:bg-primary-900/30 text-primary">
            <i class="pi pi-history text-[10px] mr-1"></i>今日已產生，讀取自紀錄
          </span>
          <span v-if="report.truncated" class="px-2.5 py-1 rounded-full font-bold bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400">
            <i class="pi pi-scissors text-[10px] mr-1"></i>內容可能被截斷
          </span>
          <span class="ml-auto text-surface-400 font-medium">
            {{ PROVIDER_LABELS[report.provider] || report.provider }}<template v-if="report.model"> ・ {{ report.model }}</template>
          </span>
        </div>

        <!-- 一句話結論：用左側色條 + 淡色底標出重點，呼應下方研判色，比純文字段落更好一眼抓到結論 -->
        <div
          v-if="report.headline"
          class="rounded-xl px-4 py-3 border-l-4 text-sm font-bold leading-relaxed text-surface-800 dark:text-surface-100"
          :style="{ borderColor: verdictColor, backgroundColor: verdictColor + '0d' }"
        >
          {{ report.headline }}
        </div>

        <!-- 關鍵價位卡片：CLAUDE.md 鐵則 2──同列卡片須等高，用 !m-0 蓋掉全域 .card 的
             legacy margin-bottom（見 assets/layout/_utils.scss），交給 grid 的 gap 處理間距 -->
        <div v-if="priceLevels.length" class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div
            v-for="(lvl, idx) in priceLevels"
            :key="idx"
            class="card !m-0 p-3 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 flex flex-col justify-between"
          >
            <div class="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-surface-400">
              <i :class="['pi', levelTypeIcon(lvl.type)]" :style="{ color: levelTypeColor(lvl.type) }"></i>
              {{ levelTypeLabel(lvl.type) }}
            </div>
            <div class="num text-lg font-black mt-1" :style="{ color: levelTypeColor(lvl.type) }">
              {{ formatPrice(lvl.price, marketMetaFor) }}
            </div>
            <div class="text-[11px] mt-0.5 text-surface-500 truncate" :title="lvl.label">{{ lvl.label }}</div>
          </div>
        </div>

        <!-- 完整敘述（Markdown 渲染；markdown-it 預設 html:false，LLM 輸出的原始 HTML 不會進入 v-html） -->
        <div
          v-if="report.report_markdown"
          class="ai-report-markdown text-sm leading-relaxed rounded-xl border border-surface-100 dark:border-surface-800 bg-surface-50/60 dark:bg-surface-800/30 px-4 py-3.5"
          v-html="renderedMarkdown"
        ></div>

        <!-- 觀察區間與交易日 -->
        <p class="text-[11px] text-surface-400 flex items-center gap-1.5 flex-wrap">
          <i class="pi pi-calendar"></i>
          觀察區間：{{ periodLabel }}
          <template v-if="report.chart?.start_date && report.chart?.end_date">
            （{{ report.chart.start_date }} ~ {{ report.chart.end_date }}）
          </template>
          <span class="text-surface-300 dark:text-surface-600">・</span>
          交易日：{{ report.trade_date }}
        </p>

        <!-- 免責聲明：後端無條件附加，前端須固定顯示且不得由使用者關閉（ADR-AI-10） -->
        <p class="text-[11px] text-surface-400 bg-surface-50 dark:bg-surface-800/60 rounded-lg px-3 py-2 leading-relaxed">
          <i class="pi pi-info-circle mr-1"></i>{{ report.disclaimer }}
        </p>

        <button
          v-if="allowReselect"
          @click="$emit('back')"
          class="text-xs font-bold text-surface-400 hover:text-primary transition-colors"
        >
          <i class="pi pi-arrow-left mr-1"></i>換個模型再看看
        </button>
      </div>
    </template>

    <template #footer>
      <button
        @click="$emit('update:visible', false)"
        class="px-4 py-2 text-sm font-bold text-surface-600 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-800 rounded-xl transition-colors"
      >
        關閉
      </button>
    </template>
  </Dialog>
</template>

<script setup>
import { computed } from 'vue';
import Dialog from 'primevue/dialog';
import MarkdownIt from 'markdown-it';
import { formatPrice } from '@/utils/format';
import { getUpDownColor } from '@/utils/marketColors';
import { useMarket } from '@/composables/useMarket';

const props = defineProps({
  visible: { type: Boolean, default: false },
  stage: { type: String, default: 'select' }, // 'select' | 'result'
  loading: { type: Boolean, default: false },
  error: { type: String, default: null },
  report: { type: Object, default: null },
  market: { type: String, default: 'tw' },
  // v3.4 模型選單（§4.3、§7.1）
  availableModels: { type: Object, default: () => ({}) }, // { claude: {display_name, default_model, models}, gemini: {...} }
  modelsLoading: { type: Boolean, default: false },
  selectedProvider: { type: String, default: '' },
  selectedModel: { type: String, default: '' },
  latestForSelection: { type: Object, default: null },
  checkingLatest: { type: Boolean, default: false },
  // 歷史頁面（AiReportHistory.vue）用 stage="result" 直接顯示已抓好的報告，沒有「選模型」
  // 這一步可退回，「返回重新選擇」／「換個模型再看看」這兩個按鈕在那個情境下沒有意義
  allowReselect: { type: Boolean, default: true }
});

defineEmits(['update:visible', 'update:selectedModel', 'select-provider', 'confirm', 'back']);

const providerCodes = computed(() => Object.keys(props.availableModels));
const currentModels = computed(() => props.availableModels[props.selectedProvider]?.models || []);

const { markets } = useMarket();
const marketMetaFor = computed(() => markets.value.find((m) => m.code === props.market) || markets.value[0]);

// html:false 是 markdown-it 的預設值，這裡明講出來：LLM 產生的內容一律走純文字＋Markdown 語法
// 解析，任何原始 <tag> 都會被當成字面文字輸出，不會進到 v-html 造成注入風險（規格書 §7.1）。
const md = new MarkdownIt({ html: false, linkify: false, breaks: true });

// 防禦性正規化：v3.3 起 report_markdown 主要由後端從結構化 sections 組裝、標題必定正確換行
// （見 backend/ai/schema.py sections_to_markdown()）；僅在模型拒答／解析失敗的保底 fallback
// 路徑才可能是自由文字，此時才用得到這道保險——標題記號前若不是換行開頭，強制插入空行。
function normalizeMarkdown(text) {
  if (!text) return '';
  return text.replace(/([^\n])[ \t]*(#{1,6}[ \t]+\S)/g, '$1\n\n$2');
}

const renderedMarkdown = computed(() =>
  props.report?.report_markdown ? md.render(normalizeMarkdown(props.report.report_markdown)) : ''
);

const PROVIDER_LABELS = { claude: 'Claude', gemini: 'Gemini' };

const VERDICT_LABELS = { bullish: '偏多', bearish: '偏空', neutral: '中性／觀望' };
const verdictLabel = computed(() => VERDICT_LABELS[props.report?.verdict] || '—');
const VERDICT_ICONS = { bullish: 'pi-arrow-up-right', bearish: 'pi-arrow-down-right', neutral: 'pi-minus' };
const verdictIcon = computed(() => VERDICT_ICONS[props.report?.verdict] || 'pi-minus');

// 紅漲綠跌是全站唯一色彩慣例（utils/marketColors.js）：偏多比照「漲」上色、偏空比照「跌」上色，
// 中性用中性文字色，不自行定義色碼。
const verdictColor = computed(() => {
  const { up, down } = getUpDownColor(props.market);
  if (props.report?.verdict === 'bullish') return up;
  if (props.report?.verdict === 'bearish') return down;
  return '#64748b';
});

const CONFIDENCE_LABELS = { high: '高', medium: '中', low: '低' };
const confidenceLabel = computed(() => CONFIDENCE_LABELS[props.report?.confidence] || props.report?.confidence);

const PERIOD_LABELS = { daily: '日線', weekly: '週線', monthly: '月線' };
const periodLabel = computed(() => {
  const p = props.report?.chart?.period;
  const m = props.report?.chart?.months;
  return `${PERIOD_LABELS[p] || p || ''}${m ? ` ・ 近 ${m} 個月` : ''}`;
});

const priceLevels = computed(() => {
  if (!props.report) return [];
  const levels = [];
  (props.report.support_levels || []).forEach((lvl) => levels.push({ type: 'support', ...lvl }));
  (props.report.resistance_levels || []).forEach((lvl) => levels.push({ type: 'resistance', ...lvl }));
  if (props.report.stop_loss !== null && props.report.stop_loss !== undefined) {
    levels.push({ type: 'stop_loss', price: props.report.stop_loss, label: '風控防守點' });
  }
  return levels;
});

function levelTypeLabel(type) {
  return { support: '支撐', resistance: '壓力', stop_loss: '停損' }[type] || type;
}

function levelTypeIcon(type) {
  return { support: 'pi-arrow-down', resistance: 'pi-arrow-up', stop_loss: 'pi-shield' }[type] || 'pi-flag';
}

function levelTypeColor(type) {
  const { up, down } = getUpDownColor(props.market);
  if (type === 'resistance') return up; // 上方壓力比照漲勢色
  if (type === 'support') return down; // 下方支撐比照跌勢色
  return '#f97316'; // 停損：中性警示色，不與漲跌語意混淆
}
</script>

<style scoped>
/* Dialog 內容區固定捲動邊界，避免整個 Dialog 隨內容長度把畫面撐爆；:deep 蓋掉 PrimeVue
   內部 class，讓捲動只發生在這一層，不會出現「Dialog 本身 + Markdown 區塊」兩層捲軸疊在一起。 */
:deep(.p-dialog-content) {
  overflow-y: auto;
}

/* Tailwind 重置了預設的標題／清單樣式，LLM 輸出的 Markdown（### 標題、**粗體**、- 清單）
   需要補上基本排版，否則整段擠成無層次的純文字。 */
.ai-report-markdown :deep(h3) {
  font-size: 0.95rem;
  font-weight: 800;
  color: var(--p-primary-color, #6366f1);
  padding-left: 0.6rem;
  border-left: 3px solid var(--p-primary-color, #6366f1);
  margin-top: 1.25rem;
  margin-bottom: 0.5rem;
}
.ai-report-markdown :deep(h3:first-child) {
  margin-top: 0;
}
.ai-report-markdown :deep(h4) {
  font-size: 0.875rem;
  font-weight: 700;
  margin-top: 0.9rem;
  margin-bottom: 0.35rem;
}
.ai-report-markdown :deep(p) {
  margin-bottom: 0.6rem;
}
.ai-report-markdown :deep(p:last-child) {
  margin-bottom: 0;
}
.ai-report-markdown :deep(ul),
.ai-report-markdown :deep(ol) {
  margin: 0.35rem 0 0.7rem 1.3rem;
  list-style: disc;
}
.ai-report-markdown :deep(ol) {
  list-style: decimal;
}
.ai-report-markdown :deep(li) {
  margin-bottom: 0.35rem;
}
.ai-report-markdown :deep(li:last-child) {
  margin-bottom: 0;
}
.ai-report-markdown :deep(li > ul),
.ai-report-markdown :deep(li > ol) {
  margin-top: 0.35rem;
}
.ai-report-markdown :deep(strong) {
  font-weight: 800;
  color: var(--p-surface-900, #0f172a);
}
:global(.app-dark) .ai-report-markdown :deep(strong) {
  color: var(--p-surface-0, #f8fafc);
}
</style>
