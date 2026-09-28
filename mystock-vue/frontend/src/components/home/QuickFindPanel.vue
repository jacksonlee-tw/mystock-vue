<template>
  <!-- 快速查找區（docs/18.個人化首頁/）：大搜尋框、最近瀏覽、我的持股／追蹤捷徑。
       搜尋本身不在這裡實作——第一個字元一打就交棒給全站唯一的 Omnibox，避免維護兩套搜尋邏輯。 -->
  <div class="flex flex-col gap-4 min-w-0">
    <!-- quick-search -->
    <div
      v-if="isEnabled('quick-search')"
      class="card !m-0 rounded-2xl border border-surface-200 dark:border-surface-700/80 bg-surface-0 dark:bg-surface-900 shadow-sm !p-4 !rounded-2xl min-w-0"
    >
      <div
        class="flex items-center gap-2 rounded-xl border border-surface-300 dark:border-surface-600 bg-surface-50 dark:bg-surface-800 px-3 py-2 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/30 transition"
      >
        <button
          type="button"
          class="shrink-0 w-8 h-8 inline-flex items-center justify-center rounded-lg text-surface-500 hover:text-primary hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
          aria-label="開啟股票搜尋"
          @click="openFromButton"
        >
          <i class="pi pi-search text-lg" aria-hidden="true"></i>
        </button>
        <input
          v-model="query"
          type="text"
          autocomplete="off"
          aria-label="搜尋股票代號或名稱"
          placeholder="搜尋股票代號或名稱…"
          class="flex-1 min-w-0 bg-transparent border-none outline-none text-base sm:text-lg font-semibold text-surface-900 dark:text-surface-0 placeholder-surface-400"
          @input="onInput"
          @compositionend="handoff"
          @keydown.enter.prevent="openFromButton"
        />
        <kbd
          class="hidden sm:inline-flex shrink-0 items-center px-2 py-1 rounded bg-surface-200 dark:bg-surface-700 text-[11px] font-bold text-surface-600 dark:text-surface-300"
          aria-hidden="true"
        >Ctrl K</kbd>
      </div>
    </div>

    <!-- recent-stocks -->
    <HomeSectionCard
      v-if="isEnabled('recent-stocks')"
      title="最近瀏覽"
      icon="pi-history"
      :has-data="recent.length > 0"
      :empty="recent.length === 0"
      empty-text="瀏覽過的股票會出現在這裡"
    >
      <template #header-extra>
        <button
          v-if="recent.length > 0"
          type="button"
          class="ml-auto text-xs font-bold text-surface-500 hover:text-primary hover:underline"
          @click="clear"
        >清除</button>
      </template>
      <ul class="flex flex-wrap gap-2 m-0 p-0 list-none">
        <li v-for="it in recent" :key="`${it.market}:${it.symbol}`" class="min-w-0 max-w-full">
          <button
            type="button"
            class="chip max-w-full"
            :title="`${it.symbol} ${it.name}`"
            @click="goStock(it.market, it.symbol)"
          >
            <span class="num font-bold">{{ it.symbol }}</span>
            <span class="truncate text-surface-600 dark:text-surface-300">{{ it.name }}</span>
            <!-- 最近瀏覽跨市場保存；與目前市場不同時標出市場，避免點進去才發現跳到另一個市場 -->
            <span
              v-if="it.market !== currentMarket"
              class="shrink-0 text-[10px] font-bold uppercase px-1 rounded bg-surface-200 dark:bg-surface-700 text-surface-600 dark:text-surface-300"
            >{{ it.market }}</span>
          </button>
        </li>
      </ul>
    </HomeSectionCard>

    <!-- my-shortcuts（需 owner：未登入不渲染、也不發請求） -->
    <HomeSectionCard
      v-if="shortcutsActive"
      title="我的持股與追蹤"
      icon="pi-star"
      :loading="shortcutsLoading"
      :has-data="shortcutsHasData"
      :empty="shortcutsEmpty"
      empty-text="目前市場尚無持股或追蹤標的"
    >
      <div class="space-y-3">
        <!-- 我的持股 -->
        <div>
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-xs font-bold text-surface-500">我的持股</span>
            <router-link to="/portfolio/holdings" class="ml-auto text-[11px] font-bold text-primary hover:underline no-underline">持股明細</router-link>
          </div>
          <p v-if="holdingsError && holdings.length === 0" class="text-xs text-surface-500 m-0">
            <i class="pi pi-exclamation-circle text-amber-500 mr-1" aria-hidden="true"></i>{{ holdingsError }}
            <button type="button" class="ml-1 font-bold text-primary hover:underline" @click="loadHoldings">重試</button>
          </p>
          <p v-else-if="holdings.length === 0" class="text-xs text-surface-400 m-0">目前市場沒有持股</p>
          <ul v-else class="flex flex-wrap gap-2 m-0 p-0 list-none">
            <li v-for="h in holdings" :key="`${h.market}:${h.symbol}`" class="min-w-0 max-w-full">
              <div class="chip !p-0 overflow-hidden max-w-full">
                <button
                  type="button"
                  class="flex items-center gap-1.5 min-w-0 pl-3 pr-1 py-1.5"
                  :title="`${h.symbol} ${h.name || ''}`"
                  @click="goStock(h.market, h.symbol)"
                >
                  <span class="num font-bold">{{ h.symbol }}</span>
                  <span class="num text-xs font-bold" :class="pnlClass(h.pnl_pct)">{{ fmtPct(h.pnl_pct) }}</span>
                </button>
                <WatchlistStarButton :market="h.market" :symbol="h.symbol" :name="h.name || ''" size="sm" class="mr-1" />
              </div>
            </li>
          </ul>
        </div>

        <!-- 我的追蹤 -->
        <div>
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-xs font-bold text-surface-500">我的追蹤</span>
            <router-link
              v-if="trackedAll.length > TRACKING_LIMIT"
              to="/portfolio/watchlist"
              class="ml-auto text-[11px] font-bold text-primary hover:underline no-underline"
            >查看全部 {{ trackedAll.length }} 檔</router-link>
          </div>
          <p v-if="trackedAll.length === 0" class="text-xs text-surface-400 m-0">目前市場沒有追蹤標的</p>
          <ul v-else class="flex flex-wrap gap-2 m-0 p-0 list-none">
            <li v-for="t in trackedShown" :key="`${t.market}:${t.symbol}`" class="min-w-0 max-w-full">
              <div class="chip !p-0 overflow-hidden max-w-full">
                <button
                  type="button"
                  class="flex items-center gap-1.5 min-w-0 pl-3 pr-1 py-1.5"
                  :title="`${t.symbol} ${t.name || ''}`"
                  @click="goStock(t.market, t.symbol)"
                >
                  <span class="num font-bold">{{ t.symbol }}</span>
                  <span class="truncate text-surface-600 dark:text-surface-300">{{ t.name }}</span>
                </button>
                <WatchlistStarButton :market="t.market" :symbol="t.symbol" :name="t.name || ''" size="sm" class="mr-1" />
              </div>
            </li>
          </ul>
        </div>
      </div>
    </HomeSectionCard>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import HomeSectionCard from '@/components/home/HomeSectionCard.vue';
