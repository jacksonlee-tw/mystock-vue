<template>
  <button
    type="button"
    :title="inList ? `已加入追蹤／觀察：${symbol}（點擊編輯）` : `加入追蹤／觀察：${symbol}`"
    class="watchlist-star-btn inline-flex items-center justify-center rounded-lg transition-colors"
    :class="[sizeClass, inList
      ? 'text-amber-500 bg-amber-50 dark:bg-amber-500/10 hover:text-amber-600'
      : 'text-surface-400 hover:text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-500/10']"
    @click.stop="onClick"
  >
    <i class="pi pi-eye" :class="iconSizeClass"></i>
  </button>
</template>

<script setup>
import { computed, watchEffect } from 'vue';
import { useWatchlistQuickAdd } from '@/composables/useWatchlistQuickAdd';
import { useTrackingList } from '@/composables/useTrackingList';

const props = defineProps({
  market: { type: String, required: true },
  symbol: { type: String, required: true },
  name: { type: String, default: '' },
  price: { type: Number, default: null },
  size: { type: String, default: 'md' } // sm | md
});

const { openQuickAdd } = useWatchlistQuickAdd();
const { has, get, ensureLoaded } = useTrackingList();

// 依 market 載入該市場的清單快取，切換市場時（例如同一元件在不同 market 下重用）自動補載
watchEffect(() => {
  ensureLoaded(props.market);
});

const inList = computed(() => has(props.market, props.symbol));

const sizeClass = computed(() => (props.size === 'sm' ? 'w-6 h-6' : 'w-8 h-8'));
const iconSizeClass = computed(() => (props.size === 'sm' ? 'text-xs' : 'text-sm'));

function onClick() {
  const existing = get(props.market, props.symbol);
  if (existing) {
    // 已在清單中：改開編輯模式，帶入既有的目標價/原因/標籤，而不是再新增一筆
    openQuickAdd({
      market: props.market,
      symbol: props.symbol,
      name: props.name || existing.name,
      price: props.price,
      note: existing.note || '',
      tags: (existing.tags || []).map((t) => t.name),
      editId: existing.id
    });
  } else {
    openQuickAdd({ market: props.market, symbol: props.symbol, name: props.name, price: props.price });
  }
}
</script>
