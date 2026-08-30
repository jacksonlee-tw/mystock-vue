import { ref, onMounted, onUnmounted } from 'vue';
import { stockApi } from '@/service/stockApi';

const isRunning = ref(false);
const fetchStatus = ref(null);
let listenerCount = 0;
let pollTimer = null;

let isFetching = false;

async function checkStatus() {
    if (isFetching) return;
    isFetching = true;
    try {
        const res = await stockApi.getFetchStatus({ timeout: 5000 });
        if (res && res.success && res.data) {
            fetchStatus.value = res.data;
            isRunning.value = !!res.data.is_running || res.data.status === 'running';
        }
    } catch (err) {
        // 防止輪詢時因網路延遲或逾時造成控制台洗版
        if (import.meta.env.DEV && err?.code !== 'ECONNABORTED') {
            console.warn('Query crawler status warning:', err?.message || err);
        }
    } finally {
        isFetching = false;
    }
}

function startPolling(intervalMs = 2000) {
    if (!pollTimer) {
        checkStatus();
        pollTimer = setInterval(checkStatus, intervalMs);
    }
}

function stopPolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

export function useCrawlerStatus() {
    onMounted(() => {
        listenerCount++;
        if (listenerCount === 1) {
            startPolling();
        }
    });

    onUnmounted(() => {
        listenerCount--;
        if (listenerCount <= 0) {
            listenerCount = 0;
            stopPolling();
        }
    });

    return {
        isRunning,
        fetchStatus,
        checkStatus
    };
}
