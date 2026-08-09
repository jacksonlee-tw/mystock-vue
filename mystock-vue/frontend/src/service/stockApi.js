import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';

const apiClient = axios.create({
    baseURL: API_BASE,
    headers: {
        'Content-Type': 'application/json'
    },
    timeout: 15000
});

export const stockApi = {
    // 取得所有可用股票資料庫與元資料
    async getAvailableStocks() {
        const response = await apiClient.get('/stocks');
        return response.data;
    },

    // 取得熱力圖資料
    async getHeatmapData(period = 'daily') {
        const response = await apiClient.get('/stocks/heatmap', {
            params: { period }
        });
        return response.data;
    },

    // 取得目前追蹤的股票清單
    async getTrackedStocks() {
        const response = await apiClient.get('/stocks/tracked');
        return response.data;
    },

    // 新增追蹤股票代號
    async addTrackedStock(stockId) {
        const response = await apiClient.post('/stocks/tracked', { stock_id: stockId });
        return response.data;
    },

    // 刪除追蹤股票代號
    async removeTrackedStock(stockId) {
        const response = await apiClient.delete(`/stocks/tracked/${stockId}`);
        return response.data;
    },

    // 取得圖表專用格式數據
    async getChartData(stockId, period = 'daily', months = 3) {
        const response = await apiClient.get(`/stocks/${stockId}/chart-data`, {
            params: { period, months }
        });
        return response.data;
    },

    // 取得股票明細數據
    async getStockDetail(stockId, period = 'daily', months = 3) {
        const response = await apiClient.get(`/stocks/${stockId}`, {
            params: { period, months }
        });
        return response.data;
    },

    // 觸發證交所資料抓取
    async triggerFetch(stocks = null, months = null) {
        const response = await apiClient.post('/fetch/trigger', { stocks, months });
        return response.data;
    },

    // 查詢抓取狀態
    async getFetchStatus() {
        const response = await apiClient.get('/fetch/status');
        return response.data;
    }
};
