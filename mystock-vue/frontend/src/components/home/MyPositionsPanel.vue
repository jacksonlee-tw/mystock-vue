<template>
  <!-- 首頁「我的部位」區塊（docs/18.個人化首頁/）：帳戶 KPI／持股前五／到價提醒／出場風控警示。
       四個 widget 全部需要 owner 登入；未登入時整個元件不渲染、不發請求（HomeView 另外顯示登入提示卡）。 -->
  <div v-if="ownerAuthenticated && anyEnabled" class="flex flex-col gap-4 min-w-0">
    <!-- ── 帳戶 KPI ─────────────────────────────────────────────
         硬性規則 #2：4 張卡結構完全一致（label／value／sub 各一行且都 truncate、不換行），
         且每張都加 !m-0，避免 .card:last-child 的 margin 規則讓最後一張比較高。
         硬性規則 #1：重抓時舊數字原地保留，只疊遮罩，不把內容換成 spinner。 -->
    <div v-if="isEnabled('portfolio-kpi')" class="relative min-w-0">
      <div
        v-if="kpi.error.value && !kpi.data.value"
        class="card !m-0 !p-4 rounded-2xl border border-surface-200 dark:border-surface-700/80 bg-surface-0 dark:bg-surface-900 shadow-sm text-sm text-surface-500 flex items-center gap-3 flex-wrap"
      >
        <span><i class="pi pi-exclamation-circle text-amber-500 mr-1" aria-hidden="true"></i>{{ kpi.error.value }}</span>
        <button type="button" class="text-xs font-bold text-primary hover:underline" @click="kpi.refresh()">重試</button>
      </div>

      <div v-else-if="kpi.loading.value && !kpi.data.value" class="grid grid-cols-2 lg:grid-cols-4 gap-3" aria-busy="true">
        <div
          v-for="n in 4"
          :key="n"
          class="card !m-0 !p-4 h-full rounded-2xl border border-surface-200 dark:border-surface-700/80 bg-surface-0 dark:bg-surface-900 shadow-sm flex flex-col gap-2"
        >
          <div class="h-3 w-16 rounded bg-surface-100 dark:bg-surface-800 animate-pulse"></div>
          <div class="h-6 w-24 rounded bg-surface-100 dark:bg-surface-800 animate-pulse"></div>
          <div class="h-3 w-20 rounded bg-surface-100 dark:bg-surface-800 animate-pulse"></div>
        </div>
      </div>

      <template v-else-if="kpi.data.value">
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div
            v-for="card in kpiCards"
            :key="card.key"
            class="card !m-0 !p-4 h-full rounded-2xl border border-surface-200 dark:border-surface-700/80 bg-surface-0 dark:bg-surface-900 shadow-sm flex flex-col gap-1 min-w-0"
          >
            <span class="text-xs font-bold text-surface-500 dark:text-surface-400 truncate">{{ card.label }}</span>
            <span class="num text-lg sm:text-xl font-black truncate" :class="card.valueClass" :title="card.value">{{ card.value }}</span>
            <span class="num text-[11px] text-surface-500 dark:text-surface-400 truncate" :title="card.sub">{{ card.sub }}</span>
          </div>
        </div>
        <div
          v-if="kpi.loading.value"
          class="absolute inset-0 rounded-2xl bg-surface-0/60 dark:bg-surface-900/60 flex items-center justify-center"
          aria-busy="true"
        >
          <i class="pi pi-spin pi-spinner text-surface-500" aria-hidden="true"></i>
        </div>
        <p v-if="kpi.error.value" class="text-[11px] text-amber-600 dark:text-amber-400 mt-2 mb-0">
          重新整理失敗，顯示的是上一次的資料
        </p>
      </template>
    </div>

    <!-- ── 三張列表卡：auto-fit 讓被關掉的卡片不會留下空欄，同列由 grid 拉齊高度 ── -->
    <div
      v-if="isEnabled('holdings-top') || isEnabled('watchlist-target') || isEnabled('risk-alerts')"
      class="grid grid-cols-[repeat(auto-fit,minmax(min(100%,19rem),1fr))] gap-4"
    >
      <!-- 持股前五 -->
      <HomeSectionCard
        v-if="isEnabled('holdings-top')"
        title="持股前五"
        icon="pi-briefcase"
        to="/portfolio/holdings"
        :loading="holdings.loading.value"
        :error="holdings.error.value"
        :has-data="holdings.data.value !== null"
        :empty="holdings.unauthorized.value || (holdings.data.value !== null && topHoldings.length === 0)"
        :empty-text="holdings.unauthorized.value ? '登入後即可顯示' : '目前沒有持股'"
        @retry="holdings.refresh()"
      >
        <ul class="list-none m-0 p-0 divide-y divide-surface-100 dark:divide-surface-800">
          <li v-for="h in topHoldings" :key="`${h.market}:${h.symbol}`">
            <router-link
              :to="stockPath(h.market, h.symbol)"
              class="flex items-center gap-2 py-2 px-1 -mx-1 rounded-lg no-underline hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
            >
              <div class="min-w-0 flex-1">
                <div class="flex items-baseline gap-1.5 min-w-0">
                  <span class="num text-sm font-black text-surface-900 dark:text-surface-0 shrink-0">{{ h.symbol }}</span>
                  <span class="text-sm text-surface-600 dark:text-surface-300 truncate">{{ h.name }}</span>
                </div>
                <div class="text-[11px] text-surface-500 dark:text-surface-400">
                  權重 <span class="num">{{ (h.weight_pct || 0).toFixed(1) }}%</span>
                </div>
              </div>
              <span
                v-if="h.quote_missing"
                class="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-bold bg-surface-100 dark:bg-surface-800 text-surface-500 dark:text-surface-400"
              >無報價</span>
              <span v-else class="num shrink-0 text-sm font-black" :class="pnlClass(h.pnl_pct)">{{ fmtPct(h.pnl_pct) }}</span>
            </router-link>
          </li>
        </ul>
      </HomeSectionCard>

      <!-- 到價提醒 -->
      <HomeSectionCard
        v-if="isEnabled('watchlist-target')"
        title="到價提醒"
        icon="pi-flag"
        to="/portfolio/watchlist"
        :loading="watchlist.loading.value"
        :error="watchlist.error.value"
        :has-data="watchlist.data.value !== null"
        :empty="watchlist.unauthorized.value || (watchlist.data.value !== null && targetHits.length === 0)"
        :empty-text="watchlist.unauthorized.value ? '登入後即可顯示' : '目前沒有接近目標價的標的'"
        @retry="watchlist.refresh()"
      >
        <ul class="list-none m-0 p-0 divide-y divide-surface-100 dark:divide-surface-800">
          <li v-for="w in targetHits" :key="`${w.market}:${w.symbol}`">
            <router-link
              :to="stockPath(w.market, w.symbol)"
              class="flex items-center gap-2 py-2 px-1 -mx-1 rounded-lg no-underline hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
            >
              <div class="min-w-0 flex-1">
                <div class="flex items-baseline gap-1.5 min-w-0">
                  <span class="num text-sm font-black text-surface-900 dark:text-surface-0 shrink-0">{{ w.symbol }}</span>
                  <span class="text-sm text-surface-600 dark:text-surface-300 truncate">{{ w.name }}</span>
                </div>
                <div class="text-[11px] text-surface-500 dark:text-surface-400 truncate">
                  現價 <span class="num">{{ fmtPrice(w.price) }}</span> / 目標 <span class="num">{{ fmtPrice(w.target_price) }}</span>
                </div>
              </div>
              <!-- 到價／接近是「買進目標」的狀態而非多空方向，不用紅綠，避免與漲跌色混淆 -->
              <span
                v-if="w.is_reached"
                class="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-black bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300"
              >已到價</span>
              <span
                v-else
                class="num shrink-0 px-1.5 py-0.5 rounded text-[11px] font-bold bg-primary-50 dark:bg-primary-900/20 text-primary"
              >距目標 {{ Math.abs(w.gap_pct).toFixed(1) }}%</span>
            </router-link>
          </li>
        </ul>
      </HomeSectionCard>

      <!-- 出場風控警示：風險提示一律用警示色（amber），不套多空色 -->
      <HomeSectionCard
        v-if="isEnabled('risk-alerts')"
        title="出場風控警示"
        icon="pi-exclamation-triangle"
        to="/alerts"
        :loading="risk.loading.value"
        :error="risk.error.value"
        :has-data="risk.data.value !== null"
        :empty="risk.unauthorized.value || (risk.data.value !== null && riskRows.length === 0)"
        :empty-text="risk.unauthorized.value ? '登入後即可顯示' : '近 5 日沒有出場風控警示'"
        @retry="risk.refresh()"
      >
        <ul class="list-none m-0 p-0 flex flex-col gap-2">
          <li v-for="a in riskRows" :key="a.id || `${a.market}:${a.stock_id}:${a.strategy_id}:${a.trade_date}`">
            <router-link
              :to="stockPath(a.market || currentMarket, a.stock_id)"
              class="block rounded-lg border-l-4 border-amber-500 bg-amber-50 dark:bg-amber-900/10 px-3 py-2 no-underline hover:bg-amber-100 dark:hover:bg-amber-900/20 transition-colors"
            >
              <div class="flex items-baseline gap-1.5 min-w-0">
                <span class="num text-sm font-black text-surface-900 dark:text-surface-0 shrink-0">{{ a.stock_id }}</span>
                <span class="text-sm text-surface-600 dark:text-surface-300 truncate">{{ a.stock_name }}</span>
                <span class="num ml-auto shrink-0 text-[11px] text-surface-500 dark:text-surface-400">{{ shortDate(a.trade_date) }}</span>
              </div>
              <div class="text-xs font-bold text-amber-700 dark:text-amber-300 truncate">{{ a.strategy_name }}</div>
              <p v-if="a.suggested_action" class="text-[11px] text-surface-600 dark:text-surface-400 mt-0.5 mb-0 line-clamp-2">
                {{ a.suggested_action }}
              </p>
            </router-link>
          </li>
        </ul>
      </HomeSectionCard>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import HomeSectionCard from '@/components/home/HomeSectionCard.vue';
