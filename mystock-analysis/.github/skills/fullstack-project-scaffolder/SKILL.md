---
name: fullstack-project-scaffolder
description: >-
  從當前專案架構產生新的 Python FastAPI + Vue 3 PrimeVue 全端專案（含 AI Agent 設定、
  後端 Clean Architecture、前端 UI 框架、文件結構），不包含 Delphi 相關內容。
  使用者必須提供目標資料夾絕對路徑，Skill 才會執行。
  當使用者提到以下任何一項時，務必使用此 Skill：
  建立全端專案、全端 scaffold、新系統架構、FastAPI Vue 新專案、
  複製專案架構、產生新專案模板、fullstack scaffold、
  建立 FastAPI PrimeVue 專案、複製架構到新資料夾、
  開新的全端系統、從模板建新專案、新建後端前端專案、
  clone architecture、scaffold fullstack project。
  即使使用者只說「幫我建一個新系統」、「開新專案架構」、
  「把架構複製到新資料夾」，也應觸發此 Skill。
---

# fullstack-project-scaffolder — 全端專案架構產生器

## 1. 目的

從當前工作區（來源專案）複製 **Python FastAPI 後端 + Vue 3 PrimeVue 前端 + AI Agent 設定 + 文件結構** 到使用者指定的目標資料夾，產生一個可直接開發的全端專案骨架。

### 複製範圍總覽

| 分類 | 來源路徑 | 說明 |
|------|---------|------|
| AI Agent | `.github/` | agents、skills、instructions、prompts、hooks、copilot-instructions.md |
| 後端架構 | `backend/` | Clean Architecture 分層（core/domain/infrastructure/services/api/schemas/db/tests） |
| 前端架構 | `frontend/` | Vue 3 + PrimeVue 3 + Vite（完整 src/ 結構） |
| 進入點 | `main.py` | FastAPI 應用程式入口 |
| 套件清單 | `requirements.txt` | Python 後端相依套件 |
| 國際化 | `locales/` | zh-TW.json、zh-CN.json |
| 文件結構 | `docs/` | 標準文件目錄骨架（排除 Delphi 與專案特定內容） |

### 明確排除項目（Delphi 相關 & 專案特定）

| 排除項目 | 原因 |
|---------|------|
| `eCard/`、`ecardsystem/`、`COMMON/` | Delphi 原始碼 |
| `prototype-ecardsystem/` | 舊版前端原型 |
| `poc/` | 設備 POC 測試 |
| `.github/skills/delphi-to-usecase/` | Delphi 專用 Skill |
| `.github/skills/delphi-to-vue/` | Delphi 專用 Skill |
| `.github/skills/delphi-to-python-driver/` | Delphi 專用 Skill |
| `.github/skills/fr3-to-reportlab/` | FastReport 專用 Skill |
| `.github/instructions/delphi-source.instructions.md` | Delphi 分析指引 |
| `docs/00_Project_Overview/UC-Delphi-對照表.md` | Delphi 對照表 |
| `docs/02_Design/A.arrivePlant/` | 專案特定設計 |
| `docs/02_Design/python-dll/` | 專案特定 DLL 設計 |
| `docs/02_Design/ai-agent/ecard-*` | eCard 專案專用 AI 文件 |
| `docs/02_Design/backend架構評估報告-*.md` | 專案特定評估 |
| `docs/02_Design/設備串接開發指引.md` | 專案特定設備文件 |
| `docs/03_Development/A.arrivePlant/` | 專案特定開發文件 |
| `backend/devices/` | 專案特定設備驅動 |
| `build/`、`dist/`、`__pycache__/`、`node_modules/` | 建置產物 |
| `.git/` | 版本控制 |
| `$null`、`*.spec`、`test_*.py`（根目錄） | 專案特定測試 / 建置 |
| `static/` | 前端建置輸出 |
| `政俯平台/`、`相关硬件文档/` | 政府平台 & 硬體文件 |

---

## 2. 前置條件

執行前**必須**確認以下條件：

| # | 條件 | 驗證方式 |
|---|------|---------|
| 1 | 使用者已提供**目標資料夾的絕對路徑** (`TARGET_DIR`) | 從訊息擷取；未提供則**必須詢問** |
| 2 | 使用者已提供**專案名稱** (`PROJECT_NAME`) | 用於 package.json、FastAPI title；未提供則從 TARGET_DIR 推斷 |
| 3 | 使用者已提供**專案標題** (`PROJECT_TITLE`) | 用於瀏覽器 title、FastAPI title；未提供則**必須詢問** |
| 4 | 來源工作區根目錄包含 `backend/`、`frontend/`、`.github/` | 自動檢查 |
| 5 | **Python ≥ 3.10** 與 **Node.js ≥ 18** 已安裝 | `python --version` / `node --version` |

