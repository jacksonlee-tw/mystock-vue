import { computed, reactive } from 'vue';

const layoutConfig = reactive({
    preset: 'Aura',
    primary: 'tech-blue', // 對應 assets/layout/variables/_accent-themes.scss 的預設主題色（深藍色系）
    surface: null,
    darkTheme: true, // 預設深色模式，搭配 tech-blue 呈現深藍色系
    menuMode: 'static'
});

const layoutState = reactive({
    staticMenuDesktopInactive: true, // 選單展開/收起選單
    overlayMenuActive: false,
    profileSidebarVisible: false,
    configSidebarVisible: false,
    staticMenuMobileActive: false,
    menuHoverActive: false,
    activeMenuItem: null
});

// 外觀個人化設定（主題色／中性色調／深色模式）存在瀏覽器的 localStorage，
// 下次用同一台瀏覽器打開就會自動套用，不用重選。這是純前端 SPA、沒有登入系統，
// 沒有「使用者帳號」可以綁定伺服器端設定，localStorage 是唯一合理的持久化方式——
// 只在「這台電腦、這個瀏覽器」生效，換瀏覽器或清瀏覽器資料就會回到預設值。
const APPEARANCE_STORAGE_KEY = 'mystock-appearance';

function loadPersistedAppearance() {
    try {
        const raw = localStorage.getItem(APPEARANCE_STORAGE_KEY);
        if (!raw) return;
        const saved = JSON.parse(raw);
        if (saved.primary) layoutConfig.primary = saved.primary;
        if (saved.surface) layoutConfig.surface = saved.surface;
        if (typeof saved.darkTheme === 'boolean') layoutConfig.darkTheme = saved.darkTheme;
    } catch (err) {
        console.warn('讀取外觀設定失敗，改用預設值:', err);
    }
}

function persistAppearance() {
    try {
        localStorage.setItem(
            APPEARANCE_STORAGE_KEY,
            JSON.stringify({
                primary: layoutConfig.primary,
                surface: layoutConfig.surface,
                darkTheme: layoutConfig.darkTheme
            })
        );
    } catch (err) {
        console.warn('儲存外觀設定失敗:', err);
    }
}

// 把目前的 layoutConfig 套到 <html> 上——實際套用主題的地方一律是純 CSS 選擇器
// （[data-accent]、[data-surface]、.app-dark），理由見 _accent-themes.scss /
// _surface-tones.scss 開頭說明，這裡只負責同步屬性，不直接處理顏色。
function applyAppearanceToDom() {
    document.documentElement.classList.toggle('app-dark', layoutConfig.darkTheme);
    document.documentElement.setAttribute('data-accent', layoutConfig.primary);
    if (layoutConfig.surface) {
        document.documentElement.setAttribute('data-surface', layoutConfig.surface);
    } else {
        document.documentElement.removeAttribute('data-surface');
    }
}

// layoutConfig／layoutState 是模組層級單例，這兩行只會在模組第一次被 import 時執行一次，
// 不管有幾個元件呼叫 useLayout()，確保「回復設定」只做一次、且越早越好（避免畫面先閃一下預設主題）。
loadPersistedAppearance();
applyAppearanceToDom();

export function useLayout() {
    const setActiveMenuItem = (item) => {
        layoutState.activeMenuItem = item.value || item;
    };

    const toggleDarkMode = () => {
        if (!document.startViewTransition) {
            executeDarkModeToggle();

            return;
        }

        document.startViewTransition(() => executeDarkModeToggle(event));
    };

    const executeDarkModeToggle = () => {
        layoutConfig.darkTheme = !layoutConfig.darkTheme;
        document.documentElement.classList.toggle('app-dark');
        persistAppearance();
    };

    const setAccent = (name) => {
        layoutConfig.primary = name;
        document.documentElement.setAttribute('data-accent', name);
        persistAppearance();
    };

    const setSurface = (name) => {
        layoutConfig.surface = name;
        document.documentElement.setAttribute('data-surface', name);
        persistAppearance();
    };

    const toggleMenu = () => {
        if (layoutConfig.menuMode === 'overlay') {
            layoutState.overlayMenuActive = !layoutState.overlayMenuActive;
        }

        if (window.innerWidth > 991) {
            layoutState.staticMenuDesktopInactive = !layoutState.staticMenuDesktopInactive;
        } else {
            layoutState.staticMenuMobileActive = !layoutState.staticMenuMobileActive;
        }
    };

    const isSidebarActive = computed(() => layoutState.overlayMenuActive || layoutState.staticMenuMobileActive);

    const isDarkTheme = computed(() => layoutConfig.darkTheme);

    const getPrimary = computed(() => layoutConfig.primary);

    const getSurface = computed(() => layoutConfig.surface);

    return {
        layoutConfig,
        layoutState,
        toggleMenu,
        isSidebarActive,
        isDarkTheme,
        getPrimary,
        getSurface,
        setActiveMenuItem,
        toggleDarkMode,
        setAccent,
        setSurface
    };
}
