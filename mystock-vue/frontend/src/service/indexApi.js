// 大盤指數 API 包裝（見 docs/10.加權指數/大盤指數功能規劃書.md 第九節）。
// 共用 stockApi.js 匯出的 apiClient 實例（同一個 baseURL/timeout 設定），不另建 axios instance。
import { apiClient } from '@/service/stockApi';

export const indexApi = {
    // 取得支援的指數清單（含資料涵蓋範圍）
    async getIndices(market = null) {
        const params = {};
        if (market) params.market = market;
        const response = await apiClient.get('/indices', { params });
        return response.data;
    },

    // 首頁／熱力圖大盤概況：一次取得所有指數的最新報價、漲跌與 Sparkline
    async getOverview(period = 'daily', market = null) {
        const params = { period };
        if (market) params.market = market;
        const response = await apiClient.get('/indices/overview', { params });
        return response.data;
    },

    // 取得單一指數的圖表專用格式資料
    async getChartData(code, period = 'daily', months = 3, market = 'tw') {
        const response = await apiClient.get(`/indices/${code}/chart-data`, {
            params: { period, months, market }
        });
        return response.data;
    },

    // 取得單一指數歷史明細數據
    async getDetail(code, period = 'daily', months = 3, market = 'tw') {
        const response = await apiClient.get(`/indices/${code}`, {
            params: { period, months, market }
        });
        return response.data;
    },

    // 多指數 Rebase 比較（大盤指數功能規劃書 FR-IDX-06）
    async compare(codes, period = 'daily', months = 12) {
        const response = await apiClient.get('/indices/compare', {
            params: { codes: codes.join(','), period, months }
        });
        return response.data;
    },

    // 類股指數當日表現排行／輪動（FR-IDX-30/31）
    async getSectors(market = 'tw') {
        const response = await apiClient.get('/indices/sectors', { params: { market } });
        return response.data;
    },

    // 手動觸發指數資料同步
    async triggerSync(codes = null, market = null, months = null, mode = 'incremental') {
        const response = await apiClient.post('/indices/sync', { codes, market, months, mode });
        return response.data;
    }
};