import { useHomeWidgets } from '@/composables/useHomeWidgets';
import { useMarket } from '@/composables/useMarket';
import { fmtPct, signed, fmtNum } from '@/composables/usePortfolioFormat';
import { shareRequest } from '@/composables/useSharedRequest';
import { portfolioApi } from '@/service/portfolioApi';
import { alertApi } from '@/service/alertApi';

const props = defineProps({
  ownerAuthenticated: { type: Boolean, default: false },
  // 登入首頁自動補抓完成後由 HomeView 遞增（docs/19.登入自動補抓資料/登入自動補抓資料_規劃書.md §3.6）。
  refreshKey: { type: Number, default: 0 }
});

const { isEnabled } = useHomeWidgets();
const { currentMarket } = useMarket();

const WIDGET_IDS = ['portfolio-kpi', 'holdings-top', 'watchlist-target', 'risk-alerts'];
const anyEnabled = computed(() => WIDGET_IDS.some((id) => isEnabled(id)));

// ── 每個 widget 各自的 loading／error／data，錯誤互相隔離 ────────────────
// reqId 遞增：快速切換市場時，較晚才回來的舊請求會被丟棄，不會蓋掉新市場的資料。
// 重抓時刻意不清 data，讓 HomeSectionCard 保留舊內容＋遮罩（硬性規則 #1）。
function isUnauthorized(err) {
  return (err?.status ?? err?.response?.status) === 401;
}

