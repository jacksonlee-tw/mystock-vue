<script setup>
import CommonLayout from '@/layout/CommonLayout.vue';
import { computed, onBeforeMount, onMounted, reactive, ref } from 'vue';
// import apiClient from '@/service/axios';
// import formatDate from '@/service/dateUtils';
import { FilterMatchMode } from '@primevue/core/api';
import { useToast } from 'primevue/usetoast';

// 響應式數據
const users = ref([]);
const productDialog = ref(false);
const deleteUserDialog = ref(false);
const selectedUsers = ref(null);
const dt = ref(null);
const submitted = ref(false);
const loading = ref([false, false, false]);
const formValid = ref(false);

const user = reactive({
    loginAccount: '',
    empId: '',
    cname: '',
    email: '',
    disabled: '',
    tcUsergroupCollection: []
});

// 獨立的查詢條件物件，與編輯用的 user 物件分離
const searchConditions = reactive({
    loginAccount: '',
    empId: '',
    cname: '',
    email: '',
    selectedGroup: null,
    disabled: null
});

const filters = ref({});
const userVO = ref({});
const tcGroup = ref([]);
const tcUsergroupSelected = ref([]);
const errors = ref({});

// 使用 Toast
const toast = useToast();

const selectedGroupItems = computed(() => {
    return tcGroup.value.filter((item) => tcUsergroupSelected.value.includes(item.id));
});

// 方法
const hideDialog = () => {
    productDialog.value = false;
    submitted.value = false;
};

const loadGroupsForDialog = async () => {
    try {
        console.log('開始載入群組資料...');
        const response = await apiClient.get('/controller/usercrud/getGroup');

        console.log('API 回應:', response);
        console.log('response.data:', response.data);
        console.log('response.data 類型:', typeof response.data);
        console.log('response.data 是否為陣列:', Array.isArray(response.data));

        // 檢查 response.data 是否為陣列
        if (!Array.isArray(response.data)) {
            console.error('API 回傳的資料不是陣列:', response.data);
            tcGroup.value = [];
            return;
        }

        // 編輯頁面不需要「---全部---」選項，只使用原始資料
        // 加強過濾邏輯，確保移除所有空白或無效的選項
        tcGroup.value = response.data.filter((item) => item && item.id !== null && item.id !== undefined && item.id !== '' && item.displayIdentifier && item.displayIdentifier.trim() !== '' && item.displayIdentifier.trim() !== '---全部---');
        console.log('載入群組資料成功:', tcGroup.value);
        console.log('過濾後的群組數量:', tcGroup.value.length);
    } catch (error) {
        console.error('獲取群組資料失敗:', error);
        console.error('錯誤詳細資訊:', error.response?.data);
        console.error('HTTP 狀態碼:', error.response?.status);

        // 設定空陣列作為後備
        tcGroup.value = [];

        // 顯示錯誤提示
        toast.add({
            severity: 'error',
            summary: '載入失敗',
            detail: '無法載入群組資料，請重試',
            life: 3000
        });
    }
};