> **重要**：`TARGET_DIR` 與 `PROJECT_TITLE` 為必填參數，禁止猜測或使用預設值。

---

## 3. 執行流程

### 步驟 1：確認參數

向使用者確認以下資訊：

| 參數 | 說明 | 預設值 |
|------|------|--------|
| `SOURCE_DIR` | 來源專案根目錄 | 當前工作區根目錄 |
| `TARGET_DIR` | 目標資料夾（絕對路徑） | **必填** |
| `PROJECT_NAME` | 專案名稱（kebab-case） | 從 TARGET_DIR 推斷 |
| `PROJECT_TITLE` | 專案中文標題 | **必填** |
| `DB_DRIVER` | 資料庫驅動 (`pyodbc` / `asyncpg` / `aiomysql`) | `pyodbc` |

---

### 步驟 2：建立目標目錄結構

```powershell
# 建立主要目錄
New-Item -ItemType Directory -Path "$TARGET_DIR" -Force | Out-Null
```

---

### 步驟 3：複製 .github AI Agent 設定

使用 PowerShell，**逐項排除** Delphi 相關 Skill 與 Instruction：

```powershell
$src = "$SOURCE_DIR\.github"
$dst = "$TARGET_DIR\.github"

# 3.1 整個目錄複製（agents、hooks、prompts）
foreach ($f in @('agents','hooks','prompts')) {
    $s = Join-Path $src $f
    if (Test-Path $s) {
        Copy-Item -Path $s -Destination $dst -Recurse -Force
        Write-Host "Synced: $f"
    }
}

# 3.2 instructions — 排除 delphi-source.instructions.md
$instrSrc = Join-Path $src 'instructions'
$instrDst = Join-Path $dst 'instructions'
New-Item -ItemType Directory -Path $instrDst -Force | Out-Null
Get-ChildItem $instrSrc -File | Where-Object { $_.Name -ne 'delphi-source.instructions.md' } | ForEach-Object {
    Copy-Item $_.FullName -Destination $instrDst -Force
    Write-Host "Synced instruction: $($_.Name)"
}

# 3.3 skills — 排除 Delphi 相關 skill 目錄
$skillSrc = Join-Path $src 'skills'
$skillDst = Join-Path $dst 'skills'
$excludeSkills = @('delphi-to-usecase','delphi-to-vue','delphi-to-python-driver','fr3-to-reportlab')
New-Item -ItemType Directory -Path $skillDst -Force | Out-Null
Get-ChildItem $skillSrc -Directory | Where-Object { $excludeSkills -notcontains $_.Name } | ForEach-Object {
    Copy-Item $_.FullName -Destination $skillDst -Recurse -Force
    Write-Host "Synced skill: $($_.Name)"
}

# 3.4 copilot-instructions.md
Copy-Item (Join-Path $src 'copilot-instructions.md') -Destination $dst -Force
Write-Host "Synced: copilot-instructions.md"
```

---

### 步驟 4：複製後端架構

```powershell
$backSrc = "$SOURCE_DIR\backend"
$backDst = "$TARGET_DIR\backend"

# 使用 robocopy 排除 __pycache__、devices 目錄
robocopy "$backSrc" "$backDst" /E /XD __pycache__ devices /XF "*.pyc"
```

同時複製根目錄檔案：

```powershell
# main.py、requirements.txt、locales/
Copy-Item "$SOURCE_DIR\main.py" "$TARGET_DIR\" -Force
Copy-Item "$SOURCE_DIR\requirements.txt" "$TARGET_DIR\" -Force
if (Test-Path "$SOURCE_DIR\requirements-dev.txt") {
    Copy-Item "$SOURCE_DIR\requirements-dev.txt" "$TARGET_DIR\" -Force
}
Copy-Item "$SOURCE_DIR\locales" "$TARGET_DIR\" -Recurse -Force
```

---

### 步驟 5：複製前端架構

```powershell
$frontSrc = "$SOURCE_DIR\frontend"
$frontDst = "$TARGET_DIR\frontend"

# 排除 node_modules、dist、build、.env 檔案
robocopy "$frontSrc" "$frontDst" /E /XD node_modules dist build /XF ".env" ".env.*"
```

> **⚠️ 若來源有 `package-lock.json`，必須一併複製**（確保版本鎖定）。

---

