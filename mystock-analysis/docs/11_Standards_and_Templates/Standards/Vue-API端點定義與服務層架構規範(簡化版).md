# Vue API端點定義與服務層架構規範（AI Coding版）

> Vue.js前端API層的模組化架構標準，適用於AI輔助開發

**版本**: v2.0.0  
**適用**: Vue 3 + Axios + RESTful API

---

## 🎯 核心原則

1. **模組化組織** - 按業務領域拆分端點定義
2. **統一命名** - 端點用`UPPER_SNAKE_CASE`，方法用`camelCase`
3. **集中管理** - 所有API路徑集中在`api/`目錄
4. **分層架構** - 端點定義層與服務層分離
5. **禁止寫死路徑** - 服務層必須使用`ENDPOINTS`常數

---

## 📁 目錄結構（大型專案）

```
src/
├── services/
│   ├── api/
│   │   ├── config.js                      # API配置
│   │   ├── endpoints.js                   # 統一端點導出
│   │   └── modules/                       # 模組化端點定義
│   │       ├── annualKpiEndpoints.js
│   │       ├── kpiIndicatorEndpoints.js
│   │       └── requirementEndpoints.js
│   │
│   ├── annualKpiSettingService.js        # 服務層
│   └── ...
│
└── config/
    └── axiosConfig.js                    # Axios配置
```

---

## 📂 配置層

### 1. API配置（config.js）

```javascript
// src/services/api/config.js
export const API_CONFIG = {
  VERSION: '/api/v1',
  BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8088',
  TIMEOUT: 30000,
  PAGINATION: {
    DEFAULT_PAGE: 0,
    DEFAULT_SIZE: 20,
    MAX_SIZE: 100
  }
}

export const API_VERSION = API_CONFIG.VERSION
export default API_CONFIG
```

---

## 🔗 端點定義層

### 2. 端點定義範本

```javascript
// src/services/api/modules/[module]Endpoints.js

import { API_VERSION } from '../config'

const BASE_PATH = `${API_VERSION}/[module-path]`

export const [MODULE]_ENDPOINTS = {
  // 基本CRUD
  LIST: BASE_PATH,
  CREATE: BASE_PATH,
  BY_ID: (id) => `${BASE_PATH}/${id}`,
  UPDATE: (id) => `${BASE_PATH}/${id}`,
  DELETE: (id) => `${BASE_PATH}/${id}`,
  
  // 巢狀群組
  CATEGORY: {
    BY_YEAR: (year) => `${BASE_PATH}/${year}/categories`,
    BATCH_UPDATE: (year) => `${BASE_PATH}/${year}/categories`,
  }
}

export default [MODULE]_ENDPOINTS
```

### 3. 實際範例：年度KPI端點

```javascript
// src/services/api/modules/annualKpiEndpoints.js

import { API_VERSION } from '../config'

const BASE_PATH = `${API_VERSION}/annual-kpi-settings`

export const ANNUAL_KPI_ENDPOINTS = {
  LIST: BASE_PATH,
  CREATE: BASE_PATH,
  YEARS: `${BASE_PATH}/years`,
  BY_YEAR: (year) => `${BASE_PATH}/${year}`,
  BY_ID: (id) => `${BASE_PATH}/detail/${id}`,
  UPDATE: (id) => `${BASE_PATH}/${id}`,
  DELETE: (id) => `${BASE_PATH}/${id}`,
  
  CATEGORY: {
    BY_YEAR: (year) => `${BASE_PATH}/${year}/categories`,
    BATCH_UPDATE: (year) => `${BASE_PATH}/${year}/categories`,
  },
  
  VALIDATION: {
    VALIDATE: (year) => `${BASE_PATH}/${year}/validate`,
  },
  
  COPY: {
    FROM_TO: (from, to) => `${BASE_PATH}/copy/${from}/${to}`,
    STATUS: (taskId) => `${BASE_PATH}/copy/${taskId}`,
  },
  
  SAVE: {
    DRAFT: (year) => `${BASE_PATH}/${year}/draft`,
    SAVE: (year) => `${BASE_PATH}/${year}/save`,
  }
}

export default ANNUAL_KPI_ENDPOINTS
```

### 4. 統一端點導出

