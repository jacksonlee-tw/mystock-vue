---
name: primevue3-development
description: >-
  Vue 3 + PrimeVue 4 + TailwindCSS 前端開發技能。涵蓋元件架構、composable 撰寫、
  service 層串接、路由設定、版面系統等完整開發流程，適用於任何採用此技術棧的專案。
  當使用者提到以下任何一項時，務必使用此 Skill：
  Vue 元件開發、前端頁面新增、composable 撰寫、API service 串接、PrimeVue 元件使用、
  DataTable 設定、表單開發、模態對話框、前端路由設定、Pinia 狀態管理、
  前端樣式調整 (Tailwind/SCSS/PrimeVue 主題)、前端測試 (Vitest/Playwright)、
  axios 設定、環境變數配置、Vite 設定，
  或任何 frontend/ 或 src/ 目錄下的 .vue/.js 程式修改。
  即使使用者只說「加一個頁面」、「修改前端」、「寫一個表單」，也應觸發此 Skill。
---

# Vue 3 + PrimeVue 4 前端開發指引

本 Skill 定義 Vue 3 + PrimeVue 4 + TailwindCSS 技術棧的架構模式與開發規範，以 **tcci-vue-template** 為基準。

**基礎技術棧：** Vue 3 / Vite 5 / PrimeVue 4（Aura theme）/ TailwindCSS 3 / Vue Router 4 / SCSS  
**可選擴充：** axios（HTTP 客戶端）/ Pinia（全域狀態管理）— 模板預設未包含，子系統依需求自行安裝。

> **專案客製化：** 若 `references/project-conventions.md` 存在，讀取該檔以獲取專案特定的路由表、
> 環境變數、Store 定義等資訊。本文件只定義通用架構模式。

---

## 1. 架構分層原則

本架構的核心理念是**關注分離**——UI、狀態、業務邏輯、API 呼叫各有歸屬，不互相越界：

```
View (.vue)                       ← 純 UI：template + 事件處理
  └→ Composable (useXxxApi.js)   ← 狀態管理 + 錯誤處理 + API 編排（選用）
       └→ Service (xxxService.js) ← 業務邏輯 + 資料轉換
            └→ fetch / axios      ← HTTP 請求（axios 為可選擴充）
                 └→ Endpoint 常數  ← URL 定義（與業務解耦）
```

> **模板預設：** 模板本身不包含 axios 或統一 HTTP 設定；`src/service/` 內為示範用靜態資料服務。  
> 子系統串接真實 API 時，建議加入 axios + axiosConfig + composables 分層架構。

這個分層讓每層可以獨立測試和替換，View 永遠不直接呼叫 fetch/axios。

---

## 2. 目錄結構

以下為模板的實際目錄結構，子系統可依需求擴充：

```
src/
├── App.vue                   # 根元件（僅含 <router-view />）
├── main.js                   # 應用入口（PrimeVue Aura + Router + Toast + Confirm）
├── assets/
│   ├── project-style.css     # TCCI 全域自訂樣式
│   ├── styles.scss           # 全域 SCSS 入口
│   ├── images/               # 靜態圖片（logo-white.svg 等）
│   └── layout/
│       ├── layout.scss       # 版面主 SCSS
│       └── variables/        # 主題 CSS 變數（_common、_dark、_light 等）
├── components/               # 可復用 UI 元件
│   ├── FloatingConfigurator.vue
│   ├── MaximizableDialog.vue
│   ├── dashboard/            # 儀表板小工具元件
│   └── landing/              # 首頁展示區塊元件
├── layout/                   # 版面骨架
│   ├── AppLayout.vue         # 主版面（Topbar + Sidebar + router-view）
│   ├── AppTopbar.vue         # 頂部列
│   ├── AppSidebar.vue        # 側邊欄
│   ├── AppMenu.vue           # 選單定義（model 陣列）
│   ├── AppMenuItem.vue       # 選單項目（遞迴渲染）
│   ├── AppFooter.vue         # 頁尾
│   ├── CommonLayout.vue      # 頁面模板（slot-based）
│   ├── AppConfigurator.vue   # 主題設定面板
│   └── composables/
│       └── layout.js         # useLayout()（版面狀態管理）
├── router/index.js           # 路由表
├── service/                  # 示範用資料服務（靜態/Mock，實際專案替換為真實 API）
│   ├── CustomerService.js
│   ├── ProductService.js
│   ├── NodeService.js
│   ├── PhotoService.js
│   └── CountryService.js
└── views/                    # 頁面元件（每路由一個 .vue）
    ├── Template.vue
    ├── HomeDashboard.vue
    ├── Dashboard.vue
    ├── CustomerManagement.vue
    ├── UserManagement.vue
    ├── Questionnaire*.vue
    ├── pages/
    │   ├── Crud.vue / UserCrud.vue / Empty.vue / Landing.vue / Documentation.vue
    │   └── auth/  Login.vue / Access.vue / Error.vue
    └── uikit/  ButtonDoc / InputDoc / TableDoc … (UI Showcase)
```

