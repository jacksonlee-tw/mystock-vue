import { apiClient } from '@/service/stockApi';

// 產業鏈知識圖譜與輪動模型（docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §7）
export const industryChainApi = {
    // 列出所有產業鏈（YAML 骨架 + 邊數量統計）
    async listChains() {
        const response = await apiClient.get('/industry-chains');
        return response.data;
    },

    // 該鏈的節點與邊（Node-Edge JSON，供力導向圖使用）
    async getChainGraph(chainId) {
        const response = await apiClient.get(`/industry-chains/${chainId}/graph`);
        return response.data;
    },

    // 該標的與其上下游的 CCF 時差曲線
    async getSymbolLeadLag(symbol) {
        const response = await apiClient.get(`/industry-chains/${symbol}/lead-lag`);
        return response.data;
    },

    // 輪動外溢雷達清單（chainId 省略則跨全部鏈彙整）
    async getSpilloverRadar(chainId = null) {
        const params = {};
        if (chainId) params.chain_id = chainId;
        const response = await apiClient.get('/industry-chains/spillover-radar', { params });
        return response.data;
    },

    // 手動觸發 LLM 產業鏈萃取（單鏈或全部）
    async triggerExtract({ chainId = null, provider = null, model = null } = {}) {
        const response = await apiClient.post('/industry-chains/extract/trigger', {
            chain_id: chainId,
            provider,
            model
        });
        return response.data;
    },

    // 產業鏈骨架設定（「管理產業鏈」維護對話框用，純讀寫 YAML，不受總開關限制）
    async getChainsConfig() {
        const response = await apiClient.get('/industry-chains/config');
        return response.data;
    },

    // 整份覆寫骨架設定：items 為完整清單（新增/編輯/刪除都是送整份清單）
    async saveChainsConfig(items) {
        const response = await apiClient.put('/industry-chains/config', { items });
        return response.data;
    }
};
