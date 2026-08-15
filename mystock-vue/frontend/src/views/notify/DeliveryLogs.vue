<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <Toast />

    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h1 class="text-3xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-history text-primary text-3xl"></i>
          發送紀錄
        </h1>
        <p class="text-base text-surface-500 mt-1">每則訊息的狀態、失敗原因與手動重送</p>
      </div>
      <Button label="重送全部失敗" icon="pi pi-replay" severity="secondary" outlined @click="resendAllFailed" />
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-3" v-if="stats">
      <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm p-4">
        <div class="text-xs font-bold text-surface-400 uppercase">近 24 小時已送出</div>
        <div class="text-2xl font-black text-surface-900 dark:text-surface-0">{{ stats.overall?.sent ?? 0 }}</div>
      </div>
      <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm p-4">
        <div class="text-xs font-bold text-surface-400 uppercase">最終失敗</div>
        <div class="text-2xl font-black text-red-500">{{ stats.overall?.dead ?? 0 }}</div>
      </div>
      <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm p-4">
        <div class="text-xs font-bold text-surface-400 uppercase">待發送</div>
        <div class="text-2xl font-black text-surface-900 dark:text-surface-0">{{ stats.overall?.pending ?? 0 }}</div>
      </div>
      <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm p-4">
        <div class="text-xs font-bold text-surface-400 uppercase">最舊待發（秒）</div>
        <div class="text-2xl font-black text-surface-900 dark:text-surface-0">{{ Math.round(stats.overall?.oldest_pending_age_sec ?? 0) }}</div>
      </div>
    </div>

    <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
      <div class="flex flex-wrap items-center gap-2 p-3 px-4 border-b border-surface-100 dark:border-surface-800">
        <SelectButton v-model="statusFilter" :options="STATUS_FILTERS" optionLabel="label" optionValue="value" @change="load" />
        <div class="ml-auto text-sm text-surface-400">共 {{ messages.length }} 筆</div>
      </div>

      <DataTable :value="messages" :loading="loading" paginator :rows="20" size="small">
        <Column field="created_at" header="時間" style="white-space:nowrap">
          <template #body="{ data }">{{ formatTime(data.created_at) }}</template>
        </Column>
        <Column field="channel_code" header="管道">
          <template #body="{ data }"><Tag :value="data.channel_code" severity="secondary" /></template>
        </Column>
        <Column header="標題">
          <template #body="{ data }"><span class="text-sm">{{ (data.subject || data.body || '').slice(0, 40) }}</span></template>
        </Column>
        <Column field="status" header="狀態">
          <template #body="{ data }"><Tag :value="STATUS_LABEL[data.status] || data.status" :severity="STATUS_SEVERITY[data.status] || 'secondary'" /></template>
        </Column>
        <Column field="attempt_count" header="嘗試" style="width:70px" />
        <Column header="">
          <template #body="{ data }">
            <Button v-if="['dead','failed'].includes(data.status)" label="重送" icon="pi pi-replay" size="small" text @click="resend(data)" />
            <Button icon="pi pi-eye" size="small" text @click="showDetail(data)" title="詳情" />
          </template>
        </Column>
      </DataTable>
    </div>

    <Dialog v-model:visible="detailDialog" header="訊息詳情" modal style="width: 32rem">
      <div v-if="detail" class="space-y-3 text-sm">
        <pre class="whitespace-pre-wrap bg-surface-50 dark:bg-surface-800 rounded-lg p-3 text-xs">{{ detail.message.body }}</pre>
        <div>
          <div class="font-bold text-xs text-surface-400 uppercase mb-1">投遞歷程</div>
          <div v-for="l in detail.logs" :key="l.id" class="flex items-center gap-2 text-xs py-1 border-b border-surface-100 dark:border-surface-800">
            <span class="text-surface-400">{{ formatTime(l.attempted_at) }}</span>
            <Tag :value="l.result" :severity="l.result === 'success' ? 'success' : 'danger'" size="small" />
            <span class="text-surface-500 truncate">{{ l.failure_reason }}</span>
          </div>
        </div>
      </div>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useToast } from 'primevue/usetoast';
import { notifyApi } from '@/service/notifyApi';

const toast = useToast();

const STATUS_LABEL = {
  sent: '已送出', failed: '失敗待重試', dead: '最終失敗', digested: '併入摘要',
  throttled: '超量轉摘要', deferred: '延後', digest_pending: '待摘要',
  skipped_duplicate: '重複略過', skipped_paused: '暫停略過', pending: '待發送', sending: '發送中'
};
const STATUS_SEVERITY = {
  sent: 'success', failed: 'warn', dead: 'danger', digested: 'secondary',
  throttled: 'secondary', deferred: 'secondary', digest_pending: 'secondary',
  skipped_duplicate: 'secondary', skipped_paused: 'secondary', pending: 'secondary', sending: 'info'
};
const STATUS_FILTERS = [
  { label: '全部', value: null },
  { label: '已送出', value: 'sent' },
  { label: '失敗', value: 'failed' },
  { label: '最終失敗', value: 'dead' }
];

const messages = ref([]);
const stats = ref(null);
const loading = ref(true);
const statusFilter = ref(null);
const detailDialog = ref(false);
const detail = ref(null);

function formatTime(t) {
  try { return new Date(t).toLocaleString('zh-TW'); } catch { return t; }
}

async function load() {
  loading.value = true;
  try {
    const params = { limit: 100 };
    if (statusFilter.value) params.status = statusFilter.value;
    messages.value = await notifyApi.admin.listMessages(params);
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: err.message, life: 4000 });
  } finally {
    loading.value = false;
  }
}

async function loadStats() {
  try {
    stats.value = await notifyApi.admin.stats();
  } catch {
    // 統計非關鍵資訊，失敗不擋主要清單
  }
}

async function resend(msg) {
  try {
    await notifyApi.admin.resendMessage(msg.message_code);
    toast.add({ severity: 'success', summary: '已重新排入發送佇列', life: 2500 });
    await load();
  } catch (err) {
    toast.add({ severity: 'error', summary: '重送失敗', detail: err.message, life: 4000 });
  }
}

async function resendAllFailed() {
  try {
    const result = await notifyApi.admin.resendAllFailed();
    toast.add({ severity: 'success', summary: `已重新排入 ${result.resent} 則失敗訊息`, life: 3000 });
    await load();
  } catch (err) {
    toast.add({ severity: 'error', summary: '重送失敗', detail: err.message, life: 4000 });
  }
}

async function showDetail(msg) {
  try {
    detail.value = await notifyApi.admin.getMessage(msg.message_code);
    detailDialog.value = true;
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入詳情失敗', detail: err.message, life: 4000 });
  }
}

onMounted(() => {
  load();
  loadStats();
});
</script>
