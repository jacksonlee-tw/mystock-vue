<template>
  <span class="inline-flex items-center">
    <button
      type="button"
      class="w-5 h-5 rounded-full inline-flex items-center justify-center text-surface-400 hover:text-primary hover:bg-primary-50 dark:hover:bg-primary-900/30 transition-colors shrink-0"
      title="策略規則說明"
      @click.stop="toggle"
    >
      <i class="pi pi-info-circle text-xs"></i>
    </button>
    <Popover ref="panelRef">
      <div v-if="strategy" class="max-w-sm space-y-2 text-sm" @click.stop>
        <div class="flex items-center gap-2 flex-wrap">
          <span class="font-black text-surface-900 dark:text-surface-0">{{ strategy.name }}</span>
          <Tag :value="strategy.scope === 'universe' ? '全市場選股池' : '追蹤清單'" :severity="strategy.scope === 'universe' ? 'info' : 'secondary'" class="text-xs scale-90" />
        </div>
        <p v-if="strategy.description" class="text-surface-600 dark:text-surface-400">{{ strategy.description }}</p>

        <div v-if="strategy.rule_summary?.length">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide mb-1">觸發條件</div>
          <ul class="list-disc list-inside space-y-0.5 text-surface-700 dark:text-surface-300">
            <li v-for="(line, i) in strategy.rule_summary" :key="i">{{ line }}</li>
          </ul>
        </div>

        <div v-if="strategy.filters_summary?.length">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide mb-1">加分濾網（只影響強度標籤，不影響是否觸發）</div>
          <ul class="list-disc list-inside space-y-0.5 text-surface-500">
            <li v-for="(line, i) in strategy.filters_summary" :key="i">{{ line }}</li>
          </ul>
        </div>

        <div v-if="strategy.cooldown_days != null || strategy.max_picks_per_day != null" class="flex items-center gap-3 pt-2 border-t border-surface-100 dark:border-surface-800 text-xs text-surface-400">
          <span v-if="strategy.cooldown_days != null">冷卻天數：{{ strategy.cooldown_days }} 天</span>
          <span v-if="strategy.max_picks_per_day != null">每日上限：{{ strategy.max_picks_per_day }} 檔</span>
        </div>
      </div>
      <div v-else class="text-sm text-surface-400">查無此策略設定</div>
    </Popover>
  </span>
</template>

<script setup>
import { ref } from 'vue';

defineProps({
  // 傳入 /api/v1/strategies 回傳的單筆策略物件（含 description/rule_summary/filters_summary）
  strategy: { type: Object, default: null }
});

const panelRef = ref(null);
function toggle(event) {
  panelRef.value?.toggle(event);
}
</script>