### 步驟 6：複製文件結構（docs）

只複製通用文件骨架，排除專案特定內容：

```powershell
$docsDst = "$TARGET_DIR\docs"

# 6.1 建立標準文件目錄結構
$docFolders = @(
    '00_Project_Overview',
    '01_Requirements\use-cases',
    '02_Design\api',
    '02_Design\db',
    '03_Development',
    '04_Tests',
    '11_Standards_and_Templates\Standards',
    '11_Standards_and_Templates\templates\document-templates',
    '11_Standards_and_Templates\templates\prompt-templates'
)
foreach ($d in $docFolders) {
    New-Item -ItemType Directory -Path (Join-Path $docsDst $d) -Force | Out-Null
}

# 6.2 複製通用文件（排除 eCard/Delphi 專案特定文件）
# 複製 Standards
$stdSrc = "$SOURCE_DIR\docs\11_Standards_and_Templates\Standards"
if (Test-Path $stdSrc) {
    Copy-Item "$stdSrc\*" "$docsDst\11_Standards_and_Templates\Standards\" -Recurse -Force
}

# 複製 document-templates
$tmplSrc = "$SOURCE_DIR\docs\11_Standards_and_Templates\templates\document-templates"
if (Test-Path $tmplSrc) {
    Copy-Item "$tmplSrc\*" "$docsDst\11_Standards_and_Templates\templates\document-templates\" -Recurse -Force
}

# 複製 prompt-templates
$ptSrc = "$SOURCE_DIR\docs\11_Standards_and_Templates\templates\prompt-templates"
if (Test-Path $ptSrc) {
    Copy-Item "$ptSrc\*" "$docsDst\11_Standards_and_Templates\templates\prompt-templates\" -Recurse -Force
}

# 6.3 複製通用設計文件（排除 A.arrivePlant、python-dll、ecard-* 等）
$designSrc = "$SOURCE_DIR\docs\02_Design"
$designDst = "$docsDst\02_Design"
$designExclude = @('A.arrivePlant','python-dll','ai-agent')
Get-ChildItem $designSrc -File | Where-Object {
    $_.Name -notmatch '架構評估報告' -and $_.Name -ne '設備串接開發指引.md'
} | ForEach-Object {
    Copy-Item $_.FullName -Destination $designDst -Force
}

# 複製保留 02_Design 子目錄（排除專案特定的）
Get-ChildItem $designSrc -Directory | Where-Object {
    $designExclude -notcontains $_.Name
} | ForEach-Object {
    Copy-Item $_.FullName -Destination $designDst -Recurse -Force
}
```

---

### 步驟 7：客製化專案設定

#### 7.1 frontend/package.json
- `"name"` → `PROJECT_NAME`（kebab-case）
- `"version"` → `"0.1.0"`
- **不可修改** `dependencies` 與 `devDependencies` 版本號碼

#### 7.2 frontend/index.html
- `<title>` → `PROJECT_TITLE`

#### 7.3 main.py
- `app = FastAPI(title="...")` → `app = FastAPI(title="PROJECT_TITLE")`

#### 7.4 .github/copilot-instructions.md
在 copilot-instructions.md 開頭修改專案概述段落：
- 將 eCard 相關描述替換為新專案名稱與簡述
- 移除 Delphi 相關技術棧段落
- 移除 Delphi 子系統目錄結構段落
- 更新 Skill 清單（移除 Delphi 相關 Skill：S1 delphi-to-usecase、S9 delphi-to-vue、S12 delphi-to-python-driver、S13 fr3-to-reportlab）
- 移除 H10 delphi-source.instructions.md Hook
- 更新目錄結構為新專案的結構

> **⚠️ copilot-instructions.md 修改量較大，建議使用檔案編輯工具逐段修改，而非手動全文替換。**

#### 7.5 建立 README.md

在 `$TARGET_DIR/README.md` 建立基本說明文件：

```markdown
# PROJECT_TITLE

## 技術棧

### 後端
- Python 3.10+
- FastAPI
- SQLAlchemy 2.0
- Pydantic v2
- Dishka（依賴注入）

### 前端
- Vue 3
- PrimeVue 3
- Vite 5
- Axios

## 快速開始

### 後端
\```bash
pip install -r requirements.txt
python main.py
\```

### 前端
\```bash
cd frontend
npm ci
npm run dev
\```

## 目錄結構
\```
├── .github/           # AI Agent 設定（agents, skills, instructions）
├── backend/           # FastAPI 後端（Clean Architecture）
│   ├── api/v1/        # API 端點（Presentation Layer）
│   ├── core/          # 橫切關注（config, DI, exception, i18n）
│   ├── db/            # 資料庫連線管理
│   ├── domain/        # 領域層（entities, ports, value_objects）
│   ├── infrastructure/# 基礎設施層（SQL/Memory repository）
│   ├── schemas/       # Pydantic DTO
│   ├── services/      # 應用邏輯層
│   └── tests/         # 單元測試
├── frontend/          # Vue 3 + PrimeVue 前端
│   └── src/
├── docs/              # 文件
├── locales/           # 國際化語系檔
├── main.py            # FastAPI 入口
└── requirements.txt   # Python 相依套件
\```
```

