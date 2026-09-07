const seedNotes = [
  { id: 1, date: '2026-08-28', sequence: 1, subject: 'AI 伺服器需求仍在加速，但估值需要耐心', content: '今天重新整理了供應鏈資料。需求面沒有反轉訊號，不過短線漲幅已經把樂觀預期反映不少，接下來更重要的是觀察法說會對下半年展望的修正。', tags: ['研究', '長期'], symbol: 'TW · 2330', status: 'published' },
  { id: 2, date: '2026-08-27', sequence: 1, subject: '市場回檔時，先檢查假設而不是急著加碼', content: '大盤今天跌破月線，盤面情緒明顯轉弱。持股回檔本身不是賣出理由，先確認原本的獲利成長假設是否改變，再決定是否調整部位。', tags: ['市場觀察', '紀律'], symbol: '', status: 'published' },
  { id: 3, date: '2026-08-25', sequence: 1, subject: '美國零售數據優於預期，消費股值得再追蹤', content: '零售銷售數據比預期穩健，利率敏感型股票出現反彈。先建立觀察清單，不在單日數據公布後追價，等下一次財報確認趨勢。', tags: ['美股', '研究'], symbol: 'US · COST', status: 'published' },
  { id: 4, date: '2026-08-22', sequence: 1, subject: '本週交易檢討：太早停利，沒有按照計畫執行', content: '原本設定的停利區間還沒到，但因為盤中波動提前賣出。結果雖然獲利，卻沒有遵守事前規則。下次要把進出場條件寫得更具體。', tags: ['交易檢討', '紀律'], symbol: 'TW · 2454', status: 'published' },
  { id: 5, date: '2026-08-20', sequence: 1, subject: '觀察台積電月線乖離率與外資持倉變化', content: '月線乖離率回到合理範圍，外資連續兩日買超。基本面仍然正向，但短線需要留意匯率與海外 ADR 的價差。', tags: ['研究', '台積電'], symbol: 'TW · 2330', status: 'published' },
  { id: 6, date: '2026-08-18', sequence: 1, subject: '建立「不追高」檢查清單', content: '當個股連續上漲時，進場前至少回答三個問題：催化劑是否仍在、預期是否已充分反映、若判斷錯誤要在哪裡停損。', tags: ['紀律'], symbol: '', status: 'published' },
  { id: 7, date: '2026-08-15', sequence: 1, subject: '美股財報季前的部位調整想法', content: '本週先降低高波動持股的部位，把現金留給財報後的錯殺機會。不是預測結果，而是控制單一事件對組合的影響。', tags: ['美股', '市場觀察'], symbol: 'US · NVDA', status: 'published' },
  { id: 8, date: '2026-08-12', sequence: 1, subject: 'ETF 長期配置：維持簡單比追逐熱門更重要', content: '檢視今年以來的配置，核心 ETF 的表現雖不突出，但讓整體波動更容易承受。投資計畫的價值在於能夠長期執行。', tags: ['長期', '配置'], symbol: 'TW · 0050', status: 'published' },
  { id: 9, date: '2026-07-30', sequence: 1, subject: '七月投資月報草稿', content: '整理本月交易與持股變化，月底再補上績效數字與策略執行率。', tags: ['月報'], symbol: '', status: 'draft' },
  { id: 10, date: '2026-07-24', sequence: 1, subject: '重新閱讀去年對半導體景氣的判斷', content: '當時低估了庫存調整所需的時間，也高估了短線反彈的持續性。這次把錯誤拆成假設、證據與執行三部分。', tags: ['研究', '交易檢討'], symbol: 'TW · 2330', status: 'published' },
  { id: 11, date: '2026-07-18', sequence: 1, subject: '建立觀察名單的判斷條件', content: '先寫條件再看價格：營收趨勢、毛利率、產業位置與估值。避免因為一根紅 K 就把標的加入長期清單。', tags: ['研究', '紀律'], symbol: '', status: 'published' },
  { id: 12, date: '2026-07-10', sequence: 1, subject: '第一次使用投資筆記回顧交易', content: '把過去的決策放在一起看，才發現自己在市場快速上漲時容易放寬進場標準。之後會在下單前先完成一頁筆記。', tags: ['交易檢討'], symbol: '', status: 'published' }
];

