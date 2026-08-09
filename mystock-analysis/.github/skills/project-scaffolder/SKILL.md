---
name: project-scaffolder
description: >-
  從 tcci-vue-template 範本專案生成新的 Vue 3 + PrimeVue 4 前端專案雛型。
  將範本檔案複製到指定目標目錄，並依新專案名稱客製化設定（package.json、標題、路由、選單等），
  最後安裝相依套件並驗證可成功編譯執行。
  當使用者提到以下任何一項時，務必使用此 Skill：
  新專案建立、專案初始化、從範本產生專案、scaffold、產生雛型系統、
  建立新系統、複製模板到新目錄、開新專案、系統雛型。
  即使使用者只說「幫我開一個新專案」或「用模板建新的」，也應觸發此 Skill。
---

# 專案雛型產生器

從 **tcci-vue-template** 範本專案，在指定目標目錄生成一個可執行的新 Vue 3 + PrimeVue 4 前端專案雛型。

---

## 1. 前置條件

執行此 Skill 前，確認以下環境已就緒：

- **Node.js** ≥ 18（含 npm）
- **tcci-vue-template** 範本專案位於 `C:\git_repos\tcci-vue-template`（或工作區根目錄）
- 使用者已指定**目標目錄**（**必填**，無預設值。若使用者未提供，必須停止並詢問）
- 使用者已指定**專案標題**（**必填**，無預設值。若使用者未提供，必須停止並詢問）
- 使用者已提供**新專案名稱**（若未提供，從目標目錄路徑推斷，例如 `mmsystem`）

---

## 2. 執行流程

依下列步驟依序執行。每步驟完成後在 todo list 標記完成。

### 步驟 1：確認參數

向使用者確認或從對話推斷以下資訊：

| 參數 | 說明 | 預設值 |
|------|------|--------|
| `TEMPLATE_DIR` | 範本專案路徑 | `C:\git_repos\tcci-vue-template` |
| `TARGET_DIR` | 新專案輸出目錄 | **必填，無預設值** |
| `PROJECT_NAME` | 新專案名稱（用於 package.json name 欄位） | 從目標路徑推斷 |
| `PROJECT_TITLE` | 瀏覽器頁籤標題 | **必填，無預設值** |
| `BASE_PATH` | Vite base 路徑（若部署在子路徑下） | `/` |

> **⚠️ `TARGET_DIR` 與 `PROJECT_TITLE` 為必填參數。** 若使用者未指定目標目錄或專案標題，必須停止流程並明確詢問使用者，不可自行假設或使用預設值。

其餘參數若使用者未明確給出，用合理預設值填入，並在開始前告知使用者最終使用的參數。

### 步驟 2：建立目標目錄並複製範本

1. 若目標目錄不存在，建立之。
2. 從範本專案複製以下檔案與目錄到目標：

```
必須複製的項目：
├── index.html
├── package.json
├── package-lock.json          （⚠️ 必須複製，確保相依套件版本鎖定）
├── vite.config.mjs
├── tailwind.config.js
├── postcss.config.js
├── jsconfig.json
├── public/                    （整個目錄）
└── src/
    ├── App.vue
    ├── main.js
    ├── assets/                （整個目錄）
    ├── components/            （整個目錄）
    ├── layout/                （整個目錄）
    ├── router/index.js
    ├── service/               （整個目錄）
    └── views/                 （整個目錄）
```

**不複製的項目（明確排除）：**
- `node_modules/`
- `dist/`
- `.git/`
- `.github/`
- `docs/`
- `CHANGELOG.md`、`LICENSE.md`、`README.md`
- `vercel.json`
- `.eslintrc.*`、`.prettierrc.*`（除非使用者要求）
- `AppMenu copy.vue`（備份檔不複製）

> **`package-lock.json` 必須複製**，不可排除。

使用終端機的 `robocopy`（Windows）或 `cp -r`（Unix）執行複製。範例：

