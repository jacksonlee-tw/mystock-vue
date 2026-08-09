---
description: "模組遷移完成最終檢查清單，git push 前驗證所有產出物齊全"
mode: "agent"
---

# 模組遷移完成檢查清單（Migration Checklist）

**觸發時機**：準備上傳 GitLab 前（git-workflow Skill 執行前）

## 檢查流程

根據模組名稱，掃描所有預期產出物是否存在且完整。

### 完整遷移產出物清單

| # | 階段 | 產出物 | 預期路徑 | 檢查方式 |
|---|------|--------|---------|---------|
| 1 | 需求 | Use Case 文件 | `docs/01_Requirements/use-cases/<Module>/UC-*.md` | 檔案存在 |
| 2 | 需求 | UC-00 總覽已更新 | `docs/01_Requirements/use-cases/UC-00-使用案例總覽.md` | 包含此模組 |
| 3 | 設計 | DB 規格書 | `docs/02_Design/db/ecard-<module>-db規格書.md` | 檔案存在 |
| 4 | 設計 | API 規格書 | `docs/02_Design/api/ecard-<module>-API規格書.md` | 檔案存在 |
| 5 | 設計 | 系統設計文件 | `docs/02_Design/<Module>/SD-<Module>-系統設計.md` | 檔案存在 |
| 6 | 後端 | SQLAlchemy Model | `backend/app/models/<module>.py` | 檔案存在 + 有 class 定義 |
| 7 | 後端 | Pydantic Schema | `backend/app/schemas/<module>.py` | 檔案存在 + 有 Create/Response |
| 8 | 後端 | FastAPI Router | `backend/app/routers/<module>_router.py` | 檔案存在 + 有 @router |
| 9 | 後端 | Service | `backend/app/services/<module>_service.py` | 檔案存在 |
| 10 | 後端 | Repository | `backend/app/repos/<module>_repo.py` | 檔案存在 |
| 11 | 前端 | Vue 頁面 | `src/views/<Module>*.vue` | 檔案存在 |
| 12 | 前端 | Service 層 | `src/service/<Module>Service.js` | 檔案存在 |
| 13 | 前端 | 路由已註冊 | `src/router/index.js` | 包含模組路由 |
| 14 | 前端 | 菜單已更新 | `src/layout/AppMenu.vue` | 包含模組菜單項 |
| 15 | 測試 | pytest 測試 | `backend/tests/test_<module>*.py` | 檔案存在 |
| 16 | 測試 | Playwright 測試 | `frontend/tests/e2e/specs/<module>*.spec.js` | 檔案存在 |
| 17 | 測試 | 測試計劃 | `docs/03_Testing/TP-<Module>-測試計劃.md` | 檔案存在 |

### 輸出格式

```markdown
## 模組遷移檢查清單 — <Module>

📊 完成度：X / 17 (XX%)

| # | 階段 | 產出物 | 狀態 | 備註 |
|---|------|--------|------|------|
| 1 | 需求 | Use Case | ✅ | 3 份 UC 文件 |
| 2 | 需求 | UC-00 總覽 | ✅ | 已包含 ManualCard |
| 3 | 設計 | DB 規格書 | ✅ | |
| ... | ... | ... | ... | ... |
| 15 | 測試 | pytest | ❌ | 缺失 |

### ❌ 缺失項目
- [ ] `backend/tests/test_manual_card_router.py` — 建議執行 @系統測試代理

### ✅ 可提交
☐ 全部通過 → 建議執行 `git-workflow` 上傳
☑ 有缺失 → 列出修正步驟後再提交
```

### 判定規則

- **全部 ✅**（17/17）：顯示「🟢 可直接提交」
- **必要項目完成**（#1~#10 通過）：顯示「🟡 核心完成，可先提交後端」
- **有 ❌ 必要項目**：顯示「🔴 阻止提交」並列出修正步驟
