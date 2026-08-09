---
description: "前端開發代理-PrimeVue4 完成後，驗證 Vue Service API 呼叫路徑與 API 規格書一致性"
mode: "agent"
---

# 前端 API 合約檢查（Frontend API Contract Check）

**觸發時機**：@前端開發代理-PrimeVue4 產出 Vue 頁面 + Service 後執行

## 檢查流程

1. 讀取 API 規格書（`docs/02_Design/api/ecard-<module>-API規格書.md`）
2. 掃描前端 Service 檔案（`src/service/<Module>Service.js`）
3. 掃描 Vue 頁面中的 API 呼叫
4. 比對合約一致性

### 檢查項目

| # | 檢查項目 | 判定標準 | 嚴重度 |
|---|---------|---------|--------|
| 1 | **API 路徑匹配** | Service 中的 URL 與 API 規格書端點一致 | ❌ 必修 |
| 2 | **HTTP Method** | fetch/axios 使用的 Method 與規格書一致 | ❌ 必修 |
| 3 | **請求參數** | Service 傳送的欄位與規格書 Request Body 一致 | ⚠️ 警告 |
| 4 | **回應欄位** | Vue 頁面使用的 response 欄位在規格書中有定義 | ⚠️ 警告 |
| 5 | **Service 覆蓋** | API 規格書每個端點在 Service 中都有對應方法 | ❌ 必修 |
| 6 | **錯誤處理** | Service 或 Composable 處理了規格書定義的錯誤碼 | ⚠️ 警告 |
| 7 | **分層合規** | Vue 頁面不直接呼叫 fetch/axios（透過 Service） | ❌ 必修 |

### 掃描方式

```javascript
// 從 Service 檔案擷取 API 呼叫
// 搜尋模式：fetch(`...`)、axios.get('...')、axios.post('...') 等
```

### 輸出格式

```markdown
## 前端 API 合約檢查報告 — <Module>

### Service 方法對照表

| API 規格書端點 | Service 方法 | URL | 狀態 |
|--------------|-------------|-----|------|
| GET /api/v1/cards | getAll() | /api/v1/cards | ✅ |
| POST /api/v1/cards | create() | /api/v1/card | ❌ 路徑不一致 |

### Vue 頁面 API 使用

| 頁面 | 使用的 Service 方法 | 直接呼叫 fetch? |
|------|-------------------|----------------|
| ManualCardForm.vue | getAll, create | ❌ 無（合規） |

### 建議修正
- [ ] ...
```
