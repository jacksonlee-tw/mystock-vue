<template>
  <div class="p-6 max-w-6xl mx-auto space-y-6">
    <Toast />

    <div class="flex items-center flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h1 class="text-3xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-filter text-primary text-3xl"></i>
          訂閱規則
        </h1>
        <p class="text-base text-surface-500 mt-1">以「事件類型 → 過濾條件 → 目標對象」三段式定義誰該收到什麼</p>
      </div>
      <div class="flex items-center gap-2">
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
            <i class="pi pi-bookmark text-primary"></i>{{ displayRuleName(s) }}
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
            <div v-else class="flex items-center flex-wrap gap-1">
              <Tag v-for="(vals, key) in s.filter_conditions" :key="key" :value="`${key}: ${Array.isArray(vals) ? vals.join('、') : vals}`" severity="secondary" />
            </div>
          </div>
          <div>
            <div class="text-xs font-bold text-surface-400 uppercase mb-1"><i class="pi pi-users"></i> 目標對象</div>
            <div class="font-bold">{{ targetLabel(s) }}</div>
            <div class="flex items-center flex-wrap gap-1 mt-1">
              <Tag v-for="channel in ruleChannels(s)" :key="channel" :value="CHANNEL_LABEL[channel] || channel" severity="info" />
              <span v-if="!ruleChannels(s).length" class="text-xs text-red-400">無可用收件端點</span>
            </div>
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
          <label class="text-sm font-bold text-surface-600 dark:text-surface-300 mb-1 block">① 事件類型（可複選）</label>
          <MultiSelect
            v-model="form.event_types"
            :options="Object.keys(EVENT_LABEL)"
            :optionLabel="(v) => EVENT_LABEL[v]"
            display="chip"
            placeholder="請選擇至少一項"
            fluid
          />
          <small v-if="form.event_types.length > 1" class="text-xs text-surface-500 mt-1 block">
            <i class="pi pi-info-circle"></i>
            將建立 <b>{{ form.event_types.length }}</b> 條規則（每個事件類型各一條，過濾條件與目標對象相同），
            日後可個別停用。
          </small>
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
      <template #footer>
        <Button label="關閉" text @click="testDialog = false" />
        <Button
          label="直接發送"
          icon="pi pi-send"
          severity="danger"
          :disabled="!testResult || !testResult.length"
          @click="openSendConfirm"
        />
      </template>
    </Dialog>

    <!-- 發送確認 -->
    <Dialog v-model:visible="sendConfirmDialog" header="確認發送？" modal style="width: 30rem">
      <div class="space-y-3">
        <Message severity="warn" :closable="false">
          這是<b>真實發送</b>，訊息會立即送出給下列收件人，<b>無法撤回</b>。
        </Message>

        <div class="text-sm space-y-1">
          <div><span class="text-surface-400">事件：</span><b>{{ EVENT_LABEL.ALERT_SIGNAL }}</b></div>
          <div><span class="text-surface-400">內容：</span>{{ testSample?.label }}</div>
        </div>

        <div>
          <div class="text-sm font-bold mb-1">
            將路由至 {{ sendTargets.length }} 個端點
          </div>
          <div v-if="!sendTargets.length" class="text-sm text-surface-400">
            命中的規則目前沒有可用端點（未驗證或已停用），送出後不會有人收到。
          </div>
          <div v-else class="space-y-1">
            <div
              v-for="ep in sendTargets.slice(0, 8)"
              :key="ep.endpoint_code"
              class="flex items-center gap-2 text-sm p-2 border border-surface-200 dark:border-surface-700 rounded-lg"
            >
              <i :class="ep.channel_code === 'email' ? 'pi pi-envelope' : 'pi pi-send'" class="text-primary"></i>
              <span class="font-bold">{{ ep.recipient_name }}</span>
              <span class="text-surface-400">— {{ ep.channel_code }}</span>
              <span class="text-xs text-surface-400 truncate">{{ ep.address }}</span>
            </div>
            <div v-if="sendTargets.length > 8" class="text-xs text-surface-400">
              …另外 {{ sendTargets.length - 8 }} 個端點
            </div>
          </div>
        </div>

        <small class="text-xs text-surface-500 block">
          <i class="pi pi-info-circle"></i>
          實際是否即時送達仍會經過通知政策（去重／每日上限／靜音時段／發送模式）；
          部分端點可能改為併入摘要或延後。發送結果可於「發送紀錄」查看。
        </small>
      </div>
      <template #footer>
        <Button label="取消" text @click="sendConfirmDialog = false" />
        <Button label="確認發送" icon="pi pi-check" severity="danger" :loading="sending" @click="doSend" />
      </template>
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
const CHANNEL_LABEL = { email: 'Email', telegram: 'Telegram', slack: 'Slack' };

