// 整合訊息通知平台 API 封裝（對照系統開發規格書 §6.2、§9.4）。
// 管理端與個人投資功能共用 Owner Session；自助端仍使用獨立的 ns_session Cookie。
import { ownerApi, privateApiClient as client } from '@/service/ownerApi';

async function unwrap(promise) {
    const res = await promise;
    return res.data.data;
}

export const notifyApi = {
    session: ownerApi,

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
        createSlackEndpoint: (code, address, opts = {}) =>
            unwrap(client.post(`/notify/recipients/${code}/endpoints/slack`, { address, ...opts })),
        createSlackEndpoint: (code, address, opts = {}) =>
            unwrap(client.post(`/notify/recipients/${code}/endpoints/slack`, { address, ...opts })),
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
