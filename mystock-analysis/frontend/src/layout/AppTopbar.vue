<script setup>
import { useLayout } from '@/layout/composables/layout';
import { useDbStatus } from '@/composables/useDbStatus';
import logoWhite from '@/assets/logo-white.svg';
import { onMounted, onUnmounted, ref } from 'vue';

const { toggleMenu } = useLayout();
const { dbStatus } = useDbStatus();

const userName = ref('地磅操作員');
const isMobile = ref(window.innerWidth <= 768);
const showUserMenu = ref(false);

function toggleUserMenu() {
    showUserMenu.value = !showUserMenu.value;
}

function logout() {
    alert('已登出');
    showUserMenu.value = false;
}

function handleClickOutside(event) {
    const userMenu = document.querySelector('.user-menu');
    const userBtn = document.querySelector('.layout-topbar-action.pi-user');
    if (userMenu && !userMenu.contains(event.target) && userBtn && !userBtn.contains(event.target)) {
        showUserMenu.value = false;
    }
}

function handleResize() {
    isMobile.value = window.innerWidth <= 768;
}

onMounted(() => {
    window.addEventListener('resize', handleResize);
    document.addEventListener('click', handleClickOutside);
});
onUnmounted(() => {
    window.removeEventListener('resize', handleResize);
    document.removeEventListener('click', handleClickOutside);
});
</script>

<template>
    <div class="layout-topbar">
        <div class="layout-topbar-logo-container">
            <button class="layout-menu-button layout-topbar-action" @click="toggleMenu">
                <i class="pi pi-bars"></i>
            </button>
            <router-link to="/" class="layout-topbar-logo">
                <img :src="logoWhite" alt="TCCI Logo" style="height: 2rem; width: auto;" />
                <span>過磅作業系統</span>
            </router-link>
        </div>

        <div class="layout-topbar-actions">
            <span style="font-size: 0.78em; background: rgba(255,255,255,0.2); border-radius: 4px; padding: 2px 8px;">V.1.0</span>

            <!-- DB 狀態徽章 -->
            <span
                :class="['db-status-badge', dbStatus.mode === 'mssql' ? 'badge-db' : 'badge-mem']"
                :title="dbStatus.mode === 'mssql'
                    ? `MS SQL Server\n伺服器：${dbStatus.server}\n資料庫：${dbStatus.database}\n公司：${dbStatus.compNo}  廠區：${dbStatus.plantNo}`
                    : '無法連線至資料庫，使用記憶體 Mock 模式'"
            >
                <span :class="['pulse-dot', dbStatus.mode === 'mssql' ? 'pulse-dot-blue' : 'pulse-dot-orange']"></span>
                <span v-if="dbStatus.mode === 'mssql'">
                    🗄 MS SQL
                    <span style="opacity:.8;font-size:.75rem;margin-left:.2rem">{{ dbStatus.server }}</span>
                </span>
                <span v-else>💾 記憶體模式</span>
            </span>

            <!-- 桌機板 -->
            <div class="layout-config-menu" v-if="!isMobile">
                <span class="username">您好：{{ userName }}</span>
                <a href="#" @click.prevent="logout" title="登出">
                    <span class="pi pi-sign-out"></span>
                </a>
            </div>

            <!-- 手機板 -->
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

<style scoped>
/* DB 狀態徽章 */
.db-status-badge {
    padding: .3rem .85rem;
    border-radius: 20px;
    font-size: .82rem;
    font-weight: 600;
    white-space: nowrap;
    display: inline-flex;
    align-items: center;
    gap: .35rem;
    cursor: default;
}
.badge-db {
    background: #1d4ed8;
    color: #fff;
    box-shadow: 0 1px 4px rgba(29,78,216,.4);
}
.badge-mem {
    background: #d97706;
    color: #fff;
    box-shadow: 0 1px 4px rgba(217,119,6,.4);
}
@keyframes pulse-dot {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: .4; transform: scale(.7); }
}
.pulse-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    animation: pulse-dot 2s ease-in-out infinite;
}
.pulse-dot-blue { background: #93c5fd; }
.pulse-dot-orange { background: #fde68a; }
</style>