**子系統擴充目錄（視需求新增）：**
```
src/
├── composables/              # Composition API 函式 (useXxx.js)
├── config/                   # axiosConfig.js, environmentConfig.js（使用 axios 時）
├── stores/                   # Pinia 全域狀態（使用 Pinia 時）
└── utils/                    # 工具函式 (errorHandler, cacheManager 等)
```

---

## 3. 檔案命名規範

| 類型 | 命名規則 | 範例 |
|------|---------|------|
| View 頁面元件 | camelCase.vue | `userList.vue`, `orderDetail.vue` |
| 可復用元件 | PascalCase.vue | `MaximizableDialog.vue`, `StatusBadge.vue` |
| Composable | use + PascalCase.js | `useOrderApi.js`, `useLoadingState.js` |
| Service | camelCase + Service.js | `orderService.js`, `userService.js` |
| Endpoint 定義 | camelCase + Endpoints.js | `orderEndpoints.js` |
| Utility | camelCase.js | `apiErrorHandler.js`, `cacheManager.js` |
| Store | camelCase.js | `auth.js`, `cart.js` |
| 常數導出 | UPPER_CASE 變數名 | `STATUS_OPTIONS`, `ERROR_TYPES` |

---

## 4. Vue 元件標準結構

所有元件使用 `<script setup>` 語法，區塊順序：script → template → style。
import 區段建議依照以下順序，讓程式碼可預測、易讀：

```vue
<script setup>
// ① Vue 核心
import { ref, computed, onMounted, watch } from 'vue'

// ② Composable
import { useOrderApi } from '@/composables/useOrderApi'
import { useConfirmDialog } from '@/composables/useConfirmDialog'

// ③ Utils / Services (view 通常不直接用 service)
import { handleApiError } from '@/utils/apiErrorHandler'

// ④ PrimeVue 服務 (元件本身由 unplugin 自動匯入)
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'

// ⑤ Props & Emits
const props = defineProps({
  orderId: { type: String, required: true }
})
const emit = defineEmits(['saved', 'cancelled'])

// ⑥ 實例化服務
const toast = useToast()

// ⑦ Composable 解構
const { isLoading, data, loadData, saveData } = useOrderApi(props.orderId)

// ⑧ 本地響應狀態
const isEditing = ref(false)

// ⑨ Computed
const canSave = computed(() => !isLoading.value && isEditing.value)

// ⑩ Methods
const handleSave = async () => { /* ... */ }

// ⑪ Watchers
watch(() => props.orderId, async (val) => { await loadData() })

// ⑫ Lifecycle
onMounted(async () => { await loadData() })
</script>

<template>
  <!-- 建議使用 CommonLayout 或 AppLayout 包裝 -->
</template>

<style scoped>
/* Tailwind 優先；必要時才用 scoped CSS/SCSS */
</style>
```

