# PrimeVue 元件進階用法

本文件提供 PrimeVue 4.x 在 Vue 3 Composition API 下的進階使用模式。
所有元件透過 `unplugin-vue-components` + `PrimeVueResolver` 自動匯入，template 直接使用即可。

---

## 目錄

1. [DataTable 資料表格](#1-datatable)
2. [Dialog 對話框](#2-dialog)
3. [Form 表單元件](#3-form)
4. [Tab 分頁](#4-tab)
5. [Toast & Confirm](#5-toast--confirm)
6. [FileUpload 檔案上傳](#6-fileupload)
7. [常見組合模式](#7-常見組合模式)

---

## 1. DataTable

### 1.1 基本：捲動 + 凍結欄位

水平垂直捲動搭配左側凍結欄位，適用於多欄位資料表：

```vue
<DataTable
  :value="data"
  scrollable
  scrollHeight="70vh"
  scrollDirection="both"
  :loading="isLoading"
  responsiveLayout="scroll"
>
  <!-- 凍結欄位 (固定在左側) -->
  <Column field="name" header="姓名" :frozen="true"
    :headerStyle="{ width: '100px', minWidth: '100px' }"
    :bodyStyle="{ width: '100px', minWidth: '100px' }" />

  <Column field="department" header="部門"
    :headerStyle="{ width: '120px' }" />

  <!-- 動態欄位 -->
  <Column v-for="col in dynamicColumns" :key="col.field" :field="col.field" :header="col.header">
    <template #body="{ data }">
      {{ data[col.field] }}
    </template>
  </Column>
</DataTable>
```

### 1.2 多層表頭 (ColumnGroup)

```vue
<DataTable :value="data" scrollable scrollDirection="both">
  <ColumnGroup type="header">
    <Row>
      <Column header="基本資料" :colspan="2" />
      <Column header="考核分數" :colspan="3" />
    </Row>
    <Row>
      <Column header="姓名" />
      <Column header="職稱" />
      <Column header="技術" />
      <Column header="態度" />
      <Column header="績效" />
    </Row>
  </ColumnGroup>

  <Column field="name" />
  <Column field="title" />
  <Column field="techScore" />
  <Column field="attitudeScore" />
  <Column field="performanceScore" />
</DataTable>
```

### 1.3 行內編輯

```vue
<DataTable :value="items" editMode="cell" @cell-edit-complete="onCellEditComplete">
  <Column field="name" header="名稱">
    <template #editor="{ data, field }">
      <InputText v-model="data[field]" autofocus />
    </template>
  </Column>

  <Column field="quantity" header="數量">
    <template #editor="{ data, field }">
      <InputNumber v-model="data[field]" :min="0" />
    </template>
  </Column>

  <Column field="category" header="類別">
    <template #editor="{ data, field }">
      <Dropdown v-model="data[field]" :options="categoryOptions"
        optionLabel="label" optionValue="value" />
    </template>
  </Column>
</DataTable>
```

```javascript
const onCellEditComplete = (event) => {
  const { data, newValue, field } = event
  if (newValue !== undefined && newValue !== null) {
    data[field] = newValue
    markChanged(data.id)
  } else {
    event.preventDefault()  // 取消無效編輯
  }
}
```

### 1.4 多選 + 操作

```vue
<DataTable
  :value="items"
  v-model:selection="selectedItems"
  dataKey="id"
>
  <Column selectionMode="multiple" style="width: 3rem" />
  <Column field="name" header="名稱" />
  <Column header="操作">
    <template #body="{ data }">
      <Button icon="pi pi-pencil" severity="info" text rounded
        @click="openEditDialog(data)" />
      <Button icon="pi pi-trash" severity="danger" text rounded
        @click="confirmDelete(data)" />
    </template>
  </Column>
</DataTable>

<!-- 批次操作 -->
<Button :label="`刪除 (${selectedItems.length})`"
  :disabled="!selectedItems.length"
  @click="batchDelete(selectedItems)" />
```

### 1.5 分頁

```vue
<DataTable
  :value="items"
  :paginator="true"
  :rows="10"
  :rowsPerPageOptions="[10, 25, 50]"
  paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown"
/>
```

---

## 2. Dialog

### 2.1 基本 Dialog

```vue
<Dialog
  v-model:visible="dialogVisible"
  :header="dialogTitle"
  modal
  :style="{ width: '50vw' }"
  :breakpoints="{ '960px': '75vw', '640px': '90vw' }"
  @hide="onDialogClose"
>
  <div class="p-fluid">
    <!-- 表單內容 -->
  </div>

  <template #footer>
    <Button label="取消" severity="secondary" @click="dialogVisible = false" />
    <Button label="確定" @click="handleSubmit" :loading="isSaving" />
  </template>
</Dialog>
```

### 2.2 可最大化 Dialog

若專案有 `MaximizableDialog` 元件：

```vue
<MaximizableDialog
  v-model:visible="dialogVisible"
  :header="title"
  modal
  :dialogStyle="{ width: '80vw' }"
  @hide="handleClose"
>
  <!-- 資訊區 -->
  <div class="grid">
    <div class="col-12 md:col-6 lg:col-4">
      <span class="font-semibold">名稱：</span>
      <span>{{ record.name }}</span>
    </div>
  </div>

  <!-- 資料表 or 表單 -->
  <DataTable :value="detailItems" />

  <template #footer>
    <Button label="取消" severity="secondary" @click="handleCancel" />
    <Button label="儲存" severity="primary" @click="handleSave" />
  </template>
</MaximizableDialog>
```

### 2.3 Modal 開關模式

```javascript
const dialogVisible = ref(false)
const currentRecord = ref(null)

const openDialog = (record) => {
  currentRecord.value = { ...record }  // 深複製防止直接修改
  dialogVisible.value = true
}

const handleClose = () => {
  dialogVisible.value = false
  currentRecord.value = null
}

const handleSave = async () => {
  try {
    await saveRecord(currentRecord.value)
    toast.add({ severity: 'success', summary: '成功', detail: '儲存完成', life: 3000 })
    handleClose()
    emit('saved')
  } catch (err) {
    handleApiError(err, toast, '儲存失敗')
  }
}
```

---

## 3. Form

### 3.1 基本表單

```vue
<div class="p-fluid grid">
  <div class="field col-12 md:col-6">
    <label for="name">名稱 *</label>
    <InputText id="name" v-model="form.name" :class="{ 'p-invalid': errors.name }" />
    <small v-if="errors.name" class="p-error">{{ errors.name }}</small>
  </div>

  <div class="field col-12 md:col-6">
    <label for="category">類別</label>
    <Dropdown id="category" v-model="form.category"
      :options="categoryOptions" optionLabel="label" optionValue="value"
      placeholder="請選擇" />
  </div>

  <div class="field col-12 md:col-6">
    <label for="amount">金額</label>
    <InputNumber id="amount" v-model="form.amount"
      mode="currency" currency="TWD" locale="zh-TW" />
  </div>

  <div class="field col-12">
    <label for="description">描述</label>
    <Textarea id="description" v-model="form.description"
      :autoResize="true" rows="3" />
  </div>

  <div class="field col-12">
    <label>啟用</label>
    <InputSwitch v-model="form.isActive" />
  </div>
</div>
```

### 3.2 表單驗證

```javascript
const form = ref({ name: '', category: null, amount: 0 })
const errors = ref({})

const validate = () => {
  errors.value = {}
  if (!form.value.name?.trim()) errors.value.name = '名稱為必填'
  if (!form.value.category) errors.value.category = '請選擇類別'
  return Object.keys(errors.value).length === 0
}

const handleSubmit = async () => {
  if (!validate()) return
  await saveData(form.value)
}
```

---

## 4. Tab

### 4.1 靜態 Tab

```vue
<Tabs v-model:value="activeTab">
  <TabList>
    <Tab value="0">基本資料</Tab>
    <Tab value="1">詳細設定</Tab>
    <Tab value="2">歷史紀錄</Tab>
  </TabList>
  <TabPanels>
    <TabPanel value="0">
      <!-- 基本資料 -->
    </TabPanel>
    <TabPanel value="1">
      <!-- 詳細設定 -->
    </TabPanel>
    <TabPanel value="2">
      <!-- 歷史紀錄 -->
    </TabPanel>
  </TabPanels>
</Tabs>
```

### 4.2 動態 Tab

```vue
<Tabs v-model:value="activeTab" @tab-change="handleTabChange">
  <TabList>
    <Tab v-for="(item, idx) in categories" :key="item.id" :value="String(idx)">
      {{ item.name }}
      <Badge v-if="item.count" :value="item.count" severity="info" class="ml-2" />
    </Tab>
  </TabList>
  <TabPanels>
    <TabPanel v-for="(item, idx) in categories" :key="item.id" :value="String(idx)">
      <DataTable :value="item.records" />
    </TabPanel>
  </TabPanels>
</Tabs>
```

---

## 5. Toast & Confirm

### 5.1 Toast 通知

```javascript
import { useToast } from 'primevue/usetoast'
const toast = useToast()

// 成功
toast.add({ severity: 'success', summary: '完成', detail: '資料已儲存', life: 3000 })

// 錯誤
toast.add({ severity: 'error', summary: '錯誤', detail: error.message, life: 5000 })

// 警告
toast.add({ severity: 'warn', summary: '警告', detail: '資料未完整', life: 4000 })

// 資訊
toast.add({ severity: 'info', summary: '提示', detail: '請確認後送出', life: 3000 })
```

### 5.2 確認對話框

```javascript
import { useConfirm } from 'primevue/useconfirm'
const confirm = useConfirm()

// 一般確認
confirm.require({
  message: '確定要執行此操作嗎？',
  header: '確認',
  icon: 'pi pi-info-circle',
  accept: () => { performAction() }
})

// 危險確認 (紅色按鈕)
confirm.require({
  message: '此操作無法復原，確定要刪除嗎？',
  header: '刪除確認',
  icon: 'pi pi-exclamation-triangle',
  acceptClass: 'p-button-danger',
  accept: () => { deleteRecord() },
  reject: () => { /* 取消 */ }
})
```

---

## 6. FileUpload

### 6.1 基本上傳

```vue
<FileUpload
  mode="basic"
  :auto="true"
  accept=".xlsx,.xls"
  :maxFileSize="10000000"
  :customUpload="true"
  @uploader="handleUpload"
  chooseLabel="選擇檔案"
/>
```

```javascript
const handleUpload = async (event) => {
  const file = event.files[0]
  const formData = new FormData()
  formData.append('file', file)

  try {
    await service.uploadFile(formData)
    toast.add({ severity: 'success', summary: '上傳成功' })
  } catch (err) {
    handleApiError(err, toast, '上傳失敗')
  }
}
```

### 6.2 帶進度條上傳

```vue
<FileUpload mode="basic" :auto="true" :customUpload="true" @uploader="handleUpload" />
<ProgressBar v-if="isUploading" :value="uploadProgress" :showValue="true" />
```

---

## 7. 常見組合模式

### 7.1 篩選 + 表格 + 分頁

```vue
<template>
  <!-- 篩選列 -->
  <div class="flex gap-3 mb-4">
    <Dropdown v-model="filters.status" :options="statusOptions"
      placeholder="狀態" class="w-12rem" />
    <InputText v-model="filters.keyword" placeholder="搜尋..." class="w-16rem" />
    <Button icon="pi pi-search" @click="handleSearch" />
    <Button icon="pi pi-refresh" severity="secondary" @click="resetFilters" />
  </div>

  <!-- 表格 -->
  <DataTable :value="filteredData" :loading="isLoading"
    :paginator="true" :rows="pageSize" :totalRecords="totalCount"
    :lazy="true" @page="onPageChange"
  >
    <Column field="name" header="名稱" sortable />
    <Column field="status" header="狀態">
      <template #body="{ data }">
        <Tag :value="data.statusLabel" :severity="data.statusSeverity" />
      </template>
    </Column>
  </DataTable>
</template>
```

### 7.2 主從表 (Master-Detail)

```vue
<template>
  <div class="grid">
    <!-- Master 列表 -->
    <div class="col-4">
      <DataTable :value="masterList" selectionMode="single"
        v-model:selection="selectedMaster" @row-select="onMasterSelect">
        <Column field="name" header="名稱" />
      </DataTable>
    </div>

    <!-- Detail 詳細 -->
    <div class="col-8">
      <div v-if="selectedMaster">
        <h3>{{ selectedMaster.name }}</h3>
        <DataTable :value="detailItems" :loading="isLoadingDetail" />
      </div>
      <div v-else class="text-center text-color-secondary p-6">
        請選擇左側項目
      </div>
    </div>
  </div>
</template>
```

```javascript
const onMasterSelect = async (event) => {
  await loadDetailItems(event.data.id)
}
```

### 7.3 CRUD 頁面完整範例

```vue
<script setup>
import { ref, onMounted } from 'vue'
import { useItemApi } from '@/composables/useItemApi'
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import { useToast } from 'primevue/usetoast'

const toast = useToast()
const { confirmDanger } = useConfirmDialog()
const { isLoading, items, loadItems, createItem, updateItem, deleteItem } = useItemApi()

const dialogVisible = ref(false)
const isEditMode = ref(false)
const form = ref({})

const openCreate = () => {
  form.value = { name: '', status: 'ACTIVE' }
  isEditMode.value = false
  dialogVisible.value = true
}

const openEdit = (item) => {
  form.value = { ...item }
  isEditMode.value = true
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    if (isEditMode.value) {
      await updateItem(form.value)
    } else {
      await createItem(form.value)
    }
    toast.add({ severity: 'success', summary: '成功', life: 3000 })
    dialogVisible.value = false
    await loadItems()
  } catch (err) {
    toast.add({ severity: 'error', summary: '失敗', detail: err.message, life: 5000 })
  }
}

const handleDelete = (item) => {
  confirmDanger(`確定刪除「${item.name}」？`).then(async () => {
    await deleteItem(item.id)
    await loadItems()
  })
}

onMounted(() => loadItems())
</script>
```
