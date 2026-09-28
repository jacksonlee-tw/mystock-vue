// 個人化首頁的 widget 勾選狀態（docs/18.個人化首頁/）。
//
// 比照 useMarket.js 的模組層單例作法：狀態定義在模組作用域，每次呼叫 useHomeWidgets() 拿到的
// 都是同一份 ref，HomeView 與設定彈窗共用，不需要 provide/inject 或 store。
//
// 為什麼存「停用清單」而不是「啟用清單」：未來新增 widget 時，舊使用者的 localStorage 裡不會有
// 新 id。存啟用清單的話新 widget 會因為「不在清單中」而被判定為關閉，使用者永遠看不到它；
// 存停用清單則是「不在清單中 = 啟用」，新 widget 自動出現，這才是預期行為。
import { computed, ref } from 'vue';

const STORAGE_KEY = 'mystock.homeWidgets';

// section 用來在設定彈窗分組，順序即首頁上的呈現順序。
export const WIDGET_REGISTRY = [
    { id: 'quick-search', label: '快速搜尋', section: '快速查找', icon: 'pi-search', requiresOwner: false },
    { id: 'recent-stocks', label: '最近瀏覽', section: '快速查找', icon: 'pi-history', requiresOwner: false },
    { id: 'my-shortcuts', label: '我的持股／追蹤捷徑', section: '快速查找', icon: 'pi-star', requiresOwner: true },

    { id: 'macro-banner', label: '總經燈號', section: '今日盤勢', icon: 'pi-globe', requiresOwner: false },
    { id: 'index-overview', label: '大盤指數', section: '今日盤勢', icon: 'pi-chart-bar', requiresOwner: false },
    { id: 'watchlist-heatmap', label: '追蹤清單今日表現', section: '今日盤勢', icon: 'pi-th-large', requiresOwner: false },

    { id: 'alerts-summary', label: '今日警示摘要', section: '訊號與推薦', icon: 'pi-bell', requiresOwner: false },
    { id: 'stock-picking', label: '選股／強勢訊號推薦', section: '訊號與推薦', icon: 'pi-filter', requiresOwner: false },
    { id: 'war-room', label: 'AI 戰情室評等', section: '訊號與推薦', icon: 'pi-shield', requiresOwner: true },

    { id: 'portfolio-kpi', label: '帳戶 KPI', section: '我的部位', icon: 'pi-wallet', requiresOwner: true },
    { id: 'holdings-top', label: '持股前五', section: '我的部位', icon: 'pi-briefcase', requiresOwner: true },
    { id: 'watchlist-target', label: '到價提醒', section: '我的部位', icon: 'pi-flag', requiresOwner: true },
    { id: 'risk-alerts', label: '出場風控警示', section: '我的部位', icon: 'pi-exclamation-triangle', requiresOwner: true }
];

export const WIDGET_SECTIONS = [...new Set(WIDGET_REGISTRY.map((w) => w.section))];

const WIDGET_BY_ID = new Map(WIDGET_REGISTRY.map((w) => [w.id, w]));
const VALID_IDS = new Set(WIDGET_BY_ID.keys());

// localStorage 在無痕視窗、封鎖 site data 的情境下連讀取都可能直接丟例外，
// 不是只有回傳 null，所以每一次存取都要包起來、失敗時安靜退回預設值。
function loadDisabled() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        // 過濾掉已被移除的舊 widget id，避免殘留資料一直佔著空間
        return Array.isArray(parsed) ? parsed.filter((id) => VALID_IDS.has(id)) : [];
    } catch {
        return [];
    }
}

function persist(ids) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
    } catch {
        // 存不進去就算了，這一輪的勾選仍然生效，只是重新整理後會回到預設
    }
}

const disabledIds = ref(loadDisabled());

export function useHomeWidgets() {
    const disabledSet = computed(() => new Set(disabledIds.value));

    function isEnabled(id) {
        return !disabledSet.value.has(id);
    }

    function toggle(id, enabled) {
        const next = new Set(disabledIds.value);
        if (enabled) next.delete(id);
        else next.add(id);
        disabledIds.value = [...next];
        persist(disabledIds.value);
    }

    function resetAll() {
        disabledIds.value = [];
        persist(disabledIds.value);
    }

    /**
     * 這個 widget 此刻是否真的會渲染：已勾選，且（需登入者）已登入。
     * 未登入時需登入的 widget 不會渲染，若區段標題只看「勾選」就會出現只剩標題的空區塊。
     */
    function isVisible(id, ownerAuthenticated) {
        const w = WIDGET_BY_ID.get(id);
        return !!w && isEnabled(id) && (!w.requiresOwner || ownerAuthenticated);
    }

    /** 某個 section 目前還有沒有任何會渲染的 widget——用來決定要不要渲染該區段的標題列。 */
    function hasEnabledIn(section, ownerAuthenticated = true) {
        return WIDGET_REGISTRY.some((w) => w.section === section && isVisible(w.id, ownerAuthenticated));
    }

    /** 目前會渲染的 widget 數量，用來判斷是否整頁空白。 */
    function visibleCount(ownerAuthenticated) {
        return WIDGET_REGISTRY.filter((w) => isVisible(w.id, ownerAuthenticated)).length;
    }

    /** 有沒有「已勾選、但需要登入」的 widget——未登入時用來決定要不要顯示登入提示卡。 */
    const hasEnabledOwnerWidget = computed(() => WIDGET_REGISTRY.some((w) => w.requiresOwner && isEnabled(w.id)));

    const enabledCount = computed(() => WIDGET_REGISTRY.length - disabledIds.value.length);

    return {
        registry: WIDGET_REGISTRY, sections: WIDGET_SECTIONS, isEnabled, toggle, resetAll,
        hasEnabledIn, visibleCount, hasEnabledOwnerWidget, enabledCount
    };
}
