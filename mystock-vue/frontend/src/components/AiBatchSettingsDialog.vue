<template>
  <Dialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    modal
    :header="symbols?.length ? `分析已選標的（${symbols.length} 檔）` : '批次設定與執行'"
    style="width: 34rem"
    :breakpoints="{ '640px': '92vw' }"
  >
    <div class="space-y-5">
      <!-- 設定區：啟用開關寫回 .env，立即生效不需重啟（見 ai/config.py::set_batch_settings()）。
           多選標的手動觸發（symbols 有值）沿用同一套設定與同一顆「批次啟用」開關——後端
           /batch/trigger 對兩種呼叫方式都要求 AI_BATCH_ENABLED=true（ai_batch.py），這裡若把
           開關藏起來，遇到尚未啟用時使用者會卡在「確認執行」失敗卻看不到能打開的開關。 -->
      <div class="space-y-3">
        <div class="flex items-center justify-between gap-3">
          <div>
            <div class="text-sm font-bold text-surface-700 dark:text-surface-200">啟用批次自動產生</div>
            <div class="text-xs text-surface-400 mt-0.5">開啟後，每日收盤 fetch→scan 完成後會自動對監控清單批次產生 AI 報告</div>
          </div>
          <ToggleSwitch v-model="form.enabled" />
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">每日批次配額</label>
          <InputNumber v-model="form.dailyQuota" :min="1" :max="500" showButtons class="w-full" inputClass="w-full" />
          <p class="text-[11px] text-surface-400 mt-1">
            單位：檔／次——當天透過批次流程「成功產生」AI 報告的股票標的數量上限，不是 token 數或美金費用；
            已有快取回讀（今日已有同 Provider＋模型報告）不算在內。
          </p>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">批次預設 Provider</label>
            <Select
              v-model="form.provider"
              :options="providerOptions"
              optionLabel="label"
              optionValue="value"
              class="w-full"
              @change="onProviderChange"
            />
          </div>
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">批次預設模型</label>
            <Select v-model="form.model" :options="modelOptions" optionLabel="label" optionValue="value" class="w-full" />
          </div>
        </div>
        <p class="text-[11px] text-surface-400 -mt-1">
          批次執行（含排程與手動觸發）一律使用這裡選定的 Provider＋模型；個股頁手動產生報告的選單不受影響。
        </p>
        <div class="flex items-center gap-2">
          <Button label="儲存設定" icon="pi pi-save" size="small" outlined :loading="saving" @click="saveSettings" />
          <span v-if="saveMessage" class="text-xs" :class="saveError ? 'text-red-600' : 'text-emerald-600'">{{ saveMessage }}</span>
        </div>
      </div>

      <!-- 執行區：先預估費用，使用者看過金額後才能按下確認執行 -->
      <div class="border-t border-surface-100 dark:border-surface-800 pt-4 space-y-3">
        <div class="text-sm font-bold text-surface-700 dark:text-surface-200">
          {{ symbols?.length ? `分析已選的 ${symbols.length} 檔（${market === 'tw' ? '台股' : '美股'}）` : `立即執行一次批次（${market === 'tw' ? '台股' : '美股'}）` }}
        </div>

        <div v-if="!estimate && !running && !result">
          <Button label="預估費用" icon="pi pi-calculator" size="small" :loading="estimating" @click="loadEstimate" />
        </div>

        <div v-if="estimate && !running && !result" class="space-y-3">
          <div class="rounded-xl border border-amber-200 dark:border-amber-800/60 bg-amber-50 dark:bg-amber-900/20 p-4 space-y-2 text-sm">
            <div class="flex items-center gap-2 font-bold text-amber-700 dark:text-amber-300">
              <i class="pi pi-exclamation-triangle"></i>執行前請確認：這會花費實際費用
            </div>
            <div class="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-surface-600 dark:text-surface-300">
              <div>{{ symbols?.length ? '已選標的' : '符合資格標的' }}：<b class="num">{{ estimate.eligible_count }}</b> 檔</div>
              <!-- ETF 排除規則只套用在「整份監控清單」批次；使用者手動勾選的子集合略過此規則
                   （見 ai/batch_job.py::run_watchlist_batch() 的說明），恆為 0，選取模式下不顯示 -->
              <div v-if="!symbols?.length">ETF 已排除：<b class="num">{{ estimate.etf_excluded_count }}</b> 檔</div>
              <div>今日已有報告：<b class="num">{{ estimate.already_covered_count }}</b> 檔</div>
              <div>今日配額剩餘：<b class="num">{{ estimate.quota_remaining }} / {{ estimate.quota_daily }}</b></div>
            </div>
            <div class="border-t border-amber-200 dark:border-amber-800/40 pt-2 mt-1 text-xs text-surface-600 dark:text-surface-300 space-y-1">
              <div>
                本次將實際呼叫 <b class="num text-sm">{{ estimate.will_call_count }}</b> 檔
                <span v-if="estimate.will_skip_quota_count > 0" class="text-amber-600 dark:text-amber-400">
                  （另有 {{ estimate.will_skip_quota_count }} 檔因配額不足會略過）
                </span>
              </div>
              <div>
                預估 token：<b class="num">{{ formatNum(estimate.estimated_total_tokens) }}</b>
                （輸入 {{ formatNum(estimate.estimated_input_tokens) }} ／ 輸出 {{ formatNum(estimate.estimated_output_tokens) }}）
              </div>
              <div>
                預估費用：
                <b class="num text-base text-amber-700 dark:text-amber-300">
                  {{ estimate.estimated_cost_usd != null ? `US$${estimate.estimated_cost_usd.toFixed(4)}` : '無法估算（缺定價資料）' }}
                </b>
                <span class="text-[11px] text-surface-400 ml-1">
                  （{{ estimate.cost_basis === 'historical' ? '依歷史平均計算' : '尚無歷史資料，依保守估計計算' }}，{{ estimate.provider }}/{{ estimate.model }}）
                </span>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <Button label="取消" text size="small" @click="estimate = null" />
            <Button
              label="確認執行" icon="pi pi-play" severity="warn" size="small"
              :disabled="estimate.will_call_count === 0"
              @click="confirmRun"
            />
          </div>
        </div>

        <div v-if="running" class="flex items-center gap-2 text-sm text-surface-500 py-3">
          <i class="pi pi-spin pi-spinner"></i>批次執行中，請稍候（依配額大小可能需要數十秒到數分鐘）…
        </div>

        <div v-if="result" class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/40 p-4 text-sm space-y-1">
          <div class="font-bold text-surface-700 dark:text-surface-200 flex items-center gap-1.5">
            <i class="pi pi-check-circle text-emerald-600"></i>執行完成
          </div>
          <div>新產生：<b class="num">{{ result.produced?.length || 0 }}</b> 檔</div>
          <div>讀取既有快取（不計費）：<b class="num">{{ result.cached?.length || 0 }}</b> 檔</div>
          <div>略過：<b class="num">{{ result.skipped?.length || 0 }}</b> 檔</div>
          <div v-if="result.skipped?.length" class="text-xs text-surface-400 mt-1">
            {{ result.skipped.slice(0, 5).map(s => `${s.symbol}(${s.reason})`).join('、') }}{{ result.skipped.length > 5 ? ' 等' : '' }}
          </div>
          <Button label="再執行一次" text size="small" class="mt-1 !px-0" @click="reset" />
        </div>
      </div>
    </div>
    <template #footer>
      <Button label="關閉" text @click="close" />
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { aiAnalysisApi } from '@/service/aiAnalysisApi';

