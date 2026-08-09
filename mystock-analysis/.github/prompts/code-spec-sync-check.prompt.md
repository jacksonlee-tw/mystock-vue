---
description: "後端開發代理-FastApi 完成後，驗證產出 Router 端點與 API 規格書一致性"
mode: "agent"
---

# 程式碼與規格同步檢查（Code-Spec Sync Check）

**觸發時機**：@後端開發代理-FastApi 產出 FastAPI 程式碼後執行

## 檢查流程

1. 讀取 API 規格書（`docs/02_Design/api/ecard-<module>-API規格書.md`）
2. 掃描 `backend/app/routers/<module>_router.py` 中的所有端點
3. 比對一致性

### 檢查項目

| # | 檢查項目 | 判定標準 | 嚴重度 |
|---|---------|---------|--------|
| 1 | **端點數量** | Router 端點數 = API 規格書端點數 | ❌ 必修 |
| 2 | **HTTP Method** | 每個端點的 Method 一致（GET/POST/PUT/DELETE） | ❌ 必修 |
| 3 | **路徑一致** | 路由 path 與規格書定義的 URL 完全匹配 | ❌ 必修 |
| 4 | **Request Schema** | Router 的 Body 參數型別名稱與規格書 DTO 名稱一致 | ⚠️ 警告 |
| 5 | **Response Schema** | Router 的 `response_model` 與規格書回應格式一致 | ⚠️ 警告 |
| 6 | **分層完整** | 每個 Router 端點有對應的 Service 方法和 Repository 方法 | ❌ 必修 |
| 7 | **Model 完整** | 每個資料表有對應的 SQLAlchemy Model 檔案 | ❌ 必修 |

### 掃描方式

```python
# 從 Router 檔案擷取端點資訊
# 搜尋模式：@router.get("/path"), @router.post("/path") 等
```

### 輸出格式

```markdown
## 程式碼-規格同步報告 — <Module>

### 端點對照表

| API 規格書 | Router 實作 | 狀態 |
|-----------|------------|------|
| GET /api/v1/cards | ✅ get_cards() | 匹配 |
| POST /api/v1/cards | ✅ create_card() | 匹配 |
| DELETE /api/v1/cards/{id} | ❌ 缺失 | 需補充 |

### 分層完整性

| Router 方法 | Service | Repository | 狀態 |
|------------|---------|------------|------|
| get_cards | ✅ | ✅ | 完整 |
| create_card | ✅ | ❌ | Service 直接操作 DB |

### 建議修正
- [ ] ...
```
