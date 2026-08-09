---
name: git-workflow
description: >-
  開發或測試完成後，自動建立 Git feature branch、stage 變更檔案、
  以 Conventional Commit 格式提交、推送至 GitLab remote。
  當使用者提到以下任何一項時，務必使用此 Skill：
  上傳到 GitLab、push 到 git、建立 branch、提交程式碼、
  git commit、git push、建立分支、上傳程式碼、推送到遠端、
  commit and push、提交並推送、建立 feature branch、
  程式碼上傳、同步到 GitLab、推到 remote。
  即使使用者只說「幫我上傳」、「push 上去」、「提交程式碼」，
  也應觸發此 Skill。
---

# git-workflow — Git 分支建立與推送至 GitLab

## 1. 目的

在開發或測試完成後，自動化執行以下 Git 操作：
1. 從當前分支建立新的 feature branch
2. 掃描並 stage 所有變更檔案
3. 以 Conventional Commit 格式提交
4. 推送至 GitLab remote
5. 輸出 Merge Request 建立連結

---

## 2. 前置條件

執行前必須確認：
- Git 已初始化（`.git/` 存在）
- 有已設定的 remote（`git remote -v` 可取得 URL）
- 工作目錄有未提交的變更（`git status --porcelain` 非空）
- 使用者已設定 `user.name` 和 `user.email`

若工作目錄無變更，回報「沒有偵測到變更檔案，無需提交」並結束。

---

## 3. 分支命名規範

### 3.1 格式

```
feature/<module>-<type>-<YYYYMMDD>
```

### 3.2 各欄位說明

| 欄位 | 說明 | 範例 |
|------|------|------|
| `<module>` | 模組名稱（kebab-case） | `manual-card`、`smart-card-sdmm`、`weighing` |
| `<type>` | 工作類型 | `backend`、`frontend`、`test`、`docs`、`full` |
| `<YYYYMMDD>` | 日期 | `20260323` |

### 3.3 Type 對照表

| 來源 Agent / 情境 | type | 範例 |
|-------------------|------|------|
| @後端開發代理-FastApi 完成 | `backend` | `feature/manual-card-backend-20260323` |
| @前端開發代理-PrimeVue4 完成 | `frontend` | `feature/manual-card-frontend-20260323` |
| @系統測試代理 完成 | `test` | `feature/manual-card-test-20260323` |
| @需求文件代理 / @系統設計代理 完成 | `docs` | `feature/manual-card-docs-20260323` |
| 完整遷移（多個 Agent 連續執行） | `full` | `feature/manual-card-full-20260323` |
| 使用者自訂 | 使用者指定 | `feature/hotfix-weighing-20260323` |

### 3.4 同日重複分支

若同名分支已存在，自動附加序號：
```
feature/manual-card-backend-20260323-2
feature/manual-card-backend-20260323-3
```

---

## 4. 工作流程

### Step 1 — 確認 Git 環境

```bash
# 確認 remote
git remote -v

# 確認當前分支
git branch --show-current

# 確認使用者資訊
git config user.name
git config user.email
```

若 remote 未設定，提示使用者先設定 remote URL。

### Step 2 — 掃描變更檔案

```bash
git status --porcelain
```

解析輸出，將變更分類並顯示摘要：

```
📊 變更檔案摘要：
   新增(A):  12 個檔案
   修改(M):   3 個檔案
   刪除(D):   0 個檔案
   合計:     15 個檔案

📂 變更分類：
   後端 Models:    app/models/manual_card.py (新增)
   後端 Schemas:   app/schemas/manual_card.py (新增)
   後端 Routers:   app/routers/manual_card_router.py (新增)
   後端 Services:  app/services/manual_card_service.py (新增)
   後端 Repos:     app/repos/manual_card_repo.py (新增)
   前端 Views:     src/views/ManualCard.vue (新增)
   前端 Service:   src/service/ManualCardService.js (新增)
   前端 Router:    src/router/index.js (修改)
   前端 Menu:      src/layout/AppMenu.vue (修改)
   測試:           tests/test_manual_card_router.py (新增)
   文件:           docs/02_Design/api/... (新增)
```

