<script setup>
import { computed } from 'vue';
import AppMenuItem from './AppMenuItem.vue';
import { useCrawlerStatus } from '@/composables/useCrawlerStatus';

const { isRunning } = useCrawlerStatus();

const model = computed(() => [
    {
        label: 'MyStock 股市選股分析',
        items: [
            { label: '全市場個股動態熱力圖', icon: 'pi pi-fw pi-th-large', to: '/' },
            { label: '全市場數據查詢', icon: 'pi pi-fw pi-table', to: '/market' },
            { label: '策略選股清單', icon: 'pi pi-fw pi-filter', to: '/picking' },
            { label: '多股綜合比較', icon: 'pi pi-fw pi-sliders-h', to: '/compare' },
            { label: '選股與圖表分析', icon: 'pi pi-fw pi-chart-line', to: '/stock/2330' },
            { label: '大盤指數', icon: 'pi pi-fw pi-globe', to: '/index/tw/TWII' },
            { label: '類股輪動', icon: 'pi pi-fw pi-sync', to: '/indices/sectors' },
            { label: '策略警示看板', icon: 'pi pi-fw pi-bell', to: '/alerts' },
            { label: '全市場代碼查詢', icon: 'pi pi-fw pi-search', to: '/stocks/symbols' },
            { label: '股票與爬蟲管理', icon: 'pi pi-fw pi-cog', to: '/stocks', loading: isRunning.value }
        ]
    },
    {
        label: '投資記帳',
        items: [
            { label: '觀察名單', icon: 'pi pi-fw pi-eye', to: '/portfolio/watchlist' },
            { label: '儀表板總覽', icon: 'pi pi-fw pi-wallet', to: '/portfolio' },
            { label: '交易紀錄', icon: 'pi pi-fw pi-list', to: '/portfolio/transactions' },
            { label: '持股總覽', icon: 'pi pi-fw pi-briefcase', to: '/portfolio/holdings' },
            { label: '已實現損益', icon: 'pi pi-fw pi-money-bill', to: '/portfolio/realized' },
            { label: '現金流/股利', icon: 'pi pi-fw pi-sync', to: '/portfolio/cashflow' },
            { label: '記帳設定', icon: 'pi pi-fw pi-cog', to: '/portfolio/settings' }
        ]
    },
    {
        label: '通知設定',
        items: [
            { label: '管道設定', icon: 'pi pi-fw pi-send', to: '/notify/channels' },
            { label: '收件人', icon: 'pi pi-fw pi-users', to: '/notify/recipients' },
            { label: '訂閱規則', icon: 'pi pi-fw pi-filter', to: '/notify/subscriptions' },
            { label: '訊息模板', icon: 'pi pi-fw pi-file-edit', to: '/notify/templates' },
            { label: '發送紀錄', icon: 'pi pi-fw pi-history', to: '/notify/logs' }
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
