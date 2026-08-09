# 前後端API串接整合測試計畫

> **專案名稱**: 達航船員考評系統 (THMCPA)  
> **模組名稱**: 級別及職稱設定 (Title Setting Module)  
> **測試版本**: v1.0.0 (API整合版)  
> **測試日期**: 2025年9月21日  
> **測試範圍**: 前後端API串接整合驗證  

---

## 📋 測試概要

### 測試目標
驗證新整合的前端程式（setTitle_Integrated.vue）與後端API的完整串接功能，確保：
- ✅ API呼叫正確性和穩定性
- ✅ 錯誤處理機制完整性
- ✅ 使用者體驗優化效果
- ✅ 效能最佳化實施成果
- ✅ 資料流轉完整性

### 測試環境
- **前端框架**: Vue.js 3 + PrimeVue
- **後端API**: Spring Boot 3 + RESTful API
- **API基礎路徑**: http://localhost:8088/api/v1/title-setting/
- **測試瀏覽器**: Chrome, Firefox, Edge
- **測試工具**: Vue DevTools, Browser DevTools, Postman

---

## 🧪 API串接功能測試

### 1. 基礎API呼叫測試

#### 1.1 職稱清單載入 ✅
**測試項目**: GET /api/v1/title-setting/titles
```javascript
// 測試案例
const testCases = [
  {
    scenario: '正常載入當前年度資料',
    params: { year: '2025', page: 0, size: 50 },
    expected: '成功載入職稱清單，顯示載入狀態'
  },
  {
    scenario: '載入歷史年度資料',
    params: { year: '2024', page: 0, size: 50 },
    expected: '成功載入並顯示唯讀狀態'
  },
  {
    scenario: '載入未來年度資料',
    params: { year: '2026', page: 0, size: 50 },
    expected: '成功載入或顯示空狀態，允許編輯'
  },
  {
    scenario: '網路錯誤處理',
    params: { year: '2025' },
    mockError: 'NETWORK_ERROR',
    expected: '顯示網路錯誤訊息和重試按鈕'
  }
]
```

**驗證重點**:
- [ ] 載入狀態指示器正確顯示
- [ ] 快取機制正常運作
- [ ] 錯誤狀態正確處理
- [ ] 重試機制有效

#### 1.2 資料儲存功能 ✅
**測試項目**: POST /api/v1/title-setting/titles/batch
```javascript
// 測試案例
const saveTestCases = [
  {
    scenario: '正常儲存新增資料',
    data: {
      year: '2025',
      titles: [
        { level: '甲級', title: '船長' },
        { level: '乙級', title: '水手長' }
      ],
      mode: 'OVERWRITE'
    },
    expected: '顯示儲存進度，成功後顯示成功訊息'
  },
  {
    scenario: '資料驗證錯誤',
    data: {
      year: '2025',
      titles: [
        { level: '', title: '船長' }  // 級別為空
      ]
    },
    expected: '顯示驗證錯誤訊息，阻止提交'
  },
  {
    scenario: '重複資料檢查',
    data: {
      year: '2025',
      titles: [
        { level: '甲級', title: '船長' },
        { level: '甲級', title: '船長' }  // 重複
      ]
    },
    expected: '顯示重複資料警告'
  }
]
```

**驗證重點**:
- [ ] 表單驗證機制完整
- [ ] 儲存進度指示清晰
- [ ] 成功/失敗反饋明確
- [ ] 樂觀鎖定機制有效

#### 1.3 複製前一年資料 ✅
**測試項目**: POST /api/v1/title-setting/titles/copy
```javascript
// 測試案例
const copyTestCases = [
  {
    scenario: '成功複製前一年資料',
    data: {
      sourceYear: '2024',
      targetYear: '2025',
      overwrite: true
    },
    expected: '顯示確認對話框，成功後進入編輯模式'
  },
  {
    scenario: '前一年無資料',
    data: {
      sourceYear: '2023',
      targetYear: '2025'
    },
    mockError: '前一年沒有資料可複製',
    expected: '顯示友善錯誤訊息'
  }
]
```

**驗證重點**:
- [ ] 確認對話框正確顯示
- [ ] 複製進度指示清晰
- [ ] 成功後自動進入編輯模式
- [ ] 錯誤處理友善

---

## 🛡️ 錯誤處理機制測試

### 2. 統一錯誤處理驗證

