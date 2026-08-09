---
name: playwright-e2e-test-generator
description: >-
  從 Use Case 文件與 Vue 頁面結構，自動產生 Playwright E2E 測試案例。
  涵蓋 Page Object Model、使用者操作流程、表單驗證、DataTable 操作等完整 UI 測試。
  當使用者提到以下任何一項時，務必使用此 Skill：
  產生 E2E 測試、UI 測試、Playwright 測試、前端測試、端對端測試、
  e2e test、playwright test、browser test、UI automation、
  產生頁面測試、表單測試、DataTable 測試、PrimeVue 元件測試、
  寫 UI 測試、前端自動化測試、畫面測試、操作流程測試。
  即使使用者只說「幫我寫前端測試」、「測這個頁面」、
  「產生 E2E 測試案例」，也應觸發此 Skill。
---

# Use Case + Vue 頁面 → Playwright E2E 測試生成 Skill

## 目標

從 Use Case 文件與 Vue 前端頁面結構，自動產生：
1. **Page Object**（`pages/<module>.page.ts`）— 頁面元素封裝
2. **E2E 測試**（`tests/<module>.spec.ts`）— 使用者操作流程測試
3. **Fixture**（`fixtures/<module>.fixture.ts`）— 測試資料與前置條件
4. **playwright.config.ts**（若不存在則產生）

產出測試針對 **Vue 3 + PrimeVue 4** 元件結構優化，使用穩定的 selector 策略。

---

## 前置讀取（每次必讀）

1. `.github/skills/primevue3-development/SKILL.md` — 前端元件架構（確保 selector 對應）
2. 對應的 Use Case 文件（測試場景來源）
3. 對應的 Vue 頁面原始碼（`.vue` 檔案，取得實際元件結構）

---

## 輸入來源

| 輸入類型 | 說明 | 範例 |
|---------|------|------|
| **Use Case 文件** | 業務流程 → 測試場景 | `docs/01_Requirements/use-cases/ManualCard/UC-*.md` |
| **Vue 頁面** | 元件結構 → Page Object | `src/views/manualCard.vue` |
| **API 規格書** | API 端點 → Mock/Intercept | `docs/02_Design/api/ecard-*-API規格書.md` |
| **口頭描述** | 測試需求描述 | 「測試人工制卡頁面的完整流程」 |

---

## PrimeVue 4 Selector 策略

### 原則：優先使用穩定 selector，避免依賴 CSS class

**Selector 優先順序：**
1. `data-testid` 屬性（最穩定，需在 Vue 元件中預設）
2. `aria-label` / `role` （PrimeVue 元件內建無障礙屬性）
3. PrimeVue 元件語義 selector（見下表）
4. CSS class（最不推薦，僅作為最後手段）

### PrimeVue 4 元件 Selector 對照表

| PrimeVue 元件 | 推薦 Selector | 說明 |
|--------------|--------------|------|
| `Button` | `getByRole('button', { name: 'label' })` | 依 label 文字定位 |
| `InputText` | `getByLabel('欄位名')` 或 `locator('[data-testid="field-name"]')` | 搭配 `<label>` |
| `Dropdown` / `Select` | `locator('.p-select')` → `.p-select-option` | PrimeVue 4 改為 `p-select` |
| `DataTable` | `locator('.p-datatable')` | 行：`.p-datatable-tbody tr` |
| `Dialog` | `locator('.p-dialog')` | 標題：`.p-dialog-title` |
| `Toast` | `locator('.p-toast-message')` | 驗證操作回饋 |
| `ConfirmDialog` | `locator('.p-confirmdialog')` | 確認/取消按鈕 |
| `Calendar` | `locator('.p-datepicker')` | PrimeVue 4 改為 `p-datepicker` |
| `Checkbox` | `getByRole('checkbox')` | 勾選狀態驗證 |
| `TabView` / `Tabs` | `getByRole('tablist')` → `getByRole('tab')` | 分頁切換 |
| `Menu` | `locator('.p-menu')` → `.p-menuitem` | 選單操作 |
| `FileUpload` | `locator('.p-fileupload')` | 檔案上傳 |

---

## 產出步驟

### Step 1：分析 Use Case → 測試場景矩陣

從 Use Case 文件提取：

