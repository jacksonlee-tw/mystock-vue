<template>
  <!-- 首頁「訊號與推薦」區：今日警示摘要／策略選股推薦／AI 戰情室評等（docs/18.個人化首頁/）。
       三個 widget 全關時（或戰情室因未登入而不顯示）整個 v-if 不渲染，不留下空的外層 DOM 與間距。
       卡片本身的 !m-0（硬性規則 #2）與「重抓保留舊內容」（硬性規則 #1）都由 HomeSectionCard 落實。 -->
  <div
    v-if="anyVisible"
    class="grid gap-4 grid-cols-[repeat(auto-fit,minmax(min(100%,18rem),1fr))] items-stretch"
  >
    <!-- 今日警示摘要 -->
    <HomeSectionCard
      v-if="alertsVisible"
      title="今日警示摘要"
      icon="pi-bell"
      to="/alerts"
      link-label="警示中心"
      :loading="alerts.loading"
      :error="alerts.error"
      :has-data="!!alerts.data"
      :empty="!!alerts.data && alerts.data.summary.total_alerts === 0"
      empty-text="最新交易日沒有警示訊號"
      @retry="alerts.refresh()"
    >
      <div v-if="alerts.data" class="space-y-3">
        <div class="flex items-end justify-between gap-2">
          <div>
            <div class="text-[11px] text-surface-400">掃描日 {{ alerts.data.summary.scan_date }}</div>
            <div class="num text-3xl font-black text-surface-900 dark:text-surface-0 leading-none mt-1">
              {{ alerts.data.summary.total_alerts }}
              <span class="text-xs font-bold text-surface-500">筆警示</span>
            </div>
          </div>
          <div class="flex gap-2 text-xs font-bold shrink-0">
            <span class="px-2 py-1 rounded-lg bg-up-soft text-up">
              偏多 <span class="num">{{ alerts.data.summary.by_direction?.bullish ?? 0 }}</span>
            </span>
            <span class="px-2 py-1 rounded-lg bg-down-soft text-down">
              偏空 <span class="num">{{ alerts.data.summary.by_direction?.bearish ?? 0 }}</span>
            </span>
          </div>
        </div>

        <ul class="space-y-2 m-0 p-0 list-none">
          <li v-for="s in topStrategies" :key="s.id" class="min-w-0">
            <div class="flex items-center justify-between gap-2 text-xs">
              <span class="truncate text-surface-700 dark:text-surface-300" :title="s.name">{{ s.name }}</span>
              <span class="num font-bold text-surface-900 dark:text-surface-0 shrink-0">{{ s.count }}</span>
            </div>
            <div class="h-1.5 rounded-full bg-surface-100 dark:bg-surface-800 mt-1 overflow-hidden">
              <div class="h-full rounded-full bg-primary" :style="{ width: s.pct + '%' }"></div>
            </div>
          </li>
        </ul>
      </div>
    </HomeSectionCard>

    <!-- 策略選股推薦 -->
    <HomeSectionCard
      v-if="pickingVisible"
      :title="pickingCfg.title"
      :icon="pickingCfg.icon"
      :to="pickingCfg.to"
      :link-label="pickingCfg.linkLabel"
      :loading="picking.loading"
      :error="picking.error"
      :has-data="!!picking.data"
      :empty="!!picking.data && pickRows.length === 0"
      :empty-text="pickingCfg.emptyText"
      @retry="picking.refresh()"
    >
      <ul class="m-0 p-0 list-none divide-y divide-surface-100 dark:divide-surface-800">
        <li v-for="row in pickRows" :key="row.stockId">
          <router-link
            :to="`/stock/${row.market}/${row.stockId}`"
            class="flex items-center gap-2 py-2 no-underline rounded hover:bg-surface-50 dark:hover:bg-surface-800/60 min-w-0"
          >
            <div class="min-w-0 flex-1">
              <div class="flex items-baseline gap-1.5 min-w-0">
                <span class="num text-sm font-black text-surface-900 dark:text-surface-0 shrink-0">{{ row.stockId }}</span>
                <span class="text-sm text-surface-600 dark:text-surface-300 truncate">{{ row.stockName }}</span>
              </div>
              <div class="text-[11px] text-surface-500 truncate" :title="row.strategyNames.join('、')">
                <span v-if="row.strategyNames.length > 1" class="font-bold text-primary">{{ row.strategyNames.length }} 策略 · </span>{{ row.strategyNames.join('、') }}
              </div>
            </div>
            <span
              class="shrink-0 px-1.5 py-0.5 text-[10px] font-black rounded"
              :class="strengthMeta(row.strength).cls"
            >{{ strengthMeta(row.strength).label }}</span>
          </router-link>
        </li>
      </ul>
    </HomeSectionCard>

    <!-- AI 戰情室評等（需 owner 登入） -->
    <HomeSectionCard
      v-if="warVisible"
      title="AI 戰情室評等"
      icon="pi-shield"
      to="/war-room"
      link-label="戰情室"
      :loading="war.loading"
      :error="war.error"
      :has-data="!!war.data"
      :empty="warEmpty"
      :empty-text="warEmptyText"
      @retry="war.refresh()"
    >
      <div v-if="war.data" class="space-y-3">
        <div class="grid grid-cols-3 gap-2 text-center">
          <div class="rounded-lg bg-up-soft py-2">
            <div class="num text-xl font-black text-up leading-none">{{ verdictCounts.bullish }}</div>
            <div class="text-[11px] font-bold text-up mt-1">看多</div>
          </div>
          <div class="rounded-lg bg-surface-100 dark:bg-surface-800 py-2">
            <div class="num text-xl font-black text-surface-700 dark:text-surface-200 leading-none">{{ verdictCounts.neutral }}</div>
            <div class="text-[11px] font-bold text-surface-500 mt-1">中立</div>
          </div>
          <div class="rounded-lg bg-down-soft py-2">
            <div class="num text-xl font-black text-down leading-none">{{ verdictCounts.bearish }}</div>
            <div class="text-[11px] font-bold text-down mt-1">看空</div>
          </div>
        </div>

        <div class="text-xs text-surface-500">
          已產生 <span class="num font-bold text-surface-800 dark:text-surface-200">{{ generatedCount }}</span>
          ／共 <span class="num font-bold text-surface-800 dark:text-surface-200">{{ war.data.items.length }}</span> 檔
          <span v-if="war.data.trade_date" class="text-surface-400"> · {{ war.data.trade_date }}</span>
        </div>

        <div v-if="hitRows.length" class="border-t border-surface-100 dark:border-surface-800 pt-2">
          <div class="text-[11px] font-bold text-surface-500 mb-1">
            已觸價 <span class="num">{{ hitTotal }}</span> 檔
          </div>
          <ul class="m-0 p-0 list-none">
            <li v-for="h in hitRows" :key="h.symbol">
              <router-link
                :to="`/stock/${h.market}/${h.symbol}`"
                class="flex items-center gap-2 py-1 no-underline rounded hover:bg-surface-50 dark:hover:bg-surface-800/60 min-w-0"
              >
                <span class="num text-sm font-black text-surface-900 dark:text-surface-0 shrink-0">{{ h.symbol }}</span>
                <span class="text-sm text-surface-600 dark:text-surface-300 truncate flex-1">{{ h.name }}</span>
                <span
                  class="shrink-0 px-1.5 py-0.5 text-[10px] font-black rounded"
                  :class="h.kind === 'target' ? 'bg-up-soft text-up' : 'bg-down-soft text-down'"
                >{{ h.kind === 'target' ? '達標價' : '觸停損' }}</span>
                <span class="num text-xs text-surface-500 shrink-0">{{ h.close }}</span>
              </router-link>
            </li>
          </ul>
        </div>
        <div v-else class="text-[11px] text-surface-400 border-t border-surface-100 dark:border-surface-800 pt-2">
          目前沒有個股觸及目標價或停損
        </div>
      </div>
    </HomeSectionCard>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue';
