<template>
  <!-- 「今日盤勢」區塊（docs/18.個人化首頁/）：總經燈號 + 大盤指數 + 追蹤清單今日表現。
       三個 widget 全關時整個根節點不渲染（v-if 讓 Vue 只留一個註解節點），不會在首頁留下多餘的間距。 -->
  <div v-if="anyEnabled" class="flex flex-col gap-4 min-w-0">
    <!-- 總經燈號：元件自己管 loading／error，位階跟著目前市場走（台股加權／美股 S&P 500）。被關掉就不掛載，因為掛載即會發請求。 -->
    <MacroDashboardBanner v-if="isEnabled('macro-banner')" />

    <!-- 大盤指數：每個指數一張等高小卡。
         硬性規則 #2：grid 卡片一律 !m-0，間距交給 gap；auto-fit 讓手機寬度自動折成 1～2 欄，不會橫向捲動。 -->
    <HomeSectionCard
      v-if="isEnabled('index-overview')"
      title="大盤指數"
      icon="pi-chart-bar"
      :loading="indexLoading"
      :error="indexError"
      :has-data="indexList !== null"
      :empty="indexList !== null && indexList.length === 0"
      empty-text="目前沒有指數資料"
      @retry="loadIndexOverview"
    >
      <div class="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(160px,1fr))]">
        <router-link
          v-for="idx in indexList"
          :key="idx.stock_id"
          :to="`/index/${idx.market || indexMarket}/${idx.stock_id}`"
          class="!m-0 h-full min-h-[104px] flex flex-col justify-between gap-2 rounded-xl border border-surface-200 dark:border-surface-700/80 bg-surface-50 dark:bg-surface-800/60 p-3 no-underline text-inherit transition-colors hover:border-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          <div class="text-xs font-bold text-surface-600 dark:text-surface-300 truncate">
            {{ idx.short_name || idx.stock_name }}
          </div>

          <div v-if="idx.has_data" class="flex items-end justify-between gap-2">
            <div class="min-w-0">
              <div class="num text-base font-black text-surface-900 dark:text-surface-0 truncate">
                {{ formatPrice(idx.latest_close) }}
              </div>
              <div class="num text-[11px] font-bold truncate" :class="changeClass(idx.change_percent)">
                {{ formatSigned(idx.change) }}（{{ formatSigned(idx.change_percent) }}%）
              </div>
            </div>
            <svg
              v-if="sparkPoints(idx.sparkline)"
              class="w-16 h-8 shrink-0"
              :class="changeClass(idx.change_percent)"
              viewBox="0 0 100 32"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <polyline
                :points="sparkPoints(idx.sparkline)"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linejoin="round"
                stroke-linecap="round"
                vector-effect="non-scaling-stroke"
              />
            </svg>
          </div>
          <div v-else class="text-sm text-surface-400">尚無資料</div>
        </router-link>
      </div>
    </HomeSectionCard>

    <!-- 追蹤清單今日表現：getHeatmapData 只回傳「追蹤中」的標的（不是全市場），所以語意是我的追蹤清單。 -->
    <HomeSectionCard
      v-if="isEnabled('watchlist-heatmap')"
      title="追蹤清單今日表現"
      icon="pi-th-large"
      to="/heatmap"
      link-label="完整熱力圖"
      :loading="heatmapLoading"
      :error="heatmapError"
      :has-data="heatmapStocks !== null"
      :empty="heatmapStocks !== null && heatmapStocks.length === 0"
      empty-text="尚無追蹤中的標的"
      @retry="loadHeatmap"
    >
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div v-for="col in columns" :key="col.key" class="min-w-0">
          <div class="text-xs font-bold mb-1.5" :class="col.titleClass">{{ col.title }}</div>
          <ul v-if="col.rows.length" class="list-none m-0 p-0 flex flex-col gap-1">
            <li v-for="s in col.rows" :key="`${s.market}:${s.stock_id}`">
              <router-link
                :to="`/stock/${s.market || heatmapMarket}/${s.stock_id}`"
                class="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 no-underline text-inherit hover:bg-surface-100 dark:hover:bg-surface-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
              >
                <span class="text-sm text-surface-800 dark:text-surface-100 truncate">
                  <span class="num font-bold">{{ s.stock_id }}</span>
                  <span class="ml-1.5 text-surface-500">{{ s.stock_name }}</span>
                </span>
                <span class="num text-sm font-bold shrink-0" :class="changeClass(s.change_percent)">
                  {{ formatSigned(s.change_percent) }}%
                </span>
              </router-link>
            </li>
          </ul>
          <div v-else class="text-sm text-surface-400 px-2 py-1.5">{{ col.emptyText }}</div>
        </div>
      </div>
    </HomeSectionCard>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import HomeSectionCard from '@/components/home/HomeSectionCard.vue';
import MacroDashboardBanner from '@/components/MacroDashboardBanner.vue';
import { indexApi } from '@/service/indexApi';
import { stockApi } from '@/service/stockApi';
import { useMarket } from '@/composables/useMarket';
import { useHomeWidgets } from '@/composables/useHomeWidgets';

const { currentMarket } = useMarket();
const { isEnabled } = useHomeWidgets();

