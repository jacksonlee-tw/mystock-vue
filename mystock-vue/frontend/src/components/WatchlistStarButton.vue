<template>
  <button
    type="button"
    :title="`加入觀察名單：${symbol}`"
    class="watchlist-star-btn inline-flex items-center justify-center rounded-lg transition-colors text-surface-400 hover:text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-500/10"
    :class="sizeClass"
    @click.stop="onClick"
  >
    <i class="pi pi-eye" :class="iconSizeClass"></i>
  </button>
</template>

<script setup>
import { computed } from 'vue';
import { useWatchlistQuickAdd } from '@/composables/useWatchlistQuickAdd';

const props = defineProps({
  market: { type: String, required: true },
  symbol: { type: String, required: true },
  name: { type: String, default: '' },
  price: { type: Number, default: null },
  size: { type: String, default: 'md' } // sm | md
});

const { openQuickAdd } = useWatchlistQuickAdd();

const sizeClass = computed(() => (props.size === 'sm' ? 'w-6 h-6' : 'w-8 h-8'));
const iconSizeClass = computed(() => (props.size === 'sm' ? 'text-xs' : 'text-sm'));

function onClick() {
  openQuickAdd({ market: props.market, symbol: props.symbol, name: props.name, price: props.price });
}
</script>