const props = defineProps({
  visible: { type: Boolean, default: false },
  market: { type: String, default: 'tw' },
  // 戰情室多選標的手動觸發時帶入；未帶（空陣列）沿用「整份監控清單」既有行為。
  symbols: { type: Array, default: () => [] }
});
// started：確認執行當下發出（帶 symbols），供戰情室在表格上標記「分析中」圖示（觸發是同步
// 阻塞呼叫，沒有逐檔進度可回報，見 confirmRun()）。settled：呼叫結束時發出，不論成功或失敗都要
// 發，讓「分析中」圖示在失敗時也會清除，不會卡住。
const emit = defineEmits(['update:visible', 'started', 'executed', 'settled']);

const form = ref({ enabled: false, dailyQuota: 70, provider: 'claude', model: null });
const saving = ref(false);
const saveMessage = ref('');
const saveError = ref(false);

// 可選 Provider／模型清單（GET /ai/models，與個股頁手動產生報告選單、LLM 執行歷史頁篩選共用
// 同一份白名單，見 ai/config.py 的 SELECTABLE_MODELS）
const providerModels = ref({}); // { claude: { display_name, default_model, models: [...] }, gemini: {...} }
const providerOptions = computed(() =>
  Object.entries(providerModels.value).map(([code, p]) => ({ label: p.display_name || code, value: code }))
);
const modelOptions = computed(() => {
  const pool = providerModels.value[form.value.provider]?.models || [];
  return pool.map((m) => ({ label: `${m.label}（${m.tier}）`, value: m.id }));
});