const SAMPLE_ALERTS = [
  {
    label: '2330 台積電・跌破MA20・中訊號', market: 'tw', strategy_id: 'price_cross_ma', strategy_category: 'technical',
    signal_type: 'SELL', signal_strength: 'moderate', stock_id: '2330', severity: 'info',
    stock_name: '台積電', strategy_name: '收盤價跌破關鍵均線',
    details: { close: 1085, ma_period: 20, ma_value: 1102.5, bias_percent: -1.59 },
    suggested_action: '跌破 MA20，可留意減碼或設定停損'
  },
  {
    label: '2317 鴻海・均線死亡交叉・強訊號', market: 'tw', strategy_id: 'ma_golden_death_cross', strategy_category: 'technical',
    signal_type: 'SELL', signal_strength: 'strong', stock_id: '2317', severity: 'info',
    stock_name: '鴻海', strategy_name: '均線死亡交叉',
    details: { close: 205, ma_period: 20, ma_value: 211.3, bias_percent: -2.98 },
    suggested_action: 'MA5 下穿 MA20，短線轉弱，建議減碼'
  },
  {
    label: '0050 元大台灣50・均線多頭排列・弱訊號', market: 'tw', strategy_id: 'ma_alignment', strategy_category: 'technical',
    signal_type: 'BUY', signal_strength: 'weak', stock_id: '0050', severity: 'info',
    stock_name: '元大台灣50', strategy_name: '均線多頭排列',
    details: { close: 107.8, ma_period: 20, ma_value: 106.1, bias_percent: 1.6 },
    suggested_action: '均線多頭排列成形，趨勢偏多'
  },
  {
    label: 'NVDA・乖離率過大・強訊號（美股）', market: 'us', strategy_id: 'extreme_bias', strategy_category: 'technical',
    signal_type: 'WARNING', signal_strength: 'strong', stock_id: 'NVDA', severity: 'warning',
    stock_name: 'NVIDIA', strategy_name: '乖離率過大警示',
    details: { close: 182.4, ma_period: 20, ma_value: 158.2, bias_percent: 15.3 },
    suggested_action: '正乖離過大，注意追高風險'
  }
];

const subscriptions = ref([]);
const groups = ref([]);
const recipients = ref([]);
const sharedEndpoints = ref([]);
const loading = ref(true);

const createDialog = ref(false);
const creating = ref(false);
const form = reactive({
  rule_name: '', event_types: ['ALERT_SIGNAL'],
  markets: [], signal_strengths: [], signal_types: [], strategy_categories: [],
  target: null
});

const testDialog = ref(false);
const testSample = ref(SAMPLE_ALERTS[0]);
const testResult = ref(null);

const sendConfirmDialog = ref(false);
const sending = ref(false);

/**
 * 把命中的規則展開為實際會收到訊息的端點清單。
 * 端點以 endpoint_code 去重（同一端點被多條規則命中只會收到一則）；
 * 只列出已驗證且啟用中的端點——其餘不會收到訊息，列出來只會誤導。
 */
const sendTargets = computed(() => {
  const byCode = new Map();

  const addRecipient = (recipient) => {
    if (!recipient) return;
    for (const ep of recipient.endpoints || []) {
      if (ep.status !== 'active' || ep.verify_status !== 'verified') continue;
      if (byCode.has(ep.endpoint_code)) continue;
      byCode.set(ep.endpoint_code, { ...ep, recipient_name: recipient.display_name });
    }
  };

  for (const rule of testResult.value || []) {
    if (rule.target_recipient_id) {
      addRecipient(recipients.value.find((r) => r.id === rule.target_recipient_id));
    } else if (rule.target_group_id) {
      const g = groups.value.find((x) => x.id === rule.target_group_id);
      for (const m of g?.members || []) {
        addRecipient(recipients.value.find((r) => r.id === m.id));
      }
    } else if (rule.target_endpoint_id) {
      // 個人端點掛在收件人底下；共用端點（Telegram 群組）沒有 recipient_id，需另外查
      let hit = null;
      let owner = null;
      for (const r of recipients.value) {
        const ep = (r.endpoints || []).find((e) => e.id === rule.target_endpoint_id);
        if (ep) { hit = ep; owner = r.display_name; break; }
      }
      if (!hit) {
        hit = sharedEndpoints.value.find((e) => e.id === rule.target_endpoint_id) || null;
        owner = hit ? '共用端點' : null;
      }
      if (hit && hit.status === 'active' && hit.verify_status === 'verified' && !byCode.has(hit.endpoint_code)) {
        byCode.set(hit.endpoint_code, { ...hit, recipient_name: owner });
      }
    }
  }
  return [...byCode.values()];
});

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

function displayRuleName(s) {
  if (s.target_endpoint_id) return s.rule_name;
  return s.rule_name.replace(/^Telegram\s*通知/, '多管道通知');
}

function ruleChannels(s) {
  const channels = new Set();
  const addRecipientChannels = (recipient) => {
    for (const ep of recipient?.endpoints || []) {
      if (ep.status === 'active' && ep.verify_status === 'verified') channels.add(ep.channel_code);
    }
  };

  if (s.target_recipient_id) {
    addRecipientChannels(recipients.value.find((r) => r.id === s.target_recipient_id));
  } else if (s.target_group_id) {
    const group = groups.value.find((g) => g.id === s.target_group_id);
    for (const member of group?.members || []) {
      addRecipientChannels(recipients.value.find((r) => r.id === member.id));
    }
  } else if (s.target_endpoint_id) {
    for (const recipient of recipients.value) {
      const endpoint = (recipient.endpoints || []).find((ep) => ep.id === s.target_endpoint_id);
      if (endpoint?.status === 'active' && endpoint.verify_status === 'verified') channels.add(endpoint.channel_code);
    }
    const shared = sharedEndpoints.value.find((ep) => ep.id === s.target_endpoint_id);
    if (shared?.status === 'active' && shared.verify_status === 'verified') channels.add(shared.channel_code);
  }

  return [...channels];
}

