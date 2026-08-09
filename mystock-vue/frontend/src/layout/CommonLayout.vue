<template>
    <div class="common-layout">
        <!-- 頁面標題區域 -->
        <slot name="header">
            <header class="page-header flex justify-between items-center">
                <h1 class="page-title text-2xl font-semibold">{{ title }}</h1>
                <div class="flex items-center gap-2">
                    <template v-if="$slots.status">
                        <slot name="status" />
                    </template>
                    <template v-else>
                        <span v-show="showStatus" :class="`status-indicator ${statusClass}`" style="margin-left: 1rem"> <i class="pi pi-file-edit"></i> {{ statusText }} </span>
                    </template>
                    <slot name="action-buttons"></slot>
                </div>
            </header>
        </slot>

        <!-- 控制面板 -->
        <slot name="control-panel"></slot>

        <!-- 主要內容區域 -->
        <Card class="main-content">
            <template #content>
                <slot />
            </template>
        </Card>
        <!-- 操作按鈕區域（已移除重複 slot，僅保留 header 右上） -->
    </div>
</template>

<script setup>
// Props for default header content
defineProps({
    title: {
        type: String,
        default: '預設標題'
    },
    showStatus: {
        type: Boolean,
        default: false
    },
    statusClass: {
        type: String,
        default: ''
    },
    statusText: {
        type: String,
        default: '預設狀態'
    }
});
</script>

<style scoped>
/* 可加入共用樣式 */
</style>
