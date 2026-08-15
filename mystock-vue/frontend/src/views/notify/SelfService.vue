<template>
  <div class="min-h-screen bg-surface-50 dark:bg-surface-950">
    <Toast />
    <ConfirmDialog />

    <div v-if="loading" class="flex items-center justify-center min-h-screen">
      <i class="pi pi-spin pi-spinner text-primary text-4xl"></i>
    </div>

    <div v-else-if="!view" class="flex items-center justify-center min-h-screen p-6">
      <div class="max-w-sm text-center">
        <i class="pi pi-lock text-4xl text-surface-400 mb-3"></i>
        <h2 class="text-lg font-black text-surface-900 dark:text-surface-0">連結已失效</h2>
        <p class="text-sm text-surface-500 mt-2">請向系統擁有者索取新的連結。</p>
      </div>
    </div>

    <div v-else class="max-w-lg mx-auto p-4 pb-24 space-y-4">
      <!-- 身分 -->
      <div class="flex items-center gap-3 rounded-2xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm p-4">
        <div class="w-11 h-11 rounded-xl bg-primary-50 dark:bg-primary-900/30 text-primary flex items-center justify-center font-black text-lg">
          {{ view.recipient.display_name.charAt(0) }}
        </div>
        <div class="flex-1 min-w-0">
          <div class="font-black text-surface-900 dark:text-surface-0">{{ view.recipient.display_name }}</div>
          <div class="text-xs text-surface-400">你正透過訊息中的專屬連結進入，不需帳號密碼</div>
        </div>
        <i class="pi pi-shield text-surface-400" title="此連結僅顯示你自己的設定"></i>
      </div>

      <!-- 我的收件方式 -->
      <div class="rounded-2xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
        <div class="p-4 border-b border-surface-100 dark:border-surface-800 font-black flex items-center gap-2">
          <i class="pi pi-inbox text-primary"></i>我的收件方式
        </div>
        <div class="divide-y divide-surface-100 dark:divide-surface-800">
          <div v-for="e in view.endpoints" :key="e.endpoint_code" class="p-4 space-y-2">
            <div class="flex items-center gap-2 text-sm font-bold">
              <i class="pi" :class="e.channel_code === 'email' ? 'pi-envelope' : 'pi-send'"></i>
              {{ e.address }}
            </div>
            <div class="grid grid-cols-2 gap-2">
              <Select v-model="e.delivery_mode" :options="MODE_OPTIONS" optionLabel="label" optionValue="value" size="small" @change="saveEndpoint(e)" />
              <InputNumber v-model="e.daily_limit" :min="1" :max="200" size="small" suffix=" 則/日" @update:modelValue="saveEndpoint(e)" />
            </div>
            <div class="flex items-center gap-2">
              <span class="text-xs text-surface-400">靜音</span>
              <input type="time" v-model="e.quiet_start_str" class="p-inputtext p-component text-xs p-1" @change="saveEndpoint(e)" />
              <span class="text-xs text-surface-400">–</span>
              <input type="time" v-model="e.quiet_end_str" class="p-inputtext p-component text-xs p-1" @change="saveEndpoint(e)" />
            </div>
            <Button label="停止此管道" size="small" text severity="danger" @click="unsubEndpoint(e)" />
          </div>
        </div>
      </div>

      <!-- 訂閱範圍 -->
      <div class="rounded-2xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
        <div class="p-4 border-b border-surface-100 dark:border-surface-800 font-black flex items-center gap-2">
          <i class="pi pi-filter text-primary"></i>我要收到哪些訊號
        </div>
        <div class="p-4 space-y-4">
          <div v-for="dim in DIMENSIONS" :key="dim.key">
            <div class="text-xs font-bold text-surface-400 uppercase mb-1.5">{{ dim.label }}</div>
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="opt in dim.options"
                :key="opt.value"
                class="px-2.5 py-1 rounded-full text-xs font-bold border cursor-pointer select-none flex items-center gap-1"
                :class="chipClass(dim.key, opt.value)"
                @click="toggleChip(dim.key, opt.value)"
              >
                <i v-if="!isAllowed(dim.key, opt.value)" class="pi pi-lock text-[9px]"></i>
                {{ opt.label }}
              </span>
            </div>
            <p v-if="dim.options.some((o) => !isAllowed(dim.key, o.value))" class="text-xs text-surface-400 mt-1">
              <i class="pi pi-info-circle"></i> 帶鎖頭的項目尚未被系統擁有者指派給你，如需開放請洽系統擁有者
            </p>
          </div>
          <Button label="儲存訂閱範圍" icon="pi pi-check" size="small" @click="savePreferences" :loading="savingPref" />
        </div>
      </div>

      <!-- 暫停 -->
      <div class="rounded-2xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
        <div class="p-4 border-b border-surface-100 dark:border-surface-800 font-black flex items-center gap-2">
          <i class="pi pi-pause text-primary"></i>暫時停止接收
        </div>
        <div class="p-4">
          <div class="grid grid-cols-4 gap-2 mb-2">
            <button
              v-for="d in [1, 3, 7, 30]"
              :key="d"
              class="border rounded-lg p-2 text-center text-sm font-bold"
              :class="'border-surface-200 dark:border-surface-700 hover:border-primary'"
              @click="pause(d)"
            >
              {{ d }} 天
            </button>
          </div>
          <p class="text-xs text-surface-400"><i class="pi pi-info-circle"></i> 暫停期間的訊息不會補送，但仍會保留在通知紀錄中</p>
        </div>
      </div>

      <!-- 通知紀錄 -->
      <div class="rounded-2xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
        <div class="p-4 border-b border-surface-100 dark:border-surface-800 font-black flex items-center gap-2">
          <i class="pi pi-history text-primary"></i>我收到的通知
        </div>
        <div class="divide-y divide-surface-100 dark:divide-surface-800 max-h-64 overflow-y-auto">
          <div v-for="m in myMessages" :key="m.message_code" class="p-3 text-sm flex items-center gap-2">
            <span class="text-xs text-surface-400 whitespace-nowrap">{{ formatTime(m.created_at) }}</span>
            <span class="flex-1 truncate">{{ (m.subject || m.body || '').slice(0, 30) }}</span>
          </div>
          <p v-if="!myMessages.length" class="p-4 text-sm text-surface-400">近 7 天沒有通知紀錄</p>
        </div>
      </div>

      <!-- 退訂 -->
      <div class="rounded-2xl border border-red-200 dark:border-red-900/40 bg-surface-0 dark:bg-surface-900 shadow-sm">
        <div class="p-4 border-b border-red-100 dark:border-red-900/30 font-black flex items-center gap-2 text-red-600">
          <i class="pi pi-times-circle"></i>不想再收到通知
        </div>
        <div class="p-4">
          <p class="text-xs text-surface-500 mb-3">退訂後將立即停止發送，不需經過系統擁有者。日後若想恢復，請向系統擁有者索取新邀請。</p>
          <Button label="退訂所有通知" icon="pi pi-times" severity="danger" outlined class="w-full" @click="unsubAll" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';
