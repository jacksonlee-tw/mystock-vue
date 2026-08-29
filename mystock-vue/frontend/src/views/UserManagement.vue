<template>
    <!-- 1.頁面標題 -->
    <CommonLayout :title="'使用者管理'">
        <template #status>
            <span :class="['status-text', 'p-tag', 'p-tag-sm', tagClass]">狀態：{{ statusText }}</span>
        </template>
        <template #action-buttons>
            <Button label="幫助" icon="pi pi-info-circle" class="p-button-help p-button-sm" @click="showHelp = true" />
        </template>
        <!-- 2. 控制面板 -->
        <template #control-panel>
            <Card class="mb-4">
                <template #content>
                    <div class="flex flex-wrap gap-3 items-end">
                        <InputText v-model="search.account" placeholder="帳號" />
                        <InputText v-model="search.name" placeholder="姓名" />
                        <Dropdown v-model="search.status" :options="statusOptions" optionLabel="label" optionValue="value" placeholder="狀態" />
                        <Button label="查詢" icon="pi pi-search" @click="onSearch" />
                        <Button label="清除" icon="pi pi-times" class="p-button-secondary" @click="onClear" />
                    </div>
                    <div class="flex items-center mt-4">
                        <div class="flex items-center gap-2">
                            <Button label="新增使用者" icon="pi pi-plus" @click="openDialog('add')" />
                        </div>
                    </div>
                </template>
            </Card>
        </template>

        <!-- 3. 主要內容區域 -->
        <DataTable :value="users" :paginator="true" :rows="10" :totalRecords="total" :loading="loading" @page="onPage" responsiveLayout="scroll">
            <Column field="account" header="帳號" />
            <Column field="name" header="姓名" />
            <Column field="email" header="Email" />
            <Column field="role" header="角色" />
            <Column field="status" header="狀態">
                <template #body="{ data }">
                    <Tag :value="data.status === 'active' ? '啟用' : '停用'" :severity="data.status === 'active' ? 'success' : 'danger'" />
                </template>
            </Column>
            <Column field="createdAt" header="建立時間" />
            <Column header="操作">
                <template #body="{ data }">
                    <Button icon="pi pi-pencil" class="p-button-text" @click="openDialog('edit', data)" />
                    <Button icon="pi pi-trash" class="p-button-text p-button-danger" @click="confirmDelete(data)" />
                </template>
            </Column>
        </DataTable>
        <MaximizableDialog v-model:visible="dialogVisible" :header="dialogMode === 'add' ? '新增使用者' : '編輯使用者'" :maximizable="true" :modal="true" :style="{ width: '500px' }">
            <form @submit.prevent="onSubmit">
                <div class="p-fluid">
                    <div class="form-row">
                        <label for="account" class="form-label">帳號</label>
                        <InputText id="account" v-model="form.account" :disabled="dialogMode === 'edit'" required class="form-input" />
                    </div>
                    <div class="form-row">
                        <label for="name" class="form-label">姓名</label>
                        <InputText id="name" v-model="form.name" required class="form-input" />
                    </div>
                    <div class="form-row">
                        <label for="email" class="form-label">Email</label>
                        <InputText id="email" v-model="form.email" required type="email" class="form-input" />
                    </div>
                    <div class="form-row">
                        <label for="role" class="form-label">角色</label>
                        <Dropdown id="role" v-model="form.role" :options="roleOptions" optionLabel="label" optionValue="value" required class="form-input" />
                    </div>
                    <div class="form-row">
                        <label for="status" class="form-label">狀態</label>
                        <div class="flex items-center gap-2">
                            <InputSwitch id="status" v-model="form.status" trueValue="active" falseValue="inactive" />
                            <span>{{ form.status === 'active' ? '啟用' : '停用' }}</span>
                        </div>
                    </div>
                </div>
                <div class="flex items-center justify-end gap-2 mt-4">
                    <Button label="取消" icon="pi pi-times" class="p-button-secondary" @click="dialogVisible = false" type="button" />
                    <Button label="儲存" icon="pi pi-check" type="submit" />
                </div>
            </form>
        </MaximizableDialog>
    </CommonLayout>

    <MaximizableDialog v-model:visible="dialogVisible" :header="dialogMode === 'add' ? '新增使用者' : '編輯使用者'" :maximizable="true" :modal="true" :style="{ width: '500px' }">
        <form @submit.prevent="onSubmit">
            <div class="p-fluid">
                <div class="form-row">
                    <label for="account" class="form-label">帳號</label>
                    <InputText id="account" v-model="form.account" :disabled="dialogMode === 'edit'" required class="form-input" />
                </div>
                <div class="form-row">
                    <label for="name" class="form-label">姓名</label>
                    <InputText id="name" v-model="form.name" required class="form-input" />
                </div>
                <div class="form-row">
                    <label for="email" class="form-label">Email</label>
                    <InputText id="email" v-model="form.email" required type="email" class="form-input" />
                </div>
                <div class="form-row">
                    <label for="role" class="form-label">角色</label>
                    <Dropdown id="role" v-model="form.role" :options="roleOptions" optionLabel="label" optionValue="value" required class="form-input" />
                </div>
                <div class="form-row">
                    <label for="status" class="form-label">狀態</label>
                    <div class="flex items-center gap-2">
                        <InputSwitch id="status" v-model="form.status" trueValue="active" falseValue="inactive" />
                        <span>{{ form.status === 'active' ? '啟用' : '停用' }}</span>
                    </div>
                </div>
            </div>
            <div class="flex items-center justify-end gap-2 mt-4">
                <Button label="取消" icon="pi pi-times" class="p-button-secondary" @click="dialogVisible = false" type="button" />
                <Button label="儲存" icon="pi pi-check" type="submit" />
            </div>
        </form>
    </MaximizableDialog>

    <Dialog v-model:visible="showHelp" header="操作說明" :modal="true" :style="{ width: '400px' }">
        <div>
            <ul class="list-disc pl-5">
                <li>可查詢、分頁、編輯、刪除使用者。</li>
                <li>點擊「新增使用者」可新增新帳號。</li>
                <li>點擊表格右側的鉛筆圖示可編輯，垃圾桶圖示可刪除。</li>
                <li>表單欄位需正確填寫，儲存後會顯示提示。</li>
            </ul>
        </div>
        <template #footer>
            <Button label="關閉" icon="pi pi-times" class="p-button-secondary" @click="showHelp = false" />
        </template>
    </Dialog>