#### 7.6 建立 .gitignore

在 `$TARGET_DIR/.gitignore` 建立：

```
__pycache__/
*.pyc
*.pyo
.env
.venv/
venv/
node_modules/
dist/
build/
*.egg-info/
.idea/
.vscode/
*.spec
$null
```

---

### 步驟 8：安裝相依套件與驗證

#### 8.1 後端驗證

```bash
cd $TARGET_DIR
pip install -r requirements.txt
python -c "from backend.core.config import HOST, PORT; print(f'Config OK: {HOST}:{PORT}')"
```

#### 8.2 前端安裝

```bash
cd $TARGET_DIR/frontend
npm ci        # 若有 package-lock.json
# 或
npm install   # 若無 package-lock.json
```

#### 8.3 前端建置驗證

```bash
cd $TARGET_DIR/frontend
npm run build
```

確認 build 零錯誤。若有錯誤，逐一修正。

#### 8.4 啟動開發伺服器（選擇性）

```bash
# 後端
cd $TARGET_DIR
python main.py

# 前端（另一終端）
cd $TARGET_DIR/frontend
npm run dev
```

---

### 步驟 9：輸出結果摘要

以 Markdown 表格向使用者回報：

```markdown
## 專案建立完成

| 分類 | 狀態 | 說明 |
|------|------|------|
| .github/agents/ | ✅ | N 個 Agent 定義檔 |
| .github/skills/ | ✅ | N 個 Skill（已排除 Delphi 相關） |
| .github/instructions/ | ✅ | N 個 Instruction Hook |
| .github/prompts/ | ✅ | N 個 Prompt Hook |
| .github/copilot-instructions.md | ✅ | 已客製化 |
| backend/ | ✅ | Clean Architecture 完整結構 |
| frontend/ | ✅ | Vue 3 + PrimeVue + Vite |
| docs/ | ✅ | 標準文件目錄骨架 + 範本 |
| locales/ | ✅ | zh-TW / zh-CN |
| main.py | ✅ | FastAPI 入口（已更新標題） |
| requirements.txt | ✅ | Python 相依套件 |
| README.md | ✅ | 專案說明（已建立） |
| .gitignore | ✅ | Git 忽略規則（已建立） |
| npm ci | ✅ / ❌ | 前端套件安裝 |
| npm run build | ✅ / ❌ | 前端建置驗證 |
```

---

## 4. 錯誤處理

| 錯誤情境 | 處理方式 |
|---------|---------|
| 使用者未提供 TARGET_DIR | 詢問：「請提供目標資料夾的絕對路徑，例如 `C:\git_repos\my-new-project`」 |
| 使用者未提供 PROJECT_TITLE | 詢問：「請提供新專案的中文標題」 |
| 目標路徑已存在且有內容 | 警告使用者同名檔案會被覆蓋，請求確認後繼續 |
| 來源目錄缺少必要結構 | 回報遺失的目錄，提示可能工作區不正確 |
| npm ci 失敗 | 改用 `npm install`；若仍失敗，檢查 Node.js 版本 |
| pip install 失敗 | 檢查 Python 版本；排除可能的套件衝突 |
| 權限不足 | 回報錯誤並建議以管理員身分重試 |

---

## 5. 注意事項

- 此操作為**覆蓋式複製**（目標中同名檔案會被覆蓋）
- `copilot-instructions.md` 複製後需要手動調整專案概述段落（Skill 會盡量自動替換，但建議複查）
- `backend/` 中的業務邏輯程式碼（services/、api/v1/endpoints/）為**範例參考**，新專案應根據需求重寫
- `frontend/src/views/` 與 `components/` 中的頁面為**範例參考**，新專案應根據需求重寫
- **不包含** `backend/devices/` — 若新專案需要設備驅動，可另外使用 `delphi-to-python-driver` Skill 或手動建立
- Agent 定義檔中引用 Delphi 相關描述的部分，複製後可能需要手動移除
