import { apiClient } from '@/service/stockApi';

export const marketApi = {
    // 查詢全市場切片資料（支援分頁、篩選、排序）
    async getMarketDaily(params = {}) {
        const response = await apiClient.get('/market/daily', { params });
        return response.data;
    },

    // 取得有資料的交易日清單
    async getMarketDates(market = 'tw') {
        const response = await apiClient.get('/market/dates', { params: { market } });
        return response.data;
    },

    // 取得全市場資料庫狀態與健康指標
    async getMarketStatus(market = 'tw') {
        const response = await apiClient.get('/market/status', { params: { market } });
        return response.data;
    },

    // 手動觸發全市場回補與抓取
    async triggerMarketFetch(payload) {
        const response = await apiClient.post('/market/fetch', payload);
        return response.data;
    },

    // 取消全市場抓取作業
    async cancelMarketFetch() {
        const response = await apiClient.post('/market/fetch/cancel');
        return response.data;
    }
};