```javascript
// src/services/api/endpoints.js

import { ANNUAL_KPI_ENDPOINTS } from './modules/annualKpiEndpoints'
import { KPI_INDICATOR_ENDPOINTS } from './modules/kpiIndicatorEndpoints'
import { REQUIREMENT_ENDPOINTS } from './modules/requirementEndpoints'

export const ENDPOINTS = {
  ANNUAL_KPI: ANNUAL_KPI_ENDPOINTS,
  KPI_INDICATOR: KPI_INDICATOR_ENDPOINTS,
  REQUIREMENT: REQUIREMENT_ENDPOINTS,
}

export { ANNUAL_KPI_ENDPOINTS, KPI_INDICATOR_ENDPOINTS, REQUIREMENT_ENDPOINTS }
export default ENDPOINTS
```

---

## 🎯 服務層

### 5. 服務層範本

```javascript
// src/services/[module]Service.js

import axiosConfig from '@/config/axiosConfig'
import { ENDPOINTS } from './api/endpoints'

/**
 * 查詢列表
 */
export const getList = async (params = {}) => {
  try {
    if (!params.required) {
      throw new Error('必填參數缺失')
    }
    
    const response = await axiosConfig.get(ENDPOINTS.MODULE.LIST, { params })
    return response.data
  } catch (error) {
    console.error('❌ [模組] 查詢失敗:', error)
    throw error
  }
}

/**
 * 根據ID查詢
 */
export const getById = async (id) => {
  try {
    if (!id) {
      throw new Error('ID為必填項目')
    }
    
    const response = await axiosConfig.get(ENDPOINTS.MODULE.BY_ID(id))
    return response.data
  } catch (error) {
    console.error(`❌ [模組] 查詢(ID:${id})失敗:`, error)
    throw error
  }
}

/**
 * 新增
 */
export const create = async (data) => {
  try {
    _validateData(data)
    const response = await axiosConfig.post(ENDPOINTS.MODULE.CREATE, data)
    return response.data
  } catch (error) {
    console.error('❌ [模組] 新增失敗:', error)
    throw error
  }
}

// 私有方法
const _validateData = (data) => {
  const required = ['field1', 'field2']
  const missing = required.filter(f => !data[f])
  if (missing.length > 0) {
    throw new Error(`缺少必填欄位: ${missing.join(', ')}`)
  }
}

export default { getList, getById, create }
```

### 6. 實際範例：年度KPI服務層

```javascript
// src/services/annualKpiSettingService.js

import axiosConfig from '@/config/axiosConfig'
import { ENDPOINTS } from './api/endpoints'

export const getYears = async () => {
  try {
    const response = await axiosConfig.get(ENDPOINTS.ANNUAL_KPI.YEARS)
    return response.data
  } catch (error) {
    console.error('❌ [年度KPI] 查詢年度列表失敗:', error)
    throw error
  }
}

export const getAnnualKpiSettingsByYear = async (year) => {
  try {
    if (!year) throw new Error('年度參數為必填項目')
    const response = await axiosConfig.get(ENDPOINTS.ANNUAL_KPI.BY_YEAR(year))
    return response.data
  } catch (error) {
    console.error(`❌ [年度KPI] 查詢${year}年度失敗:`, error)
    throw error
  }
}

export const createAnnualKpiSetting = async (data) => {
  try {
    _validateAnnualKpiSettingData(data)
    const response = await axiosConfig.post(ENDPOINTS.ANNUAL_KPI.CREATE, data)
    return response.data
  } catch (error) {
    console.error('❌ [年度KPI] 新增失敗:', error)
    throw error
  }
}

export const updateCategoriesPercentage = async (year, categories) => {
  try {
    if (!year) throw new Error('年度參數為必填項目')
    if (!Array.isArray(categories)) throw new Error('類別資料格式錯誤')
    
    const total = categories.reduce((sum, cat) => sum + (cat.percentage || 0), 0)
    if (Math.abs(total - 100) > 0.01) {
      throw new Error(`類別佔比總和必須為100%，目前為${total}%`)
    }
    
    const response = await axiosConfig.put(
      ENDPOINTS.ANNUAL_KPI.CATEGORY.BATCH_UPDATE(year),
      { categories }
    )
    return response.data
  } catch (error) {
    console.error(`❌ [年度KPI] 更新類別佔比失敗:`, error)
    throw error
  }
}

export const copyFromYearToYear = async (from, to, forceOverwrite = false) => {
  try {
    if (!from || !to) throw new Error('來源年度和目標年度為必填')
    if (from === to) throw new Error('來源和目標年度不能相同')
    
    const response = await axiosConfig.post(
      ENDPOINTS.ANNUAL_KPI.COPY.FROM_TO(from, to),
      null,
      { params: { forceOverwrite } }
    )
    return response.data
  } catch (error) {
    console.error(`❌ [年度KPI] 複製失敗:`, error)
    throw error
  }
}

const _validateAnnualKpiSettingData = (data, isCreate = true) => {
  const required = isCreate 
    ? ['year', 'categoryCode', 'categoryName', 'percentage']
    : ['categoryName', 'percentage']
  
  const missing = required.filter(f => !data[f])
  if (missing.length > 0) {
    throw new Error(`缺少必填欄位: ${missing.join(', ')}`)
  }
  
  if (data.percentage && (data.percentage < 0 || data.percentage > 100)) {
    throw new Error('百分比必須在0-100之間')
  }
}

export default {
  getYears,
  getAnnualKpiSettingsByYear,
  createAnnualKpiSetting,
  updateCategoriesPercentage,
  copyFromYearToYear
}
```

