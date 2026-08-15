<template>
  <div class="p-6 max-w-6xl mx-auto space-y-6">
    <Toast />

    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h1 class="text-3xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-filter text-primary text-3xl"></i>
          訂閱規則
        </h1>
        <p class="text-base text-surface-500 mt-1">以「事件類型 → 過濾條件 → 目標對象」三段式定義誰該收到什麼</p>
      </div>
      <div class="flex gap-2">
        <Button label="規則測試" icon="pi pi-play" severity="secondary" outlined @click="testDialog = true" />
        <Button label="新增規則" icon="pi pi-plus" @click="openCreate" />
      </div>
    </div>

    <Message severity="info" :closable="false">
      同一項目內多個值為 <b>OR</b>；不同項目之間為 <b>AND</b>；未設定的項目視為<b>不過濾</b>。
      收件人可在自助頁進一步收窄，但無法放寬。
    </Message>

    <div v-if="loading" class="flex items-center justify-center p-12">
      <i class="pi pi-spin pi-spinner text-primary text-4xl"></i>
    </div>

    <div v-else class="space-y-3">
      <div v-for="s in subscriptions" :key="s.rule_code" class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm" :class="{ 'opacity-60': s.status !== 'enabled' }">
        <div class="flex items-center justify-between p-3 px-4 border-b border-surface-100 dark:border-surface-800">
          <div class="font-black flex items-center gap-2">
            <i class="pi pi-bookmark text-primary"></i>{{ s.rule_name }}
            <Tag v-if="s.status !== 'enabled'" value="已停用" severity="secondary" />
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs text-surface-400 font-mono hidden sm:inline">{{ s.rule_code }}</span>
            <ToggleSwitch :modelValue="s.status === 'enabled'" @update:modelValue="(v) => toggle(s, v)" />
          </div>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 p-4 text-sm">
          <div>
            <div class="text-xs font-bold text-surface-400 uppercase mb-1"><i class="pi pi-bolt"></i> 事件類型</div>
            <div class="font-bold">{{ EVENT_LABEL[s.event_type] || s.event_type }}</div>
            <div class="text-xs text-surface-400 font-mono">{{ s.event_type }}</div>
          </div>
          <div>
            <div class="text-xs font-bold text-surface-400 uppercase mb-1"><i class="pi pi-filter"></i> 過濾條件</div>
            <div v-if="!Object.keys(s.filter_conditions || {}).length" class="text-surface-400">不過濾（全部）</div>
            <div v-else class="flex flex-wrap gap-1">
              <Tag v-for="(vals, key) in s.filter_conditions" :key="key" :value="`${key}: ${Array.isArray(vals) ? vals.join('、') : vals}`" severity="secondary" />
            </div>
          </div>
          <div>
            <div class="text-xs font-bold text-surface-400 uppercase mb-1"><i class="pi pi-users"></i> 目標對象</div>
            <div class="font-bold">{{ targetLabel(s) }}</div>
          </div>
        </div>
      </div>
      <p v-if="!subscriptions.length" class="text-center text-surface-400 py-8">尚無訂閱規則</p>
    </div>

    <!-- 新增規則 -->
    <Dialog v-model:visible="createDialog" header="新增訂閱規則" modal style="width: 32rem">
      <div class="space-y-3">
        <div>
          <label class="text-sm font-bold text-surface-600 dark:text-surface-300 mb-1 block">規則名稱</label>
          <InputText v-model="form.rule_name" fluid placeholder="例如：家人：台股強訊號" />
        </div>
        <div>
          <label class="text-sm font-bold text-surface-600 dark:text-surface-300 mb-1 block">① 事件類型</label>
          <Select v-model="form.event_type" :options="Object.keys(EVENT_LABEL)" :optionLabel="(v) => EVENT_LABEL[v]" fluid />
        </div>
        <div>
          <label class="text-sm font-bold text-surface-600 dark:text-surface-300 mb-1 block">② 過濾條件（留空 = 不過濾）</label>
          <div class="space-y-2">
            <MultiSelect v-model="form.markets" :options="['tw', 'us']" placeholder="市場：不過濾" fluid />
            <MultiSelect v-model="form.signal_strengths" :options="['strong', 'moderate', 'weak']" placeholder="訊號強度：不過濾" fluid />
            <MultiSelect v-model="form.signal_types" :options="['BUY', 'SELL', 'WARNING']" placeholder="訊號類型：不過濾" fluid />
            <MultiSelect v-model="form.strategy_categories" :options="['technical', 'chip', 'fundamental']" placeholder="策略分類：不過濾" fluid />
          </div>
        </div>
        <div>
          <label class="text-sm font-bold text-surface-600 dark:text-surface-300 mb-1 block">③ 目標對象</label>
          <Select v-model="form.target" :options="targetOptions" optionLabel="label" fluid placeholder="請選擇" />
        </div>
      </div>
      <template #footer>
        <Button label="取消" text @click="createDialog = false" />
        <Button label="建立規則" icon="pi pi-check" @click="submitCreate" :loading="creating" />
      </template>
    </Dialog>

    <!-- 規則測試 -->
    <Dialog v-model:visible="testDialog" header="規則測試" modal style="width: 30rem">
      <p class="text-sm text-surface-500 mb-3">選一筆模擬訊號，預覽它會命中哪些規則。</p>
      <Select v-model="testSample" :options="SAMPLE_ALERTS" optionLabel="label" fluid @change="runTest" />
      <div v-if="testResult" class="mt-4 space-y-2">
        <div v-if="!testResult.length" class="text-sm text-surface-400">沒有任何規則命中，此訊號不會發送給任何人（正常結果，不視為錯誤）。</div>
        <div v-for="s in testResult" :key="s.rule_code" class="flex items-center gap-2 p-2 border border-surface-200 dark:border-surface-700 rounded-lg text-sm">
          <i class="pi pi-check-circle text-green-500"></i>
          <div>
            <div class="font-bold">{{ s.rule_name }}</div>
            <div class="text-xs text-surface-400">→ {{ targetLabel(s) }}</div>
          </div>
        </div>
      </div>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { useToast } from 'primevue/usetoast';
