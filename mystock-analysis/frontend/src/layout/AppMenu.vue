<script setup>
import { ref } from 'vue';
import AppMenuItem from './AppMenuItem.vue';

const model = ref([
    {
        label: '過磅作業',
        items: [
            {
                label: '廠門地磅作業',
                icon: 'pi pi-fw pi-server',
                to: '/'
            }
        ]
    },
    {
        label: '查詢 / 報表',
        items: [
            {
                label: '當日磅單查詢',
                icon: 'pi pi-fw pi-list',
                to: '/'
            },
            {
                label: '黃金價格',
                icon: 'pi pi-fw pi-chart-line',
                to: '/gold'
            }
        ]
    },
    {
        label: '系統設定',
        items: [
            {
                label: '採購單管理',
                icon: 'pi pi-fw pi-briefcase',
                to: '/'
            },
            {
                label: '車輛管理',
                icon: 'pi pi-fw pi-truck',
                to: '/'
            },
            {
                label: '使用者管理',
                icon: 'pi pi-fw pi-users',
                to: '/'
            }
        ]
    }
]);
</script>

<template>
    <ul class="layout-menu">
        <template v-for="(item, i) in model" :key="item">
            <app-menu-item :item="item" :index="i"></app-menu-item>
            <li class="menu-separator" v-if="i < model.length - 1"></li>
        </template>
    </ul>
</template>

<style lang="scss" scoped></style>
