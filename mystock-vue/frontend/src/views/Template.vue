<template>
    <!-- 1.頁面標題 -->
    <CommonLayout :title="'樣板頁面'">
        <!-- 2. 控制面板 -->
        <template #control-panel>
            <Card class="mb-4">
                <template #content>
                    <div class="section-control-panel">
                        <label for="demo-dropdown">選擇類型：</label>
                        <Dropdown id="demo-dropdown" v-model="selected" :options="options" optionLabel="label" optionValue="value" placeholder="請選擇" />
                        <label for="demo-input" style="margin-left: 12px">關鍵字：</label>
                        <InputText id="demo-input" v-model="keyword" placeholder="請輸入關鍵字" style="width: 160px" />
                        <Button label="查詢" class="p-button-primary" aria-label="查詢" />
                    </div>
                </template>
            </Card>
        </template>
        <!-- 3. 主要內容區域 -->
        <div class="section-main-content">
            <h4 class="mt-5 mb-2">Tab</h4>
            <Tabs :value="activeTab">
                <TabList>
                    <Tab v-for="(tab, idx) in tabData" :key="idx" :value="idx">{{ tab.title }}</Tab>
                </TabList>
                <TabPanels>
                    <TabPanel v-for="(tab, idx) in tabData" :key="idx" :value="idx">
                        <p class="m-0">{{ tab.desc }}</p>
                    </TabPanel>
                </TabPanels>
            </Tabs>

            <!-- 新增 TabView 元件 -->
            <!-- 原本的表格 -->
            <h4 class="mt-5 mb-2">第一個列表</h4>
            <DataTable :value="tableData">
                <Column field="id" header="ID" sortable />
                <Column field="name" header="名稱" sortable />
                <Column field="status" header="狀態" sortable />
                <Column header="操作">
                    <template #body="slotProps">
                        <div>
                            <Button icon="pi pi-pencil" class="p-button-primary" aria-label="編輯" />
                            <Button icon="pi pi-trash" class="p-button-danger" aria-label="刪除" />
                            <Button label="檢視" class="p-button-info" aria-label="檢視" @click="openViewDialog(slotProps.data)" />
                        </div>
                    </template>
                </Column>
            </DataTable>

            <!-- 新增第二個 table 與分頁器 -->
            <h4 class="mt-5 mb-2">第二個列表</h4>
            <DataTable :value="pagedTable2Data">
                <Column field="code" header="代碼" sortable />
                <Column field="name" header="名稱" sortable />
                <Column field="qty" header="數量" sortable />
            </DataTable>
            <Paginator :rows="rows2" :totalRecords="table2Data.length" :first="first2" @page="onPageChange2" class="mt-2" />
        </div>
        <!-- 4. 操作按鈕區域 -->
        <div class="section-action-buttons mb-4">
            <Button icon="pi pi-plus" label="新增" class="p-button-primary" aria-label="新增" />
            <Button icon="pi pi-pencil" label="編輯" class="p-button-primary" aria-label="編輯" />
            <Button icon="pi pi-trash" label="刪除" class="p-button-danger" aria-label="刪除" />
        </div>
    </CommonLayout>

    <MaximizableDialog :visible="viewDialogVisible" header="檢視資料" :closable="true" :modal="true" :dialogStyle="{ width: isMobile ? '90vw' : '600px' }" @update:visible="viewDialogVisible = $event">
        <div v-if="viewData">
            <DataTable :value="Object.entries(viewData)" class="popup-table" :rows="10" :paginator="false" style="width: 100%">
                <Column field="0" header="欄位" />
                <Column field="1" header="值">
                    <template #body="slotProps">
                        <template v-if="slotProps.data[0] === 'name'">
                            <InputText v-model="viewData.name" style="width: 100%" :disabled="!popupEditable" />
                        </template>
                        <template v-else-if="slotProps.data[0] === 'status'">
                            <InputSwitch v-model="viewData.status" :disabled="!popupEditable" />
                        </template>
                        <template v-else>
                            {{ slotProps.data[1] }}
                        </template>
                    </template>
                </Column>
            </DataTable>
            <div style="text-align: left; margin-top: 12px">
                <Button label="編輯" class="p-button-primary" @click="popupEditable = true" v-if="!popupEditable" />
                <Button label="存檔" class="p-button-success" @click="savePopupEdit" v-if="popupEditable" />
            </div>
        </div>
        <template #footer>
            <Button label="關閉" class="p-button-secondary" @click="viewDialogVisible = false" />
            <Button label="關閉" icon="pi pi-times" class="p-button-secondary" @click="viewDialogVisible = false" />
        </template>
    </MaximizableDialog>
</template>

<script setup>
function savePopupEdit() {
    popupEditable.value = false;
    // 這裡可加 emit 或 API 呼叫
}
import MaximizableDialog from '@/components/MaximizableDialog.vue';
import CommonLayout from '@/layout/CommonLayout.vue';
import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dropdown from 'primevue/dropdown';
import InputText from 'primevue/inputtext';
import Paginator from 'primevue/paginator';
import TabPanel from 'primevue/tabpanel';
import Tabs from 'primevue/tabs';
import { computed, ref } from 'vue';
const activeTab = ref(0);
const popupEditable = ref(false);
function onTabChange(e) {
    activeTab.value = e.index;
}

const options = [
    { value: 'a', label: '選項A' },
    { value: 'b', label: '選項B' },
    { value: 'c', label: '選項C' }
];
const selected = ref(options[0].value);
const keyword = ref('');

const tableData = [
    { id: 1, name: '王小明', status: '啟用' },
    { id: 2, name: '李小華', status: '停用' },
    { id: 3, name: '陳大同', status: '啟用' }
];

// 第二個 table 測試資料
const table2Data = [
    { code: 'A001', name: '商品A', qty: 10 },
    { code: 'B002', name: '商品B', qty: 5 },
    { code: 'C003', name: '商品C', qty: 8 },
    { code: 'D004', name: '商品D', qty: 12 },
    { code: 'E005', name: '商品E', qty: 7 }
];

const rows2 = 2; // 第二個 table 每頁顯示筆數
const first2 = ref(0);
const pagedTable2Data = computed(() => {
    return table2Data.slice(first2.value, first2.value + rows2);
});
function onPageChange2(event) {
    first2.value = event.first;
}

const viewDialogVisible = ref(false);
const viewData = ref(null);
const isMobile = ref(window.innerWidth <= 768);
const tabData = [
    { title: '分頁一', desc: '這是分頁一的假資料內容' },
    { title: '分頁二', desc: '這是分頁二的假資料內容' },
    { title: '分頁三', desc: '這是分頁三的假資料內容' }
];
function handleResize() {
    isMobile.value = window.innerWidth <= 768;
}
window.addEventListener('resize', handleResize);
function openViewDialog(row) {
    viewData.value = row;
    viewDialogVisible.value = true;
    popupEditable.value = false;
}
</script>
<style scoped>
/* 可依需求補充自訂樣式 */
</style>