```bash
# Windows
robocopy "C:\git_repos\tcci-vue-template" "TARGET_DIR" /E /XD node_modules dist .git .github docs /XF "CHANGELOG.md" "LICENSE.md" "README.md" "vercel.json" "AppMenu copy.vue"
```

### 步驟 3：客製化專案設定

依序修改目標目錄中的以下檔案：

#### 3.1 package.json
- `name` → `PROJECT_NAME`（小寫 kebab-case）
- `version` → `"0.1.0"`
- ⚠️ **`dependencies` 與 `devDependencies` 的版本號碼一律不可修改**，保持與範本完全一致，確保與 `package-lock.json` 對齊，避免 `npm ci` 版本衝突

#### 3.2 index.html
- `<title>` → `PROJECT_TITLE`

#### 3.3 vite.config.mjs
- 若 `BASE_PATH` 不為 `/`，加入 `base: 'BASE_PATH'`
- 其餘保持不變

#### 3.4 src/router/index.js
- **保留範本中所有路由**，不刪除任何路由（含 uikit 展示路由、pages 路由）
- 路由結構維持與範本完全一致，方便開發者參考 UI 元件範例

#### 3.5 src/layout/AppMenu.vue
- **保留範本中所有選單項目**，不刪除任何群組（含 UI Components、Pages、Hierarchy 等）
- 選單結構維持與範本完全一致，方便開發者瀏覽所有展示頁面

#### 3.6 src/layout/AppTopbar.vue
- 將顯示文字中的「台泥資訊系統」或模板名稱替換為 `PROJECT_TITLE`

#### 3.7 保留範例檔案
- **保留** `views/uikit/` 所有 UI 展示頁面
- **保留** `views/` 下所有範例頁面（Template、Dashboard、CustomerManagement 等）
- **保留** `components/dashboard/`、`components/landing/` 目錄
- **保留** `components/FloatingConfigurator.vue`
- **保留** `service/` 下所有範例 service 檔案（CustomerService、ProductService 等）
- 這些範例檔案可供開發者參考 PrimeVue 元件用法與架構模式，待實際開發時再自行移除

### 步驟 4：安裝相依套件

使用 `npm ci` 而非 `npm install`，以確保完全依照 `package-lock.json` 安裝，不會因 `^` semver 解析到更新版本：

```bash
cd TARGET_DIR
npm ci
```

> **為何用 `npm ci`：** 範本 `package.json` 中 `primevue`、`@primeuix/themes` 等套件使用 `^` 版本前綴（如 `^4.3.1`），直接執行 `npm install` 可能解析到更新的 minor/patch 版本，導致 API 不相容錯誤。`npm ci` 嚴格依照 `package-lock.json` 安裝，保證與範本測試環境一致。

### 步驟 5：驗證可編譯

```bash
cd TARGET_DIR
npm run build
```

確認 build 無錯誤。若有錯誤，逐一修正直到 build 通過。

### 步驟 6：啟動開發伺服器驗證可執行

```bash
cd TARGET_DIR
npm run dev
```

以背景模式啟動，確認伺服器成功啟動（出現 `Local: http://localhost:xxxx`）。啟動成功後告知使用者可在瀏覽器開啟確認。

---

## 3. 驗證清單

完成所有步驟後，逐項確認：

- [ ] 目標目錄包含完整的專案結構
- [ ] `package-lock.json` 已從範本複製（確保版本鎖定）
- [ ] `package.json` 的 `name` 已更新為新專案名稱、`dependencies` 版本號未更動
- [ ] `index.html` 的 `<title>` 已更新
- [ ] 路由、選單、uikit 展示頁、範例 service 皆完整保留
- [ ] `npm run build` 零錯誤通過
- [ ] `npm run dev` 可成功啟動開發伺服器
- [ ] 瀏覽器可正常開啟首頁

---

## 4. 常見問題處理

