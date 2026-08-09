import { ref, onMounted, onUnmounted } from 'vue';
import { stockApi } from '@/service/stockApi';

const isRunning = ref(false);
const fetchStatus = ref(null);
let listenerCount = 0;
let pollTimer = null;

async function checkStatus() {
    try {
        const res = await stockApi.getFetchStatus();
        if (res && res.success && res.data) {
            fetchStatus.value = res.data;
            isRunning.value = !!res.data.is_running || res.data.status === 'running';
        }
    } catch (err) {
        console.error('Failed to query crawler status:', err);
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
