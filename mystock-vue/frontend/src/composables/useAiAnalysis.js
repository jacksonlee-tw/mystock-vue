import { ref, watch } from 'vue';
import { aiAnalysisApi } from '@/service/aiAnalysisApi';

// AI 診股報告的觸發流程（AI 技術分析報告 系統開發規格書 §7.1～§7.3，v3.4 新增模型選單）。
// 點按鈕先打開「選擇模型」畫面（stage='select'），使用者挑好 Provider／Model 後才決定：
//   - 該組合今日已有報告 → 直接讀取既有內容顯示，不擷圖、不呼叫 LLM（零成本）
//   - 沒有 → 擷取目前畫面上的 K 線圖，呼叫後端以該組合產生新報告
// 同一標的同一天，換一個模型可以再產生一次（唯一鍵含 provider+model，ADR-AI-21）。
// 非單例：每次呼叫回傳獨立狀態，供單一 StockDashboard 實例使用。

function extractErrorMessage(err) {
    return err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'AI 分析請求失敗';
}

/**
 * @param {object} params
 * @param {import('vue').Ref<string>} params.market
 * @param {import('vue').Ref<string>} params.symbol
 * @param {import('vue').Ref<string>} params.period
 * @param {import('vue').Ref<number>} params.months
 * @param {import('vue').Ref} params.chartsRef - StockCharts 元件的 template ref，須暴露 captureKlineImage()
 */
