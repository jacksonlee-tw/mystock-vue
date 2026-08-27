<script setup>
import { computed } from 'vue';
import AppMenuItem from './AppMenuItem.vue';
import { useCrawlerStatus } from '@/composables/useCrawlerStatus';
import { useMarket } from '@/composables/useMarket';

const { isRunning } = useCrawlerStatus();
const { currentMarket } = useMarket();

const model = computed(() => [
    {
        label: '市場大盤與總覽',
        items: [
            { label: '動態熱力圖', icon: 'pi pi-fw pi-th-large', to: '/' },
            { label: '大盤指數分析', icon: 'pi pi-fw pi-globe', to: currentMarket.value === 'us' ? '/index/us/GSPC' : '/index/tw/TWII' },
            { label: '類股輪動監控', icon: 'pi pi-fw pi-sync', to: '/indices/sectors' }
        ]
    },
    {
        label: '策略選股與分析',
        items: [
            { label: '策略選股清單', icon: 'pi pi-fw pi-filter', to: '/picking' },
            { label: '全市場數據篩選', icon: 'pi pi-fw pi-table', to: '/market' },
            { label: '策略警示看板', icon: 'pi pi-fw pi-bell', to: '/alerts' },
            { label: '個股圖表分析', icon: 'pi pi-fw pi-chart-line', to: '/stock/2330' },
            { label: '多股綜合比較', icon: 'pi pi-fw pi-sliders-h', to: '/compare' },
            { label: 'AI 診股報告紀錄', icon: 'pi pi-fw pi-android', to: '/ai/reports' }
        ]
    },
    {
        label: '個人投資記帳',
        items: [
            { label: '投資儀表板', icon: 'pi pi-fw pi-wallet', to: '/portfolio' },
            { label: '持股總覽', icon: 'pi pi-fw pi-briefcase', to: '/portfolio/holdings' },
            { label: '追蹤與觀察名單', icon: 'pi pi-fw pi-eye', to: '/portfolio/watchlist' },
            { label: '交易紀錄', icon: 'pi pi-fw pi-list', to: '/portfolio/transactions' },
            { label: '已實現損益', icon: 'pi pi-fw pi-money-bill', to: '/portfolio/realized' },
            { label: '現金流與股利', icon: 'pi pi-fw pi-percentage', to: '/portfolio/cashflow' },
            { label: '記帳設定', icon: 'pi pi-fw pi-sliders-v', to: '/portfolio/settings' }
        ]
    },
    {
        label: '訊息通知平台',
        items: [
            { label: '訂閱規則', icon: 'pi pi-fw pi-bell', to: '/notify/subscriptions' },
            { label: '發送紀錄', icon: 'pi pi-fw pi-history', to: '/notify/logs' },
            { label: '通知管道', icon: 'pi pi-fw pi-send', to: '/notify/channels' },
            { label: '收件人管理', icon: 'pi pi-fw pi-users', to: '/notify/recipients' },
            { label: '訊息模板', icon: 'pi pi-fw pi-file-edit', to: '/notify/templates' }
        ]
    },
    {
        label: '系統與數據管理',
        items: [
            { label: '全市場代碼查詢', icon: 'pi pi-fw pi-search', to: '/stocks/symbols' },
            { label: '股票與爬蟲管理', icon: 'pi pi-fw pi-database', to: '/stocks', loading: isRunning.value }
        ]
    }
]);
</script>

<template>
    <ul class="layout-menu">
        <template v-for="(item, i) in model" :key="item">
            <app-menu-item v-if="!item.separator" :item="item" :index="i"></app-menu-item>
            <li v-if="item.separator" class="menu-separator"></li>
        </template>
    </ul>
</template>

<style lang="scss" scoped></style>