import HomeSectionCard from '@/components/home/HomeSectionCard.vue';
import { useHomeWidgets } from '@/composables/useHomeWidgets';
import { useMarket } from '@/composables/useMarket';
import { alertApi } from '@/service/alertApi';
import { aiAnalysisApi } from '@/service/aiAnalysisApi';

const props = defineProps({
  ownerAuthenticated: { type: Boolean, default: false }
});

const { isEnabled } = useHomeWidgets();
const { currentMarket } = useMarket();

// 推薦來源依市場而異：選股策略（category=stock_picking）在 strategy_config/strategies.yaml 中皆為
// markets: ["tw"]，美股沒有這類策略。美股改用技術面的偏多（BUY）訊號當推薦——同一檔被多個技術策略
// 命中者排前面，沿用下方 pickRows 的合併排序，不另寫一套。
const PICKING_SOURCES = {
  tw: {
    category: 'stock_picking', buyOnly: false, title: '策略選股推薦', icon: 'pi-filter',
    to: '/picking', linkLabel: '策略選股清單', emptyText: '近 5 日沒有選股推薦'
  },
  us: {
    category: 'technical', buyOnly: true, title: '強勢技術訊號', icon: 'pi-chart-line',
    to: '/alerts', linkLabel: '策略警示看板', emptyText: '近 5 日沒有偏多技術訊號'
  }
};
// 標題以「資料所屬市場」為準而非 currentMarket：切換市場重抓期間舊內容仍在畫面上，標題要跟著內容走
const pickingCfg = computed(() => PICKING_SOURCES[picking.data?.market ?? currentMarket.value] || PICKING_SOURCES.tw);
const PICK_LIMIT = 8;
const STRENGTH_RANK = { strong: 3, moderate: 2, weak: 1 };

