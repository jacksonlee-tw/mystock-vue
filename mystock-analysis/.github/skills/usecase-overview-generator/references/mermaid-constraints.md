# Mermaid 11.x 語法限制與 Use Case 模擬指南

## ⚠️ 根本限制

**Mermaid 11.x（含以前所有版本）不支援 UML Use Case 圖型。**

Mermaid 支援的圖型清單（截至 v11.x）：
- `flowchart` / `graph`
- `sequenceDiagram`
- `classDiagram`
- `stateDiagram-v2`
- `erDiagram`
- `gantt`
- `pie`
- `gitGraph`
- `mindmap`
- `timeline`
- `xychart-beta`
- `block-beta`
- `architecture-beta`
- `packet-beta`

**不在清單內** = 不支援。`usecase`、`usecaseDiagram` 均不在清單內。

---

## ❌ 禁止使用的語法（PlantUML 語法，Mermaid 無法解析）

```
' 以下全部錯誤 — 來自 PlantUML，Mermaid 不支援
@startuml
left to right direction
actor "操作員" as OPR
usecase "進廠過磅" as UC1
OPR --> UC1
UC1 ..> UC2 : include
@enduml
```

常見誤用關鍵字清單：

| 關鍵字 | 來源 | Mermaid 支援？ |
|-------|------|-------------|
| `usecase` | PlantUML | ❌ 不支援 |
| `actor` | PlantUML | ❌ 不支援 |
| `left to right direction` | PlantUML | ❌ 不支援 |
| `@startuml` / `@enduml` | PlantUML | ❌ 不支援 |
| `..>` | PlantUML | ❌ 不支援 |
| `as "別名"` | PlantUML | ❌ 不支援（Mermaid 語法不同）|

---

## ✅ 正確替代方案：`flowchart LR`

### 基本結構（完整可用範本）

````mermaid
flowchart LR
    %% ── Step 1: 宣告 Actors（左側，使用 stadium 形狀）──────────
    OPR(["👤 操作員"])
    MGR(["👤 主管"])
    SYS(["⚙️ 系統"])

    %% ── Step 2: Use Cases（依業務領域用 subgraph 分組）──────────
    subgraph GRP1["🏭 核心過磅作業"]
        direction LR
        UC01("進廠過磅 A1")
        UC02("入庫過磅 A2")
        UC03("出廠過磅 B1")
    end

    subgraph GRP2["🔧 系統管理"]
        direction LR
        UC10("系統登入")
        UC11("使用者管理")
    end

    %% ── Step 3: Actor → Use Case 關係（實線箭頭）───────────────
    OPR --> UC01
    OPR --> UC03
    MGR --> UC01

    %% ── Step 4: UC 間關係（虛線 + 標籤）───────────────────────
    UC01 -. "include" .-> UC_SCALE
    UC01 -. "include" .-> UC_CARD
    UC10 -. "extend" .-> UC11
````

---

## 形狀速查表

| 用途 | Mermaid 語法 | 視覺效果 |
|-----|------------|--------|
| **Actor（使用人）** | `ID(["emoji 名稱"])` | 橢圓 / Stadium |
| **Use Case（功能）** | `ID("功能名稱")` | 圓角矩形 |
| **系統邊界** | `subgraph GRP["標題"]` `end` | 有標題的外框 |
| **一般方框** | `ID["標籤"]` | 直角矩形 |
| **菱形（判斷）** | `ID{"判斷"}` | 菱形 |

---

## 關係類型速查表

| 關係語意 | Mermaid 語法 | 說明 |
|---------|------------|-----|
| 一般關係 | `A --> B` | 帶箭頭實線 |
| include（包含） | `A -. "include" .-> B` | 帶標籤虛線箭頭 |
| extend（延伸） | `A -. "extend" .-> B` | 帶標籤虛線箭頭 |
| 無箭頭連線 | `A --- B` | 純連線 |
| 加標籤實線 | `A -- "label" --> B` | 帶標籤實線箭頭 |

**重要**：`-. "label" .->` 語法中：
- `-. ` 是虛線開始（注意有空格）
- `"label"` 是標籤（必須用引號）
- ` .->` 是虛線箭頭結束（注意有空格）

---

## `subgraph` 語法規則

```
subgraph ID["顯示標題"]
    direction LR     %% 可選：指定子圖內部方向
    節點定義...
end                  %% 必須有 end 結尾
```

注意事項：
1. `subgraph` 的 ID（如 `GRP1`）與節點 ID 不可重複
2. `end` 必須在同一縮排層
3. 子圖內的節點定義語法與頂層相同
4. `direction LR` 可在子圖內單獨設定方向（Mermaid 10.4+ 支援）

---

## 完整工作範例（5 Actors, 12 UCs, 2 Groups）

````mermaid
flowchart LR
    OPR(["👤 操作員"])
    MGR(["👤 主管"])
    ADM(["👤 管理員"])
    SYS(["⚙️ 系統"])
    FIN(["👤 計費員"])

    subgraph GRP1["🏭 核心過磅"]
        UC01("進廠過磅")
        UC02("入庫過磅")
        UC03("出廠過磅")
        UC04("出庫過磅")
    end

    subgraph GRP2["🔧 管理功能"]
        UC10("系統登入")
        UC11("使用者管理")
        UC12("參數設定")
        UC13("車輛管理")
    end

    subgraph GRP3["⚙️ 支援模組"]
        UC20("地磅通訊")
        UC21("感應卡讀寫")
        UC22("LED 顯示")
    end

    OPR --> UC01
    OPR --> UC03
    OPR --> UC21
    MGR --> UC01
    MGR --> UC02
    FIN --> UC03
    ADM --> UC10
    ADM --> UC11
    ADM --> UC12
    ADM --> UC13
    SYS --> UC20
    SYS --> UC21
    SYS --> UC22

    UC01 -. "include" .-> UC21
    UC01 -. "include" .-> UC20
    UC03 -. "include" .-> UC21
````

---

## sequenceDiagram（合法，可直接使用）

`sequenceDiagram` 是 Mermaid 的合法語法，用於描述流程時序：

````mermaid
sequenceDiagram
    participant 操作員
    participant 進廠模組
    participant 磅秤
    participant 資料庫

    操作員->>進廠模組: 開啟進廠作業
    進廠模組->>磅秤: 啟動重量讀取
    磅秤-->>進廠模組: 回傳重量
    操作員->>進廠模組: 確認過磅
    進廠模組->>資料庫: 儲存記錄
    資料庫-->>進廠模組: 磅單號碼
    進廠模組-->>操作員: 顯示完成
````

常用語法：
- `A->>B: 訊息` 實線箭頭（帶箭頭）
- `A-->>B: 訊息` 虛線箭頭（回應）
- `A-)B: 訊息` 非同步
- `Note over A,B: 說明` 跨參與者的說明框
- `loop 條件` ... `end` 循環
- `alt 條件` ... `else` ... `end` 條件分支

---

## 驗證清單

生成任何 Mermaid 區塊前，逐一確認：

- [ ] 第一行是 `flowchart LR`（不是其他任何關鍵字）
- [ ] 沒有 `usecase` 關鍵字
- [ ] 沒有 `actor` 關鍵字（flowchart 不認識此關鍵字）
- [ ] Actor ID 使用 `(["..."])` 雙括號格式
- [ ] 每個 `subgraph` 都有對應的 `end`
- [ ] 虛線箭頭格式為 `-. "label" .->`（注意引號和空格）
- [ ] 沒有中文 ID（節點 ID 僅使用英數字和底線）
- [ ] 沒有與 `subgraph` ID 重複的節點 ID
