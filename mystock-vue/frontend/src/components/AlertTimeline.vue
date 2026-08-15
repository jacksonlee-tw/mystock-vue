<template>
  <div class="space-y-6">
    <div v-for="group in groupedAlerts" :key="group.date" class="space-y-3">
      <!-- 日期分隔標頭：把清單依交易日分段，最新一天特別標示，方便一眼掃到最新訊號 -->
      <div class="flex items-center gap-2">
        <div class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700">
          <i class="pi pi-calendar text-primary text-sm"></i>
          <span class="text-sm font-black text-surface-700 dark:text-surface-200">{{ formatDateHeader(group.date) }}</span>
          <span v-if="group.isLatest" class="px-1.5 py-0.5 text-[10px] font-black bg-primary text-primary-contrast rounded-full">最新</span>
        </div>
        <span class="text-xs text-surface-400">{{ group.alerts.length }} 筆</span>
      </div>

      <div
        v-for="alert in group.alerts"
        :key="alert.id"
        class="card rounded-xl border overflow-hidden"
        :class="cardHighlightClass(alert)"
      >
        <div class="flex items-center gap-3 p-4 cursor-pointer select-none" @click="toggle(alert.id)">
          <div class="w-11 h-11 rounded-xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center shrink-0 relative">
            <i class="pi text-lg" :class="[visual(alert.direction).icon, visual(alert.direction).colorClass]"></i>
            <i
              v-if="alert.signal_strength === 'strong'"
              class="pi pi-star-fill text-[10px] text-amber-500 absolute -top-1.5 -right-1.5 bg-surface-0 dark:bg-surface-900 rounded-full p-0.5"
              title="重要訊號"
            ></i>
          </div>

          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-black text-lg text-surface-900 dark:text-surface-0">{{ alert.stock_id }}</span>
              <span class="text-base text-surface-500 truncate">{{ alert.stock_name }}</span>
              <Tag :value="strengthMeta(alert.signal_strength).label" :severity="strengthMeta(alert.signal_strength).severity" :class="alert.signal_strength === 'strong' ? 'p-tag-lg' : ''" />
              <span
                v-if="alert.signal_type"
                class="px-1.5 py-0.5 text-[10px] font-black rounded"
                :class="alert.signal_type === 'BUY' ? 'bg-up-soft text-up' : 'bg-down-soft text-down'"
              >
                {{ alert.signal_type }}
              </span>
            </div>
            <div class="text-base text-surface-600 dark:text-surface-400 mt-0.5 truncate flex items-center gap-1.5">
              <i class="pi text-xs text-surface-400" :class="categoryIcon(alert)"></i>
              {{ alert.strategy_name }} · {{ formatDirection(alert.direction) }}
            </div>
          </div>

          <div class="text-right shrink-0">
            <div class="text-xs text-surface-400">{{ alert.trade_date }}</div>
            <div v-if="alert.details?.close !== undefined" class="num font-black text-lg" :class="visual(alert.direction).colorClass">
              {{ formatDetailValue(alert.details.close) }}
            </div>
          </div>

          <i class="pi shrink-0 text-surface-400" :class="expanded.has(alert.id) ? 'pi-chevron-up' : 'pi-chevron-down'"></i>
        </div>

        <div v-if="expanded.has(alert.id)" class="px-4 pb-4 border-t border-surface-100 dark:border-surface-800 pt-3 space-y-3">
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-2 text-sm">
            <div v-for="(val, key) in alert.details" :key="key" class="bg-surface-50 dark:bg-surface-800 rounded-lg px-2 py-1.5">
              <div class="text-surface-400 text-xs">{{ detailLabel(key) }}</div>
              <div class="font-semibold text-surface-800 dark:text-surface-200 num">{{ formatDetailValue(val) }}</div>
            </div>
          </div>

          <div v-if="alert.filters_passed?.length" class="flex flex-wrap items-center gap-1.5">
            <span class="text-sm text-surface-400"><i class="pi pi-filter text-xs mr-1"></i>通過濾網：</span>
            <Tag v-for="f in alert.filters_passed" :key="f" :value="f" severity="info" />
          </div>

          <p v-if="alert.suggested_action" class="text-sm text-surface-700 dark:text-surface-300 bg-primary-50 dark:bg-primary-900/20 border border-primary-200 dark:border-primary-800 rounded-lg px-3 py-2">
            <i class="pi pi-lightbulb text-primary mr-1"></i>{{ alert.suggested_action }}
          </p>

          <button
            v-if="showChartLink"
            type="button"
            class="text-sm font-bold text-primary hover:underline flex items-center gap-1"
            @click.stop="goToChart(alert)"
          >
            <i class="pi pi-chart-line"></i> 跳轉至 K 線圖
          </button>
        </div>
      </div>
    </div>

    <div v-if="!alerts.length" class="text-center py-12 text-surface-400 text-base">
      <i class="pi pi-inbox text-3xl mb-2 block"></i>
      目前沒有符合條件的警示
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { directionVisual, formatDirectionLabel, STRENGTH_META } from '@/utils/alertDirection';
import { categoryMeta } from '@/utils/alertCategory';

