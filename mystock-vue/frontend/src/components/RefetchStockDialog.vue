<template>
  <Dialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    modal
    header="重新抓取歷史資料"
    :style="{ width: '28rem' }"
    :draggable="false"
  >
    <div class="space-y-5">
      <!-- 目標股票 -->
      <div class="flex items-center gap-3">
        <div class="w-12 h-12 shrink-0 rounded-lg bg-primary-100 dark:bg-primary-900/40 text-primary font-black flex items-center justify-center text-sm">
          {{ stockId }}
        </div>
        <div class="min-w-0">
          <div class="font-black text-surface-900 dark:text-surface-0 text-lg leading-tight">
            {{ stockId }}
          </div>
          <div v-if="stockName" class="text-sm font-bold text-primary leading-snug break-words">
            {{ stockName }}
          </div>
        </div>
      </div>

      <!-- 缺漏提示 -->
      <div
        v-if="missingDays > 0"
        class="flex items-start gap-2 text-xs font-semibold text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800/60 rounded-xl px-3 py-2.5"
      >
        <i class="pi pi-exclamation-triangle mt-0.5"></i>
        <span>偵測到 {{ missingDays }} 天缺少價格資料，請選擇足以涵蓋該區間的範圍。</span>
      </div>

      <!-- 抓取區間 -->
      <div class="space-y-2">
        <label class="block text-xs font-bold text-surface-600 dark:text-surface-400">抓取區間</label>
        <div class="flex items-center gap-0.5 bg-surface-100 dark:bg-surface-800 p-0.5 rounded-lg border border-surface-200 dark:border-surface-700">
          <button
            v-for="m in monthOptions"
            :key="m.value"
            @click="selectedMonths = m.value"
            :class="[
              'flex-1 px-2.5 py-1.5 text-xs font-bold rounded-md transition-all duration-150',
              selectedMonths === m.value
                ? 'bg-primary text-primary-contrast shadow-sm'
                : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
            ]"
          >
            {{ m.label }}
          </button>
        </div>
        <p class="text-xs text-surface-500 leading-relaxed">
          將忽略既有資料，以完整區間重新向 {{ exchangeLabel }} 抓取行情與籌碼並補齊缺漏。
          區間越長耗時越久，執行期間無法觸發其他同步任務。
        </p>
      </div>
    </div>

    <template #footer>
      <button
        @click="$emit('update:visible', false)"
        class="px-4 py-2 text-sm font-bold text-surface-600 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-800 rounded-xl transition-colors"
      >
        取消
      </button>
      <button
        @click="confirm"
        :disabled="busy"
        class="px-4 py-2 text-sm font-bold bg-primary text-primary-contrast hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl flex items-center gap-1.5 transition-colors shadow-sm"
      >
        <i :class="['pi', busy ? 'pi-spin pi-spinner' : 'pi-refresh']"></i>
        開始重新抓取
      </button>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  stockId: { type: String, default: '' },
  stockName: { type: String, default: '' },
  market: { type: String, default: 'tw' },
  missingDays: { type: Number, default: 0 },
  busy: { type: Boolean, default: false }
});

const emit = defineEmits(['update:visible', 'confirm']);

const monthOptions = [
  { label: '1 個月', value: 1 },
  { label: '3 個月', value: 3 },
  { label: '6 個月', value: 6 },
  { label: '12 個月', value: 12 }
];

const selectedMonths = ref(3);

const exchangeLabel = ref('TWSE');
watch(
  () => props.market,
  (market) => {
    exchangeLabel.value = market === 'us' ? 'NASDAQ' : 'TWSE';
  },
  { immediate: true }
);

// 每次開啟時重設；有缺漏時預設拉長到 6 個月以便涵蓋較久遠的破洞
watch(
  () => props.visible,
  (isOpen) => {
    if (isOpen) selectedMonths.value = props.missingDays > 0 ? 6 : 3;
  }
);

function confirm() {
  emit('confirm', { stockId: props.stockId, months: selectedMonths.value });
}
</script>
