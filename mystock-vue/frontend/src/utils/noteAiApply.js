// 投資筆記 AI 解析：把使用者在預覽對話框勾選的提案項目，組成既有 PATCH /investment-notes/{id} 的 payload。
// 純函式（不碰 API／DOM），行為由 noteAiApply.test.mjs 驗證。
//
// 鐵則：AI 只產生「提案」，任何寫入都只發生在使用者按下套用之後；原圖與其 data URI 定義絕不刪除。

const TAG_COLOR_SYMBOL = 'sky'; // 個股代號標籤
const TAG_COLOR_TOPIC = 'teal'; // 主題標籤

// 匹配貼上圖片時 pastedImage.js 產生的參考式定義列：`[image-1]: data:image/...`
const DEFINITION_LINE_RE = /^\[[^\]\n]+\]:[ \t]*data:image\/\S+[ \t]*$/m;
const SUMMARY_HEADING = '## AI 整理';

const escapeRegExp = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const normalizeEol = (s) => (s || '').replace(/\r\n/g, '\n');
const transcriptionHeading = (ref) => `#### 圖片 ${ref} 內容（AI 轉錄）`;

export function hasAppliedTranscription(content, ref) {
  return normalizeEol(content).includes(transcriptionHeading(ref));
}

export function hasAppliedSummary(content) {
  return new RegExp(`^${escapeRegExp(SUMMARY_HEADING)}$`, 'm').test(normalizeEol(content));
}

// ── 個股列的狀態規則（驗證結果見 backend note_ai/validator.py）──────────────
export const defaultSymbolChecked = (row) => row.status === 'verified';
export const symbolSelectable = (row) => row.status !== 'not_found';

/** 改用後端依公司名稱查到的建議代號：該建議來自主檔，視同已驗證。 */
export function adoptSuggestion(row) {
  const s = row.suggestion;
  if (!s) return row;
  return {
    ...row, market: s.market, symbol: s.symbol, name: s.name, master_name: s.name,
    status: 'verified', reason: null, suggestion: null, corrected_from: row.symbol
  };
}

// ── 內容插入 ──────────────────────────────────────────────────────────
/** 插在「引用該圖的那一段」之後；找不到引用（標記被刪掉）就退回插在圖片定義之前。 */
function insertAfterImageParagraph(content, ref, block) {
  const marker = new RegExp(`!\\[[^\\]]*\\]\\[${escapeRegExp(ref)}\\]`).exec(content);
  if (!marker) return insertBeforeDefinitions(content, block);
  const paragraphEnd = content.indexOf('\n\n', marker.index + marker[0].length);
  const at = paragraphEnd === -1 ? content.length : paragraphEnd;
  return `${content.slice(0, at)}\n\n${block}${content.slice(at)}`;
}

/** 插在文末圖片定義區之前；沒有定義區就接在文末。 */
function insertBeforeDefinitions(content, block) {
  const def = DEFINITION_LINE_RE.exec(content);
  if (!def) return `${content.replace(/\s+$/, '')}\n\n${block}\n`;
  const head = content.slice(0, def.index).replace(/\s+$/, '');
  return `${head}\n\n${block}\n\n${content.slice(def.index)}`;
}

function transcriptionBlock(t) {
  const title = (t.title || '').trim();
  return `${transcriptionHeading(t.ref)}${title ? `：${title}` : ''}\n\n${t.markdown.trim()}`;
}

function mergeTags(existingNames, additions) {
  const out = [...existingNames];
  const seen = new Set(out.map((n) => n.toLowerCase()));
  for (const name of additions) {
    if (!seen.has(name.toLowerCase())) {
      seen.add(name.toLowerCase());
      out.push(name);
    }
  }
  return out;
}

/**
 * choices: { subject: boolean, topicTags: string[], symbols: {market, symbol}[],
 *            transcriptions: string[] (image refs), summary: boolean }
 * 回傳只含「有變動」欄位的 payload；全部沒選則為 {}。
 * 標籤：PATCH 會整批覆寫，所以必須先帶入筆記既有標籤再附加；沒選任何標籤就完全不帶 tag_names。
 * 內容：呼叫端須傳入完整內容的 note（getNote() 的結果，列表只有摘要）。已套用過的轉錄／整理會略過。
 */
export function buildApplyPayload({ note, proposal, choices }) {
  const payload = {};

  if (choices.subject && proposal.suggested_subject) payload.subject = proposal.suggested_subject;

  const symbolCodes = (choices.symbols || []).map((s) => s.symbol);
  const topicTags = choices.topicTags || [];
  if (symbolCodes.length || topicTags.length) {
    payload.tag_names = mergeTags((note.tags || []).map((t) => t.name), [...topicTags, ...symbolCodes]);
    payload.tag_colors = {
      ...Object.fromEntries(topicTags.map((n) => [n, TAG_COLOR_TOPIC])),
      ...Object.fromEntries(symbolCodes.map((c) => [c, TAG_COLOR_SYMBOL]))
    };
  }

  const original = normalizeEol(note.content);
  let content = original;
  for (const ref of choices.transcriptions || []) {
    const t = (proposal.transcriptions || []).find((x) => x.ref === ref);
    if (!t || hasAppliedTranscription(content, ref)) continue;
    content = insertAfterImageParagraph(content, ref, transcriptionBlock(t));
  }
  if (choices.summary && proposal.summary_markdown && !hasAppliedSummary(content)) {
    content = insertBeforeDefinitions(content, `${SUMMARY_HEADING}\n\n${proposal.summary_markdown.trim()}`);
  }
  if (content !== original) payload.content = content;

  return payload;
}
