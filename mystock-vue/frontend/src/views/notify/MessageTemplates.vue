<template>
  <div class="p-6 max-w-6xl mx-auto space-y-6">
    <Toast />

    <div>
      <h1 class="text-3xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
        <i class="pi pi-file-edit text-primary text-3xl"></i>
        訊息模板
      </h1>
      <p class="text-base text-surface-500 mt-1">調整文案是編輯模板，不需改程式、不需重新部署</p>
    </div>

    <Message severity="info" :closable="false">
      模板數量 ＝ 事件類型數 × 啟用管道數。任一組合缺漏時會自動回退到通用模板，不會因漏補模板而靜默漏發訊息。
    </Message>

    <div v-if="loading" class="flex items-center justify-center p-12">
      <i class="pi pi-spin pi-spinner text-primary text-4xl"></i>
    </div>

    <div v-else class="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-4">
      <!-- 左：事件類型清單 -->
      <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm p-2 space-y-1 h-fit">
        <div
          v-for="et in Object.keys(EVENT_LABEL)"
          :key="et"
          class="p-2.5 rounded-lg cursor-pointer flex items-center justify-between gap-2 text-sm"
          :class="et === curEvent ? 'bg-primary-50 dark:bg-primary-900/30 text-primary font-bold' : 'hover:bg-surface-50 dark:hover:bg-surface-800'"
          @click="curEvent = et"
        >
          <span>{{ EVENT_LABEL[et] }}</span>
          <Tag v-if="!anyCustom(et)" value="預設" severity="secondary" size="small" />
        </div>
      </div>

      <!-- 右：編輯區 -->
      <div class="space-y-4">
        <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
          <Tabs :value="curChannel" @update:value="(v) => (curChannel = v)">
            <TabList>
              <Tab value="email">Email</Tab>
              <Tab value="telegram">Telegram</Tab>
            </TabList>
          </Tabs>
          <div class="p-4 space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-xs text-surface-400 font-mono">{{ curEvent.toLowerCase() }}.{{ curChannel }}</span>
              <Tag :value="curHasCustom ? '已自訂' : '使用預設模板'" :severity="curHasCustom ? 'success' : 'warn'" />
            </div>
            <div v-if="curChannel === 'email'">
              <label class="text-sm font-bold text-surface-600 dark:text-surface-300 mb-1 block">主旨</label>
              <InputText v-model="titleFormat" fluid class="font-mono text-sm" />
            </div>
            <div>
              <label class="text-sm font-bold text-surface-600 dark:text-surface-300 mb-1 block">內文</label>
              <Textarea v-model="bodyFormat" fluid rows="12" class="font-mono text-sm" />
            </div>
            <div class="flex gap-2">
              <Button label="預覽" icon="pi pi-eye" severity="secondary" outlined @click="doPreview" :loading="previewing" />
              <Button label="儲存模板" icon="pi pi-save" @click="doSave" :loading="saving" />
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm p-4">
            <div class="font-bold text-sm mb-2 flex items-center gap-2"><i class="pi pi-code text-primary"></i>可用變數</div>
            <div class="space-y-1 max-h-64 overflow-y-auto">
              <div v-for="v in variables" :key="v.var" class="text-xs flex gap-2">
                <span class="font-mono font-bold text-primary cursor-pointer" @click="insertVar(v.var)">{{ varToken(v.var) }}</span>
                <span class="text-surface-400">{{ v.desc }}</span>
              </div>
            </div>
          </div>
          <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm p-4">
            <div class="font-bold text-sm mb-2 flex items-center gap-2"><i class="pi pi-eye text-primary"></i>範例資料預覽</div>
            <pre v-if="previewResult?.ok" class="text-xs whitespace-pre-wrap bg-surface-50 dark:bg-surface-800 rounded-lg p-3 max-h-64 overflow-y-auto">{{ previewResult.subject ? '主旨：' + previewResult.subject + '\n\n' : '' }}{{ previewResult.body }}</pre>
            <div v-else-if="previewResult" class="text-xs text-red-500">{{ previewResult.error }}</div>
            <div v-else class="text-xs text-surface-400">點擊「預覽」查看渲染結果</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
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

const loading = ref(true);
const matrix = ref([]);
const curEvent = ref('ALERT_SIGNAL');
const curChannel = ref('telegram');
const titleFormat = ref('');
const bodyFormat = ref('');
const variables = ref([]);
const previewResult = ref(null);
const saving = ref(false);
const previewing = ref(false);

const curEntry = computed(() => matrix.value.find((m) => m.event_type === curEvent.value && m.channel_code === curChannel.value));
const curHasCustom = computed(() => !!curEntry.value?.has_custom);

function anyCustom(eventType) {
  return matrix.value.some((m) => m.event_type === eventType && m.has_custom);
}

async function loadMatrix() {
  loading.value = true;
  try {
    matrix.value = await notifyApi.admin.listTemplates();
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: err.message, life: 4000 });
  } finally {
    loading.value = false;
  }
}

async function loadEditor() {
  previewResult.value = null;
  const entry = curEntry.value;
  titleFormat.value = entry?.template?.title_format || '';
  bodyFormat.value = entry?.template?.body_format || '';
  try {
    variables.value = await notifyApi.admin.getTemplateVariables(curEvent.value);
  } catch {
    variables.value = [];
  }
}

function varToken(name) {
  return '{{ ' + name + ' }}';
}

function insertVar(name) {
  bodyFormat.value += varToken(name);
}

async function doSave() {
  saving.value = true;
  try {
    await notifyApi.admin.updateTemplate(curEvent.value, curChannel.value, {
      title_format: titleFormat.value || null,
      body_format: bodyFormat.value,
      body_kind: curChannel.value === 'email' ? 'html' : 'text'
    });
    toast.add({ severity: 'success', summary: '模板已儲存，下一則訊息即套用', life: 3000 });
    await loadMatrix();
  } catch (err) {
    toast.add({ severity: 'error', summary: '儲存失敗', detail: err.message, life: 4000 });
  } finally {
    saving.value = false;
  }
}

async function doPreview() {
  previewing.value = true;
  try {
    previewResult.value = await notifyApi.admin.previewTemplate({
      event_type: curEvent.value, channel_code: curChannel.value,
      title_format: titleFormat.value || null, body_format: bodyFormat.value
    });
  } catch (err) {
    previewResult.value = { ok: false, error: err.message };
  } finally {
    previewing.value = false;
  }
}

watch([curEvent, curChannel], loadEditor);

onMounted(async () => {
  await loadMatrix();
  await loadEditor();
});
</script>