async function loadModels() {
  try {
    const res = await aiAnalysisApi.getModels();
    providerModels.value = res.data?.providers || {};
  } catch (e) {
    // 非關鍵功能：清單抓不到就只留使用者目前既有的 provider/model 值，不影響其他設定的儲存
  }
}

// 切換 Provider 時，先前選的模型可能不屬於新 Provider，改帶該 Provider 的預設模型
function onProviderChange() {
  form.value.model = providerModels.value[form.value.provider]?.default_model || null;
}

const estimating = ref(false);
const estimate = ref(null);
const running = ref(false);
const result = ref(null);

function formatNum(n) {
  return n == null ? '—' : n.toLocaleString('zh-TW');
}

async function loadSettings() {
  try {
    const res = await aiAnalysisApi.getBatchSettings();
    form.value = {
      enabled: res.data.enabled,
      dailyQuota: res.data.daily_quota,
      provider: res.data.provider,
      model: res.data.model
    };
  } catch (e) {
    // 讀取失敗保留預設值，不阻擋對話框開啟；使用者仍可重新整理再試
  }
}

async function saveSettings() {
  saving.value = true;
  saveMessage.value = '';
  try {
    const res = await aiAnalysisApi.updateBatchSettings({
      enabled: form.value.enabled,
      dailyQuota: form.value.dailyQuota,
      provider: form.value.provider,
      model: form.value.model
    });
    form.value = {
      enabled: res.data.enabled,
      dailyQuota: res.data.daily_quota,
      provider: res.data.provider,
      model: res.data.model
    };
    saveError.value = false;
    saveMessage.value = '已儲存，立即生效（不需重啟服務）';
  } catch (e) {
    saveError.value = true;
    saveMessage.value = e?.response?.data?.error?.message || e?.message || '儲存失敗';
  } finally {
    saving.value = false;
  }
}

async function loadEstimate() {
  estimating.value = true;
  saveMessage.value = '';
  try {
    const res = await aiAnalysisApi.getBatchEstimate(props.market, props.symbols);
    estimate.value = res.data;
  } catch (e) {
    saveError.value = true;
    saveMessage.value = e?.response?.data?.error?.message || e?.message || '預估失敗';
  } finally {
    estimating.value = false;
  }
}

async function confirmRun() {
  running.value = true;
  const market = estimate.value.market;
  estimate.value = null;
  emit('started', { symbols: props.symbols });
  try {
    const res = await aiAnalysisApi.triggerBatch(market, props.symbols);
    result.value = res.data;
    emit('executed');
  } catch (e) {
    saveError.value = true;
    saveMessage.value = e?.response?.data?.error?.message || e?.message || '執行失敗';
  } finally {
    running.value = false;
    emit('settled');
  }
}

function reset() {
  result.value = null;
  estimate.value = null;
  saveMessage.value = '';
}

function close() {
  emit('update:visible', false);
}

watch(() => props.visible, (v) => {
  if (v) {
    reset();
    loadModels();
    loadSettings();
  }
});
</script>