const alertsVisible = computed(() => isEnabled('alerts-summary'));
const pickingVisible = computed(() => isEnabled('stock-picking'));
// 需要 owner 的 widget：未登入時不渲染、也不發請求
const warVisible = computed(() => isEnabled('war-room') && props.ownerAuthenticated);
const anyVisible = computed(() => alertsVisible.value || pickingVisible.value || warVisible.value);

/**
 * 每個 widget 各自維護 data／loading／error，錯誤互相隔離。
 * - 用遞增的 request id 丟棄過期回應：快速切換 tw/us 時，慢的舊回應不可蓋掉新資料。
 * - 重抓時「不清 data」（硬性規則 #1）：HomeSectionCard 會保留舊內容並疊遮罩。
 * - 只有 widget 被關閉（inactive）時才清 data 並讓在途請求作廢——否則重新開啟時會先閃過
 *   上一個市場的舊資料。
 */
function createWidget(isActive, load) {
  const data = ref(null);
  const loading = ref(false);
  const error = ref(null);
  let requestId = 0;

  async function refresh() {
    if (!isActive()) return;
    const id = ++requestId;
    loading.value = true;
    error.value = null;
    try {
      const result = await load(currentMarket.value);
      if (id !== requestId) return;
      data.value = result;
    } catch (e) {
      if (id !== requestId) return;
      error.value = e?.message || '載入失敗';
    } finally {
      if (id === requestId) loading.value = false;
    }
  }

  function deactivate() {
    requestId++;
    data.value = null;
    loading.value = false;
    error.value = null;
  }

  // 市場切換、或 widget 從關→開，都走同一條路徑；immediate 負責首次掛載
  watch(
    () => [currentMarket.value, isActive()],
    () => (isActive() ? refresh() : deactivate()),
    { immediate: true }
  );

  return reactive({ data, loading, error, refresh });
}

// ── 今日警示摘要 ─────────────────────────────────────────────
const alerts = createWidget(
  () => alertsVisible.value,
  async (market) => {
    // 策略清單只用來把 id 轉成中文名稱，抓不到就退回顯示 id，不該讓整張卡失敗
    const [summaryRes, strategiesRes] = await Promise.all([
      alertApi.getAlertsSummary({ market }),
      alertApi.getStrategies(market).catch(() => null)
    ]);
    const names = {};
    for (const s of strategiesRes?.data || []) names[s.id] = s.name;
    return { summary: summaryRes.data || {}, names };
  }
);

const topStrategies = computed(() => {
  if (!alerts.data) return [];
  const entries = Object.entries(alerts.data.summary.by_strategy || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);
  const max = entries[0]?.[1] || 1;
  return entries.map(([id, count]) => ({
    id,
    name: alerts.data.names[id] || id,
    count,
    pct: Math.max(4, Math.round((count / max) * 100))
  }));
});

// ── 策略選股推薦 ─────────────────────────────────────────────
const picking = createWidget(
  () => pickingVisible.value,
  async (market) => {
    const src = PICKING_SOURCES[market];
    if (!src) return { market, alerts: [] };
    const res = await alertApi.getAlerts({ market, days: 5, category: src.category });
    const alerts = res.data || [];
    return { market, alerts: src.buyOnly ? alerts.filter((a) => a.signal_type === 'BUY') : alerts };
  }
);

