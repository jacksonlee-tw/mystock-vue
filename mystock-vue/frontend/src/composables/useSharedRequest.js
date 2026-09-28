// 讓「同一時間、同一參數」的請求只真的送出一次（docs/18.個人化首頁/）。
//
// 首頁上多個 panel 會各自抓同一份資料（例如「快速查找」與「我的部位」都要持股與觀察名單）。
// 各 panel 刻意自帶資料抓取、彼此不依賴，所以重複請求改在這一層去除：飛行中的請求直接共用同一個
// Promise，完成後即刻清除——不是快取，下一次呼叫（例如切換市場）仍會取得最新資料。
const pending = new Map();

export function shareRequest(key, factory) {
    const existing = pending.get(key);
    if (existing) return existing;
    const promise = factory().finally(() => pending.delete(key));
    pending.set(key, promise);
    return promise;
}