#### 2.1 網路錯誤處理 ⚠️
```javascript
// 模擬測試
const networkErrorTests = [
  {
    scenario: '連線超時',
    mockCondition: 'timeout',
    expected: '顯示超時錯誤，提供重試選項'
  },
  {
    scenario: '伺服器無回應',
    mockCondition: 'no_response',
    expected: '顯示網路錯誤，建議檢查連線'
  },
  {
    scenario: '斷線狀態',
    mockCondition: 'offline',
    expected: '顯示離線提示，自動重試'
  }
]
```

**驗證重點**:
- [ ] 網路錯誤自動識別
- [ ] 重試機制自動觸發
- [ ] 使用者友善提示
- [ ] 離線狀態處理

#### 2.2 業務錯誤處理 ⚠️
```javascript
// 業務邏輯錯誤測試
const businessErrorTests = [
  {
    scenario: '權限不足錯誤 (403)',
    mockResponse: { status: 403, message: '沒有編輯權限' },
    expected: '顯示權限錯誤，停用編輯功能'
  },
  {
    scenario: '資料驗證錯誤 (422)',
    mockResponse: { 
      status: 422, 
      fieldErrors: [
        { field: 'title', message: '職稱不能為空' }
      ]
    },
    expected: '顯示欄位級別錯誤提示'
  },
  {
    scenario: '伺服器錯誤 (500)',
    mockResponse: { status: 500, message: '系統暫時無法處理' },
    expected: '顯示系統錯誤，提供技術支援聯絡'
  }
]
```

**驗證重點**:
- [ ] HTTP狀態碼正確處理
- [ ] 業務錯誤友善顯示
- [ ] 欄位錯誤精確定位
- [ ] 錯誤恢復引導

---

## ⚡ 效能最佳化測試

### 3. 載入效能驗證

#### 3.1 快取機制測試 ✅
```javascript
// 快取效能測試
const cacheTests = [
  {
    scenario: '首次載入',
    action: 'loadYearData(2025)',
    expected: 'API呼叫，資料存入快取'
  },
  {
    scenario: '重複載入',
    action: 'loadYearData(2025)',
    expected: '使用快取資料，無API呼叫'
  },
  {
    scenario: '快取過期',
    action: 'loadYearData(2025) after 5min',
    expected: '重新API呼叫，更新快取'
  },
  {
    scenario: '快取清除',
    action: 'clearCache() then loadYearData(2025)',
    expected: '強制API呼叫，重建快取'
  }
]
```

**驗證重點**:
- [ ] 快取命中率統計
- [ ] 快取過期機制
- [ ] 手動快取清除
- [ ] 快取狀態指示

#### 3.2 防抖動機制測試 ✅
```javascript
// 防抖動測試
const debounceTests = [
  {
    scenario: '快速連續輸入',
    action: '快速修改職稱名稱',
    expected: '只在停止輸入後觸發自動儲存'
  },
  {
    scenario: '搜尋防抖動',
    action: '快速切換年度選項',
    expected: '只載入最後選擇的年度資料'
  }
]
```

**驗證重點**:
- [ ] 防抖動延遲時間適中
- [ ] 避免重複API呼叫
- [ ] 使用者體驗流暢

#### 3.3 批次操作效能 ✅
```javascript
// 批次處理測試
const batchTests = [
  {
    scenario: '大量資料儲存',
    data: '50個職稱設定',
    expected: '批次處理，顯示進度'
  },
  {
    scenario: '批次驗證',
    data: '包含錯誤的資料集',
    expected: '快速驗證，錯誤彙總顯示'
  }
]
```

**驗證重點**:
- [ ] 批次處理效率
- [ ] 進度指示準確
- [ ] 錯誤處理完整

---

## 🎨 使用者體驗測試

### 4. 互動體驗驗證

#### 4.1 載入狀態管理 ✅
```javascript
// 載入體驗測試
const loadingUXTests = [
  {
    scenario: '資料載入中',
    expected: [
      '顯示載入遮罩',
      '載入文字描述清晰',
      '進度條(如適用)',
      '操作按鈕適當停用'
    ]
  },
  {
    scenario: '儲存進行中',
    expected: [
      '儲存按鈕顯示載入狀態',
      '其他操作按鈕停用',
      '進度提示清晰'
    ]
  }
]
```

**驗證重點**:
- [ ] 載入狀態視覺回饋
- [ ] 操作阻斷適當
- [ ] 進度資訊清晰
- [ ] 載入動畫流暢