function strengthMeta(strength) {
  if (strength === 'strong') return { label: '強', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300' };
  if (strength === 'moderate') return { label: '中', cls: 'bg-sky-100 text-sky-700 dark:bg-sky-500/20 dark:text-sky-300' };
  return { label: '弱', cls: 'bg-surface-100 text-surface-600 dark:bg-surface-800 dark:text-surface-300' };
}

// 同一檔被多個策略選中時合併成一列：命中策略數多→強度高→rank_value 小→最新 trade_date
const pickRows = computed(() => {
  if (!picking.data) return [];
  const byStock = new Map();
  for (const a of picking.data.alerts) {
    let row = byStock.get(a.stock_id);
    if (!row) {
      row = {
        stockId: a.stock_id,
        stockName: a.stock_name,
        market: a.market || picking.data.market,
        strategies: new Map(),
        strength: a.signal_strength,
        rank: Infinity,
        tradeDate: a.trade_date || ''
      };
      byStock.set(a.stock_id, row);
    }
    row.strategies.set(a.strategy_id, a.strategy_name || a.strategy_id);
    if ((STRENGTH_RANK[a.signal_strength] || 0) > (STRENGTH_RANK[row.strength] || 0)) row.strength = a.signal_strength;
    if (typeof a.rank_value === 'number' && a.rank_value < row.rank) row.rank = a.rank_value;
    if ((a.trade_date || '') > row.tradeDate) row.tradeDate = a.trade_date;
  }
  return [...byStock.values()]
    .map((r) => ({ ...r, strategyNames: [...r.strategies.values()] }))
    .sort(
      (a, b) =>
        b.strategyNames.length - a.strategyNames.length ||
        (STRENGTH_RANK[b.strength] || 0) - (STRENGTH_RANK[a.strength] || 0) ||
        a.rank - b.rank ||
        b.tradeDate.localeCompare(a.tradeDate)
    )
    .slice(0, PICK_LIMIT);
});

// ── AI 戰情室評等 ────────────────────────────────────────────
// 401 = 未登入：安靜處理成「尚未登入」的空狀態，不當成錯誤顯示
const warUnauthorized = ref(false);
const war = createWidget(
  () => warVisible.value,
  async (market) => {
    try {
      const res = await aiAnalysisApi.getWarRoom(market);
      warUnauthorized.value = false;
      return res.data || { items: [] };
    } catch (e) {
      if (e?.status === 401) {
        warUnauthorized.value = true;
        return null;
      }
      throw e;
    }
  }
);

const warEmpty = computed(() => warUnauthorized.value || (!!war.data && war.data.items.length === 0));
const warEmptyText = computed(() => (warUnauthorized.value ? '尚未登入' : '監控清單目前沒有標的'));

const verdictCounts = computed(() => {
  const counts = { bullish: 0, neutral: 0, bearish: 0 };
  for (const it of war.data?.items || []) {
    if (it.verdict in counts) counts[it.verdict]++;
  }
  return counts;
});
const generatedCount = computed(() => (war.data?.items || []).filter((it) => it.status === 'generated').length);

const hitAll = computed(() => {
  const out = [];
  for (const it of war.data?.items || []) {
    if (it.is_price_hit !== true) continue;
    const reachedTarget = it.target_price != null && it.close != null && it.close >= it.target_price;
    const hitStop = it.stop_loss != null && it.close != null && it.close <= it.stop_loss;
    if (!reachedTarget && !hitStop) continue;
    out.push({
      symbol: it.symbol,
      name: it.stock_name,
      market: it.market || currentMarket.value,
      close: it.close,
      kind: reachedTarget ? 'target' : 'stop'
    });
  }
  return out;
});
const hitTotal = computed(() => hitAll.value.length);
const hitRows = computed(() => hitAll.value.slice(0, 5));

// 登入／登出完全交給 ownerAuthenticated 的 watch 處理，刻意不監聽 owner-auth-changed：
// ownerApi.logout() 同步派送該事件時 prop 仍是 true，直接重抓會對已登出的 session 送出註定 401 的請求。
</script>