---

## 5. View 頁面模式

### 5.1 CommonLayout Slot 模板

用 `CommonLayout` 統一頁面結構，透過 named slot 組織各區塊。
slot 名稱可依專案調整，常見四區塊：

```vue
<CommonLayout :title="'訂單管理'" :showStatus="true" :statusText="statusText">
  <template #control-panel>
    <!-- 篩選條件、操作按鈕 -->
    <Dropdown v-model="selectedStatus" :options="statusOptions" placeholder="篩選狀態" />
  </template>

  <template #main-content>
    <DataTable :value="orders" :loading="isLoading" />
  </template>

  <template #action-buttons>
    <Button label="儲存" @click="handleSave" :disabled="!canSave" />
  </template>
</CommonLayout>
```

### 5.2 資料載入

```javascript
// 循序載入 — 有依賴關係時
const loadDetail = async (id) => {
  try {
    setLoading(true, '載入中...')
    const master = await service.getById(id)
    data.value = master
    await loadRelatedItems(master.categoryId)
  } catch (err) {
    handleApiError(err, toast, '載入失敗')
  } finally {
    setLoading(false)
  }
}

// 平行載入 — 無依賴時用 Promise.all
const [orders, customers, config] = await Promise.all([
  loadOrders(), loadCustomers(), loadConfig()
])
```

### 5.3 編輯與變更追蹤

```javascript
const hasUnsavedChanges = ref(false)
const isReadOnly = computed(() => data.value?.status === 'APPROVED')
const markChanged = () => { hasUnsavedChanges.value = true }

// debounce 防止頻繁觸發 API
const debouncedSave = debounce(async (id, field, val) => {
  await service.patchField(id, field, val)
}, 500)
```

---

## 6. Composable 撰寫規範

### 6.1 API Composable

封裝 API 呼叫 + 狀態管理。View 透過 composable 操作資料，不直接碰 service：

```javascript
import { ref, readonly } from 'vue'
import * as orderService from '@/services/orderService'
import { handleApiError } from '@/utils/apiErrorHandler'

export const useOrderApi = (initialId) => {
  const isLoading = ref(false)
  const error = ref(null)
  const data = ref(null)

  const loadData = async () => {
    isLoading.value = true
    error.value = null
    try {
      const response = await orderService.getById(initialId)
      data.value = response.data
    } catch (err) {
      error.value = err
      handleApiError(err)
    } finally {
      isLoading.value = false
    }
  }

  const saveData = async (payload) => {
    isLoading.value = true
    try {
      await orderService.save(payload)
    } catch (err) {
      handleApiError(err)
      throw err  // 讓 view 決定後續 UI 行為
    } finally {
      isLoading.value = false
    }
  }

  return {
    isLoading: readonly(isLoading),  // readonly 防止外部意外修改
    error: readonly(error),
    data: readonly(data),
    loadData,
    saveData
  }
}
```

### 6.2 功能型 Composable

非 API 的通用邏輯封裝，常見模式：

| 模式 | 用途 | 典型回傳 |
|------|------|---------|
| `useConfirmDialog` | 確認對話框 | `confirmAction`, `confirmDanger` |
| `useDebounce` | 輸入防抖 | `debouncedFn`, `cancel`, `flush` |
| `useLoadingState` | 多階段載入 | `isLoading`, `setLoading`, `updateProgress` |
| `useStatusFeedback` | 操作回饋 | `setSuccess`, `setError`, `resetStatus` |
| `useFileUpload` | 檔案上傳 | `upload`, `progress`, `isUploading` |
| `useCache` | 資料快取 | `get`, `set`, `invalidate` |

---

## 7. Service 層

### 7.1 Endpoint 常數

每個功能模組一個 Endpoint 檔，路徑用函式處理動態參數：

