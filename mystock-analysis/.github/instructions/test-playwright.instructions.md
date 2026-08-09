---
applyTo: "frontend/tests/**/*.spec.{js,ts}"
---

# Playwright E2E 測試規範（自動注入）

本指引在編輯 Playwright 測試檔案時自動生效。

## 架構模式（Page Object Model）

```
tests/
├── e2e/
│   ├── pages/                    # Page Objects
│   │   ├── BasePage.js           # 共用方法（login、navigate、waitForApi）
│   │   ├── ManualCardPage.js     # 模組專屬 Page Object
│   │   └── WeighingPage.js
│   ├── specs/                    # 測試規格
│   │   ├── manual-card.spec.js
│   │   └── weighing.spec.js
│   └── fixtures/                 # 測試資料
│       └── test-data.json
```

## PrimeVue 4 選擇器策略

PrimeVue 元件在 DOM 中會自動生成結構，使用以下策略定位元素：

| PrimeVue 元件 | 推薦選擇器 | 範例 |
|--------------|-----------|------|
| Button | `data-testid` 或 `.p-button` + label | `page.getByTestId('btn-save')` |
| InputText | `data-testid` 或 label 關聯 | `page.getByLabel('車號')` |
| Dropdown | `.p-select` → `.p-select-option` | 先 click trigger，再選 option |
| DataTable | `.p-datatable` → `.p-datatable-tbody tr` | `page.locator('.p-datatable-tbody tr')` |
| Dialog | `.p-dialog` | `page.locator('.p-dialog')` |
| Toast | `.p-toast-message` | `page.locator('.p-toast-message')` |
| Calendar | `.p-datepicker` | 使用 `fill()` 直接輸入日期 |

## 測試範本

```javascript
import { test, expect } from '@playwright/test';
import { ManualCardPage } from '../pages/ManualCardPage';

test.describe('人工制卡流程', () => {
    let page;
    let manualCardPage;

    test.beforeEach(async ({ browser }) => {
        page = await browser.newPage();
        manualCardPage = new ManualCardPage(page);
        await manualCardPage.navigate();
        await manualCardPage.login('operator', 'password');
    });

    test('正常制卡流程', async () => {
        // Arrange
        const cardData = { vehicleNo: '粵A12345', driverName: '張三' };

        // Act
        await manualCardPage.fillCardForm(cardData);
        await manualCardPage.submitForm();

        // Assert
        await expect(manualCardPage.successToast).toBeVisible();
        await expect(manualCardPage.cardTable).toContainText('粵A12345');
    });

    test.afterEach(async () => {
        await page.close();
    });
});
```

## Page Object 規範

```javascript
export class ManualCardPage {
    constructor(page) {
        this.page = page;
        // Locators — 集中定義
        this.vehicleInput = page.getByLabel('車號');
        this.driverInput = page.getByLabel('司機');
        this.submitBtn = page.getByTestId('btn-submit');
        this.cardTable = page.locator('.p-datatable-tbody');
        this.successToast = page.locator('.p-toast-message-success');
    }

    async navigate() {
        await this.page.goto('/manual-card');
    }

    async fillCardForm(data) {
        await this.vehicleInput.fill(data.vehicleNo);
        await this.driverInput.fill(data.driverName);
    }

    async submitForm() {
        await this.submitBtn.click();
        await this.page.waitForResponse('**/api/v1/cards');
    }
}
```

## 必要等待策略

- API 回應：`page.waitForResponse(urlPattern)`
- Toast 顯示：`expect(toast).toBeVisible({ timeout: 5000 })`
- Dialog 關閉：`expect(dialog).not.toBeVisible()`
- DataTable 載入：`expect(row).toHaveCount(expectedCount)`
- 禁止使用 `page.waitForTimeout()` 硬等待
