import { apiClient } from '@/service/stockApi';

// Phase4-輕量化新聞輿情與總經監控.md §8／§11：個股新聞與情緒查詢，僅台股有資料
// （後端 §1.3 明訂本階段僅支援 TW，呼叫端仍可傳 market，非台股後端一律回傳空清單）。
export const newsApi = {
    // 分頁查詢個股新聞與情緒評分
    async getNews(symbol, { market = 'tw', page = 1, pageSize = 20 } = {}) {
        const response = await apiClient.get(`/news/${symbol}`, {
            params: { market, page, page_size: pageSize }
        });
        return response.data;
    },

    // 5 日加權情緒分數與 Buzz Surge（§4.3）
    async getSentimentSummary(symbol, market = 'tw') {
        const response = await apiClient.get(`/news/${symbol}/sentiment-summary`, {
            params: { market }
        });
        return response.data;
    },

    // 目前納入的新聞/社群來源與啟用狀態（§11「來源開關可視性」：讓使用者知道新聞量
    // 是被白名單過濾過的結果，不是「新聞很少」的錯覺）
    async getSources() {
        const response = await apiClient.get('/news/sources');
        return response.data;
    }
};
