<script setup>
import { useLayout } from '@/layout/composables/layout';
import { onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { stockApi } from '@/service/stockApi';

const route = useRoute();
const router = useRouter();
const { toggleMenu } = useLayout();

const userName = ref('王小明 (Ming.Wang)');
const isMobile = ref(window.innerWidth <= 768);
const showUserMenu = ref(false);

const availableStocks = ref([]);
const currentStockId = ref(route.params.id || '2330');

onMounted(async () => {
    window.addEventListener('resize', handleResize);
    document.addEventListener('click', handleClickOutside);
    window.addEventListener('keydown', handleKeyDown);
    await loadAvailableStocks();
});

onUnmounted(() => {
    window.removeEventListener('resize', handleResize);
    document.removeEventListener('click', handleClickOutside);
    window.removeEventListener('keydown', handleKeyDown);
});

function handleKeyDown(event) {
    // 若使用者目前在文字輸入框內打字，不觸發快捷鍵
    const activeEl = document.activeElement;
    if (activeEl) {
        const tagName = activeEl.tagName.toLowerCase();
        if ((tagName === 'input' || tagName === 'textarea' || activeEl.isContentEditable) && tagName !== 'select') {
            return;
        }
    }

    if (!availableStocks.value || availableStocks.value.length === 0) return;

    if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
        event.preventDefault();

        const currentIndex = availableStocks.value.findIndex(s => s.stock_id === currentStockId.value);
        let nextIndex = currentIndex;

        if (event.key === 'ArrowDown') {
            nextIndex = (currentIndex + 1) % availableStocks.value.length;
        } else if (event.key === 'ArrowUp') {
            nextIndex = (currentIndex - 1 + availableStocks.value.length) % availableStocks.value.length;
        }

        if (nextIndex !== currentIndex && nextIndex >= 0 && nextIndex < availableStocks.value.length) {
            currentStockId.value = availableStocks.value[nextIndex].stock_id;
            handleStockChange();
        }
    }
}

async function loadAvailableStocks() {
    try {
        const res = await stockApi.getAvailableStocks();
        if (res.success && res.data.length > 0) {
            availableStocks.value = res.data;
            if (!route.params.id && !availableStocks.value.some(s => s.stock_id === currentStockId.value)) {
                currentStockId.value = res.data[0].stock_id;
            }
        }
    } catch (err) {
        console.error('頂部列獲取股票清單失敗:', err);
    }
}

watch(() => route.params.id, (newId) => {
    if (newId) {
        currentStockId.value = newId;
    }
});

function handleStockChange() {
    if (!currentStockId.value) return;
    const newStockId = currentStockId.value;

    // 保留目前所處的子功能視圖（例如在 /chart/kline 則保持在 /chart/kline）
    let targetPath = `/stock/${newStockId}`;
    if (route.params.chartType) {
        targetPath = `/stock/${newStockId}/chart/${route.params.chartType}`;
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
    alert('已登出');
    showUserMenu.value = false;
}

function handleClickOutside(event) {
    const userMenu = document.querySelector('.user-menu');
    const userMenuButton = document.querySelector('.layout-topbar-action.pi-user');
    if (userMenu && !userMenu.contains(event.target) && userMenuButton && !userMenuButton.contains(event.target)) {
        showUserMenu.value = false;
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
                <i class="pi pi-chart-line text-2xl text-primary"></i>
                <span class="hidden md:inline">MyStock 股市分析系統</span>
            </router-link>
        </div>

        <div class="layout-topbar-actions flex items-center gap-3">
            <!-- 頂部列靠右個股切換工具 (Header Stock Selector Tool - Right Aligned) -->
            <div class="flex items-center gap-2 bg-surface-100 dark:bg-surface-800 px-3 py-1.5 rounded-xl border border-surface-200 dark:border-surface-700 shadow-sm">
                <i class="pi pi-search text-primary text-xs"></i>
                <span class="text-xs font-bold text-surface-600 dark:text-surface-400 hidden sm:inline">個股切換:</span>
                <select 
                    v-model="currentStockId" 
                    @change="handleStockChange"
                    class="bg-transparent text-xs font-bold text-surface-900 dark:text-surface-0 focus:outline-none cursor-pointer pr-1"
                    title="選擇欲切換分析的股票"
                >
                    <option 
                        v-for="s in availableStocks" 
                        :key="s.stock_id" 
                        :value="s.stock_id" 
                        class="bg-surface-0 dark:bg-surface-900 text-surface-900 dark:text-surface-0 font-medium"
                    >
                        {{ s.stock_id }} {{ s.stock_name }}
                    </option>
                </select>
            </div>

            <!-- 版本標籤，桌機/手機都顯示在右側 -->
            <span style="font-size: 0.8em; color: #333; background: #f4f4f4; border-radius: 4px; padding: 2px 8px; vertical-align: middle">V.01</span>
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
</template>
<style scoped></style>