### Step 3 — 確認提交

向使用者確認：

```
準備建立分支並提交：
  🌿 分支: feature/manual-card-backend-20260323
  📝 Commit: feat(manual-card): 新增人工制卡模組後端程式碼
  📦 檔案: 15 個（12 新增 / 3 修改 / 0 刪除）
  🎯 Remote: origin (http://tcci-gitlab.taiwancement.com/tccifz/proj/ecardsystem.git)

按 Enter 確認，或輸入修改指示。
```

### Step 4 — 建立分支

```bash
# 從當前分支建立新分支
git checkout -b feature/<module>-<type>-<YYYYMMDD>
```

若分支已存在，加序號：
```bash
# 檢查是否存在
git branch --list "feature/<module>-<type>-<YYYYMMDD>"
# 若存在，嘗試 -2, -3, ...
git checkout -b feature/<module>-<type>-<YYYYMMDD>-2
```

### Step 5 — Stage 檔案

依類型分批 stage（便於追蹤）：

```bash
# 全部 stage
git add -A
```

**不使用** `git add .`（避免未追蹤檔案遺漏），統一使用 `git add -A`。

### Step 6 — 提交

使用 Conventional Commit 格式：

```bash
git commit -m "<type>(<scope>): <description>"
```

#### 6.1 Commit Type 對照

| 工作類型 | Commit Type | 範例 |
|---------|-------------|------|
| 後端開發 | `feat` | `feat(manual-card): 新增人工制卡模組後端程式碼` |
| 前端開發 | `feat` | `feat(manual-card): 新增人工制卡 Vue 前端頁面` |
| 測試 | `test` | `test(manual-card): 新增人工制卡 API 整合與 E2E 測試` |
| 設計文件 | `docs` | `docs(manual-card): 新增人工制卡系統設計文件` |
| 需求文件 | `docs` | `docs(manual-card): 新增人工制卡使用案例` |
| 完整遷移 | `feat` | `feat(manual-card): 完整遷移人工制卡模組（後端+前端+測試）` |
| Bug 修復 | `fix` | `fix(manual-card): 修正制卡流程驗證邏輯` |
| 重構 | `refactor` | `refactor(manual-card): 重構制卡 Service 層` |

#### 6.2 Scope 命名

`<scope>` = 模組名稱（kebab-case），與分支名稱中的 `<module>` 一致。

#### 6.3 多模組變更

若變更跨多個模組：
```bash
git commit -m "feat(weighing,manual-card): 新增過磅與制卡模組後端程式碼"
```

#### 6.4 Commit Body（選配）

對於大型提交，可加入 body 說明：
```bash
git commit -m "feat(manual-card): 完整遷移人工制卡模組

- 新增 FastAPI 後端（Model/Schema/Router/Service/Repo）
- 新增 Vue 3 + PrimeVue 4 前端頁面
- 新增 pytest API 整合測試（12 案例）
- 新增 Playwright E2E 測試（8 案例）
- 更新路由表與菜單配置"
```

### Step 7 — 推送至 GitLab

```bash
git push -u origin feature/<module>-<type>-<YYYYMMDD>
```

`-u` 設定 upstream tracking，後續可直接 `git push`。

### Step 8 — 輸出摘要

```
✅ 已推送至 GitLab：

🌿 分支:  feature/manual-card-backend-20260323
📝 Commit: feat(manual-card): 新增人工制卡模組後端程式碼 (abc1234)
📦 檔案:  15 個（12 新增 / 3 修改 / 0 刪除）
🎯 Remote: origin/feature/manual-card-backend-20260323

🔗 建立 Merge Request：
   http://tcci-gitlab.taiwancement.com/tccifz/proj/ecardsystem/-/merge_requests/new?merge_request[source_branch]=feature/manual-card-backend-20260323

💡 下一步：
   - 在 GitLab 上建立 Merge Request → 目標分支: gen-docs
   - 指派 Reviewer 進行 Code Review
   - CI/CD Pipeline 通過後合併
```

