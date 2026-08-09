# Vibe coding - Agile 經典 Prompt

以下針對「開發公司用 web 系統」且團隊內有 PM、UI/UX 設計、前後端工程、測試人員的情境，說明如何應用 Vibe Coding + Agile，並分為兩大部分實用工具：

## 1. PM 專用經典 Prompt —— 具體使用建議與範例輸出格式

（這是針對前面 Agile PM prompt 補充）

| 編號 | Prompt 範例 | 使用建議 | 範例輸出格式 |
| --- | --- | --- | --- |
| 1 | 你是一位有 5 年經驗的 Agile PM，根據這個產品 Backlog 幫我安排下個 Sprint 任務與優先順序。 | 先將 Backlog 條列貼給 AI，請其分 Sprint 並排序 | 功能管理（優先1）用戶登入（優先2） |
| 2 | 幫我製作軟體開發 6 週甘特圖，包含里程碑、任務分配、截止日。 | 輸入里程碑與團隊名單，AI 幫你時程與分工 | 週1-2：需求分析—林經理週3-6：開發—陳工程師 |
| 3 | 幫忙定義本團隊每日 15 分 stand-up 議程與提醒重點。 | 說明團隊組成，AI 自動產生會議議程與重點 | 昨天完成今日計劃遇到問題 |
| 4 | 幫我擬定本專案風險管理計劃，包含風險、影響、應對策略。 | 可要求 AI 輸出風險分類、衝擊、解決方法，適合作為 Sprint Review 輸出 | 需求變動：高衝擊，方案—加強溝通 |
| 5 | 依據團隊進展製作 Sprint 進度報告，列明完成、阻礙、待解決問題。 | 給 AI 最近進展，請其統整重點，利於進度回報 | 完成：登入頁阻礙：API 延遲 |
| 6 | 幫忙將這些 Epic 拆成 User Stories，並依價值及依賴順序列出。 | 輸入 Epic 給 AI，請其協助拆解、排序 | User Story 1（高價值） |
| 7 | 根據以下 User Story，產生測試案例與驗收標準。 | 輸入 User Story，AI 自動產生 QA 可用的案例與驗收點 | 測試案例：A 項流程驗收標準：XXX |
| 8 | 請列出這次迭代流程改進點與具體優化方法。 | Sprint 回顧時，請 AI 自動彙整改進點，供團隊會議討論 | 每日同步待強化—建議固定時段 |
| 9 | 幫我擬信給利益關係人，摘要當前進展、風險和下一步計劃。 | 指定成果讓 AI 產生簡潔專案信，用於外部溝通 | 標準郵件格式含進度內容、下一步、客套語 |
| 10 | 依現有資源與期限，模擬不同任務排序完成時間並建議最佳方案。嗓 | 提供人員、工時、任務，AI 會排程並建議順序 | 方案1：優先做A，預估2週 |

## 2. 表格：10個經典 Agile Prompt 給 UI/UX 設計人員（適用 Vibe Coding 流程）

| 編號 | Prompt 範例 | 用途說明 |
| --- | --- | --- |
| 1 | 「根據下列需求，幫我設計一個現代感強烈的登入頁介面，並產生互動原型（含動畫效果）。」 | 互動原型&潮流設計快速產生 |
| 2 | 「請根據這份 wireframe 製作對應的 React/Vue 前端程式碼，並配合設計稿調整配色與字距。」 | 將設計稿自動轉碼為前端 UI |
| 3 | 「請產生可復用的按鈕元件（有三種尺寸、四組顏色、包含 loading 狀態），需求如以下所述：」 | 元件庫設計/情境模組化 |
| 4 | 「幫我優化這個頁面的視覺層次，讓主要 CTA 更突出，用戶流程更直觀。」 | AI 自動建議與優化 UI/UX |
| 5 | 「依據這些用戶回饋，產生一組介面調整建議，並修正原型細節：」 | 用戶測試/回饋快速整合進設計優化 |
| 6 | 「幫我把這組設計稿內容整合成響應式 web layout，適配手機與電腦。」 | 響應式設計自動化轉換 |
| 7 | 「根據下列交互需求，自動加入動畫效果並輸出對應前端程式碼。」 | 互動設計/動畫自動生成 |
| 8 | 「幫我分析這兩版 wireframe 的優劣，並建議最符合使用者體驗的解法。」 | A/B 設計比較，產生 UX 改進策略 |
| 9 | 「這個主流程有哪幾個阻斷點，請依據設計原則建議改善方法，並直接修改 wireframe。」 | User Flow 痛點偵測與 wireframe 優化自動化 |
| 10 | 「根據這段描述幫我產生一套 UI style guide，附顏色、字型與元件變化範例。」 | Style Guide 生成，確保前後端一致 |

### 補充建議

