<template>
  <!-- MyStock「K 線 M」標誌：三根 K 棒排出 M 字（兩側實心＝上漲、中間空心＝回檔），
       金色均線從左下穿過實體之間往右上。底色吃 PrimeVue 主題色，切換黃銅金／科技藍／墨綠會自動跟著換。
       variant：
         brand   — 主題色底＋白色 K 棒（一般淺色／深色頁面、favicon 同款）
         onbrand — 白底＋主題色 K 棒（放在主題色底上，例如 AppTopbar 的 --p-primary-500 頂列） -->
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 48 48"
    role="img"
    :aria-label="title"
    :class="['app-logo', `app-logo--${variant}`]"
  >
    <rect class="app-logo__tile" width="48" height="48" rx="12" />
    <polyline class="app-logo__trend" points="6,41 24,33.5 42,15" fill="none" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />
    <g class="app-logo__wick" stroke-width="2" stroke-linecap="round">
      <line x1="14" y1="8.5" x2="14" y2="39" />
      <line x1="24" y1="18" x2="24" y2="37.5" />
      <line x1="34" y1="6.5" x2="34" y2="36.5" />
    </g>
    <rect class="app-logo__candle" x="10.5" y="14" width="7" height="20" rx="1.6" />
    <rect class="app-logo__hollow" x="21" y="23" width="6" height="9" rx="1.4" stroke-width="2" />
    <rect class="app-logo__candle" x="30.5" y="11" width="7" height="21" rx="1.6" />
    <circle class="app-logo__trend-dot" cx="42" cy="15" r="2.6" />
  </svg>
</template>

<script setup>
defineProps({
  size: { type: [Number, String], default: 32 },
  variant: { type: String, default: 'brand' }, // 'brand' | 'onbrand'
  title: { type: String, default: 'MyStock' }
});
</script>

<style scoped>
.app-logo {
  flex-shrink: 0;
  display: block;
}

.app-logo--brand .app-logo__tile { fill: var(--p-primary-color); }
.app-logo--brand .app-logo__wick { stroke: #fff; }
.app-logo--brand .app-logo__candle { fill: #fff; }
.app-logo--brand .app-logo__hollow { fill: var(--p-primary-color); stroke: #fff; }
.app-logo--brand .app-logo__trend { stroke: #f3c969; }
.app-logo--brand .app-logo__trend-dot { fill: #f3c969; }

/* 放在主題色底上：底色反白，K 棒改吃主題色；金線加深一階，免得在白底上糊掉 */
.app-logo--onbrand .app-logo__tile { fill: #fff; }
.app-logo--onbrand .app-logo__wick { stroke: var(--p-primary-500); }
.app-logo--onbrand .app-logo__candle { fill: var(--p-primary-500); }
.app-logo--onbrand .app-logo__hollow { fill: #fff; stroke: var(--p-primary-500); }
.app-logo--onbrand .app-logo__trend { stroke: #d9a441; }
.app-logo--onbrand .app-logo__trend-dot { fill: #d9a441; }
</style>
