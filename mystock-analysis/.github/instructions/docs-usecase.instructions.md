---
applyTo: "docs/01_Requirements/**/*.md"
---

# 使用案例文件規範（自動注入）

本指引在編輯 `docs/01_Requirements/` 下任何需求文件時自動生效。

## 檔案路徑規則

```
docs/01_Requirements/use-cases/<ModuleName>/UC-<ModuleName>-<中文名稱>.md
```

## Use Case 必要欄位

每份 Use Case 必須包含以下區段，缺漏視為不合格：

| 區段 | 必要 | 說明 |
|------|------|------|
| UC 編號 | ✅ | 格式：`UC-<Module>-NNN` |
| UC 名稱 | ✅ | 簡潔描述功能 |
| 參與者（Actor） | ✅ | 操作人員角色 |
| 前置條件 | ✅ | 執行前必須滿足的條件 |
| 後置條件 | ✅ | 成功執行後的系統狀態 |
| 主要流程 | ✅ | 編號步驟（1, 2, 3...） |
| 替代流程 | ✅ | 非正常路徑（A1, A2...） |
| 例外流程 | ✅ | 錯誤處理（E1, E2...） |
| 業務規則 | ⭕ | 如有則列出 |
| UI 需求 | ⭕ | Delphi 表單對應的前端需求 |
| 資料需求 | ⭕ | 相關資料表/欄位 |

## 業務線分類

eCard 系統有 3 條業務線，Use Case 必須標註所屬：

| 業務線 | 代碼 | 說明 |
|--------|------|------|
| 發運 | SD | Sales & Distribution（出廠） |
| 原料 | MM | Materials Management（進廠） |
| 無人值守 | WF | Weighing Fully-automated |

## Mermaid 流程圖

- Use Case 活動圖使用 `flowchart TD`
- 遵守淡色系配色（參見 copilot-instructions.md）
- 換行使用 `<br/>`

## 與 Delphi 原始碼的對應

若 Use Case 來自 Delphi 逆向工程，需標註：
- 原始 Delphi 模組名稱
- 主要表單類別名稱（如 `TfrmManualCard`）
- 對應的 .pas / .dfm 檔案路徑
