<template>
    <!-- 1.頁面標題 -->
    <CommonLayout :title="'問卷管理'">
        <template #status>
            <span :class="['status-text', 'p-tag', 'p-tag-sm', tagClass]">狀態：{{ statusText }}</span>
        </template>
        <template #action-buttons>
            <Button label="幫助" icon="pi pi-info-circle" class="p-button-help p-button-sm" @click="showHelp = true" />
        </template>
        <!-- 2. 控制面板 -->
        <!-- 查詢區 -->
        <template #control-panel>
            <Card class="mb-4">
                <template #content>
                    <div class="flex flex-wrap gap-3 items-end">
                        <InputText v-model="search.title" placeholder="問卷名稱" />
                        <Select v-model="search.status" :options="statusOptions" optionLabel="label" optionValue="value" placeholder="狀態" />
                        <Calendar v-model="search.dateRange" selectionMode="range" placeholder="建立日期區間" dateFormat="yy-mm-dd" />
                        <Button label="查詢" icon="pi pi-search" @click="onSearch" />
                        <Button label="清除" icon="pi pi-times" class="p-button-secondary" @click="onClear" />
                        <Button label="新增問卷" icon="pi pi-plus" @click="openDialog('add')" />
                    </div>
                </template>
            </Card>
        </template>
        <!-- 3. 主要內容區域 -->
        <!-- 資料表格 -->
        <DataTable :value="questionnaires" :paginator="true" :rows="10" :totalRecords="total" :loading="loading" @page="onPage" responsiveLayout="scroll">
            <Column field="title" header="問卷名稱" />
            <Column field="status" header="狀態">
                <template #body="{ data }">
                    <Tag :value="statusLabel(data.status)" :severity="statusSeverity(data.status)" />
                </template>
            </Column>
            <Column field="createdAt" header="建立日期" />
            <Column field="endAt" header="截止日期" />
            <Column field="count" header="填答人數" />
            <Column header="操作">
                <template #body="{ data }">
                    <Button icon="pi pi-eye" class="p-button-text" @click="preview(data)" />
                    <Button icon="pi pi-pencil" class="p-button-text" @click="openDialog('edit', data)" />
                    <Button icon="pi pi-trash" class="p-button-text p-button-danger" @click="confirmDelete(data)" />
                </template>
            </Column>
        </DataTable>
        <!-- 新增/編輯 Dialog -->
        <MaximizableDialog v-model:visible="dialogVisible" :header="dialogMode === 'add' ? '新增問卷' : '編輯問卷'" :maximizable="true" :modal="true" :style="{ width: '500px' }">
            <form @submit.prevent="onSubmit">
                <div class="p-fluid">
                    <div class="form-row">
                        <label for="title" class="form-label">問卷名稱</label>
                        <InputText id="title" v-model="form.title" required class="form-input" />
                    </div>
                    <div class="form-row">
                        <label for="status" class="form-label">狀態</label>
                        <Select id="status" v-model="form.status" :options="statusOptions" optionLabel="label" optionValue="value" required class="form-input" />
                    </div>
                    <div class="form-row">
                        <label for="desc" class="form-label">說明</label>
                        <InputText id="desc" v-model="form.desc" class="form-input" />
                    </div>
                    <div class="form-row">
                        <label for="date" class="form-label">期間</label>
                        <Calendar v-model="form.dateRange" selectionMode="range" placeholder="開始/結束日期" dateFormat="yy-mm-dd" class="form-input" />
                    </div>
                </div>
                <div class="flex items-center justify-end gap-2 mt-4">
                    <Button label="取消" icon="pi pi-times" class="p-button-secondary" @click="dialogVisible = false" type="button" />
                    <Button label="儲存" icon="pi pi-check" type="submit" />
                </div>
            </form>
        </MaximizableDialog>
        <!-- 幫助 Dialog -->
        <Dialog v-model:visible="showHelp" header="操作說明" :modal="true" :style="{ width: '400px' }">
            <div>
                <ul class="list-disc pl-5">
                    <li>可查詢、分頁、編輯、刪除、預覽問卷。</li>
                    <li>點擊「新增問卷」可新增新問卷。</li>
                    <li>表格右側的鉛筆圖示可編輯，垃圾桶圖示可刪除，眼睛圖示可預覽。</li>
                    <li>表單欄位需正確填寫，儲存後會顯示提示。</li>
                </ul>
            </div>
            <template #footer>
                <Button label="關閉" icon="pi pi-times" class="p-button-secondary" @click="showHelp = false" />
            </template>
        </Dialog>
    </CommonLayout>