import { notifyApi } from '@/service/notifyApi';

const toast = useToast();

const EVENT_LABEL = {
  ALERT_SIGNAL: '策略警示訊號',
  ALERT_DIGEST: '每日警示摘要',
  FETCH_COMPLETED: '每日抓取完成',
  FETCH_FAILED: '抓取失敗',
  SYSTEM_HEALTH: '系統異常'
};

const SAMPLE_ALERTS = [
  { label: '2330 台積電・跌破MA20・中訊號', market: 'tw', strategy_id: 'price_cross_ma', strategy_category: 'technical', signal_type: 'SELL', signal_strength: 'moderate', stock_id: '2330', severity: 'info' },
  { label: '2317 鴻海・均線死亡交叉・強訊號', market: 'tw', strategy_id: 'ma_golden_death_cross', strategy_category: 'technical', signal_type: 'SELL', signal_strength: 'strong', stock_id: '2317', severity: 'info' },
  { label: '0050 元大台灣50・均線多頭排列・弱訊號', market: 'tw', strategy_id: 'ma_alignment', strategy_category: 'technical', signal_type: 'BUY', signal_strength: 'weak', stock_id: '0050', severity: 'info' },
  { label: 'NVDA・乖離率過大・強訊號（美股）', market: 'us', strategy_id: 'extreme_bias', strategy_category: 'technical', signal_type: 'WARNING', signal_strength: 'strong', stock_id: 'NVDA', severity: 'warning' }
];

const subscriptions = ref([]);
const groups = ref([]);
const recipients = ref([]);
const loading = ref(true);

const createDialog = ref(false);
const creating = ref(false);
const form = reactive({
  rule_name: '', event_type: 'ALERT_SIGNAL',
  markets: [], signal_strengths: [], signal_types: [], strategy_categories: [],
  target: null
});