function createWidget(load, errorText) {
  const data = ref(null);
  const loading = ref(false);
  const error = ref(null);
  // 401＝登入已失效：不顯示錯誤，只安靜清掉私人資料並等 owner-auth-changed／HomeView 重新判定
  const unauthorized = ref(false);
  let reqId = 0;

  async function refresh() {
    const id = ++reqId;
    loading.value = true;
    error.value = null;
    try {
      const result = await load();
      if (id !== reqId) return;
      data.value = result;
      unauthorized.value = false;
    } catch (err) {
      if (id !== reqId) return;
      if (isUnauthorized(err)) {
        data.value = null;
        unauthorized.value = true;
      } else {
        error.value = errorText;
      }
    } finally {
      if (id === reqId) loading.value = false;
    }
  }

  // widget 被關掉或登出：作廢進行中的請求並清掉私人資料，之後重新開啟時走「第一次載入」骨架
  function reset() {
    reqId++;
    data.value = null;
    loading.value = false;
    error.value = null;
    unauthorized.value = false;
  }

  return { data, loading, error, unauthorized, refresh, reset };
}

const kpi = createWidget(async () => (await portfolioApi.getSummary()).data ?? null, '無法載入帳戶資料');
const holdings = createWidget(
  async () => {
    const market = currentMarket.value;
    return (await shareRequest(`holdings:${market}`, () => portfolioApi.getHoldings({ market }))).data ?? [];
  },
  '無法載入持股資料'
);
const watchlist = createWidget(
  async () => {
    const market = currentMarket.value;
    return (await shareRequest(`watchlist:${market}`, () => portfolioApi.getWatchlist({ market }))).data ?? [];
  },
  '無法載入到價提醒'
);
const risk = createWidget(
  async () =>
    (await alertApi.getAlerts({ market: currentMarket.value, days: 5, category: 'risk' })).data ?? [],
  '無法載入風控警示'
);

