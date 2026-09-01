// FR-21：匯出為投資筆記（docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §4.5、§8，v2.6 新增）。
//
// 純函式模組：只吃 IndustryChainView.vue 已經有的 graphData／radarItems／chain 資料，組出
// Markdown（表格＋Mermaid 圖），不呼叫任何 API——三個匯出範圍最終都是把組好的字串交給
// ExportToNoteDialog.vue，由它呼叫既有 investmentNoteApi.createNote()（ADR-IC-20：不新增
// 後端端點、不擴充 investment_note 的 schema）。
import { STATE_COLOR, STATE_BG, STATE_LABEL, TIER_LABEL } from '@/utils/industryChainVisuals';
import { buildNodeSubgraph } from '@/utils/industryChainGraph';

const CONFIDENCE_LABEL = { high: '高', medium: '中', low: '低' };

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

// Mermaid 節點 id 不保證能安全處理數字開頭或代號中的符號（美股偶有 BRK.B 這類代碼），
// 一律加前綴＋替換非英數字元，避免語法錯誤。
function mermaidNodeId(symbol) {
  return `n_${String(symbol).replace(/[^a-zA-Z0-9]/g, '_')}`;
}

// 節點標籤與邊標籤都可能包含雙引號（例如公司全名帶「」以外的引號），Mermaid 的 [".."] 標籤
// 語法不支援跳脫雙引號，直接置換成單引號比處理跳脫規則安全；同時砍掉換行避免整個節點錯位。
// 邊標籤（-->|text|）語法本身不加引號，字面上的 "|" 會被解析成標籤提前結束，一併置換掉。
function escapeMermaidLabel(text) {
  return String(text ?? '').replace(/"/g, "'").replace(/\|/g, '/').replace(/[\r\n]+/g, ' ').trim();
}

// buildNodeSubgraph()（雙向 BFS 多跳收集）已移至 utils/industryChainGraph.js，同時供本檔的
// 「節點路徑」匯出範圍與 IndustryChainView.vue 的 §8 v2.6 多跳路徑高亮共用（見該檔頭註解）。

// ── Mermaid 圖：節點三態配色沿用本頁既有色票（ADR-IC-21），邊的實線／虛線沿用力導向圖
//    「已核可＝實線、待核對＝虛線」的既有語意（ADR-IC-14），不是另外發明一套圖例。
export function renderChainMermaid(nodes, edges) {
  const lines = ['flowchart LR'];
  nodes.forEach((n) => {
    const id = mermaidNodeId(n.symbol);
    lines.push(`  ${id}["${escapeMermaidLabel(n.symbol)} ${escapeMermaidLabel(n.name)}"]`);
  });
  const linkStyles = [];
  edges.forEach((e, idx) => {
    const from = mermaidNodeId(e.upstream_symbol);
    const to = mermaidNodeId(e.downstream_symbol);
    const label = e.component_type ? `|${escapeMermaidLabel(e.component_type)}|` : '';
    lines.push(`  ${from} -->${label} ${to}`);
    linkStyles.push(
      e.is_verified
        ? `  linkStyle ${idx} stroke:#79746c,stroke-width:1.5px;`
        : `  linkStyle ${idx} stroke:#B26A00,stroke-width:1.5px,stroke-dasharray:5 5;`
    );
  });
  nodes.forEach((n) => {
    const id = mermaidNodeId(n.symbol);
    const fill = STATE_BG[n.state] || STATE_BG.dormant;
    const stroke = STATE_COLOR[n.state] || STATE_COLOR.dormant;
    lines.push(`  style ${id} fill:${fill},stroke:${stroke},stroke-width:2px`);
  });
  lines.push(...linkStyles);
  return lines.join('\n');
}

function renderNodeTable(nodes) {
  const rows = [...nodes].sort((a, b) => a.symbol.localeCompare(b.symbol));
  const header = '| 分層 | 代碼 | 名稱 | 狀態 | 最近收盤 |\n|---|---|---|---|---|';
  const body = rows.map((n) => {
    const close = n.close != null ? `${Number(n.close).toFixed(2)}（${n.quote_date || '—'}）` : '—';
    return `| ${TIER_LABEL[n.role] || n.role} | ${n.symbol} | ${n.name} | ${STATE_LABEL[n.state] || '尚未連動'} | ${close} |`;
  });
  return [header, ...body].join('\n');
}

function renderEdgeTable(edges) {
  const header = '| 上游 | 下游 | 供應內容 | 關聯層級 | 來源 | 核對狀態 |\n|---|---|---|---|---|---|';
  const body = edges.map((e) => {
    const source = e.source || '—';
    const verified = e.is_verified ? '已核可' : '待核對（AI 推測）';
    return `| ${e.upstream_symbol} | ${e.downstream_symbol} | ${e.component_type || '—'} | Tier ${e.relation_tier} | ${source} | ${verified} |`;
  });
  return [header, ...body].join('\n');
}

function renderRadarTable(radarItems) {
  if (!radarItems.length) return '（目前無符合條件的候選標的）';
  const header = '| 代碼 | Tier | 供應 | 領先天數 | 相關係數 | 樣本數 | 跟漲勝率 |\n|---|---|---|---|---|---|---|';
  const body = radarItems.map((r) => {
    const winRate = r.win_rate ? `${Math.round(r.win_rate.rate * 100)}%（${r.win_rate.total} 次${r.win_rate.total < 5 ? '・樣本不足' : ''}）` : '—';
    return `| ${r.symbol} | ${r.relation_tier} | ${r.downstream_leader} | ${r.peak_lag_days ?? '—'} | ${r.correlation_coefficient ?? '—'} | ${r.sample_size ?? '—'} | ${winRate} |`;
  });
  return [header, ...body].join('\n');
}

// ── 三個匯出範圍的內容產生器。回傳形狀統一為 { subject, market, symbol, tagNames, content }，
//    直接對應 ExportToNoteDialog.vue 表單欄位；market／symbol 是 ADR-IC-20 定案的單一錨點標的。

// 範圍一：整鏈快照。錨點標的預設當日已點火的下游龍頭（sorted 取第一個以求穩定），
// 沒有任何點火事件時退回鏈骨架第一個下游龍頭；一個下游龍頭都沒有的鏈理論上匯出按鈕會被
// disable（見 IndustryChainView.vue），這裡仍防守一次避免產生沒有錨點標的的筆記。
export function buildChainSnapshotNote({ chain, nodes, edges, radarItems }) {
  const ignited = nodes.filter((n) => n.state === 'ignited').map((n) => n.symbol).sort();
  const anchorSymbol = ignited[0] || chain.downstream_leaders?.[0] || nodes[0]?.symbol || null;
  const anchorNode = nodes.find((n) => n.symbol === anchorSymbol);
  const verifiedCount = edges.filter((e) => e.is_verified).length;
  const verifiedRatio = edges.length ? Math.round((verifiedCount / edges.length) * 100) : 0;

  const content = `# ${chain.name} — 產業鏈快照

擷取時間：${new Date().toLocaleString('zh-TW', { hour12: false })}　來源：產業鏈知識圖譜（Phase 3）

## 摘要
- 節點數：${nodes.length}　邊數：${edges.length}　已核可比例：${verifiedRatio}%（${verifiedCount} / ${edges.length} 筆）
- 今日已點火（下游龍頭）：${ignited.length ? ignited.join('、') : '無'}
- 輪動候選（通過全部濾網）：${radarItems.length} 檔

## 關聯圖

\`\`\`mermaid
${renderChainMermaid(nodes, edges)}
\`\`\`

## 節點清單
${renderNodeTable(nodes)}

## 輪動外溢候選
${renderRadarTable(radarItems)}
`;

  return {
    subject: `【產業鏈快照】${chain.name}（${todayDate()}）`,
    market: anchorNode?.market || 'tw',
    symbol: anchorSymbol,
    tagNames: [chain.name, '產業鏈快照'],
    content
  };
}

// 範圍二：單一關聯。錨點標的預設下游（ADR-IC-20）。
export function buildSingleEdgeNote({ chain, edge, nodesBySymbol }) {
  const upNode = nodesBySymbol.get(edge.upstream_symbol);
  const downNode = nodesBySymbol.get(edge.downstream_symbol);
  const upName = upNode?.name || edge.upstream_symbol;
  const downName = downNode?.name || edge.downstream_symbol;
  const confidence = edge.extra_data?.llm_confidence ? CONFIDENCE_LABEL[edge.extra_data.llm_confidence] || edge.extra_data.llm_confidence : null;

  const nodesForMermaid = [upNode, downNode].filter(Boolean);
  const mermaidNodes = nodesForMermaid.length === 2
    ? nodesForMermaid
    : [
        { symbol: edge.upstream_symbol, name: upName, state: 'dormant' },
        { symbol: edge.downstream_symbol, name: downName, state: 'dormant' }
      ];

  const content = `# ${edge.upstream_symbol} ${upName} → ${edge.downstream_symbol} ${downName}

- 關聯層級：Tier ${edge.relation_tier}
- 供應內容：${edge.component_type || '—'}
- 來源：${edge.source || '—'}
- 核對狀態：${edge.is_verified ? '已核可' : '待核對（AI 推測，見 ADR-IC-14）'}
${confidence ? `- AI 自評信心：${confidence}` : ''}
${edge.extra_data?.llm_evidence ? `- 依據：${edge.extra_data.llm_evidence}` : ''}
${edge.extra_data?.evidence_url ? `- 佐證來源：${edge.extra_data.evidence_url}` : ''}

\`\`\`mermaid
${renderChainMermaid(mermaidNodes, [edge])}
\`\`\`
`;

  return {
    subject: `【產業鏈關聯】${edge.upstream_symbol} → ${edge.downstream_symbol}（${todayDate()}）`,
    market: downNode?.market || 'tw',
    symbol: edge.downstream_symbol,
    tagNames: [chain?.name, '產業鏈關聯'].filter(Boolean),
    content
  };
}

// 範圍三：節點路徑。錨點標的即使用者選取的節點本身（ADR-IC-20）。
export function buildNodePathNote({ chain, node, nodes, edges }) {
  const { symbols, edges: pathEdges } = buildNodeSubgraph(node.symbol, edges);
  const pathNodes = nodes.filter((n) => symbols.has(n.symbol));

  const content = `# ${node.symbol} ${node.name} — 上下游關聯路徑

從 ${node.symbol} ${node.name} 出發，沿產業鏈供應關係雙向多跳追蹤到的完整子圖（共 ${pathNodes.length} 個節點、${pathEdges.length} 條邊），來源鏈：${chain?.name || '—'}。

\`\`\`mermaid
${renderChainMermaid(pathNodes, pathEdges)}
\`\`\`

## 節點清單
${renderNodeTable(pathNodes)}

## 邊清單
${renderEdgeTable(pathEdges)}
`;

  return {
    subject: `【節點路徑】${node.symbol} ${node.name}（${todayDate()}）`,
    market: node.market || 'tw',
    symbol: node.symbol,
    tagNames: [chain?.name, '產業鏈節點路徑'].filter(Boolean),
    content
  };
}
