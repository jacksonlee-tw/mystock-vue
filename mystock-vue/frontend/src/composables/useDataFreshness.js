// 登入首頁自動補抓：前端狀態單例（見 docs/19.登入自動補抓資料/登入自動補抓資料_規劃書.md §3.6）。
// 模組層 singleton（不是每個元件各自一份）：DataFreshnessBar 掛載／卸載（登入登出）都共用同一份
// 節流與結果狀態，避免同一頁重複掛載時各自誤判「還沒檢查過」而各打一次。
import { ref } from 'vue';
import { dataFreshnessApi } from '@/service/dataFreshnessApi';

// 前端節流：同一分頁 10 分鐘內不重複呼叫（伺服器端另有 (market, expected_date) 節流鍵兜底，
// 這裡只是省掉多分頁重整時的重複請求，讀寫都包 try/catch，失敗就當沒節流）。
const SESSION_KEY = 'mystock.freshnessCheckedAt';
const THROTTLE_MS = 10 * 60 * 1000;

const result = ref(null); // { markets: { tw: {report, action, reason}, us: {...} }, fetch? }
const checking = ref(false);
const lastError = ref(null);
// 本次 ensureFresh() 是否有市場進入 triggered/fetch_running，需要等 useCrawlerStatus().isRunning
// 由 true 轉 false 時再讀一次報告並通知首頁刷新卡片。
const awaitingCompletion = ref(false);

function readSessionCheckedAt() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? Number(raw) : 0;
  } catch {
    return 0;
  }
}

function writeSessionCheckedAt() {
  try {
    sessionStorage.setItem(SESSION_KEY, String(Date.now()));
  } catch {
    // 寫入失敗（無痕視窗／被封鎖）不影響功能，頂多這個分頁之後每次都會再檢查一次
  }
}

// GET /data-freshness 只回傳報告本身（沒有 action/reason，因為不觸發決策）；補完之後拿它來更新
// 狀態列時，用 is_stale 自行歸類成 up_to_date／throttled 兩種顯示狀態即可，不需要再打一次 catch-up。
function summarizeReport(report) {
  const staleCount = (report.stocks?.stale?.length || 0) + (report.indices?.stale?.length || 0);
  if (!report.is_stale) return { report, action: 'up_to_date', reason: '資料已是最新' };
  return { report, action: 'throttled', reason: `仍有 ${staleCount} 檔無 ${report.expected_date} 資料（可能停牌）` };
}

async function ensureFresh({ force = false } = {}) {
  if (!force && Date.now() - readSessionCheckedAt() < THROTTLE_MS) return;

  checking.value = true;
  lastError.value = null;
  try {
    const res = await dataFreshnessApi.catchUp({ force });
    if (!res.success) throw new Error(res.error?.message || '無法檢查資料狀態');
    result.value = res.data;
    writeSessionCheckedAt();
    awaitingCompletion.value = Object.values(res.data.markets || {}).some(
      (m) => m.action === 'triggered' || m.action === 'fetch_running'
    );
  } catch (e) {
    lastError.value = e?.message || '無法檢查資料狀態';
  } finally {
    checking.value = false;
  }
}

// 補抓完成（useCrawlerStatus().isRunning true → false）後呼叫：只讀報告更新狀態列，不會再觸發抓取。
async function refreshAfterCompletion() {
  awaitingCompletion.value = false;
  try {
    const res = await dataFreshnessApi.getReport();
    if (!res.success) return;
    const markets = {};
    for (const [market, report] of Object.entries(res.data || {})) {
      markets[market] = summarizeReport(report);
    }
    result.value = { ...(result.value || {}), markets };
  } catch {
    // 補完後的狀態列查詢失敗不影響其餘首頁內容；下次開首頁 ensureFresh() 仍會再檢查一次
  }
}

export function useDataFreshness() {
  return {
    result,
    checking,
    lastError,
    awaitingCompletion,
    ensureFresh,
    refreshAfterCompletion
  };
}