const anyEnabled = computed(
  () => isEnabled('macro-banner') || isEnabled('index-overview') || isEnabled('watchlist-heatmap')
);

// ---------- 共用格式化 ----------
function isNum(v) {
  return v != null && Number.isFinite(Number(v));
}
// 紅漲綠跌全站統一（不依市場切換），零值或缺值用中性灰。
function changeClass(v) {
  if (!isNum(v) || Number(v) === 0) return 'text-surface-500';
  return Number(v) > 0 ? 'text-up' : 'text-down';
}
function formatPrice(v) {
  if (!isNum(v)) return '—';
  return Number(v).toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function formatSigned(v) {
  if (!isNum(v)) return '—';
  const n = Number(v);
  return `${n > 0 ? '+' : ''}${n.toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// ---------- 大盤指數 ----------
// indexList 用 null 表示「從未載入成功」：重抓時保留舊陣列不清空，HomeSectionCard 才會走「舊內容 + 遮罩」
// 而不是骨架（硬性規則 #1）。
const indexList = ref(null);
const indexMarket = ref(currentMarket.value);
const indexLoading = ref(false);
const indexError = ref(null);
let indexReqId = 0; // 遞增 id：快速切換市場時，丟棄較舊的回應

async function loadIndexOverview() {
  const reqId = ++indexReqId;
  const market = currentMarket.value;
  indexLoading.value = true;
  indexError.value = null;
  try {
    const res = await indexApi.getOverview('daily', market);
    if (reqId !== indexReqId) return;
    if (res.success) {
      indexList.value = res.data || [];
      indexMarket.value = market;
    } else {
      indexError.value = '無法載入大盤指數';
    }
  } catch {
    if (reqId !== indexReqId) return;
    indexError.value = '無法載入大盤指數';
  } finally {
    if (reqId === indexReqId) indexLoading.value = false;
  }
}

// 把 sparkline 收盤價正規化成 SVG polyline 座標（viewBox 100x32，上下留 2px 邊界）。
// 少於 2 個有效點就不畫；全部相同時畫水平線。
function sparkPoints(series) {
  const vals = (series || []).map(Number).filter((n) => Number.isFinite(n));
  if (vals.length < 2) return '';
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min;
  const step = 100 / (vals.length - 1);
  return vals
    .map((v, i) => {
      const y = span === 0 ? 16 : 30 - ((v - min) / span) * 28;
      return `${(i * step).toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
}

// ---------- 追蹤清單今日表現 ----------
const heatmapStocks = ref(null);
const heatmapMarket = ref(currentMarket.value);
const heatmapLoading = ref(false);
const heatmapError = ref(null);
let heatmapReqId = 0;

async function loadHeatmap() {
  const reqId = ++heatmapReqId;
  const market = currentMarket.value;
  heatmapLoading.value = true;
  heatmapError.value = null;
  try {
    const res = await stockApi.getHeatmapData('daily', market);
    if (reqId !== heatmapReqId) return;
    if (res.success) {
      heatmapStocks.value = res.data || [];
      heatmapMarket.value = market;
    } else {
      heatmapError.value = '無法載入追蹤清單表現';
    }
  } catch {
    if (reqId !== heatmapReqId) return;
    heatmapError.value = '無法載入追蹤清單表現';
  } finally {
    if (reqId === heatmapReqId) heatmapLoading.value = false;
  }
}

// 資料量可能上百檔，只在資料變動時排序一次（computed 快取）。缺 change_percent 的標的先過濾掉，
// 漲幅榜只收 >0、跌幅榜只收 <0，平盤不進任何一欄。
const columns = computed(() => {
  const valid = (heatmapStocks.value || []).filter((s) => isNum(s.change_percent));
  const gainers = valid
    .filter((s) => Number(s.change_percent) > 0)
    .sort((a, b) => b.change_percent - a.change_percent)
    .slice(0, 5);
  const losers = valid
    .filter((s) => Number(s.change_percent) < 0)
    .sort((a, b) => a.change_percent - b.change_percent)
    .slice(0, 5);
  return [
    { key: 'up', title: '漲幅前 5', titleClass: 'text-up', rows: gainers, emptyText: '今日沒有上漲的標的' },
    { key: 'down', title: '跌幅前 5', titleClass: 'text-down', rows: losers, emptyText: '今日沒有下跌的標的' }
  ];
});

// ---------- 抓取排程 ----------
// 每個 widget 一個 watcher：啟用狀態或市場任一變動就重抓（immediate 負責首次）。
// 被關掉時不發請求，並遞增 reqId 讓還在飛行中的回應作廢，避免關掉後又把 loading 狀態改回來。
watch(
  [() => isEnabled('index-overview'), currentMarket],
  ([enabled]) => {
    if (enabled) {
      loadIndexOverview();
    } else {
      indexReqId++;
      indexLoading.value = false;
    }
  },
  { immediate: true }
);

watch(
  [() => isEnabled('watchlist-heatmap'), currentMarket],
  ([enabled]) => {
    if (enabled) {
      loadHeatmap();
    } else {
      heatmapReqId++;
      heatmapLoading.value = false;
    }
  },
  { immediate: true }
);
</script>
