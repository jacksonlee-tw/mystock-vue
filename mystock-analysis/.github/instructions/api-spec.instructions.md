---
applyTo: "docs/02_Design/api/**/*.md"
---

# API 規格書撰寫規範（自動注入）

本指引在編輯 API 規格書時自動生效。

## 檔案命名

```
docs/02_Design/api/ecard-<module>-API規格書.md
```

## 文件結構

```markdown
# eCard <Module> API 規格書

## 1. 總覽
## 2. Base URL 與認證
## 3. 端點列表
## 4. 端點詳細規格
  ### 4.1 POST /api/v1/<resource>
  ### 4.2 GET /api/v1/<resource>
  ### ...
## 5. 錯誤碼定義
## 6. 業務流程圖（Mermaid）
```

## RESTful 命名慣例

| 操作 | HTTP Method | 路徑模式 | 範例 |
|------|------------|---------|------|
| 列表查詢 | GET | `/api/v1/<resources>` | `GET /api/v1/weighing-records` |
| 單筆查詢 | GET | `/api/v1/<resources>/{id}` | `GET /api/v1/weighing-records/123` |
| 建立 | POST | `/api/v1/<resources>` | `POST /api/v1/weighing-records` |
| 更新 | PUT | `/api/v1/<resources>/{id}` | `PUT /api/v1/weighing-records/123` |
| 部分更新 | PATCH | `/api/v1/<resources>/{id}` | `PATCH /api/v1/weighing-records/123` |
| 刪除 | DELETE | `/api/v1/<resources>/{id}` | `DELETE /api/v1/weighing-records/123` |
| 特定動作 | POST | `/api/v1/<resources>/{id}/<action>` | `POST /api/v1/cards/123/activate` |

## 路徑規則

- 前綴統一 `/api/v1/`
- 資源名稱使用 **kebab-case 複數**：`weighing-records`、`ic-cards`
- 路徑參數用 `{id}`（整數）或 `{code}`（字串）

## 標準錯誤碼

| HTTP Status | 代碼 | 說明 |
|-------------|------|------|
| 200 | OK | 查詢/更新成功 |
| 201 | Created | 建立成功 |
| 204 | No Content | 刪除成功 |
| 400 | Bad Request | 請求格式錯誤 |
| 401 | Unauthorized | 未認證 |
| 403 | Forbidden | 無權限 |
| 404 | Not Found | 資源不存在 |
| 409 | Conflict | 資源衝突（重複） |
| 422 | Unprocessable Entity | 驗證失敗 |
| 500 | Internal Server Error | 伺服器錯誤 |

## 回應格式（統一包裝）

```json
{
  "success": true,
  "data": { ... },
  "message": "OK"
}
```

## 每個端點必須包含

1. ✅ HTTP Method + 路徑
2. ✅ 功能說明
3. ✅ Request Body / Query Parameters（含型別與必填標記）
4. ✅ Response 範例（成功 + 失敗）
5. ✅ 業務驗證規則
6. ✅ 權限需求
