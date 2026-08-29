<template>
  <div class="p-6 max-w-6xl mx-auto space-y-6">
    <Toast />
    <ConfirmDialog />

    <div class="flex items-center flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h1 class="text-3xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-users text-primary text-3xl"></i>
          收件人與端點管理
        </h1>
        <p class="text-base text-surface-500 mt-1">新增收件對象是純資料操作——不需修改設定檔，也不需重啟系統</p>
      </div>
      <div class="flex items-center gap-2">
        <Button label="收件群組" icon="pi pi-folder" severity="secondary" outlined @click="groupDialog = true" />
        <Button label="新增收件人" icon="pi pi-user-plus" @click="openCreateRecipient" />
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center p-12">
      <i class="pi pi-spin pi-spinner text-primary text-4xl"></i>
    </div>

    <template v-else>
      <div v-for="r in recipients" :key="r.recipient_code" class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
        <div class="flex items-center gap-3 p-4 border-b border-surface-100 dark:border-surface-800">
          <div class="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-900/30 text-primary flex items-center justify-center font-black">
            {{ r.display_name.charAt(0) }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="font-black text-surface-900 dark:text-surface-0 flex items-center gap-2 flex-wrap">
              {{ r.display_name }}
              <Tag v-for="g in r.group_names" :key="g" :value="g" severity="secondary" />
              <Tag v-if="r.status === 'disabled'" value="已停用" severity="danger" />
            </div>
            <div class="text-xs text-surface-400">{{ r.endpoints.length }} 個收件端點</div>
          </div>
          <Button label="加 Email" icon="pi pi-envelope" size="small" severity="secondary" outlined @click="openAddEmail(r)" />
          <Button label="綁 Telegram" icon="pi pi-send" size="small" severity="secondary" outlined @click="openBinding(r)" />
        </div>

        <div class="divide-y divide-surface-100 dark:divide-surface-800">
          <div v-for="e in r.endpoints" :key="e.endpoint_code" class="flex items-center gap-3 p-3 px-4">
            <i class="pi text-lg text-surface-400" :class="e.channel_code === 'email' ? 'pi-envelope' : 'pi-send'"></i>
            <div class="flex-1 min-w-0">
              <div class="font-semibold text-sm flex items-center gap-2 flex-wrap">
                {{ e.address }}
                <Tag :value="e.verify_status === 'verified' ? '已驗證' : '待驗證'" :severity="e.verify_status === 'verified' ? 'success' : 'warn'" size="small" />
                <Tag v-if="e.pause_until" value="暫停中" severity="warn" size="small" />
                <Tag v-if="e.status === 'disabled'" value="已停用" severity="danger" size="small" />
              </div>
              <div class="text-xs text-surface-400">
                模式 {{ MODE_LABEL[e.delivery_mode] }}　上限 {{ e.daily_limit }} 則/日
              </div>
            </div>
            <Button v-if="e.verify_status !== 'verified' && e.channel_code === 'email'" label="重寄驗證信" size="small" text @click="resendVerify(r, e)" />
            <Button icon="pi pi-send" size="small" text @click="testSend(e)" title="測試發送" />
            <Button icon="pi pi-times" size="small" text severity="danger" @click="disableEndpoint(e)" title="停用" />
          </div>
          <p v-if="!r.endpoints.length" class="p-4 text-sm text-surface-400">尚無收件端點</p>
        </div>

        <div class="flex items-center gap-2 p-3 px-4 bg-surface-50 dark:bg-surface-800/40 border-t border-surface-100 dark:border-surface-800">
          <i class="pi pi-link text-surface-400"></i>
          <span class="text-xs font-bold text-surface-500">自助設定連結</span>
          <span class="flex-1 text-xs text-surface-400 font-mono truncate">平台只保存雜湊摘要，明文只在產生當下顯示一次</span>
          <Button label="撤銷重產" icon="pi pi-refresh" size="small" text @click="issueLink(r)" />
        </div>
      </div>

      <div v-if="sharedEndpoints.length" class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
        <div class="p-4 border-b border-surface-100 dark:border-surface-800">
          <div class="font-black flex items-center gap-2"><i class="pi pi-users text-primary"></i>共用端點（系統擁有者管理）</div>
          <p class="text-xs text-surface-400 mt-0.5">Telegram 群組等多人共用位置，不屬於任何收件人，不附個人自助連結</p>
        </div>
        <div class="divide-y divide-surface-100 dark:divide-surface-800">
          <div v-for="e in sharedEndpoints" :key="e.endpoint_code" class="flex items-center gap-3 p-3 px-4">
            <i class="pi pi-send text-lg text-surface-400"></i>
            <div class="flex-1 min-w-0">
              <div class="font-semibold text-sm">{{ e.address }}</div>
              <div class="text-xs text-surface-400">模式 {{ MODE_LABEL[e.delivery_mode] }}</div>
            </div>
            <Button icon="pi pi-send" size="small" text @click="testSend(e)" title="測試發送" />
          </div>
        </div>
      </div>
    </template>

    <!-- 新增收件人 -->
    <Dialog v-model:visible="createDialog" header="新增收件人" modal style="width: 26rem">
      <div class="space-y-3">
        <div>
          <label class="text-sm font-bold text-surface-600 dark:text-surface-300 mb-1 block">顯示名稱</label>
          <InputText v-model="newRecipientName" fluid placeholder="例如：家人 B" />
        </div>
        <div>
          <label class="text-sm font-bold text-surface-600 dark:text-surface-300 mb-1 block">加入收件群組（選填）</label>
          <MultiSelect v-model="newRecipientGroups" :options="groups.map(g => g.group_name)" placeholder="不加入群組" fluid />
        </div>
      </div>
      <template #footer>
        <Button label="取消" text @click="createDialog = false" />
        <Button label="建立" icon="pi pi-check" @click="submitCreateRecipient" :loading="creating" />
      </template>
    </Dialog>

    <!-- 新增 Email 端點 -->
    <Dialog v-model:visible="emailDialog" header="新增 Email 收件端點" modal style="width: 28rem">
      <div class="space-y-3">
        <div>
          <label class="text-sm font-bold text-surface-600 dark:text-surface-300 mb-1 block">收件信箱</label>
          <InputText v-model="newEmailAddress" fluid placeholder="name@example.com" />
        </div>
        <Message severity="warn" :closable="false">Email 採個人信箱寄送，有每日寄送量限制，建議使用每日摘要模式。</Message>
      </div>
      <template #footer>
        <Button label="取消" text @click="emailDialog = false" />
        <Button label="建立並寄出驗證信" icon="pi pi-send" @click="submitAddEmail" :loading="creating" />
      </template>
    </Dialog>

    <!-- Telegram 綁定碼 -->
    <Dialog v-model:visible="bindDialog" header="綁定 Telegram" modal style="width: 26rem">
      <div class="text-center py-2">
        <div class="text-xs text-surface-400 font-bold mb-1">一次性綁定碼（15 分鐘內有效）</div>
        <div class="text-3xl font-black tracking-widest text-primary font-mono">{{ bindCode || '——' }}</div>
      </div>
      <ol class="text-sm space-y-1.5 mt-3 list-decimal list-inside text-surface-600 dark:text-surface-300">
        <li>請收件人在 Telegram 搜尋機器人並點擊「開始」</li>
        <li>在對話中直接送出上方的綁定碼</li>
        <li>機器人回覆「綁定成功」後，系統會自動建立端點並開始接收通知</li>
      </ol>
    </Dialog>

    <!-- 收件群組 -->
    <Dialog v-model:visible="groupDialog" header="收件群組" modal style="width: 24rem">
      <div class="space-y-2">
        <div v-for="g in groups" :key="g.group_code" class="flex items-center gap-2 p-2 border border-surface-200 dark:border-surface-700 rounded-lg">
          <i class="pi pi-folder text-primary"></i>
          <div class="flex-1">
            <div class="font-bold text-sm">{{ g.group_name }}</div>
            <div class="text-xs text-surface-400">{{ (g.members || []).length }} 位成員</div>
          </div>
        </div>
        <div class="flex items-center gap-2 mt-2">
          <InputText v-model="newGroupName" placeholder="新群組名稱" class="flex-1" size="small" />
          <Button icon="pi pi-plus" size="small" @click="submitCreateGroup" />
        </div>
      </div>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';
import { notifyApi } from '@/service/notifyApi';

const toast = useToast();
const confirm = useConfirm();

const MODE_LABEL = { realtime: '即時', digest: '每日摘要', critical_only: '僅緊急' };

const recipients = ref([]);
const sharedEndpoints = ref([]);
const groups = ref([]);
const loading = ref(true);

const createDialog = ref(false);
const newRecipientName = ref('');
const newRecipientGroups = ref([]);
const creating = ref(false);

const emailDialog = ref(false);
const newEmailAddress = ref('');
let emailTargetRecipient = null;

const bindDialog = ref(false);
const bindCode = ref('');

const groupDialog = ref(false);
const newGroupName = ref('');

async function load() {
  loading.value = true;
  try {
    const [recipientsRes, sharedRes, groupsRes] = await Promise.all([
      notifyApi.admin.listRecipients(),
      notifyApi.admin.listSharedEndpoints(),
      notifyApi.admin.listGroups()
    ]);
    recipients.value = recipientsRes;
    sharedEndpoints.value = sharedRes;
    groups.value = groupsRes;
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: err.message, life: 4000 });
  } finally {
    loading.value = false;
  }
}