</template>

<script setup>
import MaximizableDialog from '@/components/MaximizableDialog.vue';
import CommonLayout from '@/layout/CommonLayout.vue';

import Dialog from 'primevue/dialog';
import { useToast } from 'primevue/usetoast';
import { computed, reactive, ref } from 'vue';

const showHelp = ref(false);
const toast = useToast();

// 狀態顯示（僅顯示值，並依值給色系）
const statusText = ref('待開始'); // 僅狀態文字

// 根據狀態自動給 PrimeVue 樣板 class
const tagClass = computed(() => {
    switch (statusText.value) {
        case '啟用':
        case '已啟用':
            return 'p-tag-success';
        case '停用':
        case '已停用':
            return 'p-tag-danger';
        case '編輯中':
            return 'p-tag-info';
        case '待開始':
            return 'p-tag-secondary';
        case '只讀':
            return 'p-tag-secondary';
        case '草稿':
            return 'p-tag'; // PrimeVue 預設
        default:
            return '';
    }
});

const search = reactive({
    account: '',
    name: '',
    status: null
});
const statusOptions = [
    { label: '全部', value: null },
    { label: '啟用', value: 'active' },
    { label: '停用', value: 'inactive' }
];
const roleOptions = [
    { label: '管理員', value: 'admin' },
    { label: '一般使用者', value: 'user' }
];

const users = ref([
    { account: 'user1', name: '王小明', email: 'user1@mail.com', role: 'admin', status: 'active', createdAt: '2025-01-01' },
    { account: 'user2', name: '李小華', email: 'user2@mail.com', role: 'user', status: 'inactive', createdAt: '2025-02-01' }
]);
const total = ref(2);
const loading = ref(false);

const dialogVisible = ref(false);
const dialogMode = ref('add'); // 'add' or 'edit'
const form = reactive({
    account: '',
    name: '',
    email: '',
    role: '',
    status: 'active'
});

function openDialog(mode, data) {
    dialogMode.value = mode;
    if (mode === 'edit' && data) {
        Object.assign(form, data);
    } else {
        Object.assign(form, { account: '', name: '', email: '', role: '', status: 'active' });
    }
    dialogVisible.value = true;
}

function onSubmit() {
    if (dialogMode.value === 'add') {
        users.value.push({ ...form, createdAt: new Date().toISOString().slice(0, 10) });
        total.value++;
        toast.add({ severity: 'success', summary: '新增成功', detail: '已新增使用者', life: 2000 });
    } else {
        const idx = users.value.findIndex((u) => u.account === form.account);
        if (idx !== -1) {
            users.value[idx] = { ...form };
            toast.add({ severity: 'success', summary: '更新成功', detail: '已更新使用者', life: 2000 });
        }
    }
    dialogVisible.value = false;
}

function confirmDelete(data) {
    if (confirm(`確定要刪除帳號 ${data.account} 嗎？`)) {
        users.value = users.value.filter((u) => u.account !== data.account);
        total.value--;
        toast.add({ severity: 'info', summary: '已刪除', detail: '使用者已刪除', life: 2000 });
    }
}

function onSearch() {
    // TODO: 實作查詢功能
    toast.add({ severity: 'info', summary: '查詢', detail: '查詢功能尚未實作', life: 1500 });
}
function onClear() {
    search.account = '';
    search.name = '';
    search.status = null;
}
function onPage(e) {
    // TODO: 實作分頁功能
}
</script>

<style scoped>
/* 可依需求補充自訂樣式 */
</style>