```javascript
// services/api/modules/orderEndpoints.js
export const ORDER_ENDPOINTS = {
  LIST: '/api/v1/orders',
  BY_ID: (id) => `/api/v1/orders/${id}`,
  ITEMS: {
    LIST: (orderId) => `/api/v1/orders/${orderId}/items`,
    BY_ID: (orderId, itemId) => `/api/v1/orders/${orderId}/items/${itemId}`
  }
}
```

在 `services/api/endpoints.js` 統一匯出：
```javascript
export { ORDER_ENDPOINTS } from './modules/orderEndpoints'
export { USER_ENDPOINTS } from './modules/userEndpoints'
```

### 7.2 Service 函式

Service 負責 API 呼叫 + 資料轉換，不含 UI 狀態邏輯：

```javascript
import axiosConfig from '@/config/axiosConfig'
import { ORDER_ENDPOINTS } from './api/modules/orderEndpoints'

export const getById = async (id) => {
  try {
    return await axiosConfig.get(ORDER_ENDPOINTS.BY_ID(id))
  } catch (error) {
    console.error('[OrderService] getById error:', error)
    throw error
  }
}
```

---

## 8. HTTP 請求設定

> **模板預設不包含 axios。** 若子系統需串接後端 API，請先安裝：
> ```bash
> npm install axios
> ```

建立 `src/config/axiosConfig.js` 共用 axios 實例：

- **baseURL** 從 `environmentConfig.js` 動態取得（支援多環境）
- **Request 攔截器：** 自動附加認證 token (Bearer / Cookie)
- **Response 攔截器：** 解包後端標準回應格式 `{ success, data, message }`
- **401 處理：** 清除 token，導向登入頁
- **DEV 模式：** console 輸出請求/回應 log

---

## 9. 路由與選單

新增路由在 `router/index.js` 的根路由 children：

```javascript
{
  path: '/orders',
  name: 'orders',
  component: () => import('@/views/orderList.vue'),  // 懶載入
  meta: { requiresAuth: true }
}
```

新增選單項在 `layout/AppMenu.vue` 的 model 陣列：

```javascript
{ label: '訂單管理', icon: 'pi pi-fw pi-shopping-cart', to: '/orders' }
```

---

## 10. PrimeVue 元件模式

本模板使用 **PrimeVue 4**（`primevue ^4.3.1`）搭配 `@primeuix/themes` Aura preset（非 PrimeVue 3 的 lara/saga 主題）。  
PrimeVue 元件透過 `unplugin-vue-components` + `PrimeVueResolver` 自動匯入，
template 中直接使用即可，不需手動 import。部分常用元件（`Button`、`Card`、`DataTable` 等）
亦在 `main.js` 手動全域註冊，確保任何場合皆可使用。

詳細的 DataTable、Dialog、Form 等進階用法請參閱 `references/primevue-patterns.md`。

常用快速參考：

```javascript
// Toast 通知
const toast = useToast()
toast.add({ severity: 'success', summary: '完成', detail: '儲存成功', life: 3000 })

// 確認對話框
const confirm = useConfirm()
confirm.require({
  message: '確定刪除？',
  header: '確認',
  icon: 'pi pi-exclamation-triangle',
  acceptClass: 'p-button-danger',
  accept: () => { /* ... */ }
})
```

---

## 11. 樣式

1. **Tailwind CSS** — 主要佈局與間距 (flex, grid, p-4, mb-2)
2. **PrimeVue 4 主題** — `@primeuix/themes` Aura preset + `src/assets/layout/variables/_common.scss` CSS 變數客製化
3. **scoped SCSS** — 需覆寫 PrimeVue 或特殊視覺時才用
4. **暗色模式** — selector 策略（`<html class="app-dark">`），透過 `useLayout().toggleDarkMode()` 切換，使用 View Transition API
5. **TailwindCSS Screens：** `sm:576px / md:768px / lg:992px / xl:1200px / 2xl:1920px`（不同於 Tailwind 預設，定義於 `tailwind.config.js`）