// ── 被關掉／未登入的 widget 不發請求；關→開會補抓 ─────────────────────────
const kpiActive = computed(() => props.ownerAuthenticated && isEnabled('portfolio-kpi'));
const holdingsActive = computed(() => props.ownerAuthenticated && isEnabled('holdings-top'));
const watchlistActive = computed(() => props.ownerAuthenticated && isEnabled('watchlist-target'));
const riskActive = computed(() => props.ownerAuthenticated && isEnabled('risk-alerts'));

// 帳戶層級 TWD 金額，不受市場切換影響，所以只跟 active 走
watch(kpiActive, (on) => (on ? kpi.refresh() : kpi.reset()), { immediate: true });

// 其餘三個依市場過濾，市場切換時重抓（immediate 涵蓋首次載入）
watch([holdingsActive, currentMarket], () => (holdingsActive.value ? holdings.refresh() : holdings.reset()), { immediate: true });
watch([watchlistActive, currentMarket], () => (watchlistActive.value ? watchlist.refresh() : watchlist.reset()), { immediate: true });
watch([riskActive, currentMarket], () => (riskActive.value ? risk.refresh() : risk.reset()), { immediate: true });

// 登入／登出完全交給 ownerAuthenticated 的 watch 處理，這裡刻意不監聽 owner-auth-changed：
// ownerApi.logout() 是「同步」派送該事件，此時 HomeView 的 whoami() 還沒回來、prop 仍是 true，
// 在事件裡直接重抓會對已登出的 session 送出一串註定 401 的請求。

// 補抓完成後的原地刷新（§3.6）：只重抓目前有啟用（active）的 widget，沿用既有 refresh()。
watch(
  () => props.refreshKey,
  () => {
    if (kpiActive.value) kpi.refresh();
    if (holdingsActive.value) holdings.refresh();
    if (watchlistActive.value) watchlist.refresh();
    if (riskActive.value) risk.refresh();
  }
);

// ── 顯示用轉換 ───────────────────────────────────────────────────────────
// 紅漲綠跌（全站一律，見 assets/project-style.css）；0 或空值不著色
function pnlClass(v) {
  if (v === null || v === undefined || v === 0) return 'text-surface-500';
  return v > 0 ? 'text-up' : 'text-down';
}

function fmtPrice(n) {
  if (n === null || n === undefined) return '—';
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function shortDate(d) {
  return d ? String(d).slice(5).replace('-', '/') : '';
}

function stockPath(market, symbol) {
  return `/stock/${market}/${encodeURIComponent(symbol)}`;
}

const kpiCards = computed(() => {
  const s = kpi.data.value;
  if (!s) return [];
  const noRealized = !s.realized_lots;
  return [
    {
      key: 'account',
      label: '帳戶總值（TWD）',
      value: fmtNum(s.account_value_twd),
      valueClass: 'text-surface-900 dark:text-surface-0',
      sub: `持股 ${fmtNum(s.portfolio_value_twd)} / 現金 ${fmtNum(s.cash_balance_twd)}`
    },
    {
      key: 'unrealized',
      label: '未實現損益',
      value: signed(s.unrealized_total_twd),
      valueClass: pnlClass(s.unrealized_total_twd),
      sub: fmtPct(s.unrealized_total_pct)
    },
    {
      key: 'realized',
      label: '已實現損益',
      value: signed(s.realized_total_twd),
      valueClass: pnlClass(s.realized_total_twd),
      sub: `交易 ${signed(s.realized_trade_total_twd)} / 股利 ${signed(s.realized_dividend_income_twd)}`
    },
    {
      key: 'winrate',
      label: '勝率',
      value: noRealized ? '—' : `${(s.win_rate || 0).toFixed(1)}%`,
      valueClass: 'text-surface-900 dark:text-surface-0',
      sub: noRealized ? '尚無已實現交易' : `${s.wins} 勝 / ${s.losses} 敗`
    }
  ];
});

const topHoldings = computed(() =>
  [...(holdings.data.value || [])].sort((a, b) => (b.weight_pct || 0) - (a.weight_pct || 0)).slice(0, 5)
);

// 已到價排最前，其餘依距目標價由近到遠
const targetHits = computed(() =>
  (watchlist.data.value || [])
    .filter((w) => w.is_reached || w.is_near_target)
    .sort((a, b) => Number(b.is_reached) - Number(a.is_reached) || Math.abs(a.gap_pct) - Math.abs(b.gap_pct))
);

// 後端已依 trade_date、timestamp 由新到舊排序，直接取前 5 筆
const riskRows = computed(() => (risk.data.value || []).slice(0, 5));
</script>
