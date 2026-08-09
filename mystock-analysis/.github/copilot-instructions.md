# Copilot Instructions

## 專案概述
**MyStock 選股分析系統** — 以 Python FastAPI 為後端、Vue 3 + PrimeVue 為前端的全端股票選股分析平台。

---

## 目錄結構

```
mystock-analysis/
├── .github/                    # AI Agent 設定（agents, skills, instructions, prompts）
├── backend/                    # FastAPI 後端（Clean Architecture + DDD）
│   ├── api/v1/endpoints/       # API 端點（Presentation Layer）
│   ├── core/                   # 橫切關注（config, DI container, exception, i18n）
│   ├── db/                     # 資料庫連線管理
│   ├── domain/                 # 領域層（entities, ports, value_objects）
│   ├── infrastructure/         # 基礎設施層（SQL/Memory repository）
│   ├── schemas/                # Pydantic DTO（Request / Response）
│   ├── services/               # 應用邏輯層（Use Case 函式）
│   └── tests/                  # 單元測試（零 DB 依賴）
├── frontend/                   # Vue 3 + PrimeVue 前端
│   └── src/
│       ├── views/              # 頁面元件
│       ├── components/         # 可重用元件
│       ├── composables/        # Vue Composables（業務邏輯 Hook）
│       ├── services/           # API 呼叫層（axios）
│       ├── layout/             # 版面元件（AppLayout, AppMenu, AppSidebar）
│       ├── router/             # Vue Router 設定
│       └── config/             # 環境設定（axios, env）
├── docs/                       # 文件
│   ├── 00_Project_Overview/    # 專案總覽
│   ├── 01_Requirements/        # 需求文件
│   │   └── use-cases/          # 使用案例
│   ├── 02_Design/              # 系統設計（API 規格、DB 規格）
│   ├── 03_Development/         # 開發文件
│   ├── 04_Tests/               # 測試文件
│   └── 11_Standards_and_Templates/ # 文件規範與範本
├── locales/                    # 國際化語系（zh-TW / zh-CN）
├── main.py                     # FastAPI 應用程式入口
└── requirements.txt            # Python 相依套件
```

---

## 技術棧

### 主程式（Delphi 桌面應用）
| 技術 | 版本 | 說明 |
|------|------|------|
| Delphi | 7 / 10.x（Alexandria） | 主要開發語言（Object Pascal） |
| VCL | — | Windows 桌面 UI 框架 |
| FastReport / FR3 | — | 報表列印元件（`.fr3` 報表檔） |
| Indy TIdHTTPServer | — | HTTP API 伺服器（Webservices 模組） |

#### 主要外部 DLL / OCX
| 檔案 | 說明 |
|------|------|
| `CRT571DLL.pas`（介面宣告） | CRT571/CRT591 發卡機驅動 |
| `LEDDLL.pas`（介面宣告） | LED 顯示屏驅動 |
| `hc_icrf32.dll` / `hc_icrf64.dll` | YKS IC 卡讀卡器（32/64 位元） |
| `mwrf32.dll` | MH IC 卡讀卡器 |
| `PReadcardDll.dll` | 感應卡讀取 |
| `pTpSend.dll` | YX-TPS LED 資訊傳送 |
| `midas.dll` | Borland DataSnap 資料存取 |
| `MSCOMM32.OCX` | Microsoft Comm Control（串列埠通訊） |
| `SpeechLib_TLB.pas` | Microsoft Speech SDK 5（TTS 語音播報） |

#### SmartCardSDMM 額外子專案 DLL
| DLL | 說明 |
|-----|------|
| `TccfzDll.dll` | 無人值守外部介面 |
| `Tccmainput.dll` | 手寫輸入 |
| `TccSign.dll` | 電子簽名 |
| `TccfzCrpDll.dll` | 加密 |

---

### COMMON 共用單元（`COMMON/`）
| 檔案 | 說明 |
|------|------|
| `CardRW.pas` | IC 感應卡讀寫（被幾乎所有模組引用） |
| `UScale.pas` | 地磅（磅秤）通訊介面（RS-232 / TCP，14+ 種協定） |
| `TccUtils.pas` | 通用工具函式 |
| `UAutoUpdate.pas` | 程式自動更新 |
| `TccMD5.pas` | MD5 雜湊 |
| `TccDES.pas` / `TccCrypt.pas` | DES 加解密 |
| `TccMail.pas` | 郵件發送 |
| `NetFunc.pas` | 網路功能（TCP 連線） |
| `TccPreview.pas` | 列印預覽 |
| `Hashtable.pas` | 雜湊表 |
| `HZPY.pas` | 中文轉拼音 |