const props = defineProps({
  alerts: { type: Array, default: () => [] },
  strategyList: { type: Array, default: () => [] },
  // 個股頁面內嵌顯示時（StockAlertsPanel）本來就已經在該股票的圖表頁，不需要再顯示自我導航的連結
  showChartLink: { type: Boolean, default: true }
});

const router = useRouter();
const expanded = ref(new Set());

function toggle(id) {
  const next = new Set(expanded.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  expanded.value = next;
}

function visual(direction) {
  return directionVisual(direction);
}
function formatDirection(direction) {
  return formatDirectionLabel(direction);
}
function strengthMeta(strength) {
  return STRENGTH_META[strength] || STRENGTH_META.weak;
}

// strategy_id -> category 對照表，供清單項目顯示策略分類圖示用
const categoryByStrategyId = computed(() => Object.fromEntries(props.strategyList.map((s) => [s.id, s.category])));
function categoryIcon(alert) {
  return categoryMeta(categoryByStrategyId.value[alert.strategy_id]).icon;
}

// 依交易日分組並依日期新到舊排序；最新一組加註「最新」標籤
const groupedAlerts = computed(() => {
  const byDate = new Map();
  for (const alert of props.alerts) {
    const key = alert.trade_date || '未知日期';
    if (!byDate.has(key)) byDate.set(key, []);
    byDate.get(key).push(alert);
  }
  const dates = Array.from(byDate.keys()).sort((a, b) => (a < b ? 1 : a > b ? -1 : 0));
  return dates.map((date, idx) => ({ date, alerts: byDate.get(date), isLatest: idx === 0 }));
});

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];
function formatDateHeader(dateStr) {
  const d = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(d.getTime())) return dateStr;
  return `${dateStr}（週${WEEKDAYS[d.getDay()]}）`;
}

// 重要訊號（強度＝強）用左側粗邊框＋柔和底色 HIGHLIGHT，一眼跟其他項目區隔開
function cardHighlightClass(alert) {
  if (alert.signal_strength !== 'strong') {
    return 'border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900';
  }
  const isUp = visual(alert.direction).colorClass === 'text-up';
  return isUp ? 'border-l-4 border-up bg-up-soft' : 'border-l-4 border-down bg-down-soft';
}

const DETAIL_LABELS = {
  close: '收盤價',
  ma_period: '均線天數',
  ma_value: '均線值',
  bias_percent: '乖離率(%)',
  short_period: '短均線天數',
  long_period: '長均線天數',
  short_ma: '短均線值',
  long_ma: '長均線值',
  upper_ma: '突破均線值',
  ma_periods: '均線組合',
  squeeze_min_days: '糾結天數',
  distance_percent: '距離均線(%)',
  values: '各均線數值'
};
function detailLabel(key) {
  return DETAIL_LABELS[key] || key;
}
function formatDetailValue(val) {
  if (Array.isArray(val)) return val.join('、');
  if (val && typeof val === 'object') return Object.entries(val).map(([k, v]) => `${k}: ${v}`).join('、');
  if (typeof val === 'number') return Number.isInteger(val) ? String(val) : val.toFixed(2);
  return val ?? '-';
}

function goToChart(alert) {
  router.push(`/stock/${alert.market}/${alert.stock_id}`);
}
</script>
