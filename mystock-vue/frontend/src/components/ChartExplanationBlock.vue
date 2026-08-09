<template>
  <div v-if="explanation" :class="compact ? 'mt-3 pt-3 space-y-2' : 'mt-5 pt-4 space-y-3'" class="border-t border-surface-100 dark:border-surface-800">
    <div v-if="compact" class="space-y-1.5">
      <p class="text-xs text-surface-500 dark:text-surface-400 leading-relaxed"><span class="font-bold text-surface-600 dark:text-surface-300">定義　</span>{{ explanation.definition }}</p>
      <p class="text-xs text-surface-500 dark:text-surface-400 leading-relaxed"><span class="font-bold text-surface-600 dark:text-surface-300">用途　</span>{{ explanation.purpose }}</p>
      <p class="text-xs text-surface-500 dark:text-surface-400 leading-relaxed"><span class="font-bold text-surface-600 dark:text-surface-300">判讀　</span>{{ explanation.howToRead }}</p>
    </div>
    <div v-else class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div>
        <h4 class="text-xs font-bold tracking-wide uppercase text-surface-400 mb-1">定義</h4>
        <p class="text-sm text-surface-600 dark:text-surface-300 leading-relaxed">{{ explanation.definition }}</p>
      </div>
      <div>
        <h4 class="text-xs font-bold tracking-wide uppercase text-surface-400 mb-1">用途</h4>
        <p class="text-sm text-surface-600 dark:text-surface-300 leading-relaxed">{{ explanation.purpose }}</p>
      </div>
      <div>
        <h4 class="text-xs font-bold tracking-wide uppercase text-surface-400 mb-1">如何判讀</h4>
        <p class="text-sm text-surface-600 dark:text-surface-300 leading-relaxed">{{ explanation.howToRead }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  explanation: {
    type: Object,
    default: null
  },
  // compact：縮圖卡片用的單欄小字版；false：主圖／放大頁用的三欄版
  compact: {
    type: Boolean,
    default: false
  }
});
</script>
