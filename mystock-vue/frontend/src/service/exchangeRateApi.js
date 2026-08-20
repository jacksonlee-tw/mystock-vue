// 每日匯率（USD/JPY/CNY，backend/services/exchange_rate_fetcher.py），比照 portfolioApi.js 共用 apiClient。
import { apiClient } from '@/service/stockApi';

export const exchangeRateApi = {
    // 取得最新一筆 USD/JPY/CNY 即期匯率，供「股票與爬蟲管理」頁的匯率卡片
    async getLatest() {
        const response = await apiClient.get('/exchange-rates/latest');
        return response.data;
    },

    // 立即觸發台灣銀行牌告匯率抓取（單次同步請求，無需長輪詢進度）
    async trigger() {
        const response = await apiClient.post('/exchange-rates/trigger');
        return response.data;
    }
};