import WatchlistStarButton from '@/components/WatchlistStarButton.vue';
import { useHomeWidgets } from '@/composables/useHomeWidgets';
import { useMarket } from '@/composables/useMarket';
import { useOmnibox } from '@/composables/useOmnibox';
import { useRecentStocks } from '@/composables/useRecentStocks';
import { useTrackingList } from '@/composables/useTrackingList';
import { shareRequest } from '@/composables/useSharedRequest';
import { fmtPct } from '@/composables/usePortfolioFormat';
import { portfolioApi } from '@/service/portfolioApi';

const props = defineProps({
  ownerAuthenticated: { type: Boolean, default: false },
  // 登入首頁自動補抓完成後由 HomeView 遞增（docs/19.登入自動補抓資料/登入自動補抓資料_規劃書.md §3.6）。
  refreshKey: { type: Number, default: 0 }
});

const TRACKING_LIMIT = 12; // 追蹤清單可能很長，首頁只放前 12 檔，其餘導向完整頁

const router = useRouter();
const { isEnabled } = useHomeWidgets();
const { currentMarket } = useMarket();
const { openOmnibox } = useOmnibox();
const { recent, clear } = useRecentStocks();
const { itemsBySymbol, ensureLoaded } = useTrackingList();

function goStock(market, symbol) {
  router.push(`/stock/${market}/${symbol}`);
}

// 全站一律紅漲綠跌，不依市場切換（見 assets/project-style.css）
function pnlClass(pct) {
  if (pct === null || pct === undefined || pct === 0) return 'text-surface-500';
  return pct > 0 ? 'text-up' : 'text-down';
}

/* ── quick-search：把輸入交棒給 Omnibox ─────────────────────────── */
const query = ref('');

function handoff() {
  const q = query.value.trim();
  query.value = ''; // 清空自己的輸入框：之後的輸入都在 Omnibox 裡進行
  if (q) openOmnibox(q);
}

