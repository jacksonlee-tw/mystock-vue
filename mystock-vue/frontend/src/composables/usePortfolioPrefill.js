// 觀察名單「登錄買進」捷徑跨頁帶資料用的輕量橋接（設計文件 §五）。
// WatchlistView.vue 導到 /portfolio/transactions 前把預帶資料塞進這個模組級單例，
// TransactionList.vue 進頁時讀取＋清空，避免用 query string 傳整包表單資料。
import { ref } from 'vue';

const pendingTx = ref(null); // { market, symbol, name, price, watchId }

export function usePortfolioPrefill() {
    function setPendingTransaction(data) {
        pendingTx.value = data;
    }
    function consumePendingTransaction() {
        const v = pendingTx.value;
        pendingTx.value = null;
        return v;
    }
    return { setPendingTransaction, consumePendingTransaction };
}
