<template>
    <!-- 1.頁面標題 -->
    <CommonLayout :title="'問卷填寫'">
        <!-- 2. 控制面板 -->
        <!-- 控制面板區（可擴充說明/提示等） -->
        <template #control-panel>
            <Card class="mb-4">
                <template #content>
                    <div class="section-control-panel">
                        <span class="font-semibold">填寫說明：</span>
                        <span>請如實填寫問卷資料，所有欄位皆為必填。</span>
                    </div>
                </template>
            </Card>
        </template>
        <!-- 3. 主要內容區域 -->
        <!-- 基本資料區塊 -->
        <div class="font-bold mb-3">基本資料</div>
        <div class="mb-3">
            <label for="name" class="block mb-1">姓名</label>
            <InputText id="name" v-model="form.name" class="w-full" required />
        </div>
        <div class="mb-3">
            <label for="email" class="block mb-1">Email</label>
            <InputText id="email" v-model="form.email" class="w-full" required />
        </div>
        <div class="mb-3">
            <label class="block mb-1">性別</label>
            <Dropdown v-model="form.gender" :options="genderOptions" optionLabel="label" optionValue="value" placeholder="請選擇性別" class="w-full" />
        </div>
        <!-- 問卷題目區塊 -->
        <form @submit.prevent="onSubmit">
            <div class="font-bold mb-3">問卷題目</div>
            <div v-for="(q, idx) in questions" :key="q.id" class="mb-4 p-3 border rounded bg-gray-50">
                <div class="font-semibold mb-2">{{ idx + 1 }}. {{ q.text }}</div>
                <div v-if="q.type === 'single'">
                    <div v-for="(opt, oidx) in q.options" :key="oidx" class="flex items-center mb-1">
                        <RadioButton v-model="answers[q.id]" :inputId="'q' + q.id + 'opt' + oidx" :value="opt" />
                        <label :for="'q' + q.id + 'opt' + oidx" class="ml-2">{{ opt }}</label>
                    </div>
                </div>
                <div v-else-if="q.type === 'multiple'">
                    <div v-for="(opt, oidx) in q.options" :key="oidx" class="flex items-center mb-1">
                        <Checkbox v-model="answers[q.id]" :inputId="'q' + q.id + 'opt' + oidx" :value="opt" />
                        <label :for="'q' + q.id + 'opt' + oidx" class="ml-2">{{ opt }}</label>
                    </div>
                </div>
                <div v-else-if="q.type === 'text'">
                    <InputText v-model="answers[q.id]" class="w-full" placeholder="請輸入答案" />
                </div>
            </div>
            <div class="mb-3">
                <label class="block mb-1">意見建議</label>
                <InputText v-model="form.feedback" class="w-full" />
            </div>
            <div class="flex justify-end gap-2 mt-4">
                <Button label="取消" icon="pi pi-times" class="p-button-secondary" @click="onCancel" type="button" />
                <Button label="送出" icon="pi pi-check" type="submit" />
            </div>
        </form>
    </CommonLayout>
</template>

<script setup>
import CommonLayout from '@/layout/CommonLayout.vue';
import Button from 'primevue/button';
import Card from 'primevue/card';
import Checkbox from 'primevue/checkbox';
import Dropdown from 'primevue/dropdown';
import InputText from 'primevue/inputtext';
import RadioButton from 'primevue/radiobutton';
import { reactive, ref } from 'vue';

const form = reactive({
    name: '',
    email: '',
    gender: null,
    feedback: ''
});

const genderOptions = [
    { label: '男', value: 'male' },
    { label: '女', value: 'female' },
    { label: '其他', value: 'other' }
];

// 假資料：實際應由 API 或父頁傳入
const questions = ref([
    { id: 1, text: '您最常使用的作業系統？', type: 'single', options: ['Windows', 'macOS', 'Linux'] },
    { id: 2, text: '您會使用哪些程式語言？', type: 'multiple', options: ['JavaScript', 'Python', 'Java', 'C#'] },
    { id: 3, text: '請簡述您對本問卷的建議', type: 'text', options: [] }
]);
const answers = reactive({});

function onSubmit() {
    // TODO: 處理問卷送出
    alert('問卷已送出，感謝您的填寫！\n' + JSON.stringify({ ...form, answers }, null, 2));
}

function onCancel() {
    // TODO: 取消填寫，重置表單
    form.name = '';
    form.email = '';
    form.gender = null;
    form.feedback = '';
    Object.keys(answers).forEach((k) => delete answers[k]);
}
</script>
<style scoped>
/* 可依需求補充自訂樣式 */
</style>
