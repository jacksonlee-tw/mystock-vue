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
            { label: '選股與圖表分析', icon: 'pi pi-fw pi-chart-line', to: '/stock/2330' },
            { label: '策略警示看板', icon: 'pi pi-fw pi-bell', to: '/alerts' },
            { label: '股票與爬蟲管理', icon: 'pi pi-fw pi-cog', to: '/stocks', loading: isRunning.value }
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
