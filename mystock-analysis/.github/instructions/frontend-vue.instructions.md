---
applyTo: "prototype-ecardsystem/src/**/*.{vue,js}"
---

# 前端 Vue 3 + PrimeVue 4 開發規範（自動注入）

本指引在編輯前端 `.vue` 或 `.js` 檔案時自動生效。

## 架構分層（嚴格遵守）

```
View (.vue) → Composable (useXxxApi.js) → Service (xxxService.js) → fetch/axios
```

| 層 | 職責 | 禁止 |
|----|------|------|
| **View** | 純 UI：template + 事件觸發 | 不直接呼叫 fetch/axios |
| **Composable** | 狀態管理 + API 編排 + 錯誤處理（選用） | 不操作 DOM |
| **Service** | HTTP 請求封裝 + 資料轉換 | 不管理 UI 狀態 |

## Vue 元件規範

- **一律使用 Composition API**（`<script setup>`），禁止 Options API
- 模板內禁止複雜邏輯（超過 2 個運算子請提取為 computed）
- Props 必須定義 type 與 default
- Emit 必須使用 `defineEmits` 宣告

```vue
<script setup>
import { ref, computed } from 'vue';

const props = defineProps({
  title: { type: String, required: true },
  items: { type: Array, default: () => [] }
});

const emit = defineEmits(['update', 'delete']);
</script>
```

## PrimeVue 4 元件使用

- 元件透過 `unplugin-vue-components` + `PrimeVueResolver` 自動引入，**不需手動 import**
- 全域已註冊：`Button`、`Card`、`Tag`、`DataTable`、`Column`、`Tabs`、`TabList`、`Tab`、`TabPanel`、`TabPanels`
- Dialog 使用 `DynamicDialog` 或 `MaximizableDialog`
- Toast 使用 `useToast()` composable
- Confirm 使用 `useConfirm()` composable

## 樣式規範

- 優先使用 TailwindCSS utility class
- 客製樣式寫在 `<style scoped>` 內
- 全域共用樣式放 `src/assets/project-style.css`
- 主題色使用 PrimeVue CSS 變數（`var(--p-primary-color)`）

## 命名慣例

| 類型 | 規則 | 範例 |
|------|------|------|
| 元件檔案 | PascalCase.vue | `ManualCardForm.vue` |
| Composable | camelCase（use 前綴） | `useManualCardApi.js` |
| Service | PascalCase + Service | `ManualCardService.js` |
| 路由 name | kebab-case | `manual-card` |
| 路由 path | kebab-case | `/manual-card` |
| CSS class | kebab-case | `card-header` |

## Service 層範本

```javascript
// src/service/XxxService.js
const API_BASE = '/api/v1';

export const XxxService = {
    async getAll(params) {
        const query = new URLSearchParams(params).toString();
        const res = await fetch(`${API_BASE}/xxx?${query}`);
        return res.json();
    },
    async getById(id) {
        const res = await fetch(`${API_BASE}/xxx/${id}`);
        return res.json();
    },
    async create(data) {
        const res = await fetch(`${API_BASE}/xxx`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    }
};
```

## 路由與菜單

- 路由定義在 `src/router/index.js`
- 菜單定義在 `src/layout/AppMenu.vue` 的 `model` 陣列
- 新頁面必須同時更新路由和菜單
- 路由元件使用 lazy-load：`() => import('@/views/XxxPage.vue')`