- PM、設計師可根據真實團隊背景/需求，細化 prompt 或要求 Markdown、表格式等標準輸出。
- UI/UX 設計人員通常搭配 Figma、Sketch、Adobe XD 輸入資源，AI 能協助轉碼、優化與說明。
- 像元件、流程、使用者故事等資料詳細描述，會大幅提升 AI Vibe Coding 產出品質。

這樣您的團隊，無論在管理還是前端設計流程，都能真正落實「以語言溝通即能驅動系統開發」！

以下表格結合專案經理給出的 User Stories 概念，提供給 UI/UX 設計人員在 Agile 開發中利用 Vibe Coding 的10個經典 Prompt 範例。這些 Prompt 用來讓 AI 根據 User Story 產出設計與互動方案，促進設計快速落地並且精準對焦用戶價值。

| 編號 | Prompt 範例 | 用途說明 |
| --- | --- | --- |
| 1 | 「根據這個 User Story：‘As a [用戶], I want to [目標行為], so that [達成理由]’，幫我設計主要畫面介面與互動流程。」 | 從 User Story 快速產生整體介面設計與用戶流程 |
| 2 | 「請根據這則 User Story，產生一個可操作的互動原型，包括關鍵按鈕動作與頁面轉場效果。」 | 直接輸出互動式原型加速驗證設計想法 |
| 3 | 「針對 User Story 的目標行為，設計三種不同風格的 UI 元件選項並說明優缺點。」 | 多方案 UI 元件快速產生與比較，利於團隊決策 |
| 4 | 「將這段 User Story 對應的使用者痛點轉化為設計改進建議，並產出調整後的 wireframe。」 | 根據用戶需求設計優化建議，並用視覺稿實作 |
| 5 | 「針對此 User Story 設計響應式網頁版面，確保手機與桌面都有良好使用體驗。」 | 自動生成響應式設計方案，涵蓋不同裝置尺寸 |
| 6 | 「請基於這條 User Story，自動產生介面交互動畫描述與對應的簡單前端程式碼範例。」 | 豐富設計體驗的動畫細節與程式輔助，方便開發接手 |
| 7 | 「依據 User Story，幫我列出主要使用流程的痛點，並提出可行的用戶體驗優化方案。」 | 找出流程瓶頸並自動生成 UX 改善策略 |
| 8 | 「根據多個 User Stories，幫我統整風格指導手冊（Style Guide），包含顏色、字型與元件使用規範。」 | 彙整設計一致性與規範，便於團隊共享 |
| 9 | 「請生成以這個 User Story 為背景的用戶測試指引與邀請語，方便收集目標用戶的實測反饋。」 | 制定針對性用戶測試腳本與溝通用語 |
| 10 | 「根據此 User Story，設計一段引導式教學流程文字與介面，幫助新用戶快速上手主要功能。」 | 提供用戶教育與啟動流程的設計方案 |

這些 Prompt 都以「User Story」為核心，利用 Vibe Coding 助力 UI/UX 設計師將用戶需求快速轉化為實際的視覺與交互成果，貼近 Agile 團隊迭代步調，並提升設計與開發的同步效率。

如需，我可幫您示範更具體的 prompt 寫法範例或針對特定 User Story 產出實際示範內容。

來源
[1] 20 User story examples and best practices [https://www.justinmind.com/blog/examples-user-story-best-practices/](https://www.justinmind.com/blog/examples-user-story-best-practices/)
[2] The Ultimate Guide to UX User Stories [With Examples] [https://careerfoundry.com/en/blog/ux-design/ultimate-guide-ux-user-stories/](https://careerfoundry.com/en/blog/ux-design/ultimate-guide-ux-user-stories/)
[3] 18 ChatGPT Prompts for UX Designers [https://www.looppanel.com/blog/chatgpt-prompts-for-ux-designers](https://www.looppanel.com/blog/chatgpt-prompts-for-ux-designers)
[4] User Stories | Examples and Template [https://www.atlassian.com/agile/project-management/user-stories](https://www.atlassian.com/agile/project-management/user-stories)
[5] 18 AI Prompts to Write User Stories and Acceptance Criteria [https://www.faqprime.com/en/18-ai-prompts-to-write-user-stories-and-acceptance-criteria/](https://www.faqprime.com/en/18-ai-prompts-to-write-user-stories-and-acceptance-criteria/)
[6] Top 30 ChatGPT Prompts for UX Designers [https://www.mockplus.com/blog/post/chatgpt-prompts-for-ux-design](https://www.mockplus.com/blog/post/chatgpt-prompts-for-ux-design)
[7] User Stories: As a [UX Designer] I want to [embrace Agile] ... [https://www.interaction-design.org/literature/article/user-stories-as-a-ux-designer-i-want-to-embrace-agile-so-that-i-can-make-my-projects-user-centered](https://www.interaction-design.org/literature/article/user-stories-as-a-ux-designer-i-want-to-embrace-agile-so-that-i-can-make-my-projects-user-centered)
[8] User Story Template With Examples [https://uxmag.com/articles/user-story-template-with-examples](https://uxmag.com/articles/user-story-template-with-examples)