async function load() {
  loading.value = true;
  try {
    const [subsRes, groupsRes, recipientsRes, sharedRes] = await Promise.all([
      notifyApi.admin.listSubscriptions(),
      notifyApi.admin.listGroups(),
      notifyApi.admin.listRecipients(),
      notifyApi.admin.listSharedEndpoints()
    ]);
    subscriptions.value = subsRes;
    groups.value = groupsRes;
    recipients.value = recipientsRes;
    sharedEndpoints.value = sharedRes || [];
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
  Object.assign(form, { rule_name: '', event_types: ['ALERT_SIGNAL'], markets: [], signal_strengths: [], signal_types: [], strategy_categories: [], target: null });
  createDialog.value = true;
}

async function submitCreate() {
  if (!form.rule_name.trim() || !form.target) {
    toast.add({ severity: 'warn', summary: '請填寫規則名稱並選擇目標對象', life: 3000 });
    return;
  }
  if (!form.event_types.length) {
    toast.add({ severity: 'warn', summary: '請至少選擇一個事件類型', life: 3000 });
    return;
  }
  creating.value = true;
  try {
    const filters = {};
    if (form.markets.length) filters.markets = form.markets;
    if (form.signal_strengths.length) filters.signal_strengths = form.signal_strengths;
    if (form.signal_types.length) filters.signal_types = form.signal_types;
    if (form.strategy_categories.length) filters.strategy_categories = form.strategy_categories;

    const baseName = form.rule_name.trim();
    const multi = form.event_types.length > 1;

    // 後端一條規則只掛一個 event_type，複選時逐一建立；名稱附上事件類型以利辨識
    const created = [];
    const failed = [];
    for (const eventType of form.event_types) {
      const payload = {
        rule_name: multi ? `${baseName}（${EVENT_LABEL[eventType] || eventType}）` : baseName,
        event_type: eventType,
        filter_conditions: filters
      };
      if (form.target.type === 'group') payload.target_group_code = form.target.code;
      else payload.target_recipient_code = form.target.code;

      try {
        await notifyApi.admin.createSubscription(payload);
        created.push(eventType);
      } catch (err) {
        failed.push({ eventType, message: err.message });
      }
    }

    if (failed.length) {
      const detail = failed.map((f) => `${EVENT_LABEL[f.eventType] || f.eventType}：${f.message}`).join('；');
      toast.add({
        severity: created.length ? 'warn' : 'error',
        summary: created.length ? `已建立 ${created.length} 條，${failed.length} 條失敗` : '建立失敗',
        detail,
        life: 6000
      });
    } else {
      toast.add({ severity: 'success', summary: `已建立 ${created.length} 條規則`, life: 2500 });
    }

    if (created.length) createDialog.value = false;
    await load();
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

function openSendConfirm() {
  sendConfirmDialog.value = true;
}

async function doSend() {
  const s = testSample.value;
  if (!s) return;

  sending.value = true;
  try {
    const today = new Date();
    const tradeDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

    const result = await notifyApi.admin.injectEvent({
      event_type: 'ALERT_SIGNAL',
      severity: s.severity || 'info',
      // 手動測試每次都要真的送出，故給唯一來源鍵避開冪等去重
      source_event_key: `manual-test:${Date.now()}:${s.stock_id}:${s.strategy_id}`,
      payload: {
        stock_id: s.stock_id,
        stock_name: s.stock_name,
        market: s.market,
        strategy_id: s.strategy_id,
        strategy_name: s.strategy_name,
        signal_type: s.signal_type,
        signal_strength: s.signal_strength,
        trade_date: tradeDate,
        details: s.details || {},
        filters_passed: [],
        suggested_action: s.suggested_action || ''
      }
    });

    sendConfirmDialog.value = false;

    const created = result?.messages_created ?? 0;
    const skipped = result?.messages_skipped ?? 0;
    if (created > 0) {
      toast.add({
        severity: 'success',
        summary: `已送出 ${created} 則`,
        detail: skipped ? `另有 ${skipped} 則被政策略過（去重／上限／靜音／摘要），詳見發送紀錄` : '結果請至「發送紀錄」查看',
        life: 5000
      });
    } else {
      toast.add({
        severity: 'warn',
        summary: '沒有訊息實際送出',
        detail: skipped
          ? `${skipped} 則全被政策略過（去重／上限／靜音／摘要），詳見發送紀錄`
          : '事件已建立，但沒有命中任何可用端點',
        life: 6000
      });
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '發送失敗', detail: err.message, life: 5000 });
  } finally {
    sending.value = false;
  }
}

onMounted(async () => {
  await load();
  runTest();
});
</script>