const saveUser = async () => {
    console.log('開始儲存使用者資料:');
    submitted.value = true;

    // 檢查必填欄位：員工姓名
    if (!userVO.value.cname || !userVO.value.cname.trim()) {
        toast.add({
            severity: 'warn',
            summary: '驗證失敗',
            detail: '員工姓名為必填欄位',
            life: 3000
        });
        return;
    }

    try {
        // 直接準備 UserVO 格式，不需要轉換
        const userVOData = {
            id: userVO.value.id || null,
            loginAccount: userVO.value.loginAccount || '',
            empId: userVO.value.empId || '',
            cname: userVO.value.cname || '',
            email: userVO.value.email || '',
            disabled: userVO.value.disabled === 'true' || userVO.value.disabled === true,
            // 直接使用群組 ID 陣列作為 userGroupIdList
            userGroupIdList: userVO.value.tcUsergroupCollection || []
        };

        console.log('準備發送的 UserVO:', userVOData);

        let response;
        if (userVOData.id) {
            console.log('更新使用者資料:', userVOData);
            // 更新使用者
            response = await apiClient.put('/controller/usercrud', userVOData);
            toast.add({
                severity: 'success',
                summary: '更新成功',
                detail: '使用者資料已更新',
                life: 3000
            });
            console.log('更新回應:', response.data);
        } else {
            // 新增使用者
            console.log('新增使用者資料:', userVOData);
            response = await apiClient.post('/controller/usercrud', userVOData);
            toast.add({
                severity: 'success',
                summary: '新增成功',
                detail: '使用者資料已新增',
                life: 3000
            });
            console.log('新增回應:', response.data);
        }

        // 成功後關閉對話框
        productDialog.value = false;
        submitted.value = false;

        // 重置表單資料
        userVO.value = {};
        Object.assign(user, {
            loginAccount: '',
            empId: '',
            cname: '',
            email: '',
            disabled: '',
            tcUsergroupCollection: []
        });

        // 重新整理使用者列表
        console.log('開始重新整理使用者列表...');
        await fetchUsers();
        console.log('使用者列表重新整理完成');
    } catch (error) {
        console.error('儲存使用者資料失敗:', error);

        let errorMessage = '儲存使用者資料時發生錯誤';
        if (error.response?.data?.message) {
            errorMessage = error.response.data.message;
        } else if (error.response?.data) {
            errorMessage = error.response.data;
        }

        toast.add({
            severity: 'error',
            summary: '儲存失敗',
            detail: errorMessage,
            life: 5000
        });
    }
};

const openNew = async () => {
    await loadGroupsForDialog();
    userVO.value = {
        disabled: 'false', // 新增使用者時預設為啟用
        tcUsergroupCollection: []
    };
    submitted.value = false;
    productDialog.value = true;
};

const editUser = async (editUser) => {
    try {
        // 1. 重新載入群組資料
        await loadGroupsForDialog();

        // 2. 重新從資料庫查詢該使用者的最新資料
        const response = await apiClient.get(`/controller/usercrud/${editUser.id}`);
        const freshUserData = response.data;

        // 3. 使用最新的使用者資料
        userVO.value = { ...freshUserData };
        console.log('editUser - 從資料庫重新查詢的使用者資料:', freshUserData);

        // 4. 預設帳號狀態
        if (freshUserData.disabled !== undefined && freshUserData.disabled !== null) {
            userVO.value.disabled = String(freshUserData.disabled); // 確保轉為字串以配合 RadioButton 的值
        } else {
            userVO.value.disabled = 'false'; // 預設為啟用
        }

        // 5. 預設群組權限
        if (freshUserData.tcUsergroupCollection && Array.isArray(freshUserData.tcUsergroupCollection)) {
            userVO.value.tcUsergroupCollection = freshUserData.tcUsergroupCollection
                .map((usergroup) => {
                    // 檢查 usergroup 是否有 groupId 物件
                    if (usergroup.groupId && usergroup.groupId.id) {
                        return usergroup.groupId.id;
                    }
                    // 如果沒有 groupId 物件，可能直接是 id
                    return usergroup.id || usergroup;
                })
                .filter((id) => id !== null && id !== undefined);

            console.log('提取的群組 ID 陣列:', userVO.value.tcUsergroupCollection);
        } else {
            userVO.value.tcUsergroupCollection = [];
        }

        productDialog.value = true;
    } catch (error) {
        console.error('重新查詢使用者資料失敗:', error);
        toast.add({
            severity: 'error',
            summary: '查詢失敗',
            detail: '無法載入使用者資料，請重試',
            life: 3000
        });
    }
};

const confirmDeleteUser = async (editUser) => {
    Object.assign(user, editUser);
    deleteUserDialog.value = true;
};

const deleteUser = async () => {
    await apiClient.delete('/controller/usercrud/' + user.id);
    deleteUserDialog.value = false;
    Object.assign(user, {
        loginAccount: '',
        empId: '',
        cname: '',
        email: '',
        disabled: '',
        tcUsergroupCollection: []
    });
    toast.add({ severity: 'success', summary: 'Successful', detail: '使用者資料已刪除', life: 3000 });
    await fetchUsers();
};

