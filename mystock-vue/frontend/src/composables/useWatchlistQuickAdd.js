// 全站共用的「加入觀察名單」快速入口（設計文件 §五：個股頁面／列表提供「加入觀察」按鈕，
// 一鍵標記想買股票，無需先建立交易紀錄）。
//
// 比照 PrimeVue Toast/ConfirmDialog 的單例模式：任何頁面呼叫 openQuickAdd() 更新這裡的共享狀態，
// 唯一一個 <WatchlistQuickAddDialog /> 掛在 App.vue 監看並彈出，避免每個入口各自維護一份表單/API 呼叫邏輯。
import { reactive } from 'vue';

const state = reactive({
    visible: false,
    market: 'tw',
    symbol: '',
    name: '',
    price: null // 現有報價，用來預帶目標買進價；未知時為 null
});

export function useWatchlistQuickAdd() {
    function openQuickAdd({ market, symbol, name, price = null }) {
        Object.assign(state, { visible: true, market, symbol, name: name || symbol, price });
    }
    return { state, openQuickAdd };
}