---

## 📋 命名規範

### 端點命名（UPPER_SNAKE_CASE）

| 操作 | 端點名稱 | 範例 |
|------|---------|------|
| 列表 | `LIST` | `ENDPOINTS.CREW.LIST` |
| 單筆 | `BY_ID` | `ENDPOINTS.CREW.BY_ID(123)` |
| 條件 | `BY_*` | `ENDPOINTS.CREW.BY_YEAR(2024)` |
| 新增 | `CREATE` | `ENDPOINTS.CREW.CREATE` |
| 更新 | `UPDATE` | `ENDPOINTS.CREW.UPDATE(123)` |
| 刪除 | `DELETE` | `ENDPOINTS.CREW.DELETE(123)` |
| 批次 | `BATCH_*` | `ENDPOINTS.CREW.BATCH_UPDATE` |
| 驗證 | `VALIDATE` | `ENDPOINTS.FORM.VALIDATE` |
| 複製 | `COPY` | `ENDPOINTS.SETTING.COPY` |
| 狀態 | `STATUS` | `ENDPOINTS.TASK.STATUS(id)` |

### 服務方法命名（camelCase）

| 操作 | 方法格式 | 範例 |
|------|---------|------|
| 查詢列表 | `get[Resources]` | `getCrews()` |
| 查詢單筆 | `get[Resource]ById` | `getCrewById(id)` |
| 條件查詢 | `get[Resources]By[Condition]` | `getCrewsByYear(year)` |
| 新增 | `create[Resource]` | `createCrew(data)` |
| 更新 | `update[Resource]` | `updateCrew(id, data)` |
| 刪除 | `delete[Resource]` | `deleteCrew(id)` |
| 批次 | `batch[Action][Resources]` | `batchImportCrews(data)` |
| 驗證 | `validate[Subject]` | `validateCrewData(data)` |
| 檢查 | `check[Condition]` | `checkYearEditable(year)` |

---

## 🚫 反模式（禁止）

### ❌ 錯誤1：寫死API路徑

```javascript
// ❌ 錯誤
export const getYears = async () => {
  return await axiosConfig.get('/api/v1/annual-kpi-settings/years')
}

// ✅ 正確
export const getYears = async () => {
  return await axiosConfig.get(ENDPOINTS.ANNUAL_KPI.YEARS)
}
```

### ❌ 錯誤2：命名不一致

```javascript
// ❌ 錯誤
export const ENDPOINTS = {
  ANNUAL_KPI: {...},
  kpiIndicator: {...},  // 小寫駝峰
  score_eval: {...}     // 小寫蛇形
}

// ✅ 正確
export const ENDPOINTS = {
  ANNUAL_KPI: {...},
  KPI_INDICATOR: {...},
  SCORE_EVAL: {...}
}
```

### ❌ 錯誤3：缺少參數驗證

```javascript
// ❌ 錯誤
export const getByYear = async (year) => {
  return await axiosConfig.get(ENDPOINTS.ANNUAL_KPI.BY_YEAR(year))
}

// ✅ 正確
export const getByYear = async (year) => {
  if (!year) throw new Error('年度參數為必填項目')
  return await axiosConfig.get(ENDPOINTS.ANNUAL_KPI.BY_YEAR(year))
}
```

### ❌ 錯誤4：路徑重複定義

