// 全站共用的個股搜尋面板（Omnibox）開關（docs/18.個人化首頁/）。
//
// 比照 useWatchlistQuickAdd.js 的單例對話框模式：唯一一個 <Omnibox /> 掛在 AppTopbar，
// 任何頁面（首頁的大搜尋框、topbar 按鈕、Ctrl+K）都透過這裡的共享狀態開啟它，
// 不需要各自重寫一套搜尋 UI 與 suggestSymbols 呼叫。
//
// initialQuery 讓首頁的搜尋框可以「使用者打第一個字就接手」——把已輸入的字串交棒給 Omnibox，
// 使用者不必因為面板彈出而重打一次。
import { reactive } from 'vue';

const state = reactive({
    visible: false,
    initialQuery: ''
});

export function useOmnibox() {
    function openOmnibox(initialQuery = '') {
        state.initialQuery = initialQuery;
        state.visible = true;
    }
    return { state, openOmnibox };
}
