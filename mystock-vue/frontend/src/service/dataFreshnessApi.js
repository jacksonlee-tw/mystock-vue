// 登入首頁自動補抓（見 docs/19.登入自動補抓資料/登入自動補抓資料_規劃書.md §3.6）。
// 兩支端點都需要擁有者授權，沿用 ownerApi.js 已設好 withCredentials 的 privateApiClient。
import { privateApiClient } from '@/service/ownerApi';

export const dataFreshnessApi = {
    // market 省略 = 後端回傳所有啟用市場的報告
    async getReport(market) {
        const params = market ? { market } : {};
        const response = await privateApiClient.get('/data-freshness', { params });
        return response.data;
    },

    async catchUp({ markets, force = false } = {}) {
        const response = await privateApiClient.post('/data-freshness/catch-up', { markets, force });
        return response.data;
    }
};
