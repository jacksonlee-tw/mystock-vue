// 投資筆記（docs/8.個人投資記帳功能/個人投資筆記.md）。
import { privateApiClient as apiClient } from '@/service/ownerApi';

export const investmentNoteApi = {
    // status 預設後端為 'published'；帶 'all' 代表不篩選狀態（含草稿／已封存）
    async getNotes({ page, pageSize, dateFrom, dateTo, q, tag, market, symbol, status } = {}) {
        const params = {};
        if (page) params.page = page;
        if (pageSize) params.page_size = pageSize;
        if (dateFrom) params.date_from = dateFrom;
        if (dateTo) params.date_to = dateTo;
        if (q) params.q = q;
        if (tag) params.tag = tag;
        if (market) params.market = market;
        if (symbol) params.symbol = symbol;
        if (status) params.status = status;
        const response = await apiClient.get('/investment-notes', { params });
        return response.data;
    },

    async getNote(id) {
        const response = await apiClient.get(`/investment-notes/${id}`);
        return response.data;
    },

    async createNote(payload) {
        const response = await apiClient.post('/investment-notes', payload);
        return response.data;
    },

    async updateNote(id, payload) {
        const response = await apiClient.patch(`/investment-notes/${id}`, payload);
        return response.data;
    },

    async deleteNote(id) {
        const response = await apiClient.delete(`/investment-notes/${id}`);
        return response.data;
    },

    async getTags() {
        const response = await apiClient.get('/investment-notes/tags');
        return response.data;
    }
};
