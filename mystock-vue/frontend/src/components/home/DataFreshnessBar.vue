<template>
  <!-- 登入首頁資料新鮮度狀態列（見 docs/19.登入自動補抓資料/登入自動補抓資料_規劃書.md §3.6）。
       硬性規則 #1：固定最小高度只容納單行狀態；「仍落後清單」展開是使用者主動點擊才出現，
       不會自動撐高頁面把使用者正在看的內容往下推。狀態列刻意不列入 useHomeWidgets registry、
       也不可關閉（ADR-06：自動補抓是系統健康機制，不是可選的資訊卡片）。 -->
  <div class="min-h-[1.75rem] flex items-center">
    <!-- 檢查中（尚未有任何結果可顯示） -->
    <div v-if="checking && !hasResult" class="text-xs text-surface-400 flex items-center gap-1.5">
      <i class="pi pi-spin pi-spinner" aria-hidden="true"></i>正在檢查資料是否為最新…
    </div>

    <!-- API 失敗：不影響其他卡片，僅狀態列本身顯示重試 -->
    <div v-else-if="lastError" class="text-xs text-surface-400 flex items-center gap-1.5">
      {{ lastError }}
      <button type="button" class="font-bold text-primary hover:underline" @click="ensureFresh({ force: false })">
        重試
      </button>
    </div>

    <!-- 背景補抓中（本次觸發，或發現排程／另一分頁已有任務執行中，直接接上進度） -->
    <div v-else-if="isBusy" class="flex items-center gap-2 text-xs text-surface-600 dark:text-surface-300 w-full max-w-md">
      <i class="pi pi-spin pi-spinner text-primary shrink-0" aria-hidden="true"></i>
      <div class="flex-1 min-w-0">
        <div class="h-1.5 rounded-full bg-surface-100 dark:bg-surface-800 overflow-hidden">
          <div
            class="h-full rounded-full bg-primary transition-all"
            :style="{ width: (fetchStatus?.progress_percent || 0) + '%' }"
          ></div>
        </div>
        <div class="truncate mt-1">{{ fetchStatus?.message || '背景更新中，完成後自動刷新' }}</div>
      </div>
    </div>

    <!-- 排程時窗：讓排程自己跑完整鏈，這次不重複觸發 -->
    <div v-else-if="scheduleWindowEntry" class="text-xs text-sky-600 dark:text-sky-400 flex items-center gap-1.5">
      <i class="pi pi-info-circle" aria-hidden="true"></i>{{ scheduleWindowEntry.reason }}
    </div>

    <!-- 節流：補過仍落後（多半停牌／下市），不再自動重打，可手動強制重試 -->
    <div v-else-if="throttledMarkets.length" class="text-xs w-full">
      <div class="flex items-center gap-2 flex-wrap">
        <button
          type="button"
          class="text-amber-600 dark:text-amber-400 font-bold flex items-center gap-1.5"
          :aria-expanded="expanded"
          @click="expanded = !expanded"
        >
          <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
          {{ throttledSummary }}
          <i class="pi" :class="expanded ? 'pi-chevron-up' : 'pi-chevron-down'" aria-hidden="true"></i>
        </button>
        <button type="button" class="text-primary font-bold hover:underline" @click="ensureFresh({ force: true })">
          立即重試
        </button>
      </div>
      <div v-if="expanded" class="mt-1.5 space-y-1 text-surface-500">
        <div v-for="m in throttledMarkets" :key="m.market">
          <span class="font-bold">{{ marketLabel(m.market) }}</span>：
          <span v-if="m.report.stocks.stale.length">個股 {{ symbolList(m.report.stocks.stale, 'symbol') }}</span>
          <span v-if="m.report.stocks.stale.length && m.report.indices.stale.length"> ・ </span>
          <span v-if="m.report.indices.stale.length">指數 {{ symbolList(m.report.indices.stale, 'code') }}</span>
        </div>
      </div>
    </div>

    <!-- 全部已是最新：精簡成一個小 chip，不搶版面。刻意不用紅漲綠跌色（bg-up-soft/text-up）——
         這是系統狀態不是漲跌方向，套用漲跌色會誤導（見 memory：red=up/green=down 僅用於行情本身）。 -->
    <div v-else-if="hasResult" class="text-xs">
      <span
        class="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-green-100 dark:bg-green-500/10 text-green-700 dark:text-green-400 font-bold"
      >
        <i class="pi pi-check-circle" aria-hidden="true"></i>資料已是最新・{{ upToDateSummary }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useCrawlerStatus } from '@/composables/useCrawlerStatus';
