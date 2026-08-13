import { apiClient } from '@/service/stockApi';

export const alertApi = {
    // 查詢警示清單（均線策略警示系統 設計文件第 6.2 節）
    async getAlerts({ market, days = 7, strategy, symbol, strength } = {}) {
        const params = { days };
        if (market) params.market = market;
        if (strategy) params.strategy = strategy;
        if (symbol) params.symbol = symbol;
        if (strength) params.strength = strength;
        const response = await apiClient.get('/alerts', { params });
        return response.data;
    },

    // 今日策略摘要（均線策略警示系統 設計文件第 6.3 節）
    async getAlertsSummary({ market, date } = {}) {
        const params = {};
        if (market) params.market = market;
        if (date) params.date = date;
        const response = await apiClient.get('/alerts/summary', { params });
        return response.data;
    },

    // 手動觸發全市場掃描（均線策略警示系統 設計文件第 6.4 節）
    async triggerScan(market = 'tw', lookbackDays = null) {
        const response = await apiClient.post('/alerts/scan', { market, lookback_days: lookbackDays });
        return response.data;
    },

    // 取得目前生效之策略清單（供篩選器建立選項用）
    async getStrategies(market = null) {
        const params = {};
        if (market) params.market = market;
        const response = await apiClient.get('/strategies', { params });
        return response.data;
    }
};