---

## 5. Merge Request URL 產生規則

從 `git remote -v` 解析 GitLab URL：

| Remote URL 格式 | MR 建立 URL |
|-----------------|-------------|
| `http://host/group/project.git` | `http://host/group/project/-/merge_requests/new?merge_request[source_branch]=<branch>` |
| `git@host:group/project.git` | `http://host/group/project/-/merge_requests/new?merge_request[source_branch]=<branch>` |

解析步驟：
1. 取得 remote URL：`git remote get-url origin`
2. 移除 `.git` 尾綴
3. 若為 SSH 格式，轉換為 HTTP 格式
4. 附加 MR query string

---

## 6. 安全注意事項

- **不使用 `--force`** — 絕不強制推送
- **不使用 `--no-verify`** — 不跳過 Git hooks
- **不修改已推送的 commit** — 不使用 `--amend` 在已 push 的 commit 上
- **推送前確認** — 列出所有變更讓使用者確認才推送
- **不自動合併** — 只推送分支，合併由使用者在 GitLab UI 操作
- **敏感檔案檢查** — 推送前檢查是否包含 `.env`、`*.key`、`*password*`、`kamacfg.ini` 等敏感檔案

### 6.1 敏感檔案清單

以下檔案模式若出現在變更中，必須**警告使用者**：

```
*.env
*.key
*.pem
*.p12
*password*
*secret*
*credential*
kamacfg.ini
rfcardcfg.ini
config.ini
```

警告格式：
```
⚠️ 偵測到可能的敏感檔案：
   - kamacfg.ini（含資料庫連線設定）
   
是否確定要包含這些檔案？建議加入 .gitignore。
```

---

## 7. 與 Agent 的整合

此 Skill 設計為所有 Agent 工作流程的最後一步：

```
@後端開發代理-FastApi → Step 7 輸出摘要 → 💡「上傳到 GitLab」→ git-workflow
@前端開發代理-PrimeVue4 → Step 11 輸出摘要 → 💡「上傳到 GitLab」→ git-workflow
@系統測試代理 → Step 7 輸出摘要 → 💡「上傳到 GitLab」→ git-workflow
@需求文件代理 → 完成 UC 文件 → 💡「上傳到 GitLab」→ git-workflow
@系統設計代理 → 完成設計文件 → 💡「上傳到 GitLab」→ git-workflow
```

### 7.1 Agent 自動推導

若由 Agent 觸發，可自動推導 `<module>` 和 `<type>`：

| 觸發 Agent | 自動推導 type | module 來源 |
|-----------|--------------|------------|
| @後端開發代理-FastApi | `backend` | Agent 處理的模組名稱 |
| @前端開發代理-PrimeVue4 | `frontend` | Agent 處理的模組名稱 |
| @系統測試代理 | `test` | Agent 處理的模組名稱 |
| @需求文件代理 | `docs` | Agent 處理的模組名稱 |
| @系統設計代理 | `docs` | Agent 處理的模組名稱 |
| 使用者直接觸發 | 詢問使用者 | 詢問使用者 |

---

## 8. 常見問題處理

### 8.1 Remote 認證失敗

```
⚠️ 推送失敗：認證錯誤
請確認 GitLab 帳號權限，或執行：
  git config credential.helper store
然後重新推送。
```

### 8.2 分支衝突

```
⚠️ 遠端已存在同名分支 feature/manual-card-backend-20260323
選項：
  1. 自動加序號 → feature/manual-card-backend-20260323-2
  2. 切換到該分支繼續開發
  3. 取消操作
```

### 8.3 大量檔案變更

若變更超過 50 個檔案，顯示額外警告：
```
⚠️ 偵測到大量變更（87 個檔案）
建議分批提交，或確認是否包含非預期的檔案。
按 Enter 繼續，或輸入排除模式。
```
