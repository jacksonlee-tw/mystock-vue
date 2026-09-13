import { apiClient } from '@/service/stockApi';

// Phase4-輕量化新聞輿情與總經監控.md §8／§11：總經指標與大盤位階查詢。
export const macroApi = {
    // 全部總經指標目前可見的最新值（point-in-time 對齊，只回傳 release_date <= 今天的紀錄）
    async getIndicators() {
        const response = await apiClient.get('/macro/indicators');
        return response.data;
    },

    // 大盤指數 20MA/60MA 位階（§5.2 全域鎖底層查詢）
    async getMarketRegime(market = 'tw') {
        const response = await apiClient.get(`/macro/market-regime/${market}`);
        return response.data;
    },

    // 單一總經指標的近期已公布序列，供 Sparkline 使用（§11）
    async getIndicatorSeries(indicatorCode, limit = 30) {
        const response = await apiClient.get(`/macro/indicators/${indicatorCode}/series`, { params: { limit } });
        return response.data;
    }
};