### PrimeVue 版本不相容（啟動後出現元件或 config 錯誤）
**症狀：** `primevue.config` 為 `undefined`、spinner/icon 元件載入失敗、`main.js` 連鎖報錯。  
**原因：** `npm install` 未照 `package-lock.json` 安裝，解析到不相容版本（例如 primevue@3.50+ 已改用獨立 SVG icon 元件架構）。  
**解法：**
1. 刪除目標目錄的 `node_modules/`
2. 確認 `package-lock.json` 已從範本複製過來
3. 改用 `npm ci` 重新安裝
```bash
Remove-Item -Recurse -Force node_modules   # Windows PowerShell
npm ci
```

### ⚠️ HTML CDN 原型頁面：PrimeVue CDN 版本必須固定為 3.15.0

當任務涉及產生**獨立 HTML 原型頁面**（如需求文件用的可操作 mockup、`docs/html/` 下的靜態頁面），透過 CDN（unpkg / jsdelivr）引用 PrimeVue 時，版本選擇至關重要：

| 版本 | 狀況 | 可用？ |
|------|------|--------|
| primevue@3（最新，3.50+） | icon 元件 + style 模組完全分離，需 30+ 個額外 CDN 腳本 | ❌ |
| primevue@3.40.x | icon 已獨立為 `icons/spinner/spinner.min.js` 等，仍需額外載入 | ❌ |
| **primevue@3.15.0** | icon 以 CSS `pi pi-*` 類別內嵌，UMD CDN **自包含**，無需額外腳本 | ✅ **正確版本** |

> **根本原因：** PrimeVue 在 **3.18.0（2022年7月）** 引入 SVG icon 元件系統，將所有圖示從 CSS class 改為獨立元件。3.15.0 是該變更前**最後的穩定版**，所有 icon 仍嵌入各元件 `.min.js` 中，UMD CDN 完全自包含。

**✅ 正確的 HTML CDN 樣板（必須嚴格使用此版本）：**

```html
<!-- Vue 3 -->
<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
<!-- PrimeVue 3.15.0（⚠️ 固定此版本，勿使用最新版）-->
<script src="https://unpkg.com/primevue@3.15.0/core/core.min.js"></script>
<script src="https://unpkg.com/primevue@3.15.0/button/button.min.js"></script>
<!-- ... 其他所需元件 -->
<!-- PrimeIcons CSS -->
<link rel="stylesheet" href="https://unpkg.com/primeicons/primeicons.css" />
<!-- PrimeVue 主題 CSS（如 lara-light-blue）-->
<link rel="stylesheet" href="https://unpkg.com/primevue@3.15.0/resources/themes/lara-light-blue/theme.css" />
<link rel="stylesheet" href="https://unpkg.com/primevue@3.15.0/resources/primevue.min.css" />
```

**❌ 禁止使用的寫法：**
```html
<!-- 以下任一寫法均會導致 icon 元件載入失敗 -->
<script src="https://unpkg.com/primevue/core/core.min.js"></script>       <!-- 最新版 -->
<script src="https://unpkg.com/primevue@latest/..."></script>
<script src="https://unpkg.com/primevue@3.40.0/..."></script>
```

### 埠號衝突
**原因：** 5173 埠已被佔用。
**解法：** 使用 `npx vite --port 5174` 或修改 `vite.config.mjs` 的 `server.port`。

---

## 5. 後續擴充建議

雛型產生完成後，提醒使用者可依需求：

1. **安裝 axios：** `npm install axios`，並建立 `src/config/axiosConfig.js`
2. **安裝 Pinia：** `npm install pinia`，並建立 `src/stores/` 目錄
3. **新增頁面：** 依照 `primevue3-development` Skill 的規範新增 View + 路由 + 選單
4. **調整主題色：** 修改 `src/assets/layout/variables/_common.scss`
5. **初始化 Git：** `git init && git add . && git commit -m "init: scaffold from tcci-vue-template"`

---

## 6. 範例 Prompt

在 VS Code Copilot Chat（Agent 模式）輸入以下 prompt 即可觸發此 Skill：

```
從 tcci-vue-template 產生新系統雛型：

目標目錄：C:\git_repos\mmsystem\docs\01_Requirements\html
專案標題：MM 物料管理系統
專案名稱：mmsystem
```