> **注意**：SmartCard 系列（SDMM/SF/WF）各自在 `Command/` 子目錄維護本地副本；`AutoStartSvc` 在 `Common/` 子目錄維護獨立副本，不使用頂層 `COMMON/`。SmartCardMM 與 SmartCardSD 已合併至 SmartCardSDMM。

---

### 各子系統主要 Delphi 結構
SmartCard 系列（SDMM/SF/WF）共用相同的子目錄結構：

| 子目錄 | 說明 |
|--------|------|
| `System/` | 系統主表單（uMain、uLogin、ufrmCallUp、ufrmMCardDo 等） |
| `Command/` | 共用單元本地副本（CardRW、UScale、TccUtils、uSpvoices 等） |
| `DM/` | 資料模組（DataMod.pas / .dfm） |
| `Reports/` | FastReport 報表檔（DN.fr3、DR.fr3、QS.fr3 等） |
| `MsComm/` | MSCOMM32.OCX 串列埠元件 |
| `Microsoft Speech SDK 5/` | TTS 語音 SDK |

---

### 核心 Web 服務（Webservices）
`eCard/Webservices/TCCWebServer.dpr` — Windows Service，以 Indy HTTP Server 提供後端 API：

| 執行緒 | API 功能 |
|--------|---------|
| `SDCrtDNThread` | 發運制卡（SDCardmake） |
| `CrtDRThread` | 發運過磅（CrtDR） |
| `MMInscaleThread` / `MMOutscaleThread` | 原料進磅/出磅 |
| `GetLineupcarThread` / `CHKLNThread` | 車輛排隊與叫號 |
| `WriteA2B2Thread` | 寫入 A2/B2 磅值 |
| `QBLThread` / `QBSThread` | 查詢排隊佇列/磅秤狀態 |
| 其他 | SFIThread、SPIThread、HasOrderhread、GetOrdLotThread、CHKCarLNThread |

---

## 設定檔
| INI 檔案 | 位置 | 用途 |
|---------|------|------|
| `kamacfg.ini` | `eCard/Webservices/`、`SmartCardSDMM/TDll/` | 核心系統參數、資料庫連線 |
| `rfcardcfg.ini` | `eCard/Webservices/` | IC 卡讀卡器廠牌、COM 埠、TCP 位址 |
| `kamaCfg.ini` | `eCard/AutoStartSvc/` | 監控服務名稱、輪詢間隔 |
| `config.ini` | `eCard/SmartCardSDMM/webs/` | 無人值守 Web Service 設定 |

---

## 前端 UI 原型（prototype-ecardsystem）

### 技術棧
| 分類 | 套件 / 版本 |
|------|-----------|
| 前端框架 | Vue 3（`^3.4`） |
| 建置工具 | Vite 5（`^5.3`） |
| UI 元件庫 | PrimeVue 4（`^4.3`）+ PrimeIcons 7 |
| 主題引擎 | `@primeuix/themes` Aura Preset（支援深色模式） |
| 樣式 | Tailwind CSS 3（`^3.4`）+ `tailwindcss-primeui` |
| 預處理器 | Sass + PostCSS + Autoprefixer |
| 路由 | Vue Router 4（`^4.4`） |
| 圖表 | Chart.js 3.3 |
| 程式碼品質 | ESLint + Prettier |

### 啟動方式
```bash
cd prototype-ecardsystem
npm install
npm run dev      # 開發模式：http://localhost:5173
npm run build    # 生產建置 → dist/
npm run preview  # 預覽建置結果：http://localhost:4173
npm run lint     # 程式碼檢查與修復
```

### 主要頁面（路由）
| 路徑 | 元件 | 說明 |
|------|------|------|
| `/` | `Template.vue` | 首頁 / 版型範本 |
| `/home-dashboard` | `HomeDashboard.vue` | 主儀表板 |
| `/dashboard` | `Dashboard.vue` | 圖表範例儀表板 |
| `/customer` | `CustomerManagement.vue` | 客戶管理 |
| `/user-management` | `UserManagement.vue` | 使用者管理 |
| `/questionnaire-management` | `QuestionnaireManagement.vue` | 問卷管理 |
| `/questionnaire-setting` | `QuestionnaireSetting.vue` | 問卷設定 |
| `/questionnaire` | `Questionnaire.vue` | 問卷表格 |
| `/questionnaire-fill` | `QuestionnaireFill.vue` | 問卷填寫 |

### 架構重點
- 路徑別名：`@` → `src/`
- PrimeVue 元件透過 `unplugin-vue-components` + `PrimeVueResolver` 自動按需引入
- 全域預先註冊：`Button`、`Card`、`Tag`、`DataTable`、`Column`、`Tabs`、`TabList`、`Tab`、`TabPanel`、`TabPanels`
- 深色模式：在 `<html>` 加入 `app-dark` class 啟用
- 靜態測試資料：`public/demo/data/`（JSON），由 `src/service/` 以 `fetch` 讀取
- 客製樣式入口：`src/assets/project-style.css`