export function useAiAnalysis({ market, symbol, period, months, chartsRef }) {
    const dialogVisible = ref(false);
    // 'select'（選模型，見 §7.1 新增步驟）→ 'result'（loading/report/error，沿用原本三態邏輯）。
    const stage = ref('select');
    const loading = ref(false); // 僅在 stage==='result' 時有意義
    const dialogError = ref(null);
    const report = ref(null);

    // 可選模型清單：{ claude: { display_name, default_model, models: [{id,label,tier}] }, gemini: {...} }
    const availableModels = ref({});
    const modelsLoading = ref(false);
    const selectedProvider = ref('');
    const selectedModel = ref('');

    // 目前選擇的 provider+model 組合，今日是否已有成功報告（決定按鈕文案與行為，§7.3）
    const latestForSelection = ref(null);
    const checkingLatest = ref(false);

    // 該標的「任何 provider/model」最近一筆成功報告：供 StockDashboard.vue 頁首徽章顯示
    // 「最近一次執行過的 AI 診股報告日期＋研判方向」提醒（不論對話框是否開啟都要能查）。
    const latestReport = ref(null);
    const latestReportLoading = ref(false);

    // 該標的的歷史報告清單（不分 provider/model）：供對話框「選模型」畫面顯示歷史紀錄表格，
    // 點列可直接開啟該份報告，不必重新選模型／重新產生。
    const historyReports = ref([]);
    const historyLoading = ref(false);
    const historyTotal = ref(0);

    async function loadModels() {
        if (Object.keys(availableModels.value).length > 0) return; // 只需載一次，跨開關對話框沿用
        modelsLoading.value = true;
        try {
            const res = await aiAnalysisApi.getModels();
            availableModels.value = res.data.providers;
            selectedProvider.value = res.data.default_provider;
            selectedModel.value = availableModels.value[selectedProvider.value]?.default_model || '';
        } catch (err) {
            dialogError.value = extractErrorMessage(err) || '無法載入可選模型清單';
        } finally {
            modelsLoading.value = false;
        }
    }

    async function refreshLatestForSelection() {
        if (!symbol.value || !market.value || !selectedProvider.value || !selectedModel.value) {
            latestForSelection.value = null;
            return;
        }
        checkingLatest.value = true;
        try {
            const res = await aiAnalysisApi.getLatestReport(market.value, symbol.value, selectedProvider.value, selectedModel.value);
            latestForSelection.value = res.data || null;
        } catch {
            // 查詢失敗時保守顯示「產生」文案，不擋住主要功能
            latestForSelection.value = null;
        } finally {
            checkingLatest.value = false;
        }
    }

    // 切換選擇的模型／標的時，重新判斷「這個組合今天是否已有報告」
    watch([selectedProvider, selectedModel, market, symbol], refreshLatestForSelection);

    async function refreshLatestReport() {
        if (!symbol.value || !market.value) {
            latestReport.value = null;
            return;
        }
        latestReportLoading.value = true;
        try {
            const res = await aiAnalysisApi.getLatestReport(market.value, symbol.value);
            latestReport.value = res.data || null;
        } catch {
            // 查詢失敗時保守不顯示徽章，不影響主要頁面內容
            latestReport.value = null;
        } finally {
            latestReportLoading.value = false;
        }
    }

    // 切換標的／市場時，重新查「這檔股票有沒有執行過 AI 診股報告」，供頁首徽章使用；
    // immediate 讓元件掛載當下（尚未點開對話框）就查一次。
    watch([market, symbol], refreshLatestReport, { immediate: true });

    async function loadHistory() {
        if (!symbol.value || !market.value) {
            historyReports.value = [];
            historyTotal.value = 0;
            return;
        }
        historyLoading.value = true;
        try {
            const res = await aiAnalysisApi.listReports({ market: market.value, symbol: symbol.value, limit: 15 });
            historyReports.value = res.data?.items || [];
            historyTotal.value = res.data?.total || 0;
        } catch {
            historyReports.value = [];
            historyTotal.value = 0;
        } finally {
            historyLoading.value = false;
        }
    }

    function selectProvider(code) {
        if (code === selectedProvider.value) return;
        selectedProvider.value = code;
        const providerModels = availableModels.value[code];
        selectedModel.value = providerModels?.default_model || providerModels?.models?.[0]?.id || '';
    }

    function openSelector() {
        dialogVisible.value = true;
        stage.value = 'select';
        dialogError.value = null;
        report.value = null;
        loadModels().then(refreshLatestForSelection);
        loadHistory();
    }

    function closeDialog() {
        dialogVisible.value = false;
    }

    function backToSelect() {
        stage.value = 'select';
        dialogError.value = null;
        report.value = null;
    }

    // 直接開啟並顯示指定的既有報告，跳過「選模型」步驟：供頁首徽章（最近一次報告提醒）與
    // 對話框內的「歷史報告紀錄」表格點列使用。仍背景載入模型清單／歷史清單，讓使用者按下
    // 「換個模型再看看」返回選擇畫面時資料已就緒。
    async function viewReport(reportId) {
        dialogVisible.value = true;
        stage.value = 'result';
        dialogError.value = null;
        report.value = null;
        loading.value = true;
        loadModels().then(refreshLatestForSelection);
        loadHistory();
        try {
            const res = await aiAnalysisApi.getReport(reportId);
            report.value = res.data;
        } catch (err) {
            dialogError.value = extractErrorMessage(err);
        } finally {
            loading.value = false;
        }
    }

    async function confirm() {
        dialogError.value = null;
        report.value = null;
        stage.value = 'result';
        loading.value = true;

        if (latestForSelection.value) {
            try {
                const res = await aiAnalysisApi.getReport(latestForSelection.value.id);
                report.value = res.data;
            } catch (err) {
                dialogError.value = extractErrorMessage(err);
            } finally {
                loading.value = false;
            }
            return;
        }

        try {
            const imageBase64 = await chartsRef.value?.captureKlineImage?.();
            if (!imageBase64) {
                dialogError.value = '無法擷取 K 線圖，請確認圖表已載入後再試一次';
                return;
            }
            const res = await aiAnalysisApi.analyzeStock({
                symbol: symbol.value,
                market: market.value,
                period: period.value,
                months: months.value,
                provider: selectedProvider.value,
                model: selectedModel.value,
                imageBase64
            });
            report.value = res.data;
            await refreshLatestForSelection(); // 產生成功後按鈕文案要立刻變成「檢視今日 AI 報告」
            refreshLatestReport(); // 新報告產生後，頁首徽章與歷史清單也要跟著更新，不必等下次掛載
            loadHistory();
        } catch (err) {
            dialogError.value = extractErrorMessage(err);
        } finally {
            loading.value = false;
        }
    }

    return {
        dialogVisible,
        stage,
        loading,
        dialogError,
        report,
        availableModels,
        modelsLoading,
        selectedProvider,
        selectedModel,
        latestForSelection,
        checkingLatest,
        latestReport,
        latestReportLoading,
        historyReports,
        historyLoading,
        historyTotal,
        openSelector,
        closeDialog,
        backToSelect,
        selectProvider,
        confirm,
        viewReport
    };
}