</template>

<script setup>
import MaximizableDialog from '@/components/MaximizableDialog.vue';
import CommonLayout from '@/layout/CommonLayout.vue';
import Calendar from 'primevue/calendar';
import Dialog from 'primevue/dialog';
import Tag from 'primevue/tag';
import { useToast } from 'primevue/usetoast';
import { computed, reactive, ref } from 'vue';

const showHelp = ref(false);
const toast = useToast();

const statusText = ref('啟用'); // 狀態可依需求切換

const tagClass = computed(() => {
    switch (statusText.value) {
        case '啟用':
            return 'p-tag-success';
        case '停用':
            return 'p-tag-danger';
        case '草稿':
            return 'p-tag';
        default:
            return '';
    }
});

const search = reactive({
    title: '',
    status: null,
    dateRange: null
});
const statusOptions = [
    { label: '啟用', value: 'active' },
    { label: '停用', value: 'inactive' },
    { label: '草稿', value: 'draft' }
];

const questionnaires = ref([
    { title: '顧客滿意度調查', status: 'active', createdAt: '2025-01-01', endAt: '2025-01-31', count: 120 },
    { title: '產品回饋問卷', status: 'draft', createdAt: '2025-02-01', endAt: '2025-02-28', count: 45 }
]);
const total = ref(2);
const loading = ref(false);

const dialogVisible = ref(false);
const dialogMode = ref('add');
const form = reactive({
    title: '',
    status: 'active',
    desc: '',
    dateRange: null
});

function openDialog(mode, data) {
    dialogMode.value = mode;
    if (mode === 'edit' && data) {
        Object.assign(form, { ...data, dateRange: [data.createdAt, data.endAt] });
    } else {
        Object.assign(form, { title: '', status: 'active', desc: '', dateRange: null });
    }
    dialogVisible.value = true;
}

function onSubmit() {
    if (dialogMode.value === 'add') {
        questionnaires.value.push({
            ...form,
            createdAt: form.dateRange ? form.dateRange[0] : '',
            endAt: form.dateRange ? form.dateRange[1] : '',
            count: 0
        });
        total.value++;
        toast.add({ severity: 'success', summary: '新增成功', detail: '已新增問卷', life: 2000 });
    } else {
        // 編輯
        const idx = questionnaires.value.findIndex((q) => q.title === form.title);
        if (idx !== -1) {
            questionnaires.value[idx] = {
                ...form,
                createdAt: form.dateRange ? form.dateRange[0] : '',
                endAt: form.dateRange ? form.dateRange[1] : '',
                count: questionnaires.value[idx].count
            };
            toast.add({ severity: 'success', summary: '更新成功', detail: '已更新問卷', life: 2000 });
        }
    }
    dialogVisible.value = false;
}

function confirmDelete(data) {
    if (confirm(`確定要刪除問卷「${data.title}」嗎？`)) {
        questionnaires.value = questionnaires.value.filter((q) => q.title !== data.title);
        total.value--;
        toast.add({ severity: 'info', summary: '已刪除', detail: '問卷已刪除', life: 2000 });
    }
}

function preview(data) {
    toast.add({ severity: 'info', summary: '預覽', detail: `預覽問卷：${data.title}`, life: 1500 });
}

function onSearch() {
    toast.add({ severity: 'info', summary: '查詢', detail: '查詢功能尚未實作', life: 1500 });
}
function onClear() {
    search.title = '';
    search.status = null;
    search.dateRange = null;
}
function onPage(e) {
    // TODO: 實作分頁功能
}

// 狀態顯示用
function statusLabel(status) {
    switch (status) {
        case 'active':
            return '啟用';
        case 'inactive':
            return '停用';
        case 'draft':
            return '草稿';
        default:
            return '';
    }
}
function statusSeverity(status) {
    switch (status) {
        case 'active':
            return 'success';
        case 'inactive':
            return 'danger';
        case 'draft':
            return '';
        default:
            return '';
    }
}
</script>
<style scoped>
/* 可依需求補充自訂樣式 */
</style>
