// 追蹤與觀察名單的自訂標籤：色票對照 + 全站共用清單快取（見
// docs/14.追蹤個股清單優化/追蹤與觀察名單整合_規劃書.md §6.3）。
//
// 比照 useMarket.js 的 singleton 寫法：模組層級的 ref 讓所有引用共用同一份快取，避免每個用到
// tag 篩選/自動完成的元件（清單頁、快速加入對話框）各自重複打一次 GET /watchlist/tags。
import { ref } from 'vue';
import { portfolioApi } from '@/service/portfolioApi';

// 後端 watchlist_tag.color 是自由字串 key（見 V12 migration），這裡對應到 Tailwind 色票 class；
// 未知色一律退回 slate，不讓畫面因為舊資料帶著未列出的顏色值而爆版。
const TAG_COLOR_CLASSES = {
    slate: 'bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300',
    violet: 'bg-violet-100 dark:bg-violet-500/20 text-violet-700 dark:text-violet-300',
    amber: 'bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300',
    emerald: 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300',
    rose: 'bg-rose-100 dark:bg-rose-500/20 text-rose-700 dark:text-rose-300',
    sky: 'bg-sky-100 dark:bg-sky-500/20 text-sky-700 dark:text-sky-300'
};

export const TAG_COLOR_OPTIONS = Object.keys(TAG_COLOR_CLASSES);

export function tagColorClass(color) {
    return TAG_COLOR_CLASSES[color] || TAG_COLOR_CLASSES.slate;
}

const tags = ref([]);
const loading = ref(false);
let loaded = false;

async function refresh() {
    loading.value = true;
    try {
        const res = await portfolioApi.getWatchlistTags();
        if (res.success) tags.value = res.data;
        loaded = true;
    } finally {
        loading.value = false;
    }
}

export function useWatchlistTags() {
    if (!loaded && !loading.value) refresh();
    return { tags, loading, refresh };
}
