// 執行：cd frontend && node --test src/utils/
// 專案沒有前端測試框架；這支用 Node 內建 node:test 驗證「把 AI 提案的勾選項套用成 PATCH payload」的純函式邏輯。
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildApplyPayload, hasAppliedSummary, hasAppliedTranscription, symbolSelectable, defaultSymbolChecked, adoptSuggestion
} from './noteAiApply.js';

const DEF = '[image-1]: data:image/webp;base64,AAAA';
const note = (over = {}) => ({
  id: 7, subject: '黃勳喊話', content: `今日觀察\n\n![貼上圖片 1][image-1]\n\n結論\n\n${DEF}\n`,
  tags: [{ name: '手動標籤' }], market: null, symbol: null, ...over
});
const proposal = (over = {}) => ({
  suggested_subject: '15檔晶片股強力表態',
  topic_tags: ['晶片', '法人買超'],
  symbols: [
    { market: 'tw', symbol: '2303', name: '聯電', status: 'verified' },
    { market: 'tw', symbol: '2330', name: '台積電', status: 'verified' }
  ],
  transcriptions: [{ ref: 'image-1', kind: 'table', title: '15檔晶片股', markdown: '| 代號 |\n| --- |\n| 2303 |' }],
  summary_markdown: '### 重點\n\n聯電漲 5.76%',
  ...over
});
const none = { subject: false, topicTags: [], symbols: [], transcriptions: [], summary: false };

test('nothing selected produces an empty payload (so the apply button can be disabled)', () => {
  assert.deepEqual(buildApplyPayload({ note: note(), proposal: proposal(), choices: none }), {});
});

test('subject is only replaced when chosen', () => {
  const p = buildApplyPayload({ note: note(), proposal: proposal(), choices: { ...none, subject: true } });
  assert.deepEqual(p, { subject: '15檔晶片股強力表態' });
});

test('PATCH overwrites the whole tag set, so existing tags are preserved and new ones appended', () => {
  const p = buildApplyPayload({
    note: note(), proposal: proposal(),
    choices: { ...none, topicTags: ['晶片'], symbols: [{ market: 'tw', symbol: '2303' }] }
  });
  assert.deepEqual(p.tag_names, ['手動標籤', '晶片', '2303']);
});

test('symbol tags are colored sky and topic tags teal so they can be told apart later', () => {
  const p = buildApplyPayload({
    note: note(), proposal: proposal(),
    choices: { ...none, topicTags: ['晶片'], symbols: [{ market: 'tw', symbol: '2303' }] }
  });
  assert.deepEqual(p.tag_colors, { 2303: 'sky', 晶片: 'teal' });
});

test('tags are deduplicated case-insensitively against the note existing tags', () => {
  const p = buildApplyPayload({
    note: note({ tags: [{ name: 'NET' }] }), proposal: proposal(),
    choices: { ...none, symbols: [{ market: 'us', symbol: 'net' }] }
  });
  assert.deepEqual(p.tag_names, ['NET']);
});

test('no tags chosen means tag_names is omitted so existing tags are untouched', () => {
  const p = buildApplyPayload({ note: note(), proposal: proposal(), choices: { ...none, subject: true } });
  assert.equal('tag_names' in p, false);
  assert.equal('tag_colors' in p, false);
});

test('a transcription is inserted right after the paragraph that references its image', () => {
  const p = buildApplyPayload({ note: note(), proposal: proposal(), choices: { ...none, transcriptions: ['image-1'] } });
  const expected = '今日觀察\n\n![貼上圖片 1][image-1]\n\n#### 圖片 image-1 內容（AI 轉錄）：15檔晶片股\n\n| 代號 |\n| --- |\n| 2303 |\n\n結論\n\n' + DEF + '\n';
  assert.equal(p.content, expected);
});

test('the original image and its definition are never removed', () => {
  const p = buildApplyPayload({ note: note(), proposal: proposal(), choices: { ...none, transcriptions: ['image-1'] } });
  assert.ok(p.content.includes('![貼上圖片 1][image-1]'));
  assert.ok(p.content.includes(DEF));
});

test('a transcription whose image marker was deleted falls back to just before the image definitions', () => {
  const n = note({ content: `純文字\n\n${DEF}\n` });
  const p = buildApplyPayload({ note: n, proposal: proposal(), choices: { ...none, transcriptions: ['image-1'] } });
  assert.ok(p.content.indexOf('#### 圖片 image-1') < p.content.indexOf(DEF));
  assert.ok(p.content.startsWith('純文字'));
});

test('a text-kind transcription without a title has a clean heading', () => {
  const prop = proposal({ transcriptions: [{ ref: 'image-1', kind: 'text', title: '', markdown: '一段文字' }] });
  const p = buildApplyPayload({ note: note(), proposal: prop, choices: { ...none, transcriptions: ['image-1'] } });
  assert.ok(p.content.includes('#### 圖片 image-1 內容（AI 轉錄）\n\n一段文字'));
});

test('the summary goes at the end of the prose, before the image definitions', () => {
  const p = buildApplyPayload({ note: note(), proposal: proposal(), choices: { ...none, summary: true } });
  assert.ok(p.content.indexOf('## AI 整理') > p.content.indexOf('結論'));
  assert.ok(p.content.indexOf('## AI 整理') < p.content.indexOf(DEF));
  assert.ok(p.content.includes('聯電漲 5.76%'));
});

test('applying twice is idempotent for transcriptions and summary', () => {
  const choices = { ...none, transcriptions: ['image-1'], summary: true };
  const first = buildApplyPayload({ note: note(), proposal: proposal(), choices });
  const second = buildApplyPayload({ note: note({ content: first.content }), proposal: proposal(), choices });
  assert.equal(second.content, undefined);
  assert.equal(hasAppliedTranscription(first.content, 'image-1'), true);
  assert.equal(hasAppliedSummary(first.content), true);
  assert.equal(hasAppliedSummary(note().content), false);
});

test('CRLF content is handled', () => {
  const n = note({ content: '今日觀察\r\n\r\n![貼上圖片 1][image-1]\r\n\r\n結論\r\n\r\n' + DEF + '\r\n' });
  const p = buildApplyPayload({ note: n, proposal: proposal(), choices: { ...none, transcriptions: ['image-1'] } });
  assert.ok(p.content.includes('#### 圖片 image-1'));
  assert.ok(p.content.includes(DEF));
});

// ── 個股列的狀態規則 ─────────────────────────────────────────
test('only verified symbols are checked by default; failures need a conscious click', () => {
  assert.equal(defaultSymbolChecked({ status: 'verified' }), true);
  for (const status of ['name_mismatch', 'not_found', 'unverified']) {
    assert.equal(defaultSymbolChecked({ status }), false, status);
  }
});

test('a code that does not exist cannot be selected, other statuses can', () => {
  assert.equal(symbolSelectable({ status: 'not_found' }), false);
  for (const status of ['verified', 'name_mismatch', 'unverified']) {
    assert.equal(symbolSelectable({ status }), true, status);
  }
});

test('taking the suggested code swaps the row to a verified one', () => {
  const row = { market: 'tw', symbol: '2330', name: '聯電', status: 'name_mismatch', reason: 'x',
    suggestion: { market: 'tw', symbol: '2303', name: '聯電' } };
  const out = adoptSuggestion(row);
  assert.equal(out.symbol, '2303');
  assert.equal(out.status, 'verified');
  assert.equal(out.suggestion, null);
  assert.equal(out.corrected_from, '2330');
});
