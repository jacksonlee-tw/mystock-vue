import { apiClient } from '@/service/stockApi';
import { privateApiClient } from '@/service/ownerApi';

// AI 呼叫實測耗時常落在 10～40 秒，遠超過共用 apiClient 的預設 15000ms
// （AI 技術分析報告 系統開發規格書 §7.2）。只在這一支請求上覆寫逾時，不動全域預設，
// 否則所有行情請求的失敗回饋都會跟著變慢。
const ANALYZE_TIMEOUT_MS = 120000;

export const aiAnalysisApi = {
    // 產生（或回讀當日既有）AI 技術分析報告（規格書 §6.1）。model 未帶時後端退回該 provider
    // 的 .env 預設；帶了則必須是 /ai/models 白名單內的值（v3.4，見 useAiAnalysis.js 的選單流程）。
    async analyzeStock({ symbol, market, period, months, provider, model, imageBase64, force = false }) {
        const response = await apiClient.post(
            '/ai/analyze-stock',
            {
                symbol,
                market,
                period,
                months,
                provider: provider || undefined,
                model: model || undefined,
                image_base64: imageBase64,
                force
            },
            { timeout: ANALYZE_TIMEOUT_MS }
        );
        return response.data;
    },

    // 可選模型清單（供產生報告前的選單使用，v3.4，規格書 §4.3）
    async getModels() {
        const response = await apiClient.get('/ai/models');
        return response.data;
    },

    // AI 功能是否啟用、可用 Provider、今日已用量與配額（規格書 §6.1）
    async getStatus() {
        const response = await apiClient.get('/ai/status');
        return response.data;
    },

    // 查詢某標的（可選：特定 provider+model 組合）最近一筆成功報告，供選單判斷「這個模型組合
    // 今天是否已產生」（規格書 §6.2、§7.3，v3.4 起 provider/model 為精確判斷所需）
    async getLatestReport(market, symbol, provider, model) {
        const params = { market, symbol };
        if (provider) params.provider = provider;
        if (model) params.model = model;
        const response = await apiClient.get('/ai/reports/latest', { params });
        return response.data;
    },

    // 歷史報告列表（分頁，規格書 §6.2）
    async listReports({ market, symbol, dateFrom, dateTo, verdict, status = 'succeeded', limit = 20, offset = 0 } = {}) {
        const params = { status, limit, offset };
        if (market) params.market = market;
        if (symbol) params.symbol = symbol;
        if (dateFrom) params.date_from = dateFrom;
        if (dateTo) params.date_to = dateTo;
        if (verdict) params.verdict = verdict;
        const response = await apiClient.get('/ai/reports', { params });
        return response.data;
    },

    // 單筆報告完整內容（規格書 §6.2）
    async getReport(reportId) {
        const response = await apiClient.get(`/ai/reports/${reportId}`);
        return response.data;
    },

    // 刪除報告（誤產生時清除，規格書 §6.2）
    async deleteReport(reportId) {
        const response = await apiClient.delete(`/ai/reports/${reportId}`);
        return response.data;
    },

    // LLM 呼叫執行紀錄列表（含失敗，規格書 §6.3；功能來源 viewId 見
    // docs/16.AI技術分析/執行歷史頁面開發計劃.md §2.1）
    async listExecutions({ viewId, provider, model, status, symbol, market, dateFrom, dateTo, includeDryRun = false, limit = 20, offset = 0 } = {}) {
        const params = { include_dry_run: includeDryRun, limit, offset };
        if (viewId) params.view_id = viewId;
        if (provider) params.provider = provider;
        if (model) params.model = model;
        if (status) params.status = status;
        if (symbol) params.symbol = symbol;
        if (market) params.market = market;
        if (dateFrom) params.date_from = dateFrom;
        if (dateTo) params.date_to = dateTo;
        const response = await apiClient.get('/ai/executions', { params });
        return response.data;
    },

    // 用量與成本彙總（規格書 §6.3）。groupBy 預設 'model'，本頁目前只用 totals 區塊。
    async getUsage({ groupBy = 'model', dateFrom, dateTo } = {}) {
        const params = { group_by: groupBy };
        if (dateFrom) params.date_from = dateFrom;
        if (dateTo) params.date_to = dateTo;
        const response = await apiClient.get('/ai/usage', { params });
        return response.data;
    },

    // 戰情室彙總：監控清單 × 當日最新 AI 報告，一次查完（Phase5-三層式 AI 決策引擎與戰情室.md
    // FR-5.5，AC-P5-17 不得對每檔標的各發一次請求）。掛 require_owner，未登入會收到 401。
    // 必須用 privateApiClient（withCredentials）才會帶上 owner session cookie，否則不管有沒有
    // 登入都會 401——router 的 requiresOwner 守衛用的是 ownerApi.whoami()（同樣走
    // privateApiClient）先放行進頁面，若這裡誤用不帶憑證的 apiClient 會讓畫面直接卡在錯誤訊息，
    // 且看起來像「登入了也沒用」。
    async getWarRoom(market = 'tw') {
        const response = await privateApiClient.get('/ai/war-room', { params: { market } });
        return response.data;
    },

    // 批次設定／預估／手動觸發（監控清單批次，掛 require_owner，同上須用 privateApiClient）。
    async getBatchSettings() {
        const response = await privateApiClient.get('/ai/batch/settings');
        return response.data;
    },
    async updateBatchSettings({ enabled, dailyQuota, provider, model } = {}) {
        const payload = {};
        if (enabled !== undefined) payload.enabled = enabled;
        if (dailyQuota !== undefined) payload.daily_quota = dailyQuota;
        if (provider !== undefined) payload.provider = provider;
        if (model !== undefined) payload.model = model;
        const response = await privateApiClient.put('/ai/batch/settings', payload);
        return response.data;
    },
    // 執行前必須先呼叫這支拿到預估費用／token 量，UI 顯示給使用者確認後才可觸發 /batch/trigger。
    // symbols：戰情室多選標的手動觸發時帶入（陣列），省略則沿用「整份監控清單」既有行為。
    async getBatchEstimate(market = 'tw', symbols) {
        const params = { market };
        if (symbols?.length) params.symbols = symbols.join(',');
        const response = await privateApiClient.get('/ai/batch/estimate', { params });
        return response.data;
    },
    // 批次同步執行（逐檔呼叫 LLM，視配額大小可能需要數十秒到數分鐘），沿用 ANALYZE_TIMEOUT_MS。
    // symbols：戰情室多選標的手動觸發時帶入（陣列），省略則沿用「整份監控清單」既有行為。
    async triggerBatch(market = 'tw', symbols) {
        const payload = { market };
        if (symbols?.length) payload.symbols = symbols;
        const response = await privateApiClient.post('/ai/batch/trigger', payload, { timeout: ANALYZE_TIMEOUT_MS * 3 });
        return response.data;
    }
};
