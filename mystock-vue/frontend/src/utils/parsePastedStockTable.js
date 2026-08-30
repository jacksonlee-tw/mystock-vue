// 解析使用者貼上的股票清單表格文字，供「批次匯入」對話框使用（見 WatchlistBatchImportDialog.vue，
// 2026-08-30 需求：把 AI 聊天工具產出的產業鏈分類表貼進來，自動套用「主要分類→標籤、業務+題材→
// 追蹤原因」的匯入規則）。
//
// 支援三種常見貼上格式，皆固定欄位順序：股號、名稱、主要分類、主要業務與產業角色、核心題材與受惠邏輯。
//   1. TSV（Excel／Google Sheets／大多數聊天工具複製表格內容時的預設格式，欄位以 Tab 分隔）
//   2. Markdown pipe table（| 股號 | 名稱 | ... |，含表頭與 |---|---| 分隔列）
//   3. CSV（逗號分隔）
//
// 表格若在渲染時把儲存格文字換行（常見於聊天工具複製結果，最後一欄题材文字被拆成獨立一行），單靠
// 逐行切分會漏欄位，因此改用「股票代碼開頭 = 新的一列」判斷列的起訖：代碼列（數字或美股代號開頭，
// 後面緊接分隔符）才視為新列，其餘非空白行一律併入上一列的最後一欄（用空白接續）。

// 台股代碼（4~6 碼數字，可能帶字母尾碼如 00631L）或美股代號（1~6 碼大寫字母，可能帶 .B 這類尾綴），
// 後面緊接欄位分隔符（Tab／逗號／pipe，可能夾雜空白）才算是一列的開頭。
const ROW_START = /^\|?\s*([0-9]{4,6}[A-Z]?|[A-Z]{1,6}(?:\.[A-Z]{1,3})?)\s*[\t,|]/;

function isSeparatorRow(cells) {
  // markdown table 的 |---|---|---| 分隔列
  return cells.length > 0 && cells.every((c) => /^:?-{2,}:?$/.test(c.trim()));
}

function splitCells(line) {
  if (line.includes('\t')) return line.split('\t');
  const trimmed = line.trim();
  if (trimmed.startsWith('|')) {
    return trimmed.replace(/^\|/, '').replace(/\|$/, '').split('|');
  }
  return line.split(',');
}

/**
 * @param {string} text 使用者貼上的原始文字
 * @returns {Array<{symbol: string, name: string, category: string, business: string, theme: string}>}
 */
export function parsePastedStockTable(text) {
  const lines = String(text || '').replace(/\r\n?/g, '\n').split('\n');
  const rowLines = [];
  let current = null;

  for (const line of lines) {
    if (!line.trim()) continue; // 空行：儲存格換行造成的間隔，略過但不中斷目前這列
    if (ROW_START.test(line)) {
      if (current !== null) rowLines.push(current);
      current = line;
    } else if (current !== null) {
      current += ' ' + line.trim(); // 延續上一列最後一欄（儲存格文字換行）
    }
    // 尚未遇到任何代碼列之前的內容（表頭列、說明文字）直接捨棄
  }
  if (current !== null) rowLines.push(current);

  const rows = [];
  for (const rowLine of rowLines) {
    const cells = splitCells(rowLine).map((c) => c.trim());
    if (isSeparatorRow(cells)) continue;
    const [symbol = '', name = '', category = '', business = '', theme = ''] = cells;
    if (!symbol) continue;
    rows.push({ symbol: symbol.toUpperCase(), name, category, business, theme });
  }
  return rows;
}
