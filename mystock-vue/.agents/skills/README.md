# Agent Skills 清單

本目錄收錄依開發階段整理的工程工作流程技能（skills）。每個技能都是一份 `SKILL.md`，
描述何時使用、遵循的流程與驗證方式。開始進行非小型任務前，先確認是否有對應技能可套用；
不確定該用哪個時，優先閱讀 [using-agent-skills](./using-agent-skills/SKILL.md)（meta-skill）。

| 技能 | 說明 |
|---|---|
| [using-agent-skills](./using-agent-skills/SKILL.md) | 探索並選用合適技能的 meta-skill；開始任務或不確定該套用哪個技能時優先參考。 |
| [interview-me](./interview-me/SKILL.md) | 需求不明確時，透過一次一題的訪談釐清使用者真正想要的目標，再進入規劃或撰碼。 |
| [idea-refine](./idea-refine/SKILL.md) | 以發散/收斂思考將模糊構想精煉為明確可執行的方案，或在承諾方案前先壓力測試假設。 |
| [spec-driven-development](./spec-driven-development/SKILL.md) | 開始新功能或重大變更、尚無規格書時，先寫規格與驗收標準再寫程式。 |
| [constraint-driven-development](./constraint-driven-development/SKILL.md) | 將專案品質門檻（覆蓋率、效能、無障礙等）寫成 CONSTRAINTS.md 契約，並監控是否被悄悄降低。 |
| [planning-and-task-breakdown](./planning-and-task-breakdown/SKILL.md) | 已有規格時，將工作拆解成有順序、可驗證的任務清單。 |
| [incremental-implementation](./incremental-implementation/SKILL.md) | 以薄且可驗證的切片漸進交付變更，避免一次寫太多程式碼。 |
| [context-engineering](./context-engineering/SKILL.md) | 在新 session 開始、切換任務或輸出品質下降時，優化 agent 的上下文設定。 |
| [source-driven-development](./source-driven-development/SKILL.md) | 實作前先以官方文件驗證作法，確保程式碼有來源依據、不使用過時寫法。 |
| [doubt-driven-development](./doubt-driven-development/SKILL.md) | 對每個非小型決策進行「全新上下文」的對抗式審查，適用高風險、不熟悉或不可逆的變更。 |
| [frontend-ui-engineering](./frontend-ui-engineering/SKILL.md) | 建置具生產品質、無障礙、響應式的使用者介面（元件、頁面、版面配置）。 |
| [api-and-interface-design](./api-and-interface-design/SKILL.md) | 設計穩定的 API 與介面邊界，包含 REST/GraphQL 端點與模組間的型別契約。 |
| [test-driven-development](./test-driven-development/SKILL.md) | 以紅-綠-重構循環驅動開發：先寫失敗測試，再讓它通過。 |
| [browser-testing-with-devtools](./browser-testing-with-devtools/SKILL.md) | 透過 Chrome DevTools MCP 在真實瀏覽器中驗證前端行為、除錯與效能分析。 |
| [debugging-and-error-recovery](./debugging-and-error-recovery/SKILL.md) | 測試失敗、建置中斷或行為與預期不符時，系統性地找出並修復根本原因。 |
| [code-review-and-quality](./code-review-and-quality/SKILL.md) | 在合併變更前，從多個面向進行程式碼審查。 |
| [code-simplification](./code-simplification/SKILL.md) | 在不改變行為的前提下，簡化已變得過度複雜的程式碼。 |
| [security-and-hardening](./security-and-hardening/SKILL.md) | 依 OWASP Top 10 強化程式碼，處理使用者輸入、驗證、機密資料與第三方整合的安全性。 |
| [performance-optimization](./performance-optimization/SKILL.md) | 針對前端、後端、查詢與資料庫進行效能優化，先量測再優化。 |
| [git-workflow-and-versioning](./git-workflow-and-versioning/SKILL.md) | 規範 git 工作流程：commit、分支、衝突解決、PR、發版與變更日誌。 |
| [ci-cd-and-automation](./ci-cd-and-automation/SKILL.md) | 建立或調整 CI/CD 流水線，自動化品質關卡與部署策略。 |
| [deprecation-and-migration](./deprecation-and-migration/SKILL.md) | 安全地淘汰舊系統/API/功能，或遷移使用者與資料庫結構（expand/contract）。 |
| [documentation-and-adrs](./documentation-and-adrs/SKILL.md) | 記錄架構決策（ADR）與設計理由，尤其是變更公開 API 或發佈功能時。 |
| [observability-and-instrumentation](./observability-and-instrumentation/SKILL.md) | 為程式加入日誌、指標、追蹤與告警，確保上線後行為可觀測、可診斷。 |
| [shipping-and-launch](./shipping-and-launch/SKILL.md) | 準備正式上線：上線前檢查清單、監控設置、分階段發布與回滾計畫。 |

## 使用方式

- 每個技能資料夾底下的 `SKILL.md` 是唯一必要檔案，內含觸發時機與步驟。
- 對應的 slash command 定義在 [.github/prompts/](../../.github/prompts/)，可用 `/<skill-name>` 直接呼叫。
- 專案層級的技能總覽與挑選規則見根目錄 [.github/copilot-instructions.md](../../.github/copilot-instructions.md)。