```javascript
// ❌ 錯誤
export const ENDPOINTS = {
  LIST: '/api/v1/annual-kpi-settings',
  YEARS: '/api/v1/annual-kpi-settings/years',
}

// ✅ 正確
const BASE_PATH = `${API_VERSION}/annual-kpi-settings`
export const ENDPOINTS = {
  LIST: BASE_PATH,
  YEARS: `${BASE_PATH}/years`,
}
```

---

## 📐 常用端點模式

### 模式1：RESTful CRUD

```javascript
export const RESOURCE_ENDPOINTS = {
  LIST: BASE_PATH,
  CREATE: BASE_PATH,
  BY_ID: (id) => `${BASE_PATH}/${id}`,
  UPDATE: (id) => `${BASE_PATH}/${id}`,
  DELETE: (id) => `${BASE_PATH}/${id}`,
}
```

### 模式2：階層式資源

```javascript
export const NESTED_ENDPOINTS = {
  PARENT: {
    LIST: `${API_VERSION}/parents`,
    BY_ID: (id) => `${API_VERSION}/parents/${id}`,
  },
  CHILD: {
    BY_PARENT: (parentId) => `${API_VERSION}/parents/${parentId}/children`,
    BY_ID: (id) => `${API_VERSION}/children/${id}`,
  }
}
```

### 模式3：批次操作

```javascript
export const BATCH_ENDPOINTS = {
  BATCH_CREATE: `${BASE_PATH}/batch`,
  BATCH_UPDATE: `${BASE_PATH}/batch`,
  BATCH_DELETE: `${BASE_PATH}/batch/delete`,
}
```

### 模式4：檔案操作

```javascript
export const FILE_ENDPOINTS = {
  UPLOAD: `${BASE_PATH}/upload`,
  DOWNLOAD: (id) => `${BASE_PATH}/${id}/download`,
  TEMPLATE: `${BASE_PATH}/template`,
}
```

---

## ✅ 開發檢查清單

### 端點定義檢查
- [ ] 使用`API_VERSION`常數
- [ ] 端點命名用`UPPER_SNAKE_CASE`
- [ ] 動態參數用箭頭函數
- [ ] 避免路徑字串重複

### 服務層檢查
- [ ] 使用`ENDPOINTS`常數
- [ ] 禁止寫死API路徑
- [ ] 實作參數驗證
- [ ] 實作錯誤處理
- [ ] 私有方法用`_`前綴

---

## 🔄 快速遷移步驟

1. **建立目錄**
```bash
mkdir -p src/services/api/modules
touch src/services/api/config.js
touch src/services/api/endpoints.js
```

2. **提取端點定義**
```javascript
// 從服務層提取路徑 → 建立端點檔案
'/api/v1/annual-kpi-settings/years' → ANNUAL_KPI_ENDPOINTS.YEARS
```

3. **更新服務層**
```javascript
// 替換路徑字串為端點常數
axiosConfig.get('/api/v1/...') → axiosConfig.get(ENDPOINTS.MODULE.ACTION)
```

---

## 📚 附錄：完整範本

### 配置檔案範本

```javascript
// src/services/api/config.js
export const API_CONFIG = {
  VERSION: '/api/v1',
  BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8088',
  TIMEOUT: 30000
}
export const API_VERSION = API_CONFIG.VERSION
export default API_CONFIG
```

### 端點定義範本

```javascript
// src/services/api/modules/moduleEndpoints.js
import { API_VERSION } from '../config'
const BASE_PATH = `${API_VERSION}/module-path`

export const MODULE_ENDPOINTS = {
  LIST: BASE_PATH,
  CREATE: BASE_PATH,
  BY_ID: (id) => `${BASE_PATH}/${id}`,
  UPDATE: (id) => `${BASE_PATH}/${id}`,
  DELETE: (id) => `${BASE_PATH}/${id}`,
}
export default MODULE_ENDPOINTS
```

### 服務層範本

```javascript
// src/services/moduleService.js
import axiosConfig from '@/config/axiosConfig'
import { ENDPOINTS } from './api/endpoints'

export const getList = async (params = {}) => {
  try {
    const response = await axiosConfig.get(ENDPOINTS.MODULE.LIST, { params })
    return response.data
  } catch (error) {
    console.error('❌ [模組] 操作失敗:', error)
    throw error
  }
}

export default { getList }
```

---

**檔名**: `Vue-API-Endpoints-Standard-AI.md`  
**版本**: v2.0.0 (簡化版)  
**用途**: AI Coding 規範參考