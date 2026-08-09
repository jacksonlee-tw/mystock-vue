---
name: github-ai-sync
description: >-
  將當前專案 .github 目錄下的 AI 相關資源（agents、hooks、instructions、prompts、skills、
  copilot-instructions.md）同步複製到指定的目標專案 .github 目錄。
  使用者必須提供目標專案的絕對路徑，Skill 才會執行。
  當使用者提到以下任何一項時，務必使用此 Skill：
  同步 agent、同步 skill、複製 .github、同步 AI 設定、
  sync agent、sync skill、copy .github、sync github、
  同步到其他專案、複製 agent 到另一個專案、agent 同步、
  github AI sync、推送 agent 設定、同步 copilot 設定、
  把 agent 複製過去、同步 instructions、sync instructions。
  即使使用者只說「同步到那個專案」、「把 agent 設定複製過去」、
  「幫我同步 .github」，也應觸發此 Skill。
---

# github-ai-sync — .github AI 資源同步工具

## 1. 目的

將當前工作區（來源專案）`.github` 目錄下的 AI Agent 相關資源，一鍵同步複製到使用者指定的**目標專案** `.github` 目錄。確保多個專案之間的 AI 協作設定保持一致。

### 同步範圍

| 資料夾 / 檔案 | 說明 |
|--------------|------|
| `agents/` | Agent 定義檔（`.agent.md`） |
| `hooks/` | Git Hook 設定文件 |
| `instructions/` | Instructions Hook（路徑觸發 SOP） |
| `prompts/` | Prompt Hook（品質檢查提示） |
| `skills/` | Agent Skill 定義與附帶資源 |
| `copilot-instructions.md` | Copilot 全域指令檔 |

---

## 2. 前置條件

執行前**必須**確認以下條件，缺一不可：

| # | 條件 | 驗證方式 |
|---|------|---------|
| 1 | 使用者已提供**目標專案的絕對路徑** | 從使用者訊息中擷取；若未提供，**必須詢問使用者** |
| 2 | 來源 `.github` 目錄存在 | 檢查當前工作區根目錄下是否有 `.github` 資料夾 |
| 3 | 目標專案路徑存在 | 檢查使用者提供的路徑是否為有效目錄 |

> **重要**：若使用者未提供目標專案路徑，**禁止猜測或使用預設值**，必須明確詢問。

---

## 3. 執行流程

### 步驟 1：解析輸入參數

從使用者訊息中擷取目標專案路徑。接受以下格式：
- 絕對路徑：`C:\git_repos\my-project` 或 `/home/user/my-project`
- 帶引號路徑：`"C:\git repos\my project"`

將目標路徑記為 `$TARGET_ROOT`，同步目標為 `$TARGET_ROOT/.github`。

### 步驟 2：驗證來源與目標

使用終端機執行驗證：

```powershell
# Windows
powershell -NoProfile -Command "
  $src = '<來源 .github 路徑>';
  $dst = '<目標 .github 路徑>';
  if (!(Test-Path $src)) { throw 'ERROR: 來源 .github 目錄不存在: ' + $src }
  if (!(Test-Path (Split-Path $dst -Parent))) { throw 'ERROR: 目標專案路徑不存在' }
  Write-Host 'OK: 來源與目標路徑驗證通過'
"
```

若驗證失敗，向使用者回報錯誤並停止執行。

### 步驟 3：執行同步

使用 PowerShell（Windows）或 bash（Linux/macOS）執行複製：

**Windows：**
```powershell
powershell -NoProfile -Command "
  $src = '<來源 .github 絕對路徑>';
  $dst = '<目標 .github 絕對路徑>';
  $folders = @('agents','hooks','instructions','prompts','skills');

  # 確保目標 .github 目錄存在
  if (!(Test-Path $dst)) { New-Item -ItemType Directory -Path $dst | Out-Null }

  # 同步資料夾（遞迴覆蓋）
  foreach (\$f in \$folders) {
    \$s = Join-Path \$src \$f;
    if (Test-Path \$s) {
      Copy-Item -Path \$s -Destination \$dst -Recurse -Force;
      Write-Host ('Synced: ' + \$f)
    } else {
      Write-Host ('Skipped (not found): ' + \$f)
    }
  }

  # 同步 copilot-instructions.md
  \$ci = Join-Path \$src 'copilot-instructions.md';
  if (Test-Path \$ci) {
    Copy-Item -Path \$ci -Destination \$dst -Force;
    Write-Host 'Synced: copilot-instructions.md'
  }

  Write-Host 'Sync complete.'
"
```

**Linux / macOS：**
```bash
SRC="<來源 .github 絕對路徑>"
DST="<目標 .github 絕對路徑>"
mkdir -p "$DST"
for folder in agents hooks instructions prompts skills; do
  if [ -d "$SRC/$folder" ]; then
    cp -r "$SRC/$folder" "$DST/"
    echo "Synced: $folder"
  else
    echo "Skipped (not found): $folder"
  fi
done
if [ -f "$SRC/copilot-instructions.md" ]; then
  cp "$SRC/copilot-instructions.md" "$DST/"
  echo "Synced: copilot-instructions.md"
fi
echo "Sync complete."
```

### 步驟 4：驗證同步結果

同步完成後，統計目標中每個資料夾的檔案數量：

**Windows：**
```powershell
powershell -NoProfile -Command "
  $dst = '<目標 .github 絕對路徑>';
  $items = @('agents','hooks','instructions','prompts','skills','copilot-instructions.md');
  Write-Host '--- Sync Verification ---';
  foreach (\$f in \$items) {
    \$d = Join-Path \$dst \$f;
    if (Test-Path \$d) {
      if ((Get-Item \$d).PSIsContainer) {
        \$c = (Get-ChildItem \$d -Recurse -File | Measure-Object).Count;
        Write-Host ('{0}: {1} files' -f \$f, \$c)
      } else {
        Write-Host ('{0}: OK' -f \$f)
      }
    } else {
      Write-Host ('{0}: MISSING' -f \$f)
    }
  }
"
```

### 步驟 5：輸出結果摘要

以 Markdown 表格向使用者回報同步結果：

```markdown
| 項目 | 狀態 | 檔案數 |
|------|------|--------|
| agents/ | ✅ 已同步 | N files |
| hooks/ | ✅ 已同步 | N files |
| instructions/ | ✅ 已同步 | N files |
| prompts/ | ✅ 已同步 | N files |
| skills/ | ✅ 已同步 | N files |
| copilot-instructions.md | ✅ 已同步 | — |
```

---

## 4. 錯誤處理

| 錯誤情境 | 處理方式 |
|---------|---------|
| 使用者未提供目標路徑 | 詢問：「請提供目標專案的絕對路徑，例如 `C:\git_repos\my-project`」 |
| 目標專案路徑不存在 | 回報錯誤：「目標路徑不存在，請確認路徑是否正確」 |
| 來源 `.github` 不存在 | 回報錯誤：「當前工作區未找到 `.github` 目錄」 |
| 部分資料夾不存在 | 跳過該資料夾，在結果中標記為「⏭️ 略過（來源不存在）」 |
| 權限不足 | 回報錯誤並建議以管理員身分重試 |

---

## 5. 注意事項

- 此操作為**覆蓋式同步**（目標中同名檔案會被來源覆蓋）
- 不會刪除目標中來源沒有的檔案（只新增/更新，不刪除）
- `copilot-instructions.md` 內容可能包含專案特定資訊，同步後使用者可能需要手動調整
- 若目標專案的 `.github` 目錄不存在，會自動建立