import { notifyApi } from '@/service/notifyApi';

const toast = useToast();
const confirm = useConfirm();

const MODE_OPTIONS = [
  { label: '即時', value: 'realtime' },
  { label: '每日摘要', value: 'digest' },
  { label: '僅緊急', value: 'critical_only' }
];

const DIMENSIONS = [
  { key: 'markets', label: '市場', options: [{ label: '台股', value: 'tw' }, { label: '美股', value: 'us' }] },
  { key: 'strengths', label: '訊號強度', options: [{ label: '強', value: 'strong' }, { label: '中', value: 'moderate' }, { label: '弱', value: 'weak' }] },
  { key: 'signal_types', label: '訊號類型', options: [{ label: '買進', value: 'BUY' }, { label: '賣出', value: 'SELL' }, { label: '警告', value: 'WARNING' }] },
  { key: 'strategy_categories', label: '策略分類', options: [{ label: '技術面', value: 'technical' }, { label: '籌碼面', value: 'chip' }, { label: '基本面', value: 'fundamental' }] }
];

const loading = ref(true);
const view = ref(null);
const myMessages = ref([]);
const selected = reactive({ markets: [], strengths: [], signal_types: [], strategy_categories: [] });
const savingPref = ref(false);

function formatTime(t) {
  try { return new Date(t).toLocaleString('zh-TW'); } catch { return t; }
}

function isAllowed(dimKey, value) {
  const ceiling = view.value?.preference?.ceiling?.[dimKey] || [];
  return ceiling.includes(value);
}