function openCreateRecipient() {
  newRecipientName.value = '';
  newRecipientGroups.value = [];
  createDialog.value = true;
}

async function submitCreateRecipient() {
  if (!newRecipientName.value.trim()) return;
  creating.value = true;
  try {
    const groupCodes = groups.value.filter((g) => newRecipientGroups.value.includes(g.group_name)).map((g) => g.group_code);
    await notifyApi.admin.createRecipient(newRecipientName.value.trim(), groupCodes);
    toast.add({ severity: 'success', summary: '已新增收件人', life: 2500 });
    createDialog.value = false;
    await load();
  } catch (err) {
    toast.add({ severity: 'error', summary: '新增失敗', detail: err.message, life: 4000 });
  } finally {
    creating.value = false;
  }
}

function openAddEmail(r) {
  emailTargetRecipient = r;
  newEmailAddress.value = '';
  emailDialog.value = true;
}

async function submitAddEmail() {
  if (!newEmailAddress.value.trim() || !emailTargetRecipient) return;
  creating.value = true;
  try {
    await notifyApi.admin.createEmailEndpoint(emailTargetRecipient.recipient_code, newEmailAddress.value.trim());
    toast.add({ severity: 'success', summary: '已建立，驗證信 24 小時內有效', life: 3500 });
    emailDialog.value = false;
    await load();
  } catch (err) {
    toast.add({ severity: 'error', summary: '新增失敗', detail: err.message, life: 4000 });
  } finally {
    creating.value = false;
  }
}

