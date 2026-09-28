<template>
  <!-- 個人化首頁（docs/18.個人化首頁/）。本檔只做編排：決定哪些區塊要渲染、把登入狀態往下傳；
       各 panel 自己抓資料、自己管 loading／error，一張卡失敗不影響其他卡（比照 MacroDashboardBanner）。 -->
  <div class="home-page p-4 md:p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-2 m-0">
          <i class="pi pi-home text-primary text-xl" aria-hidden="true"></i>
          我的首頁
        </h1>
        <p class="text-sm text-surface-500 mt-1 mb-0">{{ todayText }}・{{ marketLabel }}</p>
      </div>
      <HomeWidgetSettings :owner-authenticated="ownerAuthenticated" />
    </div>

    <!-- 資料新鮮度狀態列（docs/19.登入自動補抓資料/）：只有擁有者登入時才掛載、才會發請求（AC-02）。
         v-if 本身即涵蓋「頁面載入時已登入」與「首頁完成登入後掛載」兩種觸發時機（AC-01/03），
         不需要另外監聽 owner-auth-changed。 -->
    <DataFreshnessBar v-if="ownerAuthenticated" @completed="onDataRefreshed" />

    <QuickFindPanel
      v-if="hasEnabledIn('快速查找', ownerAuthenticated)"
      :owner-authenticated="ownerAuthenticated"
      :refresh-key="refreshKey"
    />

    <section v-if="hasEnabledIn('今日盤勢', ownerAuthenticated)" aria-labelledby="home-market-pulse" class="space-y-3">
      <h2 id="home-market-pulse" class="text-sm font-bold text-surface-500 m-0">今日盤勢</h2>
      <MarketPulsePanel :refresh-key="refreshKey" />
    </section>

    <section v-if="hasEnabledIn('訊號與推薦', ownerAuthenticated)" aria-labelledby="home-signals" class="space-y-3">
      <h2 id="home-signals" class="text-sm font-bold text-surface-500 m-0">訊號與推薦</h2>
      <SignalsPanel :owner-authenticated="ownerAuthenticated" :refresh-key="refreshKey" />
    </section>

    <section v-if="showPositionsSection" aria-labelledby="home-positions" class="space-y-3">
      <h2 id="home-positions" class="text-sm font-bold text-surface-500 m-0">我的部位</h2>
      <MyPositionsPanel v-if="ownerAuthenticated" :owner-authenticated="ownerAuthenticated" :refresh-key="refreshKey" />
      <!-- 未登入：不發任何持股／觀察名單請求（避免一次打出一串註定 401 的呼叫），改顯示一張提示卡。
           authChecked 之前不顯示，避免「先閃一下登入提示、隨即被真實內容取代」。 -->
      <div
        v-else
        class="card !m-0 !rounded-2xl border border-dashed border-surface-300 dark:border-surface-600 bg-surface-0 dark:bg-surface-900 !p-4 flex flex-wrap items-center gap-3"
      >
        <i class="pi pi-lock text-surface-400 text-xl" aria-hidden="true"></i>
        <div class="flex-1 min-w-[12rem]">
          <p class="text-sm font-bold text-surface-900 dark:text-surface-0 m-0">登入後可顯示個人化內容</p>
          <p class="text-xs text-surface-500 mt-1 mb-0">持股損益、到價提醒、出場風控警示與 AI 戰情室評等需要先登入。</p>
        </div>
        <router-link
          :to="{ name: 'owner-login', query: { redirect: '/' } }"
          class="px-3 py-1.5 text-xs font-bold bg-primary text-primary-contrast rounded-lg no-underline"
        >
          前往登入
        </router-link>
      </div>
    </section>

    <!-- 全部 widget 都被取消勾選：給一個出口，而不是留下一頁空白 -->
    <div v-if="showEmpty" class="text-center text-sm text-surface-500 py-12">
      目前沒有顯示任何內容。點右上角「自訂版面」勾選想看的項目。
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useToast } from 'primevue/usetoast';
import { useMarket } from '@/composables/useMarket';
import { useHomeWidgets } from '@/composables/useHomeWidgets';
import { ownerApi } from '@/service/ownerApi';
import HomeWidgetSettings from '@/components/home/HomeWidgetSettings.vue';
import DataFreshnessBar from '@/components/home/DataFreshnessBar.vue';
import QuickFindPanel from '@/components/home/QuickFindPanel.vue';
import MarketPulsePanel from '@/components/home/MarketPulsePanel.vue';
import SignalsPanel from '@/components/home/SignalsPanel.vue';
import MyPositionsPanel from '@/components/home/MyPositionsPanel.vue';

const toast = useToast();

const { currentMarket, enabledMarkets } = useMarket();
const { hasEnabledIn, visibleCount, hasEnabledOwnerWidget } = useHomeWidgets();

const ownerAuthenticated = ref(false);
const authChecked = ref(false);

const todayText = new Date().toLocaleDateString('zh-TW', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' });
const marketLabel = computed(() => enabledMarkets.value.find((m) => m.code === currentMarket.value)?.label || currentMarket.value);

// 「我的部位」區塊：已登入看有沒有勾選的部位 widget；未登入則只要有任何需登入的 widget 被勾選，
// 就在這個位置顯示登入提示卡（authChecked 之前不顯示，避免先閃一下提示卡又被真實內容取代）。
const showPositionsSection = computed(() =>
  ownerAuthenticated.value
    ? hasEnabledIn('我的部位', true)
    : authChecked.value && hasEnabledOwnerWidget.value
);
const showEmpty = computed(
  () => authChecked.value && visibleCount(ownerAuthenticated.value) === 0 && !showPositionsSection.value
);

async function checkAuth() {
  ownerAuthenticated.value = await ownerApi.whoami();
  authChecked.value = true;
}

// 自動補抓完成（docs/19.登入自動補抓資料/登入自動補抓資料_規劃書.md §3.6）：只遞增 refreshKey
// 讓各 panel 用既有的 fetch 流程原地重抓（硬性規則 #1：不整頁 refresh、不用 :key 重掛元件、
// scrollY 不歸零），再跳 toast 告知使用者。
const refreshKey = ref(0);
function onDataRefreshed() {
  refreshKey.value++;
  toast.add({ severity: 'success', summary: '資料更新完成', detail: '已補上最新交易日資料', life: 3000 });
}

// 登入／登出時 ownerApi 會廣播此事件（見 service/ownerApi.js），首頁即時切換個人化區塊
onMounted(() => {
  checkAuth();
  window.addEventListener('owner-auth-changed', checkAuth);
});
onUnmounted(() => window.removeEventListener('owner-auth-changed', checkAuth));
</script>
