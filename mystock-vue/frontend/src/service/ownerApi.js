import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:18888/api/v1';

export const privateApiClient = axios.create({
    baseURL: API_BASE,
    headers: { 'Content-Type': 'application/json' },
    timeout: 15000,
    withCredentials: true
});

privateApiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        const payload = error.response?.data;
        const wrapped = new Error(payload?.error?.message || payload?.detail || error.message || '請求失敗');
        wrapped.code = payload?.error?.code;
        wrapped.status = error.response?.status;
        return Promise.reject(wrapped);
    }
);

async function unwrap(promise) {
    const response = await promise;
    return response.data.data;
}

// 登入／登出成功時廣播，讓 useTrackingList.js 等「記住未登入、不再重打註定 401 的請求」的快取
// 得以重置，下次掛載才會重新嘗試（避免耦合成直接互相 import，見該檔案內的說明）。
function notifyAuthChanged() {
    if (typeof window !== 'undefined') window.dispatchEvent(new Event('owner-auth-changed'));
}

export const ownerApi = {
    async login(password) {
        const response = await privateApiClient.post('/auth/session', { password });
        if (!response.data.success) {
            const error = new Error(response.data.error?.message || '登入失敗');
            error.code = response.data.error?.code;
            throw error;
        }
        notifyAuthChanged();
        return response.data.data;
    },

    async logout() {
        const result = await unwrap(privateApiClient.delete('/auth/session'));
        notifyAuthChanged();
        return result;
    },

    async changePassword(currentPassword, newPassword) {
        const response = await privateApiClient.put('/auth/password', {
            current_password: currentPassword,
            new_password: newPassword
        });
        if (!response.data.success) {
            const error = new Error(response.data.error?.message || '密碼變更失敗');
            error.code = response.data.error?.code;
            throw error;
        }
        return response.data.data;
    },

    async whoami() {
        try {
            await privateApiClient.get('/auth/session');
            return true;
        } catch {
            return false;
        }
    }
};