<template>
    <!-- 1.頁面標題 -->
    <CommonLayout title="問卷表格">
        <!-- 3. 主要內容區域 -->
        <template #default>
            <div class="module-content">
                <DataTable :value="filteredData" scrollable scrollHeight="400px" class="table-module">
                    <Column field="id" header="料號">
                        <template #body="{ data }">
                            <div>{{ data.id || '0' }}</div>
                        </template>
                    </Column>
                    <Column field="name" header="料名">
                        <template #body="{ data }">
                            <Select v-model="data.name" :options="nameOptions" placeholder="請選擇" class="w-full" style="max-width: 100%" />
                        </template>
                    </Column>
                    <Column field="note1" header="備註1">
                        <template #body="{ data }">
                            <div>{{ data.note1 || '0' }}</div>
                        </template>
                    </Column>
                    <Column field="note2" header="備註2">
                        <template #body="{ data }">
                            <InputNumber v-model="data.note2" placeholder="輸入數字" class="w-full" style="max-width: 100%" />
                        </template>
                    </Column>
                    <Column field="field5" header="欄位5">
                        <template #body="{ data }">
                            <Select v-model="data.field5" :options="field5Options" placeholder="請選擇" :disabled="true" class="w-full" style="max-width: 100%" />
                        </template>
                    </Column>
                    <Column field="field6" header="欄位6">
                        <template #body="{ data }">
                            <InputText v-model="data.field6" placeholder="輸入內容" class="w-full" style="max-width: 100%" />
                        </template>
                    </Column>
                    <Column field="field9" header="欄位9">
                        <template #body="{ data }">
                            <InputText v-model="data.field9" placeholder="輸入內容" class="w-full" style="max-width: 100%" />
                        </template>
                    </Column>
                    <Column field="field10" header="欄位10">
                        <template #body="{ data }">
                            <InputText v-model="data.field10" placeholder="輸入內容" class="w-full" style="max-width: 100%" />
                        </template>
                    </Column>
                    <Column field="field11" header="欄位11">
                        <template #body="{ data }">
                            <Select v-model="data.field11" :options="nameOptions" placeholder="請選擇" class="w-full" style="max-width: 100%" />
                        </template>
                    </Column>
                    <Column field="field12" header="欄位12">
                        <template #body="{ data }">
                            <InputNumber v-model="data.field12" placeholder="輸入數字" class="w-full" />
                        </template>
                    </Column>
                    <Column field="field13" header="欄位13">
                        <template #body="{ data }">
                            <InputText v-model="data.field13" placeholder="輸入內容" class="w-full" style="max-width: 100%" />
                        </template>
                    </Column>
                    <Column field="field14" header="欄位14">
                        <template #body="{ data }">
                            <InputText v-model="data.field14" placeholder="輸入內容" class="w-full" style="max-width: 100%" />
                        </template>
                    </Column>
                </DataTable>
            </div>
        </template>
    </CommonLayout>
</template>

<script setup>
import CommonLayout from '@/layout/CommonLayout.vue';
import { useToast } from 'primevue/usetoast';
import { computed, onMounted, ref } from 'vue';

const toast = useToast();

// 搜尋相關
const searchQuery = ref('');
const showAddDialog = ref(false);
const submitted = ref(false);
const saving = ref(false);

// 分頁相關
const first = ref(0);
const pageSize = ref(10);
const totalItems = ref(100);
const currentPage = computed(() => Math.floor(first.value / pageSize.value) + 1);

// 表格資料
const tableData = ref([
    {
        id: '001',
        name: '',
        note1: '0',
        note2: 0,
        field5: '',
        field6: '',
        field9: '',
        field10: '',
        field11: '',
        field12: null,
        field13: '',
        field14: ''
    },
    {
        id: '002',
        name: '',
        note1: '0',
        note2: null,
        field5: '',
        field6: '',
        field9: '',
        field10: '',
        field11: '',
        field12: null,
        field13: '',
        field14: ''
    },
    {
        id: '003',
        name: '',
        note1: '0',
        note2: null,
        field5: '',
        field6: '',
        field9: '',
        field10: '',
        field11: '',
        field12: null,
        field13: '',
        field14: ''
    },
    {
        id: '004',
        name: '',
        note1: '0',
        note2: null,
        field5: '',
        field6: '',
        field9: '',
        field10: '',
        field11: '',
        field12: null,
        field13: '',
        field14: ''
    },
    {
        id: '005',
        name: '',
        note1: '0',
        note2: null,
        field5: '',
        field6: '',
        field9: '',
        field10: '',
        field11: '',
        field12: null,
        field13: '',
        field14: ''
    },
    {
        id: '006',
        name: '',
        note1: '0',
        note2: null,
        field5: '',
        field6: '',
        field9: '',
        field10: '',
        field11: '',
        field12: null,
        field13: '',
        field14: ''
    },
    {
        id: '004',
        name: '',
        note1: '0',
        note2: null,
        field5: '',
        field6: '',
        field9: '',
        field10: '',
        field11: '',
        field12: null,
        field13: '',
        field14: ''
    },
    {
        id: '005',
        name: '',
        note1: '0',
        note2: null,
        field5: '',
        field6: '',
        field9: '',
        field10: '',
        field11: '',
        field12: null,
        field13: '',
        field14: ''
    },
    {
        id: '006',
        name: '',
        note1: '0',
        note2: null,
        field5: '',
        field6: '',
        field9: '',
        field10: '',
        field11: '',
        field12: null,
        field13: '',
        field14: ''
    }
]);

