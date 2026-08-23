// 個人投資記帳與績效追蹤模組（docs/8.個人投資記帳功能/），比照 stockApi.js/alertApi.js 共用 apiClient。
import { apiClient } from '@/service/stockApi';

export const portfolioApi = {
    // ── 交易紀錄 ──────────────────────────────────────────────
    async getTransactions({ market, side, keyword, dateFrom, dateTo } = {}) {
        const params = {};
        if (market) params.market = market;
        if (side) params.side = side;
        if (keyword) params.keyword = keyword;
        if (dateFrom) params.date_from = dateFrom;
        if (dateTo) params.date_to = dateTo;
        const response = await apiClient.get('/transactions', { params });
        return response.data;
    },

    async createTransaction(payload) {
        const response = await apiClient.post('/transactions', payload);
        return response.data;
    },

    async updateTransaction(id, payload) {
        const response = await apiClient.put(`/transactions/${id}`, payload);
        return response.data;
    },

    async deleteTransaction(id) {
        const response = await apiClient.delete(`/transactions/${id}`);
        return response.data;
    },

    async importTransactions({ file, csvText } = {}) {
        const form = new FormData();
        if (file) form.append('file', file);
        if (csvText) form.append('csv_text', csvText);
        const response = await apiClient.post('/transactions/import', form, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        return response.data;
    },

    // 匯出直接回傳 axios 的 Blob response，呼叫端負責觸發下載（見 TransactionList.vue）
    async exportTransactionsBlob({ market, side, keyword, dateFrom, dateTo } = {}) {
        const params = {};
        if (market) params.market = market;
        if (side) params.side = side;
        if (keyword) params.keyword = keyword;
        if (dateFrom) params.date_from = dateFrom;
        if (dateTo) params.date_to = dateTo;
        return apiClient.get('/transactions/export', { params, responseType: 'blob' });
    },

    // ── 持股與帳戶總覽 ─────────────────────────────────────────
    async getHoldings({ market, costMethod } = {}) {
        const params = {};
        if (market) params.market = market;
        if (costMethod) params.cost_method = costMethod;
        const response = await apiClient.get('/portfolio/holdings', { params });
        return response.data;
    },

    async getSummary() {
        const response = await apiClient.get('/portfolio/summary');
        return response.data;
    },

    // symbols 形如 ['tw:2330', 'us:AAPL']
    async getQuotes(symbols) {
        const response = await apiClient.get('/portfolio/quotes', { params: { symbols: symbols.join(',') } });
        return response.data;
    },

    // ── 已實現損益與績效 ───────────────────────────────────────
    async getRealized({ market, costMethod } = {}) {
        const params = {};
        if (market) params.market = market;
        if (costMethod) params.cost_method = costMethod;
        const response = await apiClient.get('/performance/realized', { params });
        return response.data;
    },

    async getHistory({ groupBy = 'month', market, costMethod } = {}) {
        const params = { group_by: groupBy };
        if (market) params.market = market;
        if (costMethod) params.cost_method = costMethod;
        const response = await apiClient.get('/performance/history', { params });
        return response.data;
    },

    async getReturns() {
        const response = await apiClient.get('/performance/returns');
        return response.data;
    },

    // ── 現金流與股利 ───────────────────────────────────────────
    async getDividends({ market } = {}) {
        const params = {};
        if (market) params.market = market;
        const response = await apiClient.get('/dividends', { params });
        return response.data;
    },

    async createDividend(payload) {
        const response = await apiClient.post('/dividends', payload);
        return response.data;
    },

    async deleteDividend(id) {
        const response = await apiClient.delete(`/dividends/${id}`);
        return response.data;
    },

    async getCashflows() {
        const response = await apiClient.get('/cashflow');
        return response.data;
    },

    async createCashflow(payload) {
        const response = await apiClient.post('/cashflow', payload);
        return response.data;
    },

    async deleteCashflow(id) {
        const response = await apiClient.delete(`/cashflow/${id}`);
        return response.data;
    },

    // ── 追蹤與觀察名單（原「觀察名單」，見 docs/14.追蹤個股清單優化/） ─────
    // tags: tag id 陣列（AND 語意）；hasTarget/crawlOnly 為 true/false 時才會帶入查詢字串
    async getWatchlist({ market, tags, q, hasTarget, crawlOnly, withCoverage } = {}) {
        const params = {};
        if (market) params.market = market;
        if (tags && tags.length) params.tags = (Array.isArray(tags) ? tags : [tags]).join(',');
        if (q) params.q = q;
        if (hasTarget !== undefined && hasTarget !== null) params.has_target = hasTarget;
        if (crawlOnly !== undefined && crawlOnly !== null) params.crawl_only = crawlOnly;
        if (withCoverage) params.with_coverage = true;
        const response = await apiClient.get('/watchlist', { params });
        return response.data;
    },

    async addWatchlist(payload) {
        const response = await apiClient.post('/watchlist', payload);
        return response.data;
    },

    async updateWatchlist(id, payload) {
        const response = await apiClient.put(`/watchlist/${id}`, payload);
        return response.data;
    },

    async setWatchlistCrawlEnabled(id, enabled) {
        const response = await apiClient.patch(`/watchlist/${id}/crawl`, { enabled });
        return response.data;
    },

    async removeWatchlist(id) {
        const response = await apiClient.delete(`/watchlist/${id}`);
        return response.data;
    },

    // ── 追蹤與觀察名單：自訂標籤 ────────────────────────────────
    async getWatchlistTags() {
        const response = await apiClient.get('/watchlist/tags');
        return response.data;
    },

    async createWatchlistTag(payload) {
        const response = await apiClient.post('/watchlist/tags', payload);
        return response.data;
    },

    async updateWatchlistTag(id, payload) {
        const response = await apiClient.put(`/watchlist/tags/${id}`, payload);
        return response.data;
    },

    async deleteWatchlistTag(id) {
        const response = await apiClient.delete(`/watchlist/tags/${id}`);
        return response.data;
    },

    // ── 記帳設定 ──────────────────────────────────────────────
    async getSettings() {
        const response = await apiClient.get('/settings');
        return response.data;
    },

    async updateSettings(payload) {
        const response = await apiClient.put('/settings', payload);
        return response.data;
    },

    // 代號查名稱：沿用既有跨市場代號搜尋（markets.py），不重造 SYMBOL_NAME_MAP
    async searchSymbol(q, market = null) {
        const params = { q };
        if (market) params.market = market;
        const response = await apiClient.get('/markets/search', { params });
        return response.data;
    }
};
