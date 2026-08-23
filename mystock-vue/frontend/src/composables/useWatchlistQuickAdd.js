// 全站共用的「加入追蹤與觀察名單」快速入口（原「加入觀察名單」，整合擴充見
// docs/14.追蹤個股清單優化/追蹤與觀察名單整合_規劃書.md §6.3）。
//
// 比照 PrimeVue Toast/ConfirmDialog 的單例模式：任何頁面呼叫 openQuickAdd() 更新這裡的共享狀態，
// 唯一一個 <WatchlistQuickAddDialog /> 掛在 App.vue 監看並彈出，避免每個入口各自維護一份表單/API 呼叫邏輯。
//
// editId 非 null 時代表「編輯既有清單項目」（例如 WatchlistStarButton 對已在清單中的股票再次點擊，
// 或其他頁面加入後透過 toast 動作鈕「補充原因／標籤」開啟），對話框會改呼叫 PUT 而非 POST。
import { reactive } from 'vue';

const state = reactive({
    visible: false,
    editId: null,
    market: 'tw',
    symbol: '',
    name: '',
    price: null, // 現有報價，用來預帶目標買進價；未知時為 null
    note: '',
    tags: []
});

export function useWatchlistQuickAdd() {
    function openQuickAdd({ market, symbol, name, price = null, note = '', tags = [], editId = null }) {
        Object.assign(state, { visible: true, editId, market, symbol, name: name || symbol, price, note, tags });
    }
    return { state, openQuickAdd };
}
