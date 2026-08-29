<template>
    <!-- 1.頁面標題 -->
    <CommonLayout :title="'問卷設定'">
        <!-- 2. 控制面板 -->
        <!-- 控制面板區（可擴充查詢/篩選等） -->
        <template #control-panel>
            <Card class="mb-4">
                <template #content>
                    <div class="section-control-panel">
                        <span class="font-semibold">問卷設定說明：</span>
                        <span>請填寫問卷基本資訊，設定啟用狀態與期間。</span>
                    </div>
                </template>
            </Card>
        </template>
        <!-- 3. 主要內容區域 -->
        <!-- 基本資料區塊 -->
        <div class="font-bold mb-3">問卷基本資料</div>
        <div class="mb-3">
            <label for="title" class="block mb-1">問卷標題</label>
            <InputText id="title" v-model="form.title" class="w-full" required />
        </div>
        <div class="mb-3">
            <label for="desc" class="block mb-1">問卷說明</label>
            <InputText id="desc" v-model="form.description" class="w-full" />
        </div>
        <div class="mb-3 flex items-center gap-6">
            <label class="block mb-1 mr-2">狀態</label>
            <InputSwitch v-model="form.status" trueValue="active" falseValue="inactive" />
            <span class="ml-2">{{ form.status === 'active' ? '啟用' : '停用' }}</span>
        </div>
        <div class="mb-3 flex items-center gap-4">
            <div class="flex-1">
                <label class="block mb-1">開始日期</label>
                <Calendar v-model="form.startDate" showIcon dateFormat="yy-mm-dd" class="w-full" />
            </div>
            <div class="flex-1">
                <label class="block mb-1">結束日期</label>
                <Calendar v-model="form.endDate" showIcon dateFormat="yy-mm-dd" class="w-full" />
            </div>
        </div>
        <!-- 題目設定區塊 -->
        <form @submit.prevent="onSubmit">
            <div class="flex items-center justify-between mb-2">
                <label class="block font-bold">題目設定</label>
                <Button label="新增題目" icon="pi pi-plus" size="small" @click="addQuestion" type="button" />
            </div>
            <div v-for="(q, idx) in questions" :key="q.id" class="p-3 mb-2 border rounded bg-gray-50">
                <div class="flex gap-2 items-center mb-2">
                    <span class="font-semibold">題目{{ idx + 1 }}</span>
                    <Button icon="pi pi-trash" class="p-button-danger p-button-sm" @click="removeQuestion(idx)" type="button" text />
                </div>
                <div class="mb-2">
                    <InputText v-model="q.text" class="w-full" placeholder="請輸入題目內容" />
                </div>
                <div class="mb-2 flex gap-2 items-center">
                    <label>題型：</label>
                    <Dropdown v-model="q.type" :options="questionTypeOptions" optionLabel="label" optionValue="value" class="w-32" />
                </div>
                <div v-if="q.type === 'single' || q.type === 'multiple'" class="mb-2">
                    <div v-for="(opt, oidx) in q.options" :key="oidx" class="flex items-center gap-2 mb-1">
                        <InputText v-model="q.options[oidx]" class="w-64" placeholder="選項內容" />
                        <Button icon="pi pi-trash" class="p-button-danger p-button-xs" @click="removeOption(idx, oidx)" type="button" text />
                    </div>
                    <Button label="新增選項" icon="pi pi-plus" size="small" @click="addOption(idx)" type="button" class="mt-1" />
                </div>
            </div>
            <div class="flex items-center justify-end gap-2 mt-4">
                <Button label="取消" icon="pi pi-times" class="p-button-secondary" @click="onCancel" type="button" />
                <Button label="儲存" icon="pi pi-check" type="submit" />
            </div>
        </form>
    </CommonLayout>
</template>

<script setup>
import CommonLayout from '@/layout/CommonLayout.vue';
import Button from 'primevue/button';
import Calendar from 'primevue/calendar';
import Card from 'primevue/card';
import Dropdown from 'primevue/dropdown';
import InputSwitch from 'primevue/inputswitch';
import InputText from 'primevue/inputtext';
import { reactive } from 'vue';

const form = reactive({
    title: '',
    description: '',
    status: null,
    startDate: null,
    endDate: null
});

const statusOptions = [
    { label: '啟用', value: 'active' },
    { label: '停用', value: 'inactive' }
];

// 題目資料
import { ref } from 'vue';
let nextQid = 1;
const questions = ref([
    // 預設一題範例
    { id: nextQid++, text: '', type: 'single', options: [''] }
]);
const questionTypeOptions = [
    { label: '單選', value: 'single' },
    { label: '複選', value: 'multiple' },
    { label: '簡答', value: 'text' }
];

function addQuestion() {
    questions.value.push({ id: nextQid++, text: '', type: 'single', options: [''] });
}
function removeQuestion(idx) {
    questions.value.splice(idx, 1);
}
function addOption(qidx) {
    questions.value[qidx].options.push('');
}
function removeOption(qidx, oidx) {
    questions.value[qidx].options.splice(oidx, 1);
}

function onSubmit() {
    // TODO: 儲存問卷設定（含題目）
    alert('問卷設定已儲存！\n' + JSON.stringify({ ...form, questions: questions.value }, null, 2));
}

function onCancel() {
    // TODO: 取消編輯，返回上一頁或重置表單
    form.title = '';
    form.description = '';
    form.status = null;
    form.startDate = null;
    form.endDate = null;
    questions.value = [{ id: nextQid++, text: '', type: 'single', options: [''] }];
}
</script>
<style scoped>
/* 可依需求補充自訂樣式 */
</style>