const secondTableData = ref([
    {
        id: '006',
        name: '',
        note1: '0',
        note2: 0,
        field5: '',
        field6: '',
        field9: '',
        field10: '',
        field11: '',
        field12: null,
        field13: '',
        field14: ''
    }
]);

// 選項資料
const nameOptions = ref([
    { label: '選項1', value: 'option1' },
    { label: '選項2', value: 'option2' },
    { label: '選項3', value: 'option3' }
]);

const field5Options = ref([
    { label: '欄位5選項1', value: 'field5_1' },
    { label: '欄位5選項2', value: 'field5_2' }
]);

const statusOptions = ref([
    { label: '草稿', value: 'draft' },
    { label: '進行中', value: 'active' },
    { label: '已結束', value: 'ended' }
]);

// 新增問卷資料
const newQuestionnaire = ref({
    title: '',
    description: '',
    status: null
});

// 計算過濾後的資料
const filteredData = computed(() => {
    if (!searchQuery.value) return tableData.value;

    return tableData.value.filter((item) => Object.values(item).some((value) => String(value).toLowerCase().includes(searchQuery.value.toLowerCase())));
});

// 方法
const search = () => {
    console.log('搜尋:', searchQuery.value);
    toast.add({
        severity: 'info',
        summary: '搜尋',
        detail: `搜尋關鍵字：${searchQuery.value}`,
        life: 3000
    });
};

const resetSearch = () => {
    searchQuery.value = '';
};

const onPageChange = (event) => {
    first.value = event.first;
};

const hideAddDialog = () => {
    showAddDialog.value = false;
    submitted.value = false;
    newQuestionnaire.value = {
        title: '',
        description: '',
        status: null
    };
};

const saveQuestionnaire = () => {
    submitted.value = true;

    if (!newQuestionnaire.value.title) {
        return;
    }

    saving.value = true;

    // 模擬儲存
    setTimeout(() => {
        tableData.value.push({
            id: String(tableData.value.length + 1).padStart(3, '0'),
            name: newQuestionnaire.value.title,
            note1: '0',
            note2: null,
            field5: '',
            field6: '',
            field9: '',
            field10: '',
            field11: '',
            field12: null,
            field13: '',
            field14: ''
        });

        toast.add({
            severity: 'success',
            summary: '成功',
            detail: '問卷新增成功',
            life: 3000
        });

        saving.value = false;
        hideAddDialog();
    }, 1000);
};

// 滾動同步功能
const setupScrollSync = () => {
    const allHeaderWrappers = document.querySelectorAll('.scrollable-header-wrapper');
    const allContentWrappers = document.querySelectorAll('.scrollable-content-wrapper');

    allContentWrappers.forEach((contentWrapper, index) => {
        const headerWrapper = allHeaderWrappers[index];
        if (headerWrapper && contentWrapper) {
            contentWrapper.addEventListener('scroll', function () {
                headerWrapper.scrollLeft = contentWrapper.scrollLeft;
            });
        }
    });
};

