<template>
  <div v-if="explanation" class="border-t border-surface-100 dark:border-surface-800" :class="compact ? 'mt-3' : 'mt-5 pt-4 space-y-3'">
    
    <!-- 收合版 (Compact) -->
    <div v-if="compact" class="flex flex-col">
      <button 
        @click.stop="isExpanded = !isExpanded" 
        class="flex items-center gap-1.5 py-2 text-xs font-bold text-surface-500 hover:text-primary transition-colors focus:outline-none"
      >
        <i :class="['pi text-[10px] transition-transform duration-200', isExpanded ? 'pi-chevron-down' : 'pi-chevron-right']"></i>
        了解此圖表
      </button>
      
      <div v-show="isExpanded" class="space-y-1.5 pb-2">
        <p class="text-[11px] text-surface-500 dark:text-surface-400 leading-relaxed"><span class="font-bold text-surface-600 dark:text-surface-300">定義　</span>{{ explanation.definition }}</p>
        <p class="text-[11px] text-surface-500 dark:text-surface-400 leading-relaxed"><span class="font-bold text-surface-600 dark:text-surface-300">用途　</span>{{ explanation.purpose }}</p>
        <p class="text-[11px] text-surface-500 dark:text-surface-400 leading-relaxed"><span class="font-bold text-surface-600 dark:text-surface-300">判讀　</span>{{ explanation.howToRead }}</p>
      </div>
    </div>
    
    <!-- 完整展開版 (非 Compact) -->
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
import { ref } from 'vue';

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

const isExpanded = ref(false);
</script>