---

## 文件結構（docs/）
| 路徑 | 說明 |
|------|------|
| `docs/00_Project_Overview/UC-Delphi-對照表.md` | UC 代號 A~X 與 Delphi 原始碼完整對照（5 大區塊） |
| `docs/01_Requirements/use-cases/UC-00-使用案例總覽.md` | 全系統 76 個使用案例總覽（含 Mermaid 圖） |
| `docs/01_Requirements/use-cases/{模組名稱}/使用案例.md` | 各模組個別使用案例（24 個模組） |
| `docs/11_Standards_and_Templates/` | 文件規範與 Markdown 範本 |

---

## AI Agent / Skill / Hook 清單

### Agent（代理人）× 6

| # | Agent 名稱 | 檔案位置 | SDLC 階段 | 編排的 Skill |
|---|-----------|---------|-----------|-------------|
| A0 | **@開發協調官-orchestrator** | `.github/agents/開發協調官-orchestrator.agent.md` | 全流程編排 | 協調 A1~A5 依序執行，含品質關卡 |
| A1 | **@需求文件代理** | `.github/agents/需求文件代理.agent.md` | 需求收集 | delphi-to-usecase, usecase-overview-generator |
| A2 | **@系統設計代理** | `.github/agents/系統設計代理.agent.md` | 系統設計 | usecase-to-design, db-spec-generator, api-spec-generator |
| A3 | **@後端開發代理-FastApi** | `.github/agents/後端開發代理-FastApi.agent.md` | 開發（後端） | fastapi-development, db-to-sqlalchemy-generator, api-to-fastapi-scaffold, delphi-to-python-driver, fr3-to-reportlab |
| A4 | **@前端開發代理-PrimeVue4** | `.github/agents/前端開發代理-PrimeVue4.agent.md` | 開發（前端） | primevue3-development, delphi-to-vue, project-scaffolder |
| A5 | **@系統測試代理** | `.github/agents/系統測試代理.agent.md` | 測試 | test-plan-generator, api-integration-test-generator, playwright-e2e-test-generator |

> **流水線執行順序**：`@開發協調官-orchestrator` → A1 需求 → A2 設計 → A3 後端 / A4 前端（可並行）→ A5 測試 → git-workflow 推送

### Skill（技能）× 21

| # | Skill 名稱 | SDLC 階段 | 觸發詞範例 |
|---|-----------|-----------|----------|
| S1 | `delphi-to-usecase` | 需求 | 「產生使用案例」「分析 Delphi」 |
| S2 | `usecase-overview-generator` | 需求 | 「更新 UC 總覽」「UC-00」 |
| S3 | `usecase-to-design` | 設計 | 「產生設計文件」「use case 轉設計」 |
| S4 | `db-spec-generator` | 設計 | 「產生 DB 規格書」「資料庫設計」 |
| S5 | `api-spec-generator` | 設計 | 「產生 API 規格書」「API 設計」 |
| S6 | `fastapi-development` | 開發 | 「寫後端」「FastAPI 開發」 |
| S7 | `db-to-sqlalchemy-generator` | 開發 | 「產生 SQLAlchemy Model」 |
| S8 | `api-to-fastapi-scaffold` | 開發 | 「產生 FastAPI 框架」「API 轉程式碼」 |
| S9 | `delphi-to-vue` | 開發 | 「Delphi 轉 Vue」「轉成網頁」 |
| S10 | `primevue3-development` | 開發 | 「Vue 前端開發」「加一個頁面」 |
| S11 | `project-scaffolder` | 開發 | 「建新專案」「初始化專案」 |
| S12 | `delphi-to-python-driver` | 開發 | 「DLL 轉 Python」「設備驅動」 |
| S13 | `fr3-to-reportlab` | 開發 | 「fr3 轉換」「報表轉 PDF」 |
| S14 | `skill-creator` | 工具 | 「建立 Skill」「新增技能」 |
| S15 | `api-integration-test-generator` | 測試 | 「產生 API 測試」「pytest 測試」 |
| S16 | `playwright-e2e-test-generator` | 測試 | 「產生 E2E 測試」「Playwright」 |
| S17 | `test-plan-generator` | 測試 | 「產生測試計劃」「QA 文件」 |
| S18 | `project-management-generator` | 管理 | 「產生甘特圖」「專案計劃」 |
| S19 | `git-workflow` | 部署 | 「push 到 git」「上傳到 GitLab」 |
| S20 | `mermaid-diagram-fixer` | 工具 | 「修 Mermaid」「圖表錯誤」 |
| S21 | `fullstack-project-scaffolder` | 工具 | 「建立全端專案」「複製架構」「開新系統」 |

### Instructions Hook（路徑觸發 SOP）× 10

