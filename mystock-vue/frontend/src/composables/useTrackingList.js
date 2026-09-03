// 全站共用的「追蹤與觀察名單」快取（見
// docs/14.追蹤個股清單優化/追蹤與觀察名單整合_規劃書.md §6.3）。
//
// 用途：WatchlistStarButton 等一鍵加入入口用來判斷「這檔股票是否已加入清單」，並在各頁加入／編輯
// 後即時反映，不必整頁重新整理。比照 useWatchlistQuickAdd.js 的模組層級單例寫法。
import { reactive } from 'vue';
import { portfolioApi } from '@/service/portfolioApi';

// key: "market:SYMBOL" -> watchlist item
const itemsBySymbol = reactive(new Map());
const loadedMarkets = new Set();
// 未登入擁有者時 GET /watchlist 一律 401（core/owner_auth.py require_owner）：熱力圖／產業鏈頁面
// 一次掛載就有十幾顆 WatchlistStarButton，若每顆都各自重打一次註定失敗的請求，會在後端 access log
// 洗版一堆 401。記住「這個市場目前打不通」，掛載時直接跳過，不再重送；登入/登出時 ownerApi 會
// dispatch 'owner-auth-changed'，下面監聽到就清掉，讓下次掛載重新嘗試。
const deniedMarkets = new Set();
const inFlight = new Map(); // market -> Promise，避免同市場同時多個星號按鈕掛載時發出重複請求

function cacheKey(market, symbol) {
    return `${market}:${String(symbol || '').toUpperCase()}`;
}

async function refresh(market) {
    const existing = inFlight.get(market);
    if (existing) return existing; // 已有同市場的請求在飛行中，直接搭便車等它完成

    const promise = (async () => {
        try {
            const res = await portfolioApi.getWatchlist({ market });
            if (!res.success) return;
            // 只替換該市場既有的快取項目，不影響其他市場已載入的資料
            for (const k of [...itemsBySymbol.keys()]) {
                if (k.startsWith(`${market}:`)) itemsBySymbol.delete(k);
            }
            res.data.forEach((item) => itemsBySymbol.set(cacheKey(item.market, item.symbol), item));
            loadedMarkets.add(market);
            deniedMarkets.delete(market);
        } catch (err) {
            // 快取載入失敗不阻斷頁面，星號按鈕退回「未加入」的保守顯示，使用者仍可正常點擊加入
            if (err?.status === 401 || err?.response?.status === 401) deniedMarkets.add(market);
        } finally {
            inFlight.delete(market);
        }
    })();
    inFlight.set(market, promise);
    return promise;
}

function ensureLoaded(market) {
    if (loadedMarkets.has(market) || deniedMarkets.has(market)) return Promise.resolve();
    return refresh(market);
}

if (typeof window !== 'undefined') {
    window.addEventListener('owner-auth-changed', () => deniedMarkets.clear());
}

function has(market, symbol) {
    return itemsBySymbol.has(cacheKey(market, symbol));
}

function get(market, symbol) {
    return itemsBySymbol.get(cacheKey(market, symbol)) || null;
}

export function useTrackingList() {
    return { itemsBySymbol, refresh, ensureLoaded, has, get };
}
