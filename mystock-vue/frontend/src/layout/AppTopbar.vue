<script setup>
import { useLayout } from '@/layout/composables/layout';
import { onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { stockApi } from '@/service/stockApi';
import { useToast } from 'primevue/usetoast';
import { useMarket } from '@/composables/useMarket';
import Omnibox from '@/components/Omnibox.vue';

const route = useRoute();
const router = useRouter();
const { toggleMenu, toggleDarkMode, isDarkTheme, layoutConfig, setAccent, setSurface } = useLayout();
const { currentMarket, setMarket, marketMeta, enabledMarkets, setMarketsFromApi } = useMarket();
const toast = useToast();

const omniboxRef = ref(null);

const userName = ref('傑克森');
const isMobile = ref(window.innerWidth <= 768);
const showUserMenu = ref(false);
const showAppearanceMenu = ref(false);

// 主題強調色（accent）與中性色調（surface）都可自由切換，且會存進 localStorage
// （見 layout.js composable 的 persistAppearance／loadPersistedAppearance），下次
// 打開同一台瀏覽器會自動套用。實際套色透過 assets/layout/variables/_accent-themes.scss、
// _surface-tones.scss 的 [data-accent]／[data-surface] CSS 屬性選擇器，不呼叫 PrimeVue 的
// updatePreset()／updateSurfacePalette() 執行期 API（兩個檔案的頭部都有詳細說明：
// 在這個 Vite dev server 設定下那組 API 不會真的生效）。
const accentOptions = [
    { name: 'brass', label: '黃銅金', swatch: '#8f6413' },
    { name: 'tech-blue', label: '科技藍', swatch: '#2563eb' },
    { name: 'forest', label: '沉穩墨綠', swatch: '#0f766e' },
    { name: 'ink', label: '極簡墨', swatch: '#18181b' }
];

const surfaceOptions = [
    { name: 'slate', label: '石板灰', swatch: '#64748b' },
    { name: 'zinc', label: '鋅灰', swatch: '#71717a' },
    { name: 'stone', label: '石灰', swatch: '#78716c' },
    { name: 'gray', label: '中性灰', swatch: '#6b7280' }
];

function toggleAppearanceMenu() {
    showAppearanceMenu.value = !showAppearanceMenu.value;
}

function selectAccent(option) {
    setAccent(option.name);
}

function selectSurface(option) {
    setSurface(option.name);
}

const availableStocks = ref([]);
const currentStockId = ref(route.params.id || '2330');

onMounted(async () => {
    window.addEventListener('resize', handleResize);
    document.addEventListener('click', handleClickOutside);
    window.addEventListener('keydown', handleKeyDown);
    try {
        const marketsRes = await stockApi.getMarkets();
        if (marketsRes.success) {
            setMarketsFromApi(marketsRes.data);
        }
    } catch (e) {
        console.error('Failed to load markets', e);
    }
    await loadAvailableStocks();
});

onUnmounted(() => {
    window.removeEventListener('resize', handleResize);
    document.removeEventListener('click', handleClickOutside);
    window.removeEventListener('keydown', handleKeyDown);
});

function handleKeyDown(event) {
    // 若使用者目前在文字輸入框內打字（如 Omnibox 搜尋框、input、textarea），不觸發快捷鍵
    const activeEl = document.activeElement;
    if (activeEl) {
        const tagName = activeEl.tagName.toLowerCase();
        if ((tagName === 'input' || tagName === 'textarea' || activeEl.isContentEditable) && tagName !== 'select') {
            return;
        }
    }

    if (!availableStocks.value || availableStocks.value.length === 0) return;

    if (event.key === 'ArrowUp' || event.key === 'ArrowDown' || event.key === '[' || event.key === ']') {
        event.preventDefault();

        // 確保 currentStockId 與當前路由 id 同步
        if (route.params.id && currentStockId.value !== route.params.id) {
            currentStockId.value = route.params.id;
        }

        const currentIndex = availableStocks.value.findIndex(s => s.stock_id === currentStockId.value);
        let nextIndex = currentIndex;

        if (event.key === 'ArrowDown' || event.key === ']') {
            nextIndex = currentIndex < 0 ? 0 : (currentIndex + 1) % availableStocks.value.length;
        } else if (event.key === 'ArrowUp' || event.key === '[') {
            nextIndex = currentIndex < 0 ? availableStocks.value.length - 1 : (currentIndex - 1 + availableStocks.value.length) % availableStocks.value.length;
        }

        if (nextIndex >= 0 && nextIndex < availableStocks.value.length) {
            currentStockId.value = availableStocks.value[nextIndex].stock_id;
            handleStockChange();
        }
    }
}

async function loadAvailableStocks() {
    try {
        const activeMarket = route.params.market || currentMarket.value || 'tw';
        const res = await stockApi.getAvailableStocks(activeMarket);
        if (res.success && res.data.length > 0) {
            availableStocks.value = res.data;
            if (route.params.id) {
                currentStockId.value = route.params.id;
            } else if (!availableStocks.value.some(s => s.stock_id === currentStockId.value)) {
                currentStockId.value = res.data[0].stock_id;
            }
        }
    } catch (err) {
        console.error('頂部列獲取股票清單失敗:', err);
    }
}

watch([() => route.params.market, currentMarket], () => {
    loadAvailableStocks();
});

watch(() => route.params.id, (newId) => {
    if (newId) {
        currentStockId.value = newId;
    }
});

function handleStockChange() {
    if (!currentStockId.value) return;
    const newStockId = currentStockId.value;
    const activeMarket = route.params.market || currentMarket.value || 'tw';

    // 保留目前所處的子功能視圖（例如在 /stock/tw/2330/chart/kline 則保持在 /stock/tw/${newStockId}/chart/kline）
    let targetPath = `/stock/${activeMarket}/${newStockId}`;
    if (route.params.chartType) {
        targetPath = `/stock/${activeMarket}/${newStockId}/chart/${route.params.chartType}`;
    }

    router.push({
        path: targetPath,
        query: { ...route.query }
    });
}

function toggleUserMenu() {
    showUserMenu.value = !showUserMenu.value;
}

function logout() {
    toast.add({ severity: 'info', summary: '已登出', life: 3000 });
    showUserMenu.value = false;
}

function handleClickOutside(event) {
    const userMenu = document.querySelector('.user-menu');
    const userMenuButton = document.querySelector('.layout-topbar-action.pi-user');
    if (userMenu && !userMenu.contains(event.target) && userMenuButton && !userMenuButton.contains(event.target)) {
        showUserMenu.value = false;
    }

    const appearanceMenu = document.querySelector('.appearance-menu');
    const appearanceButton = document.querySelector('.appearance-menu-button');
    if (
        appearanceMenu &&
        !appearanceMenu.contains(event.target) &&
        appearanceButton &&
        !appearanceButton.contains(event.target)
    ) {
        showAppearanceMenu.value = false;
    }
}

function handleResize() {
    isMobile.value = window.innerWidth <= 768;
}
</script>

<template>
    <div class="layout-topbar">
        <div class="layout-topbar-logo-container">
            <button class="layout-menu-button layout-topbar-action" @click="toggleMenu">
                <i class="pi pi-bars"></i>
            </button>
            <router-link to="/" class="layout-topbar-logo flex items-center gap-2">
                <span class="w-7 h-7 rounded-md bg-primary text-primary-contrast flex items-center justify-center text-xs font-black">M</span>
                <span class="hidden md:inline font-bold">MyStock 投資系統</span>
            </router-link>
        </div>

        <div class="layout-topbar-actions flex items-center gap-3">
            <!-- 頂部列靠右個股切換工具 (Omnibox) -->
            <button 
                @click="omniboxRef?.open()"
                class="flex items-center gap-2 bg-surface-100 dark:bg-surface-800 px-3 py-1.5 rounded-lg border border-surface-200 dark:border-surface-700 hover:bg-surface-200 dark:hover:bg-surface-700 transition-colors text-left sm:w-64"
                title="搜尋股票代號或名稱 (Ctrl+K)"
            >
                <i class="pi pi-search text-primary text-xs"></i>
                <span class="text-xs font-bold text-surface-500 flex-1 truncate">搜尋代號或名稱...</span>
                <span class="text-[10px] font-bold bg-surface-200 dark:bg-surface-700 text-surface-500 px-1.5 py-0.5 rounded hidden sm:inline">Ctrl K</span>
            </button>

            <!-- 市場切換 -->
            <div class="flex items-center gap-0.5 bg-surface-100 dark:bg-surface-800 p-0.5 rounded-lg border border-surface-200 dark:border-surface-700">
                <button
                    v-for="m in enabledMarkets"
                    :key="m.code"
                    @click="() => {
                        setMarket(m.code);
                        if (route.path.startsWith('/stock/')) {
                            // Automatically go to first stock in that market if available
                            currentStockId.value = '';
                            router.push('/');
                        }
                    }"
                    :class="[
                        'px-3 py-1 text-xs font-bold rounded-md transition-all duration-150',
                        currentMarket === m.code ? 'bg-primary text-primary-contrast shadow-sm' : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
                    ]"
                >{{ m.label }}</button>
            </div>
            
            <span v-if="marketMeta.session_state === 'open'" class="px-2 py-0.5 bg-green-100 text-green-700 text-[10px] rounded font-bold">盤中</span>
            <span v-else-if="marketMeta.session_state === 'pre_market'" class="px-2 py-0.5 bg-orange-100 text-orange-700 text-[10px] rounded font-bold">盤前</span>
            <span v-else-if="marketMeta.session_state === 'after_hours'" class="px-2 py-0.5 bg-indigo-100 text-indigo-700 text-[10px] rounded font-bold">盤後</span>
            <span v-else-if="marketMeta.session_state === 'closed'" class="px-2 py-0.5 bg-surface-200 text-surface-600 text-[10px] rounded font-bold">收盤</span>

            <!-- 外觀：淺色/深色即時切換，即時生效 -->
            <button
                type="button"
                class="layout-topbar-action"
                :title="isDarkTheme ? '切換為淺色模式' : '切換為深色模式'"
                @click="toggleDarkMode"
            >
                <i :class="['pi', isDarkTheme ? 'pi-sun' : 'pi-moon']"></i>
            </button>

            <!-- 外觀：主題強調色與中性色調選擇 -->
            <div class="relative">
                <button
                    type="button"
                    class="appearance-menu-button layout-topbar-action"
                    title="調整主題色與介面色調"
                    @click="toggleAppearanceMenu"
                >
                    <i class="pi pi-palette"></i>
                </button>
                <div
                    v-if="showAppearanceMenu"
                    class="appearance-menu absolute top-[2.75rem] right-0 w-56 p-3 bg-surface-0 dark:bg-surface-900 border border-surface-200 dark:border-surface-700 rounded-lg shadow-lg z-50 space-y-3"
                >
                    <div>
                        <span class="text-[11px] font-bold uppercase tracking-wide text-surface-400">主題色</span>
                        <div class="flex gap-2 mt-2">
                            <button
                                v-for="a in accentOptions"
                                :key="a.name"
                                type="button"
                                :title="a.label"
                                @click="selectAccent(a)"
                                :class="[
                                    'w-7 h-7 rounded-full border-2 transition-colors',
                                    layoutConfig.primary === a.name ? 'border-surface-900 dark:border-surface-0' : 'border-transparent'
                                ]"
                                :style="{ backgroundColor: a.swatch }"
                            ></button>
                        </div>
                        <p class="text-[11px] text-surface-500 mt-1.5">{{ accentOptions.find(a => a.name === layoutConfig.primary)?.label || '黃銅金' }}</p>
                    </div>
                    <div class="pt-2 border-t border-surface-100 dark:border-surface-800">
                        <span class="text-[11px] font-bold uppercase tracking-wide text-surface-400">中性色調</span>
                        <div class="flex gap-2 mt-2">
                            <button
                                v-for="s in surfaceOptions"
                                :key="s.name"
                                type="button"
                                :title="s.label"
                                @click="selectSurface(s)"
                                :class="[
                                    'w-6 h-6 rounded-full border-2 transition-colors',
                                    layoutConfig.surface === s.name ? 'border-surface-900 dark:border-surface-0' : 'border-transparent'
                                ]"
                                :style="{ backgroundColor: s.swatch }"
                            ></button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 版本標籤，桌機/手機都顯示在右側 -->
            <span class="num text-[11px] font-bold text-surface-500 bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded px-1.5 py-0.5">V.01</span>
            <div class="layout-config-menu" v-if="!isMobile">
                <span class="username">您好: {{ userName }}</span>
                <a href="#" @click.prevent="logout">
                    <span class="pi pi-sign-out"></span>
                </a>
            </div>

            <!-- 手機板設計 -->
            <div class="layout-config-menu-mobile" v-if="isMobile">
                <button class="layout-topbar-action pi pi-user" @click="toggleUserMenu"></button>
                <div v-if="showUserMenu" class="user-menu">
                    <span class="username">{{ userName }}</span>
                    <a href="#" @click.prevent="logout">
                        <span class="pi pi-sign-out"></span>
                    </a>
                </div>
            </div>
        </div>
    </div>
    
    <Omnibox ref="omniboxRef" />
</template>
<style scoped></style>
