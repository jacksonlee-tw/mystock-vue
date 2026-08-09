<template>
    <CommonLayout>
        <template #header>
            <div class="flex items-center justify-between">
                <div>
                    <h2 class="text-2xl font-bold mb-1">歡迎，{{ userName }}！</h2>
                </div>
                <div class="text-gray-500 text-base">{{ today }}</div>
            </div>
        </template>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- 系統公告/最新消息 -->
            <Card>
                <template #title>
                    <span class="font-semibold">系統公告 / 最新消息</span>
                </template>
                <template #content>
                    <ul>
                        <li v-for="(item, idx) in newsList" :key="idx" class="mb-2 flex flex-row items-center">
                            <span class="inline-block px-2 py-1 rounded mr-2 bg-blue-100 text-blue-800">{{ item.type }}</span>
                            <span>{{ item.title }}</span>
                        </li>
                        <li v-if="!newsList.length" class="text-gray-400">目前無公告</li>
                    </ul>
                </template>
            </Card>

            <!-- 我的待辦/提醒（可選） -->
            <Card v-if="todoList.length">
                <template #title>
                    <span class="font-semibold">我的待辦 / 提醒</span>
                </template>
                <template #content>
                    <ul>
                        <li v-for="(todo, idx) in todoList" :key="idx" class="mb-2 flex items-center">
                            <span class="inline-block px-2 py-1 rounded mr-2 bg-green-100 text-green-800">{{ todo.type }}</span>
                            <span>{{ todo.title }}</span>
                            <Button label="前往" class="ml-auto p-button-text p-button-sm" @click="goTo(todo.link)" />
                        </li>
                    </ul>
                </template>
            </Card>

            <!-- 幫助/聯絡資訊 -->
            <Card>
                <template #title>
                    <span class="font-semibold">幫助 / 聯絡資訊</span>
                </template>
                <template #content>
                    <ul class="mb-2 space-y-2">
                        <li><a href="#" class="text-blue-600 hover:underline">常見問題</a></li>
                        <li><a href="#" class="text-blue-600 hover:underline">操作手冊下載</a></li>
                    </ul>
                    <div class="text-gray-600">
                        客服信箱：<a href="mailto:support@example.com" class="text-blue-600">support@example.com</a><br />
                        服務電話：0800-123-456
                    </div>
                </template>
            </Card>
        </div>
    </CommonLayout>
</template>

<script setup>
import CommonLayout from '@/layout/CommonLayout.vue';
import Button from 'primevue/button';
import Card from 'primevue/card';
import { ref } from 'vue';

const userName = '王小明'; // 實際應由登入資訊取得
const today = new Date().toLocaleDateString();

const newsList = ref([
    { type: '公告', title: '11/20 系統維護通知（23:00~02:00 服務暫停）', severity: 'warning' },
    { type: '消息', title: '新功能上線：問卷管理，歡迎體驗', severity: 'info' },
    { type: '公告', title: '12/01 啟用新版登入驗證機制', severity: 'success' },
    { type: '提醒', title: '年底資料備份作業將於 12/15 進行', severity: 'help' }
]);

const todoList = ref([
    { type: '待填寫', title: '問卷：2025年度滿意度調查', link: '/questionnaire/fill/1' },
    { type: '待審核', title: '新用戶註冊審核（王小華）', link: '/user/approval' },
    { type: '待回覆', title: '客服信件：功能諮詢回覆', link: '/support/mail' },
    { type: '待確認', title: '資料異動申請（#20251117）', link: '/data/approval' }
]);

// 調試用 - 檢查假資料是否載入
console.log('HomeDashboard 假資料載入:', {
    userName,
    today,
    newsListLength: newsList.value.length,
    todoListLength: todoList.value.length,
    newsList: newsList.value,
    todoList: todoList.value
});

function goTo(link) {
    // 實際應用可用 router.push
    window.location.href = link;
}
</script>

<style scoped>
/* 可依需求補充自訂樣式 */
</style>