async function resendVerify(r, e) {
  try {
    await notifyApi.admin.resendVerification(r.recipient_code, e.endpoint_code);
    toast.add({ severity: 'success', summary: '驗證信已重新寄出', life: 2500 });
  } catch (err) {
    toast.add({ severity: 'error', summary: '寄送失敗', detail: err.message, life: 4000 });
  }
}

async function openBinding(r) {
  bindCode.value = '';
  bindDialog.value = true;
  try {
    const result = await notifyApi.admin.issueBindingCode(r.recipient_code);
    bindCode.value = result.code;
  } catch (err) {
    toast.add({ severity: 'error', summary: '產生綁定碼失敗', detail: err.message, life: 4000 });
    bindDialog.value = false;
  }
}

async function testSend(e) {
  try {
    const result = await notifyApi.admin.testSend(e.endpoint_code);
    toast.add({ severity: result.ok ? 'success' : 'error', summary: result.ok ? '測試訊息已送出' : '發送失敗', detail: result.detail, life: 4000 });
  } catch (err) {
    toast.add({ severity: 'error', summary: '測試失敗', detail: err.message, life: 4000 });
  }
}

function disableEndpoint(e) {
  confirm.require({
    message: `確定要停用端點「${e.address}」嗎？歷史紀錄會保留。`,
    header: '停用端點',
    icon: 'pi pi-exclamation-triangle',
    accept: async () => {
      try {
        await notifyApi.admin.disableEndpoint(e.endpoint_code);
        toast.add({ severity: 'success', summary: '已停用', life: 2500 });
        await load();
      } catch (err) {
        toast.add({ severity: 'error', summary: '停用失敗', detail: err.message, life: 4000 });
      }
    }
  });
}

function issueLink(r) {
  confirm.require({
    message: '撤銷並重新產生後，舊連結會立即失效。確定要繼續嗎？',
    header: '撤銷重產自助連結',
    icon: 'pi pi-exclamation-triangle',
    accept: async () => {
      try {
        const result = await notifyApi.admin.issueSelfServiceLink(r.recipient_code);
        toast.add({ severity: 'success', summary: '新連結已產生（僅顯示一次）', detail: result.url, life: 10000 });
      } catch (err) {
        toast.add({ severity: 'error', summary: '產生失敗', detail: err.message, life: 4000 });
      }
    }
  });
}

async function submitCreateGroup() {
  if (!newGroupName.value.trim()) return;
  try {
    await notifyApi.admin.createGroup(newGroupName.value.trim());
    newGroupName.value = '';
    toast.add({ severity: 'success', summary: '已建立群組', life: 2500 });
    groups.value = await notifyApi.admin.listGroups();
  } catch (err) {
    toast.add({ severity: 'error', summary: '建立失敗', detail: err.message, life: 4000 });
  }
}

onMounted(load);
</script>
