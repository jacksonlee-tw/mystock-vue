<template>
  <div v-if="market === 'tw'" class="card !m-0 rounded-2xl border border-surface-200 dark:border-surface-700/80 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
    <!-- 標頭：一律顯示，比照 StockAlertsPanel.vue 的既有慣例 -->
    <div class="flex flex-wrap items-center gap-3 px-5 py-4">
      <div class="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-900/30 text-primary flex items-center justify-center shrink-0">
        <i class="pi pi-megaphone text-lg"></i>
      </div>
      <div class="min-w-0">
        <div class="font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
          新聞輿情
          <span
            v-if="sentiment5d !== null"
            class="text-xs font-bold px-1.5 py-0.5 rounded"
            :class="sentimentBadgeClass"
          >
            近5日情緒 {{ sentiment5d >= 0 ? '+' : '' }}{{ sentiment5d.toFixed(2) }}
          </span>
        </div>
        <!-- 來源開關可視性（§11）：讓使用者知道看到的新聞量是被白名單過濾過的結果 -->
        <button
          type="button"
          class="text-xs text-surface-500 hover:text-primary flex items-center gap-1"
          @click="showSources = !showSources"
        >
          目前納入 {{ enabledSourceCount }} 個來源
          <i class="pi text-[10px]" :class="showSources ? 'pi-chevron-up' : 'pi-chevron-down'"></i>
        </button>
        <div v-if="showSources" class="mt-1 flex flex-wrap gap-1">
          <span
            v-for="s in sources"
            :key="s.id"
            class="text-[11px] px-1.5 py-0.5 rounded-full border"
            :class="s.enabled
              ? 'border-primary/30 bg-primary-50 dark:bg-primary-900/20 text-primary'
              : 'border-surface-200 dark:border-surface-700 text-surface-400 line-through'"
          >
            {{ s.name }}
          </span>
        </div>
      </div>
    </div>

    <!-- 載入中／失敗：inline 提示，不做整頁遮罩，比照 StockAlertsPanel.vue -->
    <div v-if="loading" class="px-5 pb-5 flex items-center gap-2 text-sm text-surface-400">
      <i class="pi pi-spin pi-spinner"></i>正在載入新聞...
    </div>
    <div v-else-if="error" class="px-5 pb-5 flex items-center gap-2 text-sm text-red-500">
      <i class="pi pi-exclamation-circle"></i>{{ error }}
      <button type="button" class="font-bold underline hover:no-underline" @click="load">重試</button>
    </div>
    <div v-else-if="newsItems.length === 0" class="px-5 pb-5 text-sm text-surface-400 flex items-center gap-1.5">
      <i class="pi pi-inbox"></i>近期沒有符合來源白名單的新聞
    </div>

    <template v-else>
      <ul class="px-5 pb-5 pt-1 space-y-3">
        <li
          v-for="item in visibleNews"
          :key="item.id"
          class="flex flex-col gap-1 pb-3 border-b border-surface-100 dark:border-surface-800 last:border-0 last:pb-0"
        >
          <div class="flex items-start justify-between gap-2">
            <a
              :href="item.news_url"
              target="_blank"
              rel="noopener noreferrer"
              class="text-sm font-semibold text-surface-800 dark:text-surface-100 hover:text-primary leading-snug"
            >
              {{ item.title }}
            </a>
            <span
              v-if="item.sentiment_label"
              class="shrink-0 text-[11px] font-bold px-1.5 py-0.5 rounded-full"
              :class="sentimentTagClass(item.sentiment_label)"
            >
              {{ sentimentLabelText(item.sentiment_label) }}
            </span>
          </div>
          <div class="text-xs text-surface-400 flex items-center gap-2">
            <span>{{ item.source }}</span>
            <span>·</span>
            <span>{{ formatPublishedAt(item.published_at) }}</span>
          </div>
        </li>
      </ul>
      <div v-if="newsItems.length > collapsedCount" class="px-5 pb-4 -mt-1">
        <button
          type="button"
          class="w-full text-center text-sm font-bold text-primary hover:underline py-1"
          @click="expanded = !expanded"
        >
          {{ expanded ? '收合' : `顯示全部 ${newsItems.length} 則` }}
          <i class="pi ml-1" :class="expanded ? 'pi-chevron-up' : 'pi-chevron-down'"></i>
        </button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { newsApi } from '@/service/newsApi';

const props = defineProps({
  stockId: { type: String, required: true },
  market: { type: String, required: true }
});

// §1.3：新聞情緒功能本階段僅支援台股，非台股一律不掛載本面板（見上方 template 的 v-if）。

const collapsedCount = 5;
const expanded = ref(false);
const newsItems = ref([]);
const sources = ref([]);
const sentiment5d = ref(null);
const loading = ref(true);
const error = ref(null);
const showSources = ref(false);

const visibleNews = computed(() => (expanded.value ? newsItems.value : newsItems.value.slice(0, collapsedCount)));
const enabledSourceCount = computed(() => sources.value.filter((s) => s.enabled).length);

// 情緒分數色彩沿用「紅漲綠跌」既有規定：分數為正（偏多）視同看漲取紅，為負（偏空）取綠
// （見 docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md §11 的配色說明；`bg-up-soft`／
// `text-up` 等 class 已在既有 CSS 變數層把「上漲=紅」固定死，跟 marketColors.js 是同一套
// 語意，這裡直接用 class 而非額外呼叫 colorForValue() 算 hex 色碼）。
const sentimentBadgeClass = computed(() => {
  if (sentiment5d.value === null) return '';
  return sentiment5d.value >= 0 ? 'bg-up-soft text-up' : 'bg-down-soft text-down';
});

const SENTIMENT_LABEL_TEXT = { BULLISH: '偏多', BEARISH: '偏空', NEUTRAL: '中立' };
function sentimentLabelText(label) {
  return SENTIMENT_LABEL_TEXT[label] || label;
}
function sentimentTagClass(label) {
  if (label === 'BULLISH') return 'bg-up-soft text-up';
  if (label === 'BEARISH') return 'bg-down-soft text-down';
  return 'bg-surface-100 dark:bg-surface-800 text-surface-500';
}

function formatPublishedAt(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  if (Number.isNaN(d.getTime())) return isoStr;
  return d.toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

async function loadSources() {
  try {
    const res = await newsApi.getSources();
    if (res.success) sources.value = res.data.sources;
  } catch {
    // 來源清單只是輔助資訊，載入失敗不影響新聞本身的呈現
  }
}

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const [newsRes, summaryRes] = await Promise.all([
      newsApi.getNews(props.stockId, { market: props.market, pageSize: 20 }),
      newsApi.getSentimentSummary(props.stockId, props.market)
    ]);
    if (newsRes.success) newsItems.value = newsRes.data.items;
    else error.value = '載入新聞時發生未知錯誤';
    if (summaryRes.success) sentiment5d.value = summaryRes.data.sentiment_5d;
  } catch (err) {
    error.value = err.response?.data?.error?.message || err.response?.data?.detail || err.message || '無法載入新聞';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadSources();
  if (props.market === 'tw') load();
});

watch([() => props.stockId, () => props.market], () => {
  expanded.value = false;
  if (props.market === 'tw') load();
});
</script>
