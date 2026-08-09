---
applyTo: "docs/02_Design/**/*.md"
---

# 設計文件規範（自動注入）

本指引在編輯 `docs/02_Design/` 下任何設計文件時自動生效。

## Mermaid 圖表規範（強制）

1. **使用淡色系配色**（pastel）— 禁止深色或高飽和度

   | 語意 | fill | stroke |
   |------|------|--------|
   | 起始/終止 | `#f3e5f5` | `#7b1fa2` |
   | 輸入/需求 | `#e3f2fd` | `#1565c0` |
   | 設計/分析 | `#fff9c4` | `#f9a825` |
   | 開發/實作 | `#e8f5e9` | `#2e7d32` |
   | 測試/驗證 | `#fce4ec` | `#c62828` |
   | 工具/服務 | `#e0f7fa` | `#00838f` |

2. **語法規則**：
   - 使用 `flowchart TD/LR`，禁止舊版 `graph TD/LR`
   - 換行一律用 `<br/>`，禁止 `\n`
   - 每行一個節點宣告
   - 含空格/中文的標籤必須用雙引號包覆
   - 節點 ID 只能使用字母、數字、底線（無 `-` 或 `:`）

3. **ERD 圖表**：
   - 使用 `erDiagram` 類型
   - 表名使用 UPPER_SNAKE_CASE
   - 標註外鍵關係與基數

## 設計文件結構

```markdown
# SD-<Module>-系統設計

## 1. 功能說明
## 2. 資料表明細（引用 DB 規格書）
## 3. ER Diagram（Mermaid erDiagram）
## 4. API 端點摘要（引用 API 規格書）
## 5. 相關 Delphi 程式清單
## 6. 關鍵 SQL 語句
## 7. 備註
```

## 交叉引用規則

- 設計文件引用 DB 規格書：`[DB 規格書](../db/ecard-<module>-db規格書.md)`
- 設計文件引用 API 規格書：`[API 規格書](../api/ecard-<module>-API規格書.md)`
- 表名/欄位名使用 backtick 包覆：`WEIGHING_RECORD.VEHICLE_NO`
