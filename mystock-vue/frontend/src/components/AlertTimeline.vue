<template>
  <div class="space-y-3">
    <div
      v-for="alert in alerts"
      :key="alert.id"
      class="card rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 overflow-hidden"
    >
      <div class="flex items-center gap-3 p-4 cursor-pointer select-none" @click="toggle(alert.id)">
        <div class="w-9 h-9 rounded-lg bg-surface-100 dark:bg-surface-800 flex items-center justify-center shrink-0">
          <i class="pi text-base" :class="[visual(alert.direction).icon, visual(alert.direction).colorClass]"></i>
        </div>

        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="font-bold text-surface-900 dark:text-surface-0">{{ alert.stock_id }}</span>
            <span class="text-sm text-surface-500 truncate">{{ alert.stock_name }}</span>
            <Tag :value="strengthMeta(alert.signal_strength).label" :severity="strengthMeta(alert.signal_strength).severity" />
          </div>
          <div class="text-sm text-surface-600 dark:text-surface-400 mt-0.5 truncate">
            {{ alert.strategy_name }} · {{ formatDirection(alert.direction) }}
          </div>
        </div>

        <div class="text-right shrink-0">
          <div class="text-xs text-surface-400">{{ alert.trade_date }}</div>
          <div v-if="alert.details?.close" class="num font-bold" :class="visual(alert.direction).colorClass">
            {{ alert.details.close }}
          </div>
        </div>

        <i class="pi shrink-0 text-surface-400" :class="expanded.has(alert.id) ? 'pi-chevron-up' : 'pi-chevron-down'"></i>
      </div>

      <div v-if="expanded.has(alert.id)" class="px-4 pb-4 border-t border-surface-100 dark:border-surface-800 pt-3 space-y-3">
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
          <div v-for="(val, key) in alert.details" :key="key" class="bg-surface-50 dark:bg-surface-800 rounded-lg px-2 py-1.5">
            <div class="text-surface-400">{{ detailLabel(key) }}</div>
            <div class="font-semibold text-surface-800 dark:text-surface-200 num">{{ formatDetailValue(val) }}</div>
          </div>
        </div>

        <div v-if="alert.filters_passed?.length" class="flex flex-wrap items-center gap-1.5">
          <span class="text-xs text-surface-400">通過濾網：</span>
          <Tag v-for="f in alert.filters_passed" :key="f" :value="f" severity="info" />
        </div>

        <p v-if="alert.suggested_action" class="text-xs text-surface-700 dark:text-surface-300 bg-primary-50 dark:bg-primary-900/20 border border-primary-200 dark:border-primary-800 rounded-lg px-3 py-2">
          <i class="pi pi-lightbulb text-primary mr-1"></i>{{ alert.suggested_action }}
        </p>

        <button
          type="button"
          class="text-xs font-bold text-primary hover:underline flex items-center gap-1"
          @click.stop="goToChart(alert)"
        >
          <i class="pi pi-chart-line"></i> 跳轉至 K 線圖
        </button>
      </div>
    </div>

    <div v-if="!alerts.length" class="text-center py-12 text-surface-400 text-sm">
      <i class="pi pi-inbox text-3xl mb-2 block"></i>
      目前沒有符合條件的警示
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { directionVisual, formatDirectionLabel, STRENGTH_META } from '@/utils/alertDirection';

defineProps({
  alerts: { type: Array, default: () => [] }
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