import { useDataFreshness } from '@/composables/useDataFreshness';
import { useMarket } from '@/composables/useMarket';

// 補抓完成後（isRunning true → false）由本元件重讀報告＋通知 HomeView 原地刷新各卡片＋跳 toast，
// 不做整頁 refresh（硬性規則 #1）。
const emit = defineEmits(['completed']);

const { result, checking, lastError, awaitingCompletion, ensureFresh, refreshAfterCompletion } = useDataFreshness();
const { isRunning, fetchStatus } = useCrawlerStatus();
const { enabledMarkets, currentMarket } = useMarket();

const expanded = ref(false);
const MARKET_LABELS = { tw: '台股', us: '美股' };

function marketLabel(market) {
  return MARKET_LABELS[market] || market;
}
function shortDate(d) {
  return d ? d.slice(5).replace('-', '/') : '—';
}
function symbolList(items, key) {
  return items.map((i) => i[key]).join('、');
}

const hasResult = computed(() => !!result.value?.markets);

// 顯示順序：目前市場排第一，其餘依 useMarket().enabledMarkets 順序（§3.6）
const orderedMarketCodes = computed(() => {
  if (!hasResult.value) return [];
  const codes = Object.keys(result.value.markets);
  const enabledOrder = enabledMarkets.value.map((m) => m.code).filter((c) => codes.includes(c));
  const rest = codes.filter((c) => !enabledOrder.includes(c));
  const ordered = [...enabledOrder, ...rest];
  const cur = currentMarket.value;
  return ordered.includes(cur) ? [cur, ...ordered.filter((c) => c !== cur)] : ordered;
});

const marketEntries = computed(() =>
  orderedMarketCodes.value.map((code) => ({ market: code, ...result.value.markets[code] }))
);

const isBusy = computed(
  () => isRunning.value || marketEntries.value.some((m) => m.action === 'triggered' || m.action === 'fetch_running')
);

const scheduleWindowEntry = computed(() => marketEntries.value.find((m) => m.action === 'schedule_window') || null);

const throttledMarkets = computed(() => marketEntries.value.filter((m) => m.action === 'throttled'));
const throttledSummary = computed(() => {
  const total = throttledMarkets.value.reduce(
    (sum, m) => sum + m.report.stocks.stale.length + m.report.indices.stale.length,
    0
  );
  return `${total} 檔仍無最新資料（可能停牌）`;
});

const upToDateSummary = computed(() =>
  marketEntries.value.map((m) => `${marketLabel(m.market)} ${shortDate(m.report.expected_date)}`).join('・')
);

onMounted(() => {
  // 元件只在 ownerAuthenticated 為 true 時才會被 HomeView v-if 掛載（未登入不渲染、不發請求，AC-02），
  // 掛載本身即涵蓋「頁面載入時已登入」與「首頁完成登入後 v-if 重新掛載」兩種時機（AC-01/AC-03）。
  ensureFresh();
});

// isRunning true → false 且正在等待這次補抓結果 → 重讀報告、通知 HomeView 原地刷新（不整頁 refresh）
watch(isRunning, async (running, wasRunning) => {
  if (!running && wasRunning && awaitingCompletion.value) {
    await refreshAfterCompletion();
    emit('completed');
  }
});
</script>