const state = { notes: [...seedNotes], page: 1, pageSize: 5, editingId: null, dark: false };
const $ = (id) => document.getElementById(id);
const pad = (value) => String(value).padStart(2, '0');
const dateLabel = (date) => { const d = new Date(`${date}T00:00:00`); return `${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())}`; };
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));

function allTags() {
  const counts = {};
  state.notes.forEach((note) => note.tags.forEach((tag) => { counts[tag] = (counts[tag] || 0) + 1; }));
  return Object.entries(counts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function filteredNotes() {
  const query = $('searchInput').value.trim().toLowerCase();
  const month = $('dateInput').value;
  const tag = $('tagFilter').value;
  const sort = $('sortSelect').value;
  return state.notes.filter((note) => {
    const searchable = `${note.subject} ${note.content} ${note.symbol}`.toLowerCase();
    return (!query || searchable.includes(query)) && (!month || note.date.startsWith(month)) && (!tag || note.tags.includes(tag));
  }).sort((a, b) => sort === 'newest' ? `${b.date}-${b.sequence}`.localeCompare(`${a.date}-${a.sequence}`) : `${a.date}-${a.sequence}`.localeCompare(`${b.date}-${b.sequence}`));
}

function renderFilters() {
  const selected = $('tagFilter').value;
  $('tagFilter').innerHTML = '<option value="">所有標籤</option>' + allTags().map(([tag, count]) => `<option value="${escapeHtml(tag)}">${escapeHtml(tag)} (${count})</option>`).join('');
  $('tagFilter').value = selected;
  $('tagCloud').innerHTML = allTags().map(([tag, count]) => `<button type="button" class="${selected === tag ? 'active' : ''}" data-tag="${escapeHtml(tag)}">${escapeHtml(tag)} <em>${count}</em></button>`).join('');
}

function renderNotes() {
  const notes = filteredNotes();
  const totalPages = Math.max(1, Math.ceil(notes.length / state.pageSize));
  state.page = Math.min(state.page, totalPages);
  const pageNotes = notes.slice((state.page - 1) * state.pageSize, state.page * state.pageSize);
  $('resultCount').textContent = `${notes.length} 篇`;
  $('resultLabel').textContent = $('searchInput').value || $('dateInput').value || $('tagFilter').value ? '篩選結果' : '全部筆記';
  $('emptyState').hidden = notes.length > 0;
  $('noteList').innerHTML = pageNotes.map((note) => `<article class="note-card" data-id="${note.id}">
    <div class="note-date"><strong>${dateLabel(note.date).slice(5)}</strong>${dateLabel(note.date).slice(0, 4)} · <span class="note-sequence">#${note.sequence}</span></div>
    <div class="note-main"><h2>${escapeHtml(note.subject)}${note.status === 'draft' ? ' <span class="draft-label">草稿</span>' : ''}</h2><p>${escapeHtml(note.content)}</p><div class="note-meta">${note.tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}${note.symbol ? `<span class="symbol">${escapeHtml(note.symbol)}</span>` : ''}</div></div>
    <div class="note-actions"><button class="action-button edit" data-action="edit" title="編輯" aria-label="編輯"><i class="pi pi-pencil"></i></button><button class="action-button delete" data-action="delete" title="刪除" aria-label="刪除"><i class="pi pi-trash"></i></button></div>
  </article>`).join('');
  $('pagination').innerHTML = totalPages > 1 ? Array.from({ length: totalPages }, (_, index) => `<button class="page-button ${state.page === index + 1 ? 'active' : ''}" data-page="${index + 1}">${index + 1}</button>`).join('') : '';
  updateSummary();
}

function updateSummary() {
  const august = state.notes.filter((note) => note.date.startsWith('2026-08'));
  $('noteCount').textContent = state.notes.length;
  $('monthCount').textContent = august.length;
  $('topTag').textContent = allTags()[0]?.[0] || '—';
  const latest = state.notes.slice().sort((a, b) => b.date.localeCompare(a.date))[0];
  $('lastUpdated').textContent = latest?.date === '2026-08-28' ? '今天' : latest ? dateLabel(latest.date).slice(5) : '—';
}

function nextSequence(date, id) { return Math.max(0, ...state.notes.filter((note) => note.date === date && note.id !== id).map((note) => note.sequence)) + 1; }
function openModal(note = null) { state.editingId = note?.id || null; $('modalTitle').textContent = note ? '編輯投資筆記' : '新增投資筆記'; $('noteId').value = note?.id || ''; $('noteDate').value = note?.date || '2026-08-28'; $('noteStatus').value = note?.status || 'published'; $('noteSubject').value = note?.subject || ''; $('noteContent').value = note?.content || ''; $('noteTags').value = note?.tags.join(', ') || ''; $('noteSymbol').value = note?.symbol || ''; $('sequenceHint').innerHTML = note ? `<i class="pi pi-hashtag"></i> 當日流水號 #${note.sequence}` : '<i class="pi pi-hashtag"></i> 儲存後自動取得當日流水號'; $('noteModal').hidden = false; setTimeout(() => $('noteSubject').focus(), 0); }
function closeModal() { $('noteModal').hidden = true; state.editingId = null; }
function showToast(message) { $('toast').querySelector('span').textContent = message; $('toast').classList.add('show'); setTimeout(() => $('toast').classList.remove('show'), 2200); }

$('newNoteButton').addEventListener('click', () => openModal());
$('closeModal').addEventListener('click', closeModal);
$('cancelButton').addEventListener('click', closeModal);
$('noteModal').addEventListener('click', (event) => { if (event.target === $('noteModal')) closeModal(); });
['searchInput', 'dateInput', 'tagFilter', 'sortSelect'].forEach((id) => $(id).addEventListener('input', () => { state.page = 1; renderNotes(); renderFilters(); }));
$('clearFilters').addEventListener('click', () => { $('searchInput').value = ''; $('dateInput').value = ''; $('tagFilter').value = ''; state.page = 1; renderNotes(); renderFilters(); });
$('tagCloud').addEventListener('click', (event) => { const button = event.target.closest('[data-tag]'); if (button) { $('tagFilter').value = button.dataset.tag; state.page = 1; renderNotes(); renderFilters(); } });
$('pagination').addEventListener('click', (event) => { const button = event.target.closest('[data-page]'); if (button) { state.page = Number(button.dataset.page); renderNotes(); window.scrollTo({ top: 0, behavior: 'smooth' }); } });
$('noteList').addEventListener('click', (event) => { const card = event.target.closest('[data-id]'); if (!card) return; const note = state.notes.find((item) => item.id === Number(card.dataset.id)); if (event.target.closest('[data-action="edit"]')) openModal(note); if (event.target.closest('[data-action="delete"]') && confirm(`確定刪除「${note.subject}」？`)) { state.notes = state.notes.filter((item) => item.id !== note.id); renderNotes(); renderFilters(); showToast('筆記已刪除'); } });
$('noteForm').addEventListener('submit', (event) => { event.preventDefault(); const editing = Boolean(state.editingId); const date = $('noteDate').value; const note = { id: state.editingId || Date.now(), date, sequence: nextSequence(date, state.editingId), subject: $('noteSubject').value.trim(), content: $('noteContent').value.trim(), tags: $('noteTags').value.split(',').map((tag) => tag.trim()).filter(Boolean).slice(0, 10), symbol: $('noteSymbol').value.trim(), status: $('noteStatus').value }; if (editing) state.notes = state.notes.map((item) => item.id === state.editingId ? note : item); else state.notes.unshift(note); closeModal(); state.page = 1; renderNotes(); renderFilters(); showToast(editing ? '筆記已更新' : `筆記已儲存 · ${date} #${note.sequence}`); });
$('themeButton').addEventListener('click', () => { state.dark = !state.dark; document.body.classList.toggle('dark', state.dark); $('themeButton').innerHTML = `<i class="pi pi-${state.dark ? 'sun' : 'moon'}"></i>`; });

renderFilters();
renderNotes();
