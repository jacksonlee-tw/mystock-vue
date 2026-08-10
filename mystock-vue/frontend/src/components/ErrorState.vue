<template>
  <div class="flex flex-col items-center justify-center p-12 text-center gap-4">
    <!-- 圖示 -->
    <div :class="['w-16 h-16 rounded-full flex items-center justify-center', iconBg]">
      <i :class="['text-3xl', iconClass]"></i>
    </div>

    <!-- 標題與說明 -->
    <div>
      <h3 class="text-lg font-bold text-surface-800 dark:text-surface-100 mb-1">{{ title }}</h3>
      <p class="text-sm text-surface-500 dark:text-surface-400 max-w-sm">
        {{ displayMessage }}
      </p>
    </div>

    <!-- 操作按鈕 -->
    <div class="flex gap-2 mt-2">
      <button
        v-if="primaryAction"
        @click="primaryAction.handler"
        class="px-4 py-2 text-sm font-semibold rounded-lg bg-primary text-primary-contrast hover:opacity-90 transition-opacity"
      >
        <i v-if="primaryAction.icon" :class="['pi mr-1.5', primaryAction.icon]"></i>
        {{ primaryAction.label }}
      </button>
      <button
        v-if="secondaryAction"
        @click="secondaryAction.handler"
        class="px-4 py-2 text-sm font-semibold rounded-lg border border-surface-300 dark:border-surface-600 text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
      >
        <i v-if="secondaryAction.icon" :class="['pi mr-1.5', secondaryAction.icon]"></i>
        {{ secondaryAction.label }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRouter } from 'vue-router';

const props = defineProps({
  /** error 物件：{ code, message, details? } */
  error: {
    type: Object,
    default: () => ({ code: 'INTERNAL_ERROR', message: '發生未知錯誤' })
  },
  /** 覆寫重試函式 */
  onRetry: { type: Function, default: null }
});

const router = useRouter();

// 每個錯誤碼對應的顯示設定
const ERROR_CONFIG = {
  SYMBOL_NOT_FOUND: {
    icon: 'pi-search',
    iconBg: 'bg-amber-100 dark:bg-amber-900/30',
    iconClass: 'pi-search text-amber-600 dark:text-amber-400',
    title: '找不到此代號',
    defaultMessage: '查無對應的股票資料，請確認代號是否正確。',
    primary: { label: '搜尋股票', icon: 'pi-search', action: 'search' },
    secondary: { label: '返回首頁', icon: 'pi-home', action: 'home' }
  },
  MARKET_NOT_FOUND: {
    icon: 'pi-globe',
    iconBg: 'bg-red-100 dark:bg-red-900/30',
    iconClass: 'pi-globe text-red-600 dark:text-red-400',
    title: '市場代碼無效',
    defaultMessage: '請求的市場代碼不存在，已為您導向首頁。',
    primary: { label: '返回首頁', icon: 'pi-home', action: 'home' }
  },
  INVALID_MARKET_INDICATOR: {
    icon: 'pi-ban',
    iconBg: 'bg-blue-100 dark:bg-blue-900/30',
    iconClass: 'pi-ban text-blue-600 dark:text-blue-400',
    title: '此市場不提供此分析',
    defaultMessage: '您請求的指標或分析頁面在此市場尚不支援。',
    primary: { label: '返回', icon: 'pi-arrow-left', action: 'back' },
    secondary: { label: '前往首頁', icon: 'pi-home', action: 'home' }
  },
  FETCH_IN_PROGRESS: {
    icon: 'pi-spin pi-spinner',
    iconBg: 'bg-primary/10',
    iconClass: 'pi-spin pi-spinner text-primary',
    title: '同步進行中',
    defaultMessage: '資料同步任務正在執行，請稍候再試。'
  },
  SYMBOL_UNRESOLVED: {
    icon: 'pi-exclamation-triangle',
    iconBg: 'bg-amber-100 dark:bg-amber-900/30',
    iconClass: 'pi-exclamation-triangle text-amber-600 dark:text-amber-400',
    title: '代號無法驗證',
    defaultMessage: '此代號存在於設定中，但資料來源無法確認。',
    primary: { label: '前往管理頁', icon: 'pi-cog', action: 'manage' }
  },
  UPSTREAM_ERROR: {
    icon: 'pi-wifi',
    iconBg: 'bg-red-100 dark:bg-red-900/30',
    iconClass: 'pi-wifi text-red-600 dark:text-red-400',
    title: '資料源暫時無法連線',
    defaultMessage: '外部資料來源回應異常，顯示最後快取資料。如問題持續請稍後再試。',
    primary: { label: '重試', icon: 'pi-refresh', action: 'retry' }
  },
  INTERNAL_ERROR: {
    icon: 'pi-exclamation-circle',
    iconBg: 'bg-red-100 dark:bg-red-900/30',
    iconClass: 'pi-exclamation-circle text-red-600 dark:text-red-400',
    title: '系統發生錯誤',
    defaultMessage: '伺服器發生未預期的錯誤，請重新整理頁面。',
    primary: { label: '重新整理', icon: 'pi-refresh', action: 'reload' }
  }
};

const config = computed(() =>
  ERROR_CONFIG[props.error?.code] || ERROR_CONFIG.INTERNAL_ERROR
);

const iconBg = computed(() => config.value.iconBg);
const iconClass = computed(() => config.value.iconClass);
const title = computed(() => config.value.title);
const displayMessage = computed(() => props.error?.message || config.value.defaultMessage);

function resolveAction(actionDef) {
  if (!actionDef) return null;
  const actionMap = {
    home:   () => router.push('/'),
    back:   () => router.back(),
    reload: () => window.location.reload(),
    retry:  () => props.onRetry?.(),
    search: () => document.dispatchEvent(new CustomEvent('mystock:open-search')),
    manage: () => router.push('/stocks')
  };
  return {
    label: actionDef.label,
    icon: actionDef.icon,
    handler: actionMap[actionDef.action] || (() => router.push('/'))
  };
}

const primaryAction = computed(() => resolveAction(config.value.primary));
const secondaryAction = computed(() => resolveAction(config.value.secondary));
</script>

