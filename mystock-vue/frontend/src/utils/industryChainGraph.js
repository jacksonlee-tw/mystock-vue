// 產業鏈知識圖譜的圖結構純函式（BFS 多跳收集），供兩個用途共用：
// 1. utils/industryChainExport.js 的 FR-21「節點路徑」匯出範圍
// 2. IndustryChainView.vue 的 §8 v2.6「圖形互動深度」①多跳路徑高亮（hover 節點時）
// 抽成獨立檔案（而非留在 industryChainExport.js 裡）是因為第 2 個用途跟「匯出」無關，
// 從一個叫 xxxExport.js 的模組 import 圖走訪邏輯語意上會很奇怪。
export function buildNodeSubgraph(startSymbol, edges) {
  const outgoing = new Map(); // symbol -> 以該symbol為上游的邊（往下游走）
  const incoming = new Map(); // symbol -> 以該symbol為下游的邊（往上游走）
  edges.forEach((e) => {
    if (!outgoing.has(e.upstream_symbol)) outgoing.set(e.upstream_symbol, []);
    outgoing.get(e.upstream_symbol).push(e);
    if (!incoming.has(e.downstream_symbol)) incoming.set(e.downstream_symbol, []);
    incoming.get(e.downstream_symbol).push(e);
  });

  const visitedSymbols = new Set([startSymbol]);
  const visitedEdgeKeys = new Set();
  const collectedEdges = [];

  function walk(direction) {
    const map = direction === 'down' ? outgoing : incoming;
    const queue = [startSymbol];
    while (queue.length) {
      const sym = queue.shift();
      const next = map.get(sym) || [];
      for (const e of next) {
        const key = `${e.upstream_symbol}->${e.downstream_symbol}`;
        if (!visitedEdgeKeys.has(key)) {
          visitedEdgeKeys.add(key);
          collectedEdges.push(e);
        }
        const otherSymbol = direction === 'down' ? e.downstream_symbol : e.upstream_symbol;
        if (!visitedSymbols.has(otherSymbol)) {
          visitedSymbols.add(otherSymbol);
          queue.push(otherSymbol);
        }
      }
    }
  }
  walk('down');
  walk('up');

  return { symbols: visitedSymbols, edges: collectedEdges };
}

// 邊的穩定 key，供呼叫端比對某條邊是否落在 buildNodeSubgraph() 收集到的路徑內
export function edgeKey(edge) {
  return `${edge.upstream_symbol}->${edge.downstream_symbol}`;
}