function chipClass(dimKey, value) {
  if (!isAllowed(dimKey, value)) return 'border-surface-100 dark:border-surface-800 text-surface-300 dark:text-surface-600 cursor-not-allowed';
  const active = selected[dimKey].includes(value);
  return active
    ? 'border-primary bg-primary-50 dark:bg-primary-900/30 text-primary'
    : 'border-surface-200 dark:border-surface-700 text-surface-500 hover:border-primary';
}

function toggleChip(dimKey, value) {
  if (!isAllowed(dimKey, value)) {
    toast.add({ severity: 'warn', summary: '此項目未開放', detail: '請洽系統擁有者調整授權範圍', life: 3000 });
    return;
  }
  const list = selected[dimKey];
  const idx = list.indexOf(value);
  if (idx >= 0) list.splice(idx, 1);
  else list.push(value);
}

function timeToStr(t) {
  if (!t) return '';
  if (typeof t === 'string') return t.slice(0, 5);
  return `${String(t.hour ?? 0).padStart(2, '0')}:${String(t.minute ?? 0).padStart(2, '0')}`;
}

async function load() {
  loading.value = true;
  try {
    view.value = await notifyApi.self.me();
    const sel = view.value.preference.selected;
    selected.markets = [...(sel.markets || [])];
    selected.strengths = [...(sel.strengths || [])];
    selected.signal_types = [...(sel.signal_types || [])];
    selected.strategy_categories = [...(sel.strategy_categories || [])];
    for (const e of view.value.endpoints) {
      e.quiet_start_str = timeToStr(e.quiet_start);
      e.quiet_end_str = timeToStr(e.quiet_end);
    }
    myMessages.value = await notifyApi.self.myMessages();
  } catch (err) {
    view.value = null;
  } finally {
    loading.value = false;
  }
}

async function savePreferences() {
  savingPref.value = true;
  try {
    await notifyApi.self.updatePreferences({ ...selected });
    toast.add({ severity: 'success', summary: '設定已儲存，下次發送即套用', life: 3000 });
  } catch (err) {
    toast.add({ severity: 'error', summary: '儲存失敗', detail: err.message, life: 4000 });
  } finally {
    savingPref.value = false;
  }
}

async function saveEndpoint(e) {
  try {
    await notifyApi.self.updateEndpoint(e.endpoint_code, {
      delivery_mode: e.delivery_mode,
      daily_limit: e.daily_limit,
      quiet_start: e.quiet_start_str || null,
      quiet_end: e.quiet_end_str || null
    });
    toast.add({ severity: 'success', summary: '已更新', life: 2000 });
  } catch (err) {
    toast.add({ severity: 'error', summary: '更新失敗', detail: err.message, life: 4000 });
  }
}

function pause(days) {
  confirm.require({
    message: `確定要暫停通知 ${days} 天嗎？期間不會發送、也不會補送。`,
    header: '暫停通知',
    icon: 'pi pi-pause',
    accept: async () => {
      try {
        await notifyApi.self.pause(days);
        toast.add({ severity: 'success', summary: `已暫停 ${days} 天，到期自動恢復`, life: 3000 });
        await load();
      } catch (err) {
        toast.add({ severity: 'error', summary: '暫停失敗', detail: err.message, life: 4000 });
      }
    }
  });
}

function unsubEndpoint(e) {
  confirm.require({
    message: `確定要停止「${e.address}」這個管道嗎？`,
    header: '停止此管道',
    icon: 'pi pi-exclamation-triangle',
    accept: async () => {
      try {
        await notifyApi.self.unsubscribe('endpoint', e.endpoint_code);
        toast.add({ severity: 'success', summary: '已停止，立即生效', life: 2500 });
        await load();
      } catch (err) {
        toast.add({ severity: 'error', summary: '操作失敗', detail: err.message, life: 4000 });
      }
    }
  });
}

function unsubAll() {
  confirm.require({
    message: '退訂後你的所有收件方式都將立即停止接收，包含系統異常等緊急通知。此操作無法自行復原。',
    header: '確認退訂所有通知？',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await notifyApi.self.unsubscribe('all');
        toast.add({ severity: 'success', summary: '已退訂所有通知', life: 3000 });
        await load();
      } catch (err) {
        toast.add({ severity: 'error', summary: '操作失敗', detail: err.message, life: 4000 });
      }
    }
  });
}

onMounted(load);
</script>