const fetchTcGroups = async () => {
    try {
        const response = await apiClient.get('/controller/usercrud/getGroup');

        // 查詢條件需要「---全部---」選項
        const groupsWithDefault = [{ id: null, displayIdentifier: '---全部---' }, ...response.data];

        tcGroup.value = groupsWithDefault;
    } catch (error) {
        console.error('獲取群組資料失敗:', error);
    }
};

const initFilters = () => {
    filters.value = {
        global: { value: null, matchMode: FilterMatchMode.CONTAINS }
    };
};

const fetchUsers = async () => {
    const params = {};

    // 使用獨立的查詢條件物件
    if (searchConditions.loginAccount) params.loginAccount = searchConditions.loginAccount;
    if (searchConditions.empId) params.empId = searchConditions.empId;
    if (searchConditions.cname) params.cname = searchConditions.cname;
    if (searchConditions.email) params.email = searchConditions.email;
    if (searchConditions.selectedGroup && searchConditions.selectedGroup.id !== null) {
        params.groupId = searchConditions.selectedGroup.id;
    }
    if (searchConditions.disabled) params.disabled = searchConditions.disabled;
    console.log('params:', params);
    // 使用查詢參數發送請求
    const response = await apiClient.get('/controller/usercrud', { params });
    console.log('Query params:', params);
    users.value = response.data;
    console.log('response.data:', response.data);
    toast.add({ severity: 'success', summary: 'Successful', detail: '資料查詢完成', life: 3000 });
};

// 查詢函數：由查詢按鈕觸發
const searchUsers = async () => {
    console.log('開始查詢使用者資料...');
    console.log('查詢條件:', searchConditions);
    await fetchUsers();
};

const searchUserByConditions = async () => {
    const response = await apiClient.get('/controller/usercrud');
    users.value = response.data;
};

const fetchGroups = async () => {
    // 空函數保留
};

const onCheckboxChange = (event, item) => {
    console.log('Checkbox changed:', item.code, event);
    tcGroup.value.filter((item) => tcUsergroupSelected.value.includes(item.id));
};

// 計算屬性
const getDisabled = computed(() => {
    return (inventoryStatus) => {
        switch (inventoryStatus) {
            case false:
                return '啟用';
            case true:
                return '停用';
            default:
                return inventoryStatus;
        }
    };
});

const getDisabledSeverity = computed(() => {
    return (inventoryStatus) => {
        switch (inventoryStatus) {
            case false:
                return 'success'; // 啟用顯示成功綠色
            case true:
                return 'danger'; // 停用顯示危險紅色
            default:
                return 'secondary'; // 預設顏色
        }
    };
});

// 生命週期鉤子
onBeforeMount(() => {
    initFilters();
});

onMounted(async () => {
    console.log('載入群組資料...');
    await fetchTcGroups();
});
</script>