#### 4.2 操作確認機制 ✅
```javascript
// 確認對話框測試
const confirmationTests = [
  {
    scenario: '刪除列確認',
    trigger: '點擊刪除按鈕',
    expected: '顯示危險操作確認對話框'
  },
  {
    scenario: '取消編輯確認',
    trigger: '有未儲存變更時點擊取消',
    expected: '顯示未儲存變更確認對話框'
  },
  {
    scenario: '複製資料確認',
    trigger: '點擊複製前一年資料',
    expected: '顯示覆蓋確認對話框'
  }
]
```

**驗證重點**:
- [ ] 確認對話框設計清晰
- [ ] 操作後果說明明確
- [ ] 按鈕標籤語意正確
- [ ] 鍵盤操作支援

#### 4.3 即時反饋機制 ✅
```javascript
// 即時反饋測試
const feedbackTests = [
  {
    scenario: '成功操作反饋',
    action: '成功儲存資料',
    expected: 'Toast成功訊息，綠色主題'
  },
  {
    scenario: '錯誤操作反饋',
    action: '驗證失敗',
    expected: 'Toast錯誤訊息，紅色主題，停留時間較長'
  },
  {
    scenario: '警告資訊反饋',
    action: '資料有潛在問題',
    expected: 'Toast警告訊息，橙色主題'
  }
]
```

**驗證重點**:
- [ ] 反饋訊息即時性
- [ ] 視覺層次清晰
- [ ] 訊息內容友善
- [ ] 自動關閉時機適當

---

## 🔧 功能整合測試

### 5. 完整流程驗證

#### 5.1 新增職稱完整流程 ✅
```javascript
// 端到端測試流程
const e2eNewTitleFlow = [
  {
    step: 1,
    action: '選擇年度',
    expected: '載入該年度資料，判斷編輯權限'
  },
  {
    step: 2,
    action: '點擊編輯按鈕',
    expected: '進入編輯模式，顯示草稿狀態'
  },
  {
    step: 3,
    action: '點擊新增列表',
    expected: '新增空白列，自動聚焦第一個欄位'
  },
  {
    step: 4,
    action: '填寫級別和職稱',
    expected: '即時驗證，顯示變更狀態'
  },
  {
    step: 5,
    action: '點擊存檔',
    expected: '驗證資料，顯示儲存進度，成功後回到唯讀'
  }
]
```

**驗證重點**:
- [ ] 流程步驟順暢
- [ ] 狀態轉換正確
- [ ] 資料持久化成功
- [ ] 錯誤處理完整

#### 5.2 複製資料完整流程 ✅
```javascript
// 複製資料端到端測試
const e2eCopyFlow = [
  {
    step: 1,
    action: '選擇未來年度',
    expected: '顯示空狀態，顯示複製按鈕'
  },
  {
    step: 2,
    action: '點擊複製前一年資料',
    expected: '顯示確認對話框'
  },
  {
    step: 3,
    action: '確認複製',
    expected: '執行複製API，顯示進度'
  },
  {
    step: 4,
    action: '複製完成',
    expected: '載入複製的資料，自動進入編輯模式'
  },
  {
    step: 5,
    action: '修改後儲存',
    expected: '更新資料，清除快取'
  }
]
```

**驗證重點**:
- [ ] 複製邏輯正確
- [ ] 資料來源驗證
- [ ] 目標覆蓋處理
- [ ] 快取同步更新

---

## 📊 效能基準測試

### 6. 效能指標驗證

#### 6.1 載入效能指標 ⚡
```javascript
// 效能基準
const performanceBenchmarks = {
  initialLoad: {
    target: '< 2秒',
    measurement: 'Time to Interactive'
  },
  apiResponse: {
    target: '< 500ms',
    measurement: '95% API響應時間'
  },
  cacheHit: {
    target: '< 50ms',
    measurement: '快取資料載入時間'
  },
  formValidation: {
    target: '< 100ms',
    measurement: '即時驗證響應時間'
  }
}
```

**測試方法**:
- [ ] 使用 Performance API 測量
- [ ] 記錄 Network 面板時間
- [ ] 監控 Memory 使用量
- [ ] 測試不同資料量場景

#### 6.2 記憶體使用測量 ⚡
```javascript
// 記憶體使用監控
const memoryTests = [
  {
    scenario: '正常使用',
    actions: '載入→編輯→儲存→切換年度',
    expected: '記憶體穩定，無洩漏'
  },
  {
    scenario: '重複操作',
    actions: '重複載入不同年度100次',
    expected: '記憶體增長線性，GC有效'
  }
]
```

**驗證重點**:
- [ ] 記憶體洩漏檢查
- [ ] 快取大小控制
- [ ] DOM 節點清理
- [ ] 事件監聽器清理

