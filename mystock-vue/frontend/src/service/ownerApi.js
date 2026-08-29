import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';

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

export const ownerApi = {
    async login(password) {
        const response = await privateApiClient.post('/auth/session', { password });
        if (!response.data.success) {
            const error = new Error(response.data.error?.message || '登入失敗');
            error.code = response.data.error?.code;
            throw error;
        }
        return response.data.data;
    },

    async logout() {
        return unwrap(privateApiClient.delete('/auth/session'));
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