const testDialog = ref(false);
const testSample = ref(SAMPLE_ALERTS[0]);
const testResult = ref(null);

const targetOptions = computed(() => [
  ...groups.value.map((g) => ({ label: `群組：${g.group_name}`, type: 'group', code: g.group_code })),
  ...recipients.value.map((r) => ({ label: `收件人：${r.display_name}`, type: 'recipient', code: r.recipient_code }))
]);

function targetLabel(s) {
  if (s.target_group_id) {
    const g = groups.value.find((x) => x.id === s.target_group_id);
    return `群組：${g?.group_name || s.target_group_id}`;
  }
  if (s.target_recipient_id) {
    const r = recipients.value.find((x) => x.id === s.target_recipient_id);
    return `收件人：${r?.display_name || s.target_recipient_id}`;
  }
  if (s.target_endpoint_id) return `單一端點 #${s.target_endpoint_id}`;
  return '—';
}

async function load() {
  loading.value = true;
  try {
    const [subsRes, groupsRes, recipientsRes] = await Promise.all([
      notifyApi.admin.listSubscriptions(),
      notifyApi.admin.listGroups(),
      notifyApi.admin.listRecipients()
    ]);
    subscriptions.value = subsRes;
    groups.value = groupsRes;
    recipients.value = recipientsRes;
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: err.message, life: 4000 });
  } finally {
    loading.value = false;
  }
}

async function toggle(s, on) {
  try {
    await notifyApi.admin.updateSubscription(s.rule_code, { status: on ? 'enabled' : 'disabled' });
    toast.add({ severity: 'success', summary: on ? '已啟用規則' : '已停用規則', life: 2000 });
    await load();
  } catch (err) {
    toast.add({ severity: 'error', summary: '操作失敗', detail: err.message, life: 4000 });
  }
}

function openCreate() {
  Object.assign(form, { rule_name: '', event_type: 'ALERT_SIGNAL', markets: [], signal_strengths: [], signal_types: [], strategy_categories: [], target: null });
  createDialog.value = true;
}

async function submitCreate() {
  if (!form.rule_name.trim() || !form.target) {
    toast.add({ severity: 'warn', summary: '請填寫規則名稱並選擇目標對象', life: 3000 });
    return;
  }
  creating.value = true;
  try {
    const filters = {};
    if (form.markets.length) filters.markets = form.markets;
    if (form.signal_strengths.length) filters.signal_strengths = form.signal_strengths;
    if (form.signal_types.length) filters.signal_types = form.signal_types;
    if (form.strategy_categories.length) filters.strategy_categories = form.strategy_categories;

    const payload = { rule_name: form.rule_name.trim(), event_type: form.event_type, filter_conditions: filters };
    if (form.target.type === 'group') payload.target_group_code = form.target.code;
    else payload.target_recipient_code = form.target.code;

    await notifyApi.admin.createSubscription(payload);
    toast.add({ severity: 'success', summary: '規則已建立', life: 2500 });
    createDialog.value = false;
    await load();
  } catch (err) {
    toast.add({ severity: 'error', summary: '建立失敗', detail: err.message, life: 4000 });
  } finally {
    creating.value = false;
  }
}

function runTest() {
  const facts = testSample.value;
  testResult.value = subscriptions.value.filter((s) => {
    if (s.status !== 'enabled' || s.event_type !== 'ALERT_SIGNAL') return false;
    const f = s.filter_conditions || {};
    if (f.markets && !f.markets.includes(facts.market)) return false;
    if (f.signal_strengths && !f.signal_strengths.includes(facts.signal_strength)) return false;
    if (f.signal_types && !f.signal_types.includes(facts.signal_type)) return false;
    if (f.strategy_categories && !f.strategy_categories.includes(facts.strategy_category)) return false;
    return true;
  });
}

onMounted(async () => {
  await load();
  runTest();
});
</script>