---

## 🔍 相容性測試

### 7. 瀏覽器相容性

#### 7.1 主流瀏覽器測試 🌐
```javascript
// 瀏覽器支援矩陣
const browserMatrix = [
  { browser: 'Chrome', version: '≥90', status: '✅ 完全支援' },
  { browser: 'Firefox', version: '≥88', status: '✅ 完全支援' },
  { browser: 'Safari', version: '≥14', status: '⚠️ 需要測試' },
  { browser: 'Edge', version: '≥90', status: '✅ 完全支援' }
]
```

**測試重點**:
- [ ] API呼叫相容性
- [ ] ES6+ 語法支援
- [ ] CSS Grid/Flexbox 顯示
- [ ] 事件處理相容性

#### 7.2 行動裝置測試 📱
```javascript
// 響應式設計測試
const mobileTests = [
  {
    device: 'iPhone 12',
    viewport: '390×844',
    expected: '介面正常顯示，觸控操作順暢'
  },
  {
    device: 'iPad',
    viewport: '768×1024',
    expected: '表格適當縮放，編輯功能正常'
  },
  {
    device: 'Android Tablet',
    viewport: '800×1280',
    expected: '佈局自適應，載入速度可接受'
  }
]
```

**驗證重點**:
- [ ] 觸控操作友善
- [ ] 螢幕適應性良好
- [ ] 載入速度可接受
- [ ] 離線功能(如適用)

---

## ✅ 測試執行檢查清單

### 8. 測試準備和執行

#### 8.1 測試環境準備 🛠️
- [ ] 後端API服務正常運行
- [ ] 測試資料庫準備完成
- [ ] 前端開發環境配置正確
- [ ] 瀏覽器開發工具準備
- [ ] 網路模擬工具設定(如需要)

#### 8.2 測試資料準備 📋
- [ ] 有效的測試年度資料
- [ ] 權限測試用戶帳號
- [ ] 異常情況模擬資料
- [ ] 效能測試大量資料

#### 8.3 測試執行順序 🔄
1. **基礎功能測試** (API呼叫、資料載入)
2. **錯誤處理測試** (網路錯誤、業務錯誤)
3. **效能最佳化測試** (快取、防抖動)
4. **使用者體驗測試** (載入狀態、確認對話框)
5. **整合流程測試** (端到端完整流程)
6. **效能基準測試** (載入時間、記憶體使用)
7. **相容性測試** (多瀏覽器、響應式)

#### 8.4 問題記錄和修復 🐛
- [ ] 建立問題追蹤清單
- [ ] 記錄重現步驟
- [ ] 分類問題嚴重程度
- [ ] 驗證修復效果
- [ ] 迴歸測試執行

---

## 📈 測試結果評估

### 9. 成功標準

#### 9.1 功能性標準 ✅
- **API串接**: 所有API呼叫成功率 ≥ 99%
- **錯誤處理**: 所有錯誤情況都有適當處理
- **資料一致性**: 前後端資料同步準確
- **業務邏輯**: 所有業務規則正確實現

#### 9.2 效能標準 ⚡
- **初始載入**: < 2秒完成
- **API響應**: 95% 請求 < 500ms
- **快取命中**: 快取資料載入 < 50ms
- **記憶體使用**: 穩定，無明顯洩漏

#### 9.3 使用者體驗標準 🎨
- **載入回饋**: 所有載入狀態都有視覺指示
- **錯誤友善**: 錯誤訊息清晰易懂
- **操作流暢**: 無明顯延遲和卡頓
- **直覺操作**: 符合用戶習慣和期望

---

## 🚀 測試完成交付

### 10. 交付成果

#### 10.1 測試報告 📊
- [ ] 完整的測試執行記錄
- [ ] 問題清單和修復狀況
- [ ] 效能基準測試結果
- [ ] 相容性測試結果

#### 10.2 技術文件 📚
- [ ] API串接使用說明
- [ ] 錯誤處理指南
- [ ] 效能最佳化建議
- [ ] 維護和監控指南

#### 10.3 部署清單 🛠️
- [ ] 環境配置檢查
- [ ] 依賴項目確認
- [ ] 資料庫遷移腳本
- [ ] 監控和日誌設定

---

> **測試計畫版本**: v1.0  
> **最後更新**: 2025年9月21日  
> **負責人**: 開發團隊  
> **審核人**: 技術主管  
> 
> **下一步**: 執行測試計畫，記錄結果，準備生產部署