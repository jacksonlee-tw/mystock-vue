<template>
  <!-- 首頁所有 widget 共用的卡片外殼（docs/18.個人化首頁/）。
       兩條 CLAUDE.md 硬性規則在這裡統一落實，各 panel 不必各自處理：
       #1 重新抓取（切換 tw/us）時保留舊內容原地掛載，只疊半透明遮罩＋spinner；只有「第一次載入且完全
          沒資料」才顯示骨架——把內容換成小轉圈會讓頁面高度塌陷、捲軸彈回頂端。
       #2 grid 內卡片一律 !m-0，中和 assets/layout/_utils.scss 的 .card:last-child margin 規則，
          讓同一列卡片等高。 -->
  <!-- !p-4／!rounded-2xl：legacy .card 的 padding／border-radius 與 Tailwind utility 同權重且後定義者勝
       （見 assets/project-style.css 對 .bg-up-soft 的說明），不加 ! 會被蓋成 2rem 內距，與 KPI 卡不一致。 -->
  <section class="card !m-0 relative !rounded-2xl border border-surface-200 dark:border-surface-700/80 bg-surface-0 dark:bg-surface-900 shadow-sm !p-4 flex flex-col min-w-0">
    <header class="flex items-center gap-2 mb-3">
      <i v-if="icon" :class="['pi', icon, 'text-primary']" aria-hidden="true"></i>
      <h3 class="text-sm font-bold text-surface-900 dark:text-surface-0 m-0">{{ title }}</h3>
      <slot name="header-extra" />
      <router-link
        v-if="to"
        :to="to"
        class="ml-auto text-xs font-bold text-primary hover:underline shrink-0 no-underline"
      >
        {{ linkLabel }} <i class="pi pi-arrow-right text-[10px]" aria-hidden="true"></i>
      </router-link>
    </header>

    <!-- 第一次載入、尚無任何資料：骨架 -->
    <div v-if="loading && !hasData" class="space-y-2 py-1" aria-busy="true">
      <div class="h-4 rounded bg-surface-100 dark:bg-surface-800 animate-pulse"></div>
      <div class="h-4 w-4/5 rounded bg-surface-100 dark:bg-surface-800 animate-pulse"></div>
      <div class="h-4 w-3/5 rounded bg-surface-100 dark:bg-surface-800 animate-pulse"></div>
    </div>

    <!-- 失敗且沒有舊資料可顯示 -->
    <div v-else-if="error && !hasData" class="text-sm text-surface-500 py-3 flex flex-col items-start gap-2">
      <span><i class="pi pi-exclamation-circle text-amber-500 mr-1" aria-hidden="true"></i>{{ error }}</span>
      <button type="button" class="text-xs font-bold text-primary hover:underline" @click="emit('retry')">重試</button>
    </div>

    <!-- 載入完成但沒有內容 -->
    <div v-else-if="empty" class="text-sm text-surface-400 py-4 text-center">
      {{ emptyText }}
      <!-- 切換市場重抓期間給一點回饋，避免空狀態畫面完全靜止 -->
      <i v-if="loading" class="pi pi-spin pi-spinner ml-1" aria-hidden="true"></i>
    </div>

    <!-- 有資料：內容原地保留，重新抓取時只疊遮罩 -->
    <div v-else class="relative flex-1 min-w-0">
      <slot />
      <div
        v-if="loading"
        class="absolute inset-0 rounded-lg bg-surface-0/60 dark:bg-surface-900/60 flex items-center justify-center"
        aria-busy="true"
      >
        <i class="pi pi-spin pi-spinner text-surface-500" aria-hidden="true"></i>
      </div>
      <p v-if="error" class="text-[11px] text-amber-600 dark:text-amber-400 mt-2 mb-0">
        重新整理失敗，顯示的是上一次的資料
      </p>
    </div>
  </section>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  icon: { type: String, default: '' }, // 例如 'pi-bell'
  to: { type: [String, Object], default: null }, // 右上「前往完整頁面」連結
  linkLabel: { type: String, default: '查看全部' },
  loading: { type: Boolean, default: false },
  error: { type: String, default: null },
  // hasData：slot 有東西可以渲染（即使是上一次的舊資料）。決定「骨架」與「保留舊內容＋遮罩」的分界。
  hasData: { type: Boolean, default: false },
  // empty：資料已載入但查無內容，改顯示 emptyText
  empty: { type: Boolean, default: false },
  emptyText: { type: String, default: '目前沒有資料' }
});
const emit = defineEmits(['retry']);
</script>
