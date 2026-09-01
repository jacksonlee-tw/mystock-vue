// 產業鏈知識圖譜（docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md）共用視覺常數。
//
// 原本 TIER_LABEL／STATE_LABEL／STATE_COLOR／STATE_BG 只定義在 IndustryChainView.vue 內，
// FR-21（匯出為投資筆記，§4.5／§8）需要在 Mermaid 圖表沿用同一套「節點三態」色票
// （ADR-IC-21：「不重用《AI 報告規格》／本文件 §3.0 的架構圖色票」），抽成共用模組讓
// 力導向圖與匯出的 Mermaid 圖永遠讀同一份定義，不會日後改了一邊、另一邊沒跟著改而顏色兜不起來。
export const TIER_LABEL = { tier2: '上游', tier1: '中游', downstream: '下游龍頭' };
export const STATE_LABEL = { ignited: '已突破', candidate: '低位階候選', dormant: '尚未連動' };
export const STATE_COLOR = { ignited: '#8F6413', candidate: '#B26A00', dormant: '#a8a29a' };
export const STATE_BG = { ignited: '#F8EEDA', candidate: '#FFF3E0', dormant: '#f0efec' };
