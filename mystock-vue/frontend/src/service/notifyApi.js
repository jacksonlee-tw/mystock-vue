// 整合訊息通知平台 API 封裝（對照系統開發規格書 §6.2、§9.4）。
// 管理端／自助端都靠 Cookie 授權（require_owner / require_self_service），
// 因此這裡另外開一個帶 withCredentials 的 axios 實例，不共用 stockApi.js 的 apiClient
// （既有 apiClient 不需要帶 Cookie，維持原行為不變）。
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';

const client = axios.create({
    baseURL: API_BASE,
    headers: { 'Content-Type': 'application/json' },
    timeout: 15000,
    withCredentials: true
});

// 統一把後端的 {success:false, error:{code,message}} 轉成好讀的 Error，
// 呼叫端只需 try/catch 拿 err.message、err.code 即可，不用每處都檢查 res.success。
client.interceptors.response.use(
    (res) => res,
    (err) => {
        const payload = err.response?.data;
        const message = payload?.error?.message || err.message || '請求失敗';
        const wrapped = new Error(message);
        wrapped.code = payload?.error?.code;
        wrapped.status = err.response?.status;
        return Promise.reject(wrapped);
    }
);

async function unwrap(promise) {
    const res = await promise;
    return res.data.data;
}

export const notifyApi = {
    session: {
        async login(password) {
            const res = await client.post('/notify/session', { password });
            if (!res.data.success) {
                const e = new Error(res.data.error?.message || '登入失敗');
                e.code = res.data.error?.code;
                throw e;
            }
            return res.data.data;
        },
        async logout() {
            return unwrap(client.delete('/notify/session'));
        },
        async whoami() {
            try {
                await client.get('/notify/session');
                return true;
            } catch {
                return false;
            }
        }
    },

    admin: {
        // ── 管道 ──
        listChannels: () => unwrap(client.get('/notify/channels')),
        getChannel: (code) => unwrap(client.get(`/notify/channels/${code}`)),
        updateChannel: (code, settings) => unwrap(client.put(`/notify/channels/${code}`, { settings })),
        enableChannel: (code) => unwrap(client.post(`/notify/channels/${code}/enable`)),
        disableChannel: (code) => unwrap(client.post(`/notify/channels/${code}/disable`)),
        testChannel: (code) => unwrap(client.post(`/notify/channels/${code}/test`)),

        // ── 收件人 ──
        listRecipients: () => unwrap(client.get('/notify/recipients')),
        createRecipient: (displayName, groupCodes = []) =>
            unwrap(client.post('/notify/recipients', { display_name: displayName, group_codes: groupCodes })),
        updateRecipient: (code, updates) => unwrap(client.patch(`/notify/recipients/${code}`, updates)),
        disableRecipient: (code) => unwrap(client.delete(`/notify/recipients/${code}`)),
        getRecipientPreferences: (code) => unwrap(client.get(`/notify/recipients/${code}/preferences`)),
        updateCeiling: (code, ceiling) => unwrap(client.put(`/notify/recipients/${code}/ceiling`, ceiling)),
        issueSelfServiceLink: (code) => unwrap(client.post(`/notify/recipients/${code}/self-service-link`)),
        revokeSelfServiceLink: (code) => unwrap(client.delete(`/notify/recipients/${code}/self-service-link`)),

        // ── 端點 ──
        createEmailEndpoint: (code, address, opts = {}) =>
            unwrap(client.post(`/notify/recipients/${code}/endpoints/email`, { address, ...opts })),
        resendVerification: (code, endpointCode) =>
            unwrap(client.post(`/notify/recipients/${code}/endpoints/${endpointCode}/resend-verification`)),
        issueBindingCode: (code) => unwrap(client.post(`/notify/recipients/${code}/binding-code`)),
        issueGroupBindingCode: () => unwrap(client.post('/notify/binding-code/group')),
        listSharedEndpoints: () => unwrap(client.get('/notify/endpoints/shared')),
        updateEndpoint: (code, updates) => unwrap(client.patch(`/notify/endpoints/${code}`, updates)),
        testSend: (code) => unwrap(client.post(`/notify/endpoints/${code}/test-send`)),
        disableEndpoint: (code) => unwrap(client.post(`/notify/endpoints/${code}/disable`)),

        // ── 群組 ──
        listGroups: () => unwrap(client.get('/notify/groups')),
        createGroup: (groupName) => unwrap(client.post('/notify/groups', { group_name: groupName })),
        addGroupMember: (groupCode, recipientCode) =>
            unwrap(client.post(`/notify/groups/${groupCode}/members`, { recipient_code: recipientCode })),
        removeGroupMember: (groupCode, recipientCode) =>
            unwrap(client.delete(`/notify/groups/${groupCode}/members/${recipientCode}`)),

        // ── 訂閱規則 ──
        listSubscriptions: () => unwrap(client.get('/notify/subscriptions')),
        createSubscription: (payload) => unwrap(client.post('/notify/subscriptions', payload)),
        updateSubscription: (code, updates) => unwrap(client.patch(`/notify/subscriptions/${code}`, updates)),
        previewSubscription: (ruleCode, eventType, sampleFacts) =>
            unwrap(client.post('/notify/subscriptions/preview', {
                rule_code: ruleCode, event_type: eventType, sample_facts: sampleFacts
            })),

        // ── 模板 ──
        listTemplates: () => unwrap(client.get('/notify/templates')),
        getTemplate: (eventType, channel) => unwrap(client.get(`/notify/templates/${eventType}/${channel}`)),
        updateTemplate: (eventType, channel, payload) =>
            unwrap(client.put(`/notify/templates/${eventType}/${channel}`, payload)),
        getTemplateVariables: (eventType) => unwrap(client.get(`/notify/templates/variables/${eventType}`)),
        previewTemplate: (payload) => unwrap(client.post('/notify/templates/preview', payload)),

        // ── 發送紀錄 ──
        listMessages: (params = {}) => unwrap(client.get('/notify/messages', { params })),
        getMessage: (code) => unwrap(client.get(`/notify/messages/${code}`)),
        resendMessage: (code) => unwrap(client.post(`/notify/messages/${code}/resend`)),
        resendAllFailed: () => unwrap(client.post('/notify/messages/resend-failed')),
        stats: () => unwrap(client.get('/notify/stats')),

        // ── 稽核／測試 ──
        listAudit: (limit = 100) => unwrap(client.get('/notify/audit', { params: { limit } })),
        injectEvent: (payload) => unwrap(client.post('/notify/events', payload))
    },

    self: {
        me: () => unwrap(client.get('/notify/me')),
        updatePreferences: (updates) => unwrap(client.patch('/notify/me/preferences', updates)),
        updateEndpoint: (endpointCode, updates) => unwrap(client.patch(`/notify/me/endpoints/${endpointCode}`, updates)),
        pause: (days) => unwrap(client.post('/notify/me/pause', { days })),
        resume: () => unwrap(client.delete('/notify/me/pause')),
        unsubscribe: (scope, endpointCode = null) =>
            unwrap(client.post('/notify/me/unsubscribe', { scope, endpoint_code: endpointCode, confirm: true })),
        myMessages: () => unwrap(client.get('/notify/me/messages'))
    }
};
