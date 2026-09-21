// 投資筆記 AI 解析（backend/api/v1/endpoints/note_ai.py）。與 investmentNoteApi 同用 privateApiClient
// （筆記是私人內容，後端掛 require_owner）。
import { privateApiClient as apiClient } from '@/service/ownerApi';

// 一次含圖的 LLM 呼叫通常 10～60 秒；比照 aiAnalysisApi.js 覆寫預設的 15 秒逾時。
const ANALYZE_TIMEOUT_MS = 120000;

export const noteAiApi = {
    // 功能是否啟用、今日用量與配額、預設 provider／model（解析前顯示費用提示用）
    async getStatus() {
        const response = await apiClient.get('/note-ai/status');
        return response.data;
    },

    // 對一篇筆記做解析，回傳「提案」；不會寫入筆記，套用走 investmentNoteApi.updateNote
    async analyzeNote(noteId, { provider, model } = {}) {
        const response = await apiClient.post(
            `/note-ai/notes/${noteId}/analyze`,
            { provider: provider || null, model: model || null },
            { timeout: ANALYZE_TIMEOUT_MS }
        );
        return response.data;
    }
};