---

## 12. Pinia Store（可選擴充）

> **模板預設不包含 Pinia。** 若子系統需要全域狀態管理，請先安裝：
> ```bash
> npm install pinia
> ```
> 並在 `src/main.js` 中 `app.use(createPinia())` 加在 `app.use(router)` 之前。

使用 Composition API 風格（`setup store`）定義：

```javascript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token'))
  const userInfo = ref(null)

  const isAuthenticated = computed(() => !!token.value)

  const setToken = (t) => { token.value = t; localStorage.setItem('token', t) }
  const logout = () => { token.value = null; localStorage.removeItem('token') }

  return { token, userInfo, isAuthenticated, setToken, logout }
})
```

---

## 13. 環境變數

Vite 專案的前端環境變數以 `VITE_` 前綴，透過 `import.meta.env.VITE_XXX` 讀取。
常見變數：

| 變數 | 用途 |
|------|------|
| `VITE_API_BASE_URL` | API 位址 |
| `VITE_API_TIMEOUT` | 請求逾時 (ms) |
| `VITE_ENV_TYPE` | 環境類型 |
| `VITE_DEBUG` | 除錯模式 |

建議封裝為 `config/environmentConfig.js` 提供型別安全的存取函式：
```javascript
export const getEnvVar = (key, defaultVal) => import.meta.env[key] ?? defaultVal
export const getBooleanEnvVar = (key, defaultVal) => import.meta.env[key] === 'true' ?? defaultVal
```

---

## 14. 錯誤處理

統一在 `utils/apiErrorHandler.js` 處理：

```javascript
import { handleApiError } from '@/utils/apiErrorHandler'

try {
  await apiCall()
} catch (err) {
  handleApiError(err, toast, '操作失敗')  // 自動分析狀態碼 + 顯示 Toast
}
```

錯誤類型建議分類：NETWORK、TIMEOUT、VALIDATION、AUTH、PERMISSION、NOT_FOUND、SERVER。

---

## 15. 測試

- **單元測試 (Vitest)：** `__tests__/` 或 `*.spec.js`，jsdom 環境
- **E2E 測試 (Playwright)：** `e2e/` 目錄

```javascript
import { describe, it, expect } from 'vitest'
import { useOrderApi } from '@/composables/useOrderApi'

describe('useOrderApi', () => {
  it('should initialize with loading false', () => {
    const { isLoading } = useOrderApi('test-id')
    expect(isLoading.value).toBe(false)
  })
})
```

---

## 16. 新增功能 Checklist

建立完整功能模組的標準步驟：

1. `views/featurePage.vue` — View 頁面（使用 `CommonLayout`）
2. `router/index.js` — 在根路由 `children` 新增路由（懶載入）
3. `layout/AppMenu.vue` — 在 `model` 陣列新增選單項
4. `service/featureService.js` — Service 函式（視需要，串接真實 API 時）
5. `composables/useFeatureApi.js` — API Composable（引入狀態管理與錯誤處理）
6. `components/modals/FeatureModal.vue` — 對話框（視需要）
7. `__tests__/useFeatureApi.spec.js` — 測試（視需要）

**最簡單的新增頁面三步驟：**
1. 建立 `src/views/MyPage.vue`（使用 `<CommonLayout>`）
2. `router/index.js` 加入 `{ path: '/my-page', component: () => import('@/views/MyPage.vue') }`
3. `AppMenu.vue` model 加入 `{ label: '功能名', icon: 'pi pi-fw pi-icon', to: '/my-page' }`

---

## 17. 參考資料

以下檔案提供更詳細的指引，在需要時讀取：

| 檔案 | 何時讀取 |
|------|---------|
| `references/primevue-patterns.md` | 開發 DataTable、Dialog、Form、Tab 等 PrimeVue 元件時 |
| `references/project-conventions.md` | 需要了解專案特有慣例（路由表、Store、環境變數、認證流程）時 |
