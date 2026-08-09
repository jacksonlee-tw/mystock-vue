# 後端開發人員 Prompt Library

## 📋 文件說明
本文件收集後端開發人員在使用AI工具進行SpringBoot專案開發時的常用prompt，涵蓋API開發、資料庫設計、安全性實作、單元測試、效能優化、部署運維等各個環節。

## 🏷️ Prompt 分類
- **API開發**: REST API設計、Controller實作、API文件生成
- **資料庫操作**: JPA Entity設計、Repository實作、SQL優化
- **安全性**: Spring Security設定、認證授權、資料驗證
- **測試**: 單元測試、整合測試、Mock測試
- **效能優化**: 快取機制、異步處理、資料庫優化
- **部署運維**: Docker容器化、CI/CD、監控日誌

## 📊 Prompt 清單表

| ID | 類別 | Prompt名稱 | 用途 | 更新日期 | 使用頻率 |
|----|------|------------|------|----------|----------|
| P001 | API開發 | RESTful API控制器生成 | 根據業務需求生成完整Controller | YYYY-MM-DD | ⭐⭐⭐⭐⭐ |
| P002 | 資料庫操作 | JPA Entity與Repository設計 | 生成資料庫實體類與存取層 | 待新增 | - |
| P003 | 安全性 | Spring Security設定 | 實作認證授權機制 | 待新增 | - |
| P004 | 測試 | 單元測試案例生成 | 為Service層生成JUnit測試 | 待新增 | - |
| P005 | 效能優化 | Redis快取實作 | 實作分散式快取機制 | 待新增 | - |
| P006 | 部署運維 | Docker化配置 | 生成Dockerfile與docker-compose | 待新增 | - |
| P007 | 測試 | Controller單元測試生成 | 為Controller生成完整單元測試 | 2024-01-15 | ⭐⭐⭐⭐ |

---

## 📝 Prompt 詳細內容

### 🆔 P001 - RESTful API控制器生成

**分類**: API開發  
**優先級**: 高  
**適用場景**: 需要快速建立符合RESTful規範的API控制器時使用

#### Prompt 內容:
```
你是資深的SpringBoot後端工程師。
請根據以下需求生成完整的RESTful API控制器：

**業務領域**: [業務實體名稱，如：User、Product、Order]
**主要功能**: [CRUD操作需求說明]
**技術要求**: 
- 使用Spring Boot 3+
- 遵循RESTful API設計原則
- 包含完整的HTTP狀態碼處理
- 實作資料驗證
- 包含異常處理機制

請生成以下內容：
1. Controller類別（包含完整CRUD操作）
2. DTO/VO物件定義
3. 全域異常處理器
4. API文件註解（Swagger/OpenAPI）
5. 輸入驗證註解
6. 單元測試範例

技術規格：
- HTTP方法：GET, POST, PUT, DELETE
- 路徑設計：/api/v1/[resources]
- 回應格式：統一JSON格式
- 錯誤處理：標準化錯誤回應
```

#### 使用說明:
- 將`[業務實體名稱]`替換為實際的業務實體
- 將`[CRUD操作需求說明]`替換為具體的功能需求
- 可根據專案架構調整技術版本和規範
- 建議配合實際的Service層和Repository層使用

#### 預期輸出:
- 生成完整的SpringBoot Controller程式碼
- 包含完善的資料驗證和異常處理
- 符合RESTful API設計最佳實務
- 提供對應的單元測試範例代碼

#### 相關標籤:
`#SpringBoot` `#RESTfulAPI` `#Controller` `#CRUD`

---

## 🔄 使用指南

### 快速開始
1. 根據開發需求從清單表中選擇合適的prompt
2. 複製對應的prompt內容
3. 根據實際專案情況調整參數
4. 在AI工具中執行prompt

### 自訂Prompt
當現有prompt不能完全滿足需求時，可以參考現有格式新增客製化prompt：

```markdown
### 🆔 PXXX - [Prompt名稱]

**分類**: [分類名稱]  
**優先級**: [高/中/低]  
**適用場景**: [使用情境說明]

#### Prompt 內容:
```
[具體的prompt內容]
```

#### 使用說明:
- [使用注意事項]

#### 預期輸出:
- [預期的輸出結果]

#### 相關標籤:
`#標籤1` `#標籤2`
```

### 版本控制
- 定期檢視使用頻率，優化常用prompt

---

## 📈 貢獻指南

歡迎團隊成員貢獻新的prompt或改進現有prompt：

1. **新增Prompt**: 按照標準格式新增到對應分類
2. **更新現有Prompt**: 修改內容並更新日期
3. **回饋使用經驗**: 更新使用頻率評級
4. **分享最佳實務**: 在使用說明中補充實用技巧