| UC 元素 | 對應測試 |
|---------|---------|
| 主要流程步驟 | Happy Path E2E 測試 |
| 替代流程 | 異常情境測試 |
| 前提條件 | Test fixture / beforeEach |
| 成功後條件 | Assertion（斷言） |
| 資料欄位 | 表單驗證測試 |
| 使用人角色 | 認證 fixture（不同角色登入） |

### Step 2：分析 Vue 頁面 → Page Object

掃描 `.vue` 檔案，提取頁面元素：

```typescript
// pages/<module>.page.ts
import { type Page, type Locator } from '@playwright/test';

export class <Module>Page {
  readonly page: Page;

  // — 定位器 —
  readonly pageTitle: Locator;
  readonly dataTable: Locator;
  readonly createButton: Locator;
  readonly searchInput: Locator;
  readonly dialog: Locator;
  readonly saveButton: Locator;
  readonly cancelButton: Locator;
  readonly toast: Locator;

  constructor(page: Page) {
    this.page = page;
    this.pageTitle = page.locator('h2, .p-card-title').first();
    this.dataTable = page.locator('.p-datatable');
    this.createButton = page.getByRole('button', { name: '新增' });
    this.searchInput = page.locator('[data-testid="search-input"]');
    this.dialog = page.locator('.p-dialog');
    this.saveButton = page.getByRole('button', { name: '儲存' });
    this.cancelButton = page.getByRole('button', { name: '取消' });
    this.toast = page.locator('.p-toast-message');
  }

  // — 導航 —
  async goto() {
    await this.page.goto('/<route-path>');
  }

  // — 操作 —
  async fillForm(data: Record<string, string>) {
    for (const [field, value] of Object.entries(data)) {
      await this.page.locator(`[data-testid="field-${field}"]`).fill(value);
    }
  }

  async selectDropdown(testId: string, optionText: string) {
    await this.page.locator(`[data-testid="${testId}"]`).click();
    await this.page.locator('.p-select-option').filter({ hasText: optionText }).click();
  }

  async getTableRowCount(): Promise<number> {
    return this.dataTable.locator('tbody tr').count();
  }

  async clickTableRowAction(rowIndex: number, actionName: string) {
    const row = this.dataTable.locator('tbody tr').nth(rowIndex);
    await row.getByRole('button', { name: actionName }).click();
  }

  // — 斷言輔助 —
  async expectToastMessage(text: string) {
    await this.toast.filter({ hasText: text }).waitFor({ state: 'visible' });
  }

  async expectDialogVisible() {
    await this.dialog.waitFor({ state: 'visible' });
  }

  async expectDialogHidden() {
    await this.dialog.waitFor({ state: 'hidden' });
  }
}
```

### Step 3：產生 E2E 測試

每個 Use Case 的主要流程 → 一個 `test.describe` 區塊：

```typescript
// tests/<module>.spec.ts
import { test, expect } from '@playwright/test';
import { <Module>Page } from '../pages/<module>.page';

test.describe('<中文模組名稱>', () => {

  let modulePage: <Module>Page;

  test.beforeEach(async ({ page }) => {
    modulePage = new <Module>Page(page);
    // TODO: 若需登入，加入登入 fixture
    await modulePage.goto();
  });

  // ============================================================
  // UC-001: <使用案例名稱>
  // ============================================================

  test('UC-001: 正常流程 — <主要流程描述>', async ({ page }) => {
    // Step 1: <流程步驟 1>
    await modulePage.createButton.click();
    await modulePage.expectDialogVisible();

    // Step 2: <流程步驟 2 — 填寫表單>
    await modulePage.fillForm({
      '<field1>': '<test_value>',
      '<field2>': '<test_value>',
    });

    // Step 3: <流程步驟 3 — 送出>
    await modulePage.saveButton.click();

    // Assert: <成功後條件>
    await modulePage.expectToastMessage('操作成功');
    await modulePage.expectDialogHidden();
  });

  test('UC-001: 替代流程 — <異常情境>', async ({ page }) => {
    await modulePage.createButton.click();
    await modulePage.expectDialogVisible();

    // 不填必填欄位直接送出
    await modulePage.saveButton.click();

    // Assert: 驗證錯誤訊息
    const errorMsg = page.locator('.p-message-error, .p-invalid');
    await expect(errorMsg).toBeVisible();
  });


  // ============================================================
  // UC-002: <使用案例名稱>
  // ============================================================

  test('UC-002: 正常流程 — <主要流程描述>', async ({ page }) => {
    // ...依 Use Case 主要流程步驟展開
  });

});
```

