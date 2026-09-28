// 「最近瀏覽個股」記錄（docs/18.個人化首頁/）。
//
// 為什麼放 localStorage 而不是後端：本系統為單一擁有者、無使用者表（見 V14 migration 對
// activity_log.created_by 的註解），也沒有通用偏好儲存表。最近瀏覽純屬瀏覽器端的便利功能，
// 不值得為它開一張表或一個端點，取捨與 useHomeWidgets.js 一致。
//
// 模組層單例：StockDashboard 寫入、首頁讀取，兩邊看到的是同一份 ref，不需要事件或輪詢。
import { ref } from 'vue';

const STORAGE_KEY = 'mystock.recentStocks';
const MAX_ITEMS = 12;

function load() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return [];
        return parsed.filter((it) => it && it.market && it.symbol).slice(0, MAX_ITEMS);
    } catch {
        return [];
    }
}

const recent = ref(load());

export function useRecentStocks() {
    /**
     * 記錄一次瀏覽。呼叫端應在「資料成功載入、拿得到股票名稱之後」才呼叫，
     * 不要在 route 變更的當下就記——否則使用者手打錯的代號也會被記進清單。
     */
    function record({ market, symbol, name }) {
        if (!market || !symbol) return;
        const key = `${market}:${symbol}`;
        const next = [
            { market, symbol, name: name || symbol, ts: Date.now() },
            ...recent.value.filter((it) => `${it.market}:${it.symbol}` !== key)
        ].slice(0, MAX_ITEMS);
        recent.value = next;
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        } catch {
            // 寫不進去不影響這一輪的顯示
        }
    }

    function clear() {
        recent.value = [];
        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch {
            /* 同上 */
        }
    }

    return { recent, record, clear };
}