function onInput(e) {
  // 中文輸入法組字中（isComposing）若此時清空輸入框會打斷組字，等 compositionend 再交棒
  if (e.isComposing) return;
  handoff();
}

// Enter／點放大鏡：輸入框通常已被交棒清空，此時就是單純開啟空白的 Omnibox
function openFromButton() {
  const q = query.value.trim();
  query.value = '';
  openOmnibox(q);
}

/* ── my-shortcuts：我的持股（portfolioApi）＋我的追蹤（useTrackingList） ── */
const holdings = ref([]);
const holdingsLoading = ref(false);
const holdingsError = ref(null);
const trackingLoading = ref(false);
// 第一次持股請求結束（不論成敗）才算 settled：決定該顯示骨架，還是內容／空狀態
const settled = ref(false);

let holdingsRid = 0; // 遞增 request id：快速切換市場時丟棄過期回應
let trackingRid = 0;

// 需 owner 的 widget：未啟用或未登入時完全不渲染、不發請求
const shortcutsActive = computed(() => isEnabled('my-shortcuts') && props.ownerAuthenticated);

async function loadHoldings() {
  const rid = ++holdingsRid;
  holdingsLoading.value = true;
  holdingsError.value = null;
  try {
    // 與「我的部位」的持股前五共用同一次請求（shareRequest），不重複打 /portfolio/holdings
    const market = currentMarket.value;
    const res = await shareRequest(`holdings:${market}`, () => portfolioApi.getHoldings({ market }));
    if (rid !== holdingsRid) return;
    if (res?.success) holdings.value = res.data || [];
    else holdingsError.value = '持股資料載入失敗';
  } catch {
    if (rid !== holdingsRid) return;
    // 失敗時不清掉舊資料（硬性規則 #1：內容保持掛載）
    holdingsError.value = '持股資料載入失敗';
  } finally {
    if (rid === holdingsRid) {
      holdingsLoading.value = false;
      settled.value = true;
    }
  }
}

async function loadTracking() {
  const rid = ++trackingRid;
  trackingLoading.value = true;
  try {
    // ensureLoaded 內建快取與 401 記憶（deniedMarkets），已載入的市場不會重打
    await ensureLoaded(currentMarket.value);
  } finally {
    if (rid === trackingRid) trackingLoading.value = false;
  }
}

watch(
  [currentMarket, shortcutsActive],
  ([, active]) => {
    if (!active) {
      // 作廢進行中的請求；登出時一併清掉個人持股資料，不留在記憶體
      holdingsRid++;
      trackingRid++;
      holdingsLoading.value = false;
      trackingLoading.value = false;
      if (!props.ownerAuthenticated) {
        holdings.value = [];
        holdingsError.value = null;
        settled.value = false;
      }
      return;
    }
    loadHoldings();
    loadTracking();
  },
  { immediate: true }
);

// 補抓完成後的原地刷新（§3.6）：只有「我的持股與追蹤」這張卡依賴會被補抓影響的價格／涵蓋範圍資料，
// 「最近瀏覽」是本機瀏覽紀錄，不受影響，不需重抓。
watch(
  () => props.refreshKey,
  () => {
    if (!shortcutsActive.value) return;
    loadHoldings();
    loadTracking();
  }
);

// 追蹤清單為全站單例快取（reactive Map）：星號按鈕加入／移除後這裡會即時反映
const trackedAll = computed(() => {
  const list = [];
  for (const item of itemsBySymbol.values()) {
    if (item.market === currentMarket.value) list.push(item);
  }
  return list;
});
const trackedShown = computed(() => trackedAll.value.slice(0, TRACKING_LIMIT));

const shortcutsLoading = computed(() => holdingsLoading.value || trackingLoading.value);
const hasAnyShortcut = computed(() => holdings.value.length > 0 || trackedAll.value.length > 0);
const shortcutsHasData = computed(() => settled.value || hasAnyShortcut.value);
const shortcutsEmpty = computed(
  () => settled.value && !hasAnyShortcut.value && !holdingsError.value && !shortcutsLoading.value
);
</script>

<style scoped>
/* 通用 chip：最近瀏覽／持股／追蹤共用外觀 */
.chip {
  @apply inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-surface-200 bg-surface-0 text-[13px] text-surface-900 transition-colors
    hover:border-primary hover:bg-surface-50
    dark:border-surface-700 dark:bg-surface-900 dark:text-surface-0 dark:hover:bg-surface-800;
}
</style>