### Step 4：產生測試 Fixture

```typescript
// fixtures/<module>.fixture.ts
import { test as base } from '@playwright/test';
import { <Module>Page } from '../pages/<module>.page';

type Fixtures = {
  modulePage: <Module>Page;
  authenticatedPage: <Module>Page;
};

export const test = base.extend<Fixtures>({
  modulePage: async ({ page }, use) => {
    const modulePage = new <Module>Page(page);
    await modulePage.goto();
    await use(modulePage);
  },
  authenticatedPage: async ({ page }, use) => {
    // 登入流程
    await page.goto('/login');
    await page.getByLabel('帳號').fill('testuser');
    await page.getByLabel('密碼').fill('testpass');
    await page.getByRole('button', { name: '登入' }).click();
    await page.waitForURL('**/home**');

    const modulePage = new <Module>Page(page);
    await modulePage.goto();
    await use(modulePage);
  },
});
```

### Step 5：產生 / 更新 playwright.config.ts

若不存在，產生標準配置：

```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e/tests',
  outputDir: './e2e/test-results',
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: './e2e/playwright-report' }],
    ['list'],
  ],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
  },
});
```

---

## 測試案例生成規則

### 每個 Use Case 的標準測試矩陣

| # | 測試類型 | 測試名稱格式 | 來源 |
|---|---------|-------------|------|
| 1 | Happy Path | `UC-XXX: 正常流程 — <描述>` | UC 主要流程 |
| 2 | 表單驗證 | `UC-XXX: 必填欄位驗證` | UC 資料欄位（必填） |
| 3 | 異常流程 | `UC-XXX: 替代流程 — <情境>` | UC 替代流程 |
| 4 | 頁面載入 | `頁面正常載入並顯示標題` | 基礎 Smoke Test |
| 5 | DataTable | `列表正確顯示資料` | 有 DataTable 時 |
| 6 | 分頁 | `分頁切換正常` | DataTable 有分頁時 |
| 7 | 搜尋/篩選 | `搜尋條件正確過濾` | 有搜尋功能時 |
| 8 | Dialog CRUD | `新增/編輯/刪除對話框流程` | CRUD 頁面 |
| 9 | 確認刪除 | `刪除確認對話框` | 有刪除功能時 |
| 10 | 權限 | `無權限使用者不可操作` | UC 有角色限制時 |

---

## 輸出路徑

```
e2e/
├── playwright.config.ts
├── pages/
│   └── <module>.page.ts          # Page Object
├── fixtures/
│   └── <module>.fixture.ts       # 測試 Fixture
├── tests/
│   └── <module>.spec.ts          # E2E 測試案例
├── test-results/                  # 測試結果（gitignore）
└── playwright-report/             # HTML 報告（gitignore）
```

---

## 輸出摘要

```
✅ 已產生 Playwright E2E 測試：

📂 Page Object:  e2e/pages/<module>.page.ts
📂 Fixture:      e2e/fixtures/<module>.fixture.ts
📂 Test:         e2e/tests/<module>.spec.ts
📂 Config:       playwright.config.ts（若為首次產生）

📊 測試覆蓋：
   Happy Path    — N 案例（來自 UC 主要流程）
   表單驗證      — N 案例（來自 UC 資料欄位）
   異常流程      — N 案例（來自 UC 替代流程）
   合計          — N 案例

💡 執行測試：
   npx playwright test e2e/tests/<module>.spec.ts
   npx playwright test --ui    # 互動模式
   npx playwright show-report  # 查看 HTML 報告
```

---

## 與其他 Skill 的串接

```
delphi-to-usecase → Use Case 文件
        ↓
delphi-to-vue → Vue 3 頁面
        ↓
playwright-e2e-test-generator → Page Object + E2E 測試  ← 本 Skill
        ↓
test-plan-generator → 完整測試計劃（含 E2E 測試項目）
```