<template>
    <CommonLayout :title="'使用者管理'">
        <template #control-panel>
            <Card class="mb-4">
                <template #content>
                    <!-- 查詢條件區域 -->
                    <div class="text-lg font-bold mb-4">查詢條件</div>
                    <Fluid class="flex items-center flex-wrap gap-4">
                        <div class="flex items-center w-full md:w-1/4">
                            <label for="loginAccount" class="w-32 text-right pr-2">登入帳號:</label>
                            <InputText id="loginAccount" v-model="searchConditions.loginAccount" type="text" class="w-20" />
                        </div>
                        <div class="flex items-center item-center w-full md:w-1/4">
                            <label for="empId" class="w-32 text-right pr-2">員工編號:</label>
                            <InputText id="empId" v-model="searchConditions.empId" type="text" class="w-20" />
                        </div>
                        <div class="flex items-center item-center w-full md:w-1/4">
                            <label for="cname" class="w-32 text-right pr-2">員工姓名:</label>
                            <InputText id="cname" v-model="searchConditions.cname" type="text" class="w-20" />
                        </div>
                        <div class="flex items-center item-center w-full md:w-1/4">
                            <label for="tcUserGroupCollection" class="w-32 text-right pr-2">群組:</label>
                            <Dropdown id="tcUserGroupCollection" v-model="searchConditions.selectedGroup" :options="tcGroup" optionLabel="displayIdentifier" class="w-20" placeholder="請選擇"></Dropdown>
                        </div>
                        <div class="flex items-center item-center w-full md:w-1/4">
                            <label for="email" class="w-32 text-right pr-2">電子信箱:</label>
                            <InputText id="email" v-model="searchConditions.email" type="text" class="w-20" />
                        </div>
                        <div class="flex items-center item-center w-full md:w-1/4">
                            <label for="disabled" class="w-32 text-right pr-2">帳號停用:</label>
                            <RadioButton id="option1" name="option" value="false" v-model="searchConditions.disabled" />
                            <label for="option1" class="leading-none ml-2">啓用</label>
                            <RadioButton id="option2" name="option" value="true" v-model="searchConditions.disabled" />
                            <label for="option2" class="leading-none ml-2">停用</label>
                        </div>
                        <div class="flex items-center flex-wrap gap-2">
                            <Button type="button" label="查詢" :loading="loading[0]" @click="searchUsers" />
                        </div>
                    </Fluid>

                    <div class="mb-3 mt-4">
                        <Button type="button" label="新增使用者" icon="pi pi-plus" severity="success" @click="openNew" style="width: auto" />
                    </div>
                </template>
            </Card>
        </template>
        <Fluid class="p-4">
            <!-- 操作按鈕區域 -->
            <!-- 主要內容區域 -->
            <DataTable
                ref="dt"
                :value="users"
                v-model:selection="selectedUsers"
                :paginator="true"
                :rows="10"
                :filters="filters"
                paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
                :rowsPerPageOptions="[5, 10, 25]"
                currentPageReportTemplate="顯示第 {first} 至 {last} 筆，總共 {totalRecords} 筆"
            >
                <template #header>
                    <div class="flex items-center flex-column md:flex-row md:justify-content-between md:align-items-center">
                        <h5 class="m-0">查詢結果</h5>
                    </div>
                </template>

                <Column field="id" header="ID" :sortable="true" headerStyle="width:3%; min-width:2rem;">
                    <template #body="slotProps">
                        {{ slotProps.data.id }}
                    </template>
                </Column>
                <Column field="loginAccount" header="登入帳號" :sortable="true" headerStyle="width:10%; min-width:2rem;">
                    <template #body="slotProps">
                        {{ slotProps.data.loginAccount }}
                    </template>
                </Column>
                <Column field="empId" header="員工編號" :sortable="true" headerStyle="width:10%; min-width:2rem;">
                    <template #body="slotProps">
                        {{ slotProps.data.empId }}
                    </template>
                </Column>
                <Column field="cname" header="員工姓名" :sortable="true" headerStyle="width:10%; min-width:2rem;">
                    <template #body="slotProps">
                        {{ slotProps.data.cname }}
                    </template>
                </Column>
                <Column field="email" header="電子信箱" :sortable="true" headerStyle="width:14%; min-width:2rem;">
                    <template #body="slotProps">
                        {{ slotProps.data.email }}
                    </template>
                </Column>
                <Column field="creator" header="建立者" :sortable="true" headerStyle="width:9%; min-width:2rem;">
                    <template #body="slotProps">
                        {{ slotProps.data.creator }}
                    </template>
                </Column>
                <Column field="disabled" header="帳號狀態" headerStyle="width:8%; min-width:2rem;">
                    <template #body="slotProps">
                        <Tag :severity="getDisabledSeverity(slotProps.data.disabled)">{{ getDisabled(slotProps.data.disabled) }}</Tag>
                    </template>
                </Column>
                <Column field="createtimestamp" header="建立時間" :sortable="true" headerStyle="width:16%; min-width:2rem;">
                    <template #body="slotProps">
                        {{ formatDate(slotProps.data.createtimestamp) }}
                    </template>
                </Column>
                <Column header="動作" :sortable="true" headerStyle="width:15%; min-width:2rem;">
                    <template #body="slotProps">
                        <div class="flex items-center flex-column gap-2">
                            <div class="flex items-center gap-2">
                                <Button icon="pi pi-pencil" severity="success" rounded @click="editUser(slotProps.data)" />
                                <Button icon="pi pi-trash" severity="danger" rounded @click="confirmDeleteUser(slotProps.data)" />
                            </div>
                        </div>
                    </template>
                </Column>
            </DataTable>
        </Fluid>
    </CommonLayout>
</template>