| # | 檔案 | `applyTo` 模式 | 用途 |
|---|------|---------------|------|
| H1 | `backend-python.instructions.md` | `backend/**/*.py` | FastAPI 架構分層規範 |
| H2 | `frontend-vue.instructions.md` | `prototype-ecardsystem/src/**/*.{vue,js}` | Vue 3 + PrimeVue 4 規範 |
| H3 | `test-python.instructions.md` | `backend/tests/**/*.py` | pytest AAA 模式 |
| H4 | `test-playwright.instructions.md` | `frontend/tests/**/*.spec.{js,ts}` | Playwright POM 模式 |
| H5 | `docs-design.instructions.md` | `docs/02_Design/**/*.md` | Mermaid 淡色系配色 |
| H6 | `docs-usecase.instructions.md` | `docs/01_Requirements/**/*.md` | Use Case 範本格式 |
| H7 | `sqlalchemy-model.instructions.md` | `backend/app/models/**/*.py` | SQLAlchemy 2.0 Mapped 規範 |
| H8 | `pydantic-schema.instructions.md` | `backend/app/schemas/**/*.py` | Pydantic v2 ConfigDict 規範 |
| H9 | `api-spec.instructions.md` | `docs/02_Design/api/**/*.md` | RESTful 命名與錯誤碼規範 |
| H10 | `delphi-source.instructions.md` | `eCard/**/*.pas` | Delphi 分析指引 |

### Prompt Hook（Agent 銜接品質檢查）× 5

| # | 檔案 | 觸發時機 | 檢查內容 |
|---|------|---------|--------|
| W1 | `design-completeness-check.prompt.md` | @系統設計代理 完成後 | DB ↔ API 欄位一致性 |
| W2 | `code-spec-sync-check.prompt.md` | @後端開發代理-FastApi 完成後 | Router ↔ API 規格同步 |
| W3 | `frontend-api-contract-check.prompt.md` | @前端開發代理-PrimeVue4 完成後 | Service URL ↔ API 規格同步 |
| W4 | `test-coverage-matrix.prompt.md` | @系統測試代理 完成後 | UC 場景測試覆蓋度 |
| W5 | `migration-checklist.prompt.md` | git push 前 | 模組遷移 17 項產出物完整性 |

### Git Hook（Husky 自動化檢查）× 3

| Hook | 觸發時機 | 檢查內容 |
|------|---------|--------|
| `pre-commit` | `git commit` 前 | ESLint + Prettier / Ruff + Black |
| `commit-msg` | commit message 輸入後 | Conventional Commit 格式驗證 |
| `pre-push` | `git push` 前 | pytest + npm build 編譯驗證 |

---

## 注意事項
- `.pas` 為 Object Pascal 原始碼，`.dfm` 為對應的表單設計檔（二進位或文字格式）
- `.dpr` 為 Delphi 專案主檔，`.dproj` 為 MSBuild 專案檔（Delphi 2007+）
- 修改表單時，`.pas` 與 `.dfm` 必須同步維護
- `SmartCardSDMM` 為功能最完整的合併版本，包含十餘個子專案（無人值守、電子簽名、COM 介面等）
- 所有前端終端均透過 `Webservices/TCCWebServer` HTTP API 存取資料庫（SQL Server）
- 前端原型 `prototype-ecardsystem` 需 Node.js ≥ 18

---

## Mermaid 圖表規範（全域強制）

所有 UML 圖、流程圖（含 Use Case、系統設計、Agent 流程）**必須**遵守以下規範：

1. **使用淡色系配色**（pastel）— 禁止深色或高飽和度
   | 語意 | fill | stroke |
   |------|------|--------|
   | 起始 / 終止 | `#f3e5f5` | `#7b1fa2` |
   | 輸入 / 需求 | `#e3f2fd` | `#1565c0` |
   | 設計 / 分析 | `#fff9c4` | `#f9a825` |
   | 開發 / 實作 | `#e8f5e9` | `#2e7d32` |
   | 測試 / 驗證 | `#fce4ec` | `#c62828` |
   | 工具 / 服務 | `#e0f7fa` | `#00838f` |
   | 部署 / 管理 | `#c8e6c9` | `#2e7d32` |

2. **換行符號**：標籤內換行一律用 `<br/>`，禁止使用 `\n`
3. **每行一個節點**：同一行不可放置多個節點宣告
4. **含空格 / 中文的標籤**：必須用雙引號包覆（subgraph 標題、邊線標籤同規則）
5. **圖表類型**：使用 `flowchart TD/LR`，禁止舊版 `graph TD/LR`
6. **節點 ID**：只能使用字母、數字、底線，不含 `-` 或 `:`

> 發生 Mermaid 語法錯誤時，請使用 `mermaid-diagram-fixer` Skill 修復。
