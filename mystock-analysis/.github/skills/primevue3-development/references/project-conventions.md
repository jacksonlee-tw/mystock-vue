# 專案客製化慣例範本

> 使用此範本為你的專案建立 `project-conventions.md`，
> 填入專案特定的路由表、Store、環境變數、認證流程等資訊。
> Skill 在產生程式碼時會優先讀取此檔，確保符合你的專案慣例。

---

## 1. 專案資訊

| 項目 | 值 |
|------|-----|
| 專案名稱 | <!-- 例如：達航船員考評系統 --> |
| 前端目錄 | <!-- 例如：frontend/ --> |
| 後端技術 | <!-- 例如：SpringBoot 3 + MySQL --> |
| API 前綴 | <!-- 例如：/api/v1/ --> |
| 回應格式 | <!-- 例如：{ success: boolean, data: T, message: string } --> |

---

## 2. 路由表

列出所有已定義的路由：

```javascript
// router/index.js
const routes = [
  // { path: '/login', name: 'login', component: Login, meta: { requiresAuth: false } },
  // { path: '/', component: AppLayout, children: [
  //   { path: '/', name: 'home', component: HomePage },
  //   { path: '/users', name: 'users', component: UserList },
  //   ...
  // ]}
]
```

---

## 3. 選單結構

```javascript
// layout/AppMenu.vue model 陣列
const menuItems = [
  // { label: 'A.使用者管理', icon: 'pi pi-fw pi-users', to: '/users' },
  // { label: 'B.訂單管理', icon: 'pi pi-fw pi-shopping-cart', to: '/orders' },
]
```

---

## 4. 認證流程

<!-- 描述你的專案如何管理認證：JWT / CAS / OAuth2 / Session 等 -->

```
認證方式：<!-- 例如：JWT + CAS SSO -->
登入端點：<!-- 例如：/api/v1/auth/login -->
Token 儲存：<!-- 例如：localStorage -->
Auth bypass：<!-- 例如：VITE_BYPASS_AUTH=true 開發模式跳過 -->
```

---

## 5. Pinia Store 清單

列出已有的 Store 定義：

| Store | 用途 | 關鍵 state / actions |
|-------|------|---------------------|
| <!-- auth --> | <!-- 認證狀態 --> | <!-- token, userInfo, login(), logout() --> |

---

## 6. 環境變數

列出專案使用的所有 VITE_ 環境變數：

| 變數 | 用途 | 預設值 |
|------|------|--------|
| <!-- VITE_API_BASE_URL --> | <!-- API 位址 --> | <!-- http://localhost:8088 --> |

---

## 7. 已有功能模組

每個模組的 Endpoint → Service → Composable → View 對應：

| 模組 | Endpoint | Service | Composable | View |
|------|----------|---------|------------|------|
| <!-- 使用者 --> | <!-- userEndpoints.js --> | <!-- userService.js --> | <!-- useUserApi.js --> | <!-- userList.vue --> |

---

## 8. 共用元件

專案自訂的可復用元件：

| 元件 | 用途 | Props |
|------|------|-------|
| <!-- MaximizableDialog --> | <!-- 可全螢幕Dialog --> | <!-- visible, header, modal, dialogStyle --> |

---

## 9. 程式碼風格

```
Prettier: <!-- printWidth: 100, semi: false, singleQuote: true -->
ESLint: <!-- Vue 3 essential, 允許單字元件名稱 -->
UI 文字語言: <!-- 中文 -->
註解語言: <!-- 中英文皆可 -->
```

---

## 10. 特殊慣例

<!-- 記錄任何專案獨有的慣例或限制 -->
<!-- 例如：
- CommonLayout 使用 4 個 slot: #header, #control-panel, #main-content, #action-buttons
- 所有 API composable 回傳 readonly state
- 使用 useDebounce 包裝所有即時更新操作
-->