// 動態同步表頭和表體欄位寬度（支援響應式滿版）
const syncColumnWidths = () => {
    const headerTables = document.querySelectorAll('.scrollable-header-table');
    const bodyTables = document.querySelectorAll('.scrollable-body-table');

    headerTables.forEach((headerTable, tableIndex) => {
        const bodyTable = bodyTables[tableIndex];
        if (!bodyTable) return;

        const headerCells = headerTable.querySelectorAll('th');
        const firstRowCells = bodyTable.querySelectorAll('tr:first-child td');

        if (headerCells.length !== firstRowCells.length) return;

        // 清除之前設定的寬度
        headerCells.forEach((th) => {
            th.style.width = '';
            th.style.minWidth = '';
            th.style.maxWidth = '';
        });
        const allBodyCells = bodyTable.querySelectorAll('td');
        allBodyCells.forEach((td) => {
            td.style.width = '';
            td.style.minWidth = '';
            td.style.maxWidth = '';
        });

        // 清除表格寬度讓其自然填滿
        headerTable.style.width = '';
        bodyTable.style.width = '';

        requestAnimationFrame(() => {
            // 獲取可用寬度
            const headerWrapper = headerTable.closest('.scrollable-header-wrapper');
            const bodyWrapper = bodyTable.closest('.scrollable-content-wrapper');

            if (!headerWrapper || !bodyWrapper) return;

            const availableWidth = Math.min(headerWrapper.clientWidth, bodyWrapper.clientWidth);
            const columnCount = headerCells.length;

            // 計算每欄的最小需求寬度（完全動態，根據內容自動調整）
            const minWidths = [];
            let totalMinWidth = 0;

            for (let i = 0; i < columnCount; i++) {
                // 暫時設定為自動寬度來測量實際內容需求
                headerCells[i].style.width = 'auto';
                const columnCells = bodyTable.querySelectorAll(`td:nth-child(${i + 1})`);
                columnCells.forEach((cell) => (cell.style.width = 'auto'));

                // 獲取自然寬度
                const headerWidth = headerCells[i].offsetWidth;
                let maxBodyWidth = 0;
                columnCells.forEach((cell) => {
                    maxBodyWidth = Math.max(maxBodyWidth, cell.offsetWidth);
                });

                // 最小寬度為內容需求寬度和基本寬度的較大值
                const minWidth = Math.max(headerWidth, maxBodyWidth, 100);
                minWidths.push(minWidth);
                totalMinWidth += minWidth;
            }

            // 計算實際寬度分配
            const columnWidths = [];
            if (totalMinWidth >= availableWidth) {
                // 空間不足，使用最小寬度
                columnWidths.push(...minWidths);
            } else {
                // 空間充足，平均分配剩餘空間
                const extraSpace = availableWidth - totalMinWidth;
                const extraPerColumn = extraSpace / columnCount;

                for (let i = 0; i < columnCount; i++) {
                    columnWidths.push(minWidths[i] + extraPerColumn);
                }
            }

            // 應用計算出的寬度
            headerCells.forEach((th, index) => {
                const width = `${columnWidths[index]}px`;
                th.style.width = width;
                th.style.minWidth = width;
                th.style.maxWidth = width;
            });

            // 為每欄的所有 TD 設定相同寬度
            for (let i = 0; i < columnWidths.length; i++) {
                const width = `${columnWidths[i]}px`;
                const columnCells = bodyTable.querySelectorAll(`td:nth-child(${i + 1})`);
                columnCells.forEach((cell) => {
                    cell.style.width = width;
                    cell.style.minWidth = width;
                    cell.style.maxWidth = width;
                });
            }

            // 設定表格總寬度
            const totalWidth = columnWidths.reduce((sum, width) => sum + width, 0);
            headerTable.style.width = `${Math.ceil(totalWidth)}px`;
            bodyTable.style.width = `${Math.ceil(totalWidth)}px`;
        });
    });
};

// 調整表頭 padding
const adjustHeaderPadding = () => {
    const bodyContainers = document.querySelectorAll('.table-body-container');
    const headerSections = document.querySelectorAll('.scrollable-header-section');

    bodyContainers.forEach((bodyContainer, index) => {
        const headerSection = headerSections[index];
        if (bodyContainer && headerSection) {
            const hasVerticalScroll = bodyContainer.scrollHeight > bodyContainer.clientHeight;
            if (hasVerticalScroll) {
                const scrollbarWidth = bodyContainer.offsetWidth - bodyContainer.clientWidth;
                headerSection.style.paddingRight = scrollbarWidth + 'px';
            } else {
                headerSection.style.paddingRight = '0px';
            }
        }
    });
};

onMounted(() => {
    setTimeout(() => {
        setupScrollSync();
        adjustHeaderPadding();
        syncColumnWidths(); // 同步欄位寬度

        // 視窗大小改變時重新同步
        window.addEventListener('resize', () => {
            adjustHeaderPadding();
            setTimeout(syncColumnWidths, 50); // 延遲一點確保DOM更新完成
        });

        const observers = [];
        const tableBodies = document.querySelectorAll('.scrollable-body-table tbody');
        tableBodies.forEach((tableBody) => {
            if (tableBody) {
                const observer = new MutationObserver(() => {
                    adjustHeaderPadding();
                    setTimeout(syncColumnWidths, 50); // 內容變化時重新同步寬度
                });
                observer.observe(tableBody, { childList: true, subtree: true });
                observers.push(observer);
            }
        });
    }, 200); // 稍微延長初始延遲，確保所有元素都渲染完成
});
</script>

<style scoped>
@import '@/assets/survey.css';
:deep(.table-module th),
:deep(.table-module .p-datatable .p-datatable-thead > tr > th),
:deep(.table-module .p-datatable-scrollable-header-table th),
:deep(.table-module .p-datatable-scrollable-header th),
:deep(.table-module th.p-frozen-column) {
    min-width: 100px !important;
    width: auto !important;
    white-space: nowrap !important;
}
</style>
