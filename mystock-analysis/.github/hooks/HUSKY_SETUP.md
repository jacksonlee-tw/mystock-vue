# Husky Git Hooks 設定

> 本設定統一管理 eCard 系統的 Git hook，在 commit / push 時自動執行程式碼品質檢查。

---

## 安裝 Husky + lint-staged + commitlint

此設定需要在專案根目錄執行一次：

```bash
# 1. 安裝工具包
npm install -D husky lint-staged commitlint @commitlint/config-conventional

# 2. 初始化 Husky（建立 .husky 目錄）
npx husky install

# 3. 配置文件已在根目錄就位（見下方檔案清單）
```

---

## 檔案清單

| 檔案 | 用途 | 位置 |
|------|------|------|
| `.husky/pre-commit` | commit 前：ESLint + Ruff + Prettier | 根目錄 |
| `.husky/commit-msg` | commit message 驗證：Conventional Commit | 根目錄 |
| `.husky/pre-push` | push 前：pytest + npm build | 根目錄 |
| `lint-staged.config.js` | lint-staged 設定 | 根目錄 |
| `commitlint.config.js` | commitlint 設定 | 根目錄 |

---

## Hook 詳細說明

### pre-commit（commit 前檢查）

**觸發時機**：執行 `git commit` 時

**檢查內容**：
- 前端 Vue 檔：ESLint + Prettier
- 後端 Python 檔：Ruff lint + Black format
- Markdown：基礎格式驗證

**失敗時**：commit 被阻止，顯示錯誤清單

```bash
# 手動跳過此 hook（不建議）：
git commit --no-verify
```

### commit-msg（提交訊息驗證）

**觸發時機**：輸入 commit message 後

**檢查內容**：
- 訊息格式：`type(scope): description`
- Conventional Commit 標準

**允許的 type**：

| type | 說明 |
|------|------|
| `feat` | 新功能 |
| `fix` | 缺陷修復 |
| `docs` | 文件更新 |
| `style` | 程式碼風格（空白、分號等） |
| `refactor` | 重構（不改功能） |
| `perf` | 性能優化 |
| `test` | 測試相關 |
| `ci` | CI/CD 設定 |
| `chore` | 雜務（依賴更新等） |

**範例**：
```
feat(manual-card): 新增人工制卡頁面
fix(weighing-api): 修正稱重異常處理
docs(setup): 更新安裝指引
```

### pre-push（推送前檢查）

**觸發時機**：執行 `git push` 時

**檢查內容**：
- 後端：執行 pytest（快速子集，無網路測試）
- 前端：執行 `npm run build` 編譯驗證
- 防止推送無法執行的程式碼

**失敗時**：push 被阻止

```bash
# 手動跳過（不建議）：
git push --no-verify
```

---

## 常見問題

### Q1：commit 被 ESLint 阻止該怎辦？

執行 `npm run lint` 自動修復，然後重新 commit：

```bash
npm run lint
git add .
git commit -m "fix: auto-format"
```

### Q2：想跳過 pre-commit 檢查？

**不建議**，但如果必要：

```bash
git commit --no-verify -m "hotfix: urgent bug"
```

### Q3：pytest 時間太長，能加快嗎？

pre-push 預設只執行標記 `@pytest.mark.quick` 的快速測試：

```bash
# 手動執行完整測試
pytest
```

### Q4：誰該設定 Husky？

團隊中只需**一個開發者**執行 `npm install` + `npx husky install`，
其他人 clone 時 Git hook 會自動啟用。

---

## 禁用整個 Hook 系統（不建議）

若要暫時停用所有 hook：

```bash
# 禁用
husky uninstall

# 重新啟用
husky install
```
