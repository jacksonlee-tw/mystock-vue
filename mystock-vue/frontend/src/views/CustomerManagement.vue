<template>
    <!-- 1.頁面標題 -->
    <CommonLayout :title="'客戶管理'">
        <!-- 2. 控制面板 -->
        <template #control-panel>
            <Card class="mb-4">
                <template #content>
                    <div class="section-control-panel">
                        <InputText v-model="search" placeholder="搜尋客戶..." />
                        <Button label="查詢" class="p-button-primary" @click="onSearch" />
                    </div>
                </template>
            </Card>
        </template>
        <!-- 3. 主要內容區域 -->
        <div class="section-main-content">
            <Tabs :value="activeTab" @update:value="activeTab = $event">
                <TabList>
                    <Tab :value="0">全部客戶</Tab>
                    <Tab :value="1">VIP 客戶</Tab>
                </TabList>
                <TabPanels>
                    <TabPanel :value="0">
                        <DataTable :value="customers">
                            <Column field="id" header="ID" />
                            <Column field="name" header="姓名" />
                            <Column header="狀態">
                                <template #body="slotProps">
                                    <InputSwitch v-model="slotProps.data.status" :true-value="'啟用'" :false-value="'停用'" />
                                </template>
                            </Column>
                            <Column header="操作">
                                <template #body="slotProps">
                                    <Button icon="pi pi-pencil" class="p-button-primary" @click="edit(slotProps.data)" />
                                    <Button icon="pi pi-trash" class="p-button-danger" @click="remove(slotProps.data)" />
                                </template>
                            </Column>
                        </DataTable>
                    </TabPanel>
                    <TabPanel :value="1">
                        <DataTable :value="vipCustomers">
                            <Column field="id" header="ID" />
                            <Column field="name" header="姓名" />
                            <Column field="status" header="狀態" />
                        </DataTable>
                    </TabPanel>
                </TabPanels>
            </Tabs>
        </div>
        <div class="section-action-buttons mb-4">
            <Button label="新增客戶" class="p-button-success" @click="showAddDialog = true" />
        </div>
        <Dialog v-model:visible="showAddDialog" header="新增客戶" :modal="true">
            <div>
                <InputText v-model="newCustomer.name" placeholder="姓名" />
                <Button label="儲存" class="p-button-primary" @click="save" />
            </div>
        </Dialog>
    </CommonLayout>
</template>

<script setup>
import CommonLayout from '@/layout/CommonLayout.vue';
import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dialog from 'primevue/dialog';
import InputSwitch from 'primevue/inputswitch';
import InputText from 'primevue/inputtext';
import Tab from 'primevue/tab';
import TabList from 'primevue/tablist';
import TabPanel from 'primevue/tabpanel';
import TabPanels from 'primevue/tabpanels';
import Tabs from 'primevue/tabs';
import { computed, ref } from 'vue';

const search = ref('');
const activeTab = ref(0);
const customers = ref([
    { id: 1, name: '王小明', status: '啟用' },
    { id: 2, name: '李小華', status: '停用' }
]);
const vipCustomers = computed(() => customers.value.filter((c) => c.status === '啟用'));
const showAddDialog = ref(false);
const newCustomer = ref({ name: '' });

function onSearch() {
    /* 搜尋邏輯 */
}
function edit(row) {
    /* 編輯邏輯 */
}
function remove(row) {
    /* 刪除邏輯 */
}
function save() {
    if (newCustomer.value.name) {
        customers.value.push({
            id: customers.value.length + 1,
            name: newCustomer.value.name,
            status: '啟用'
        });
        newCustomer.value.name = '';
        showAddDialog.value = false;
    }
}
</script>
