<template>
  <div class="p-6 max-w-6xl mx-auto space-y-6">
    <Toast />

    <div class="flex items-center flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h1 class="text-3xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-send text-primary text-3xl"></i>
          管道設定
        </h1>
        <p class="text-base text-surface-500 mt-1">啟用／停用各管道並維護必要設定；停用某管道時，其他管道完全不受影響</p>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center p-12">
      <i class="pi pi-spin pi-spinner text-primary text-4xl"></i>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div
        v-for="ch in channels"
        :key="ch.channel_code"
        class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden"
      >
        <div class="flex items-center gap-3 p-4 border-b border-surface-100 dark:border-surface-800">
          <div class="w-11 h-11 rounded-xl bg-primary-50 dark:bg-primary-900/30 text-primary flex items-center justify-center text-lg">
            <i class="pi" :class="iconFor(ch)"></i>
          </div>
          <div class="flex-1 min-w-0">
            <div class="font-black text-surface-900 dark:text-surface-0 flex items-center gap-2">
              {{ ch.channel_name }}
              <Tag :value="statusLabel(ch.status)" :severity="statusSeverity(ch.status)" />
            </div>
            <div class="text-xs text-surface-400">{{ ch.channel_code }}</div>
          </div>
          <ToggleSwitch :modelValue="ch.status === 'enabled'" @update:modelValue="(v) => toggle(ch, v)" />
        </div>

        <div class="p-4 space-y-2">
          <div v-for="f in fieldsFor(ch)" :key="f.key" class="flex items-center justify-between gap-2 text-sm">
            <label class="text-surface-500 font-semibold">{{ f.label }}</label>
            <Select
              v-if="f.type === 'select'"
              v-model="editing[ch.channel_code][f.key]"
              :options="f.options"
              optionLabel="label"
              optionValue="value"
              class="w-56"
              size="small"
            />
            <InputText
              v-else
              v-model="editing[ch.channel_code][f.key]"
              :type="f.masked ? 'password' : 'text'"
              :placeholder="f.masked ? '未變更則留空' : ''"
              :autocomplete="f.masked ? 'new-password' : 'off'"
              class="w-56"
              size="small"
            />
          </div>

          <button
            v-if="helpFor(ch)"
            type="button"
            class="text-xs text-primary font-semibold flex items-center gap-1 mt-1 hover:underline"
            @click="toggleHelp(ch.channel_code)"
          >
            <i class="pi" :class="openHelp[ch.channel_code] ? 'pi-chevron-down' : 'pi-question-circle'"></i>
            {{ openHelp[ch.channel_code] ? '收合說明' : `如何取得${helpFor(ch).fieldLabel}？` }}
          </button>
          <div
            v-if="helpFor(ch) && openHelp[ch.channel_code]"
            class="text-xs text-surface-600 dark:text-surface-300 bg-surface-50 dark:bg-surface-800/50 rounded-lg p-3 space-y-1.5"
          >
            <ol class="list-decimal list-inside space-y-1">
              <li v-for="(step, i) in helpFor(ch).steps" :key="i">{{ step }}</li>
            </ol>
            <p v-if="helpFor(ch).warning" class="text-amber-600 dark:text-amber-400 font-semibold flex items-start gap-1 pt-1">
              <i class="pi pi-exclamation-triangle mt-0.5"></i>
              <span>{{ helpFor(ch).warning }}</span>
            </p>
          </div>

          <div class="flex items-center gap-2 mt-3">
            <Button label="連線測試" icon="pi pi-bolt" severity="secondary" outlined size="small" class="flex-1" :loading="testingCode === ch.channel_code" @click="test(ch)" />
            <Button label="儲存設定" icon="pi pi-save" size="small" class="flex-1" :loading="savingCode === ch.channel_code" @click="save(ch)" />
          </div>
          <p v-if="ch.last_health_detail" class="text-xs text-surface-600 dark:text-surface-300 font-semibold mt-2">{{ ch.last_health_detail }}</p>
          <p v-if="ch.last_health_at" class="text-xs text-surface-400 mt-1">上次測試：{{ formatTime(ch.last_health_at) }}</p>
        </div>
      </div>
    </div>

    <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm p-4">
      <div class="flex items-center gap-2 text-sm text-surface-600 dark:text-surface-300">
        <i class="pi pi-sitemap text-primary"></i>
        <b>擴充性驗證點</b>：未來新增其他管道時，只需「定義設定項目＋新增轉接單元＋補模板」三項，
        既有的訂閱規則、收件人資料、路由與政策邏輯零改動。
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { useToast } from 'primevue/usetoast';
import { notifyApi } from '@/service/notifyApi';

const toast = useToast();
const channels = ref([]);
const loading = ref(true);
const editing = reactive({});
const savingCode = ref(null);
const testingCode = ref(null);

const FIELD_DEFS = {
  email: [
    { key: 'smtp_host', label: 'SMTP 主機', default: 'smtp.gmail.com' },
    { key: 'smtp_port', label: 'SMTP 埠', default: '587' },
    {
      key: 'smtp_security', label: '加密方式', type: 'select', default: 'starttls',
      options: [
        { label: '自動（依埠號判斷）', value: '' },
        { label: 'STARTTLS（587）', value: 'starttls' },
        { label: 'SSL/TLS（465）', value: 'ssl' }
      ]
    },
    { key: 'smtp_user', label: '帳號' },
    { key: 'smtp_password', label: '密碼', masked: true },
    { key: 'sender_name', label: '寄件人名稱' },
    { key: 'sender_email', label: '寄件信箱' }
  ],
  telegram: [
    { key: 'bot_token', label: '機器人憑證', masked: true }
  ],
  slack: [
    { key: 'webhook_url', label: 'Webhook URL', masked: true }
  ]
};

const CHANNEL_ICONS = {
  email: 'pi-envelope',
  telegram: 'pi-send',
  slack: 'pi-hashtag'
};

// 各管道憑證的取得步驟（純說明文字，不影響送出邏輯）
const CHANNEL_HELP = {
  email: {
    fieldLabel: 'Gmail 密碼（App Password）',
    steps: [
      'SMTP 主機／埠／加密方式已預設為 Gmail 設定（smtp.gmail.com、587、STARTTLS），帳號填完整 Gmail 地址即可，通常不需更動',
      '密碼欄位不能填平常登入 Gmail 用的密碼——Google 會直接回 534 5.7.9 拒絕，必須改用「應用程式密碼」',
      '前往 https://myaccount.google.com/security，確認「兩步驟驗證」已是開啟狀態（沒開的話要先開啟，需要手機驗證一次）',
      '兩步驟驗證開啟後，前往 https://myaccount.google.com/apppasswords',
      '應用程式名稱填 MyStock，按建立，會產生一組 16 碼（4 組英文字母，例如 abcd efgh ijkl mnop）',
      '把這組 16 碼複製貼到左側「密碼」欄位（連空格一起貼也沒關係，Google 會自動忽略）',
      '這組密碼只會顯示一次，沒複製到的話回同一頁刪除舊的、重新產生一組即可'
    ],
    warning: '若在 apppasswords 頁面看不到「應用程式密碼」選項，通常是兩步驟驗證還沒真的開啟，或此帳號是進階保護計畫／企業 Workspace 管理員關閉了此功能——後者需改用另一個一般 Gmail 帳號寄信。'
  },
  telegram: {
    fieldLabel: '機器人憑證',
    steps: [
      '在 Telegram 搜尋 @BotFather（官方認證帳號，藍勾勾）並開啟對話',
      '傳送指令 /newbot',
      '依提示輸入機器人的顯示名稱（例如「MyStock 通知」）',
      '再輸入機器人的使用者名稱，必須以 bot 結尾（例如 mystock_jackson_bot）',
      '建立成功後，BotFather 會回傳一段包含 Token 的訊息（例如 8745986133:AAH2wZ...），複製整串貼到左側「機器人憑證」欄位',
      '儲存並連線測試成功後，還要到「收件人管理」頁對你自己按「綁 Telegram」，取得 4 位數綁定碼，再到 Telegram 對該機器人傳送這組碼完成綁定，才會真的收到通知'
    ],
    warning: '這組 Token 等同機器人的帳號密碼，請勿分享給他人或貼在公開頁面。'
  },
  slack: {
    fieldLabel: 'Webhook URL',
    steps: [
      '瀏覽器開啟 https://api.slack.com/apps（用你 Slack 工作區的帳號登入）',
      '點「Create New App」→「From scratch」，輸入 App 名稱並選擇你的工作區',
      '進入 App 設定頁，左側選單點「Incoming Webhooks」',
      '把右上角開關切到 On',
      '往下捲，點「Add New Webhook to Workspace」',
      '選擇這個 Webhook 要發送到「哪一個頻道」（例如 #mystock），按 Allow',
      '複製產生的網址（格式為 https://hooks.slack.com/services/…），貼到左側「Webhook URL」欄位'
    ],
    warning: '這組網址等同密碼，任何拿到它的人都能對該頻道發訊息，請勿分享或貼在公開頁面。'
  }
};

function fieldsFor(ch) {
  return FIELD_DEFS[ch.channel_code] || [];
}

function helpFor(ch) {
  return CHANNEL_HELP[ch.channel_code] || null;
}

const openHelp = reactive({});
function toggleHelp(code) {
  openHelp[code] = !openHelp[code];
}

function iconFor(ch) {
  return CHANNEL_ICONS[ch.channel_code] || 'pi-bell';
}

function statusLabel(s) {
  return { enabled: '正常', disabled: '已停用', misconfigured: '設定不全', circuit_open: '已熔斷' }[s] || s;
}
function statusSeverity(s) {
  return { enabled: 'success', disabled: 'secondary', misconfigured: 'warn', circuit_open: 'danger' }[s] || 'secondary';
}
function formatTime(t) {
  try { return new Date(t).toLocaleString('zh-TW'); } catch { return t; }
}

/**
 * preserveEditing：只更新管道狀態，不覆寫表單。
 * 連線測試後若無條件重填表單，使用者還沒儲存的輸入會被靜默清掉（改了埠號卻跳回舊值）。
 */
async function load({ preserveEditing = false } = {}) {
  loading.value = true;
  try {
    channels.value = await notifyApi.admin.listChannels();
    for (const ch of channels.value) {
      if (preserveEditing && editing[ch.channel_code]) continue;
      editing[ch.channel_code] = {};
      for (const f of fieldsFor(ch)) {
        editing[ch.channel_code][f.key] = f.masked ? '' : (ch.settings?.[f.key] ?? f.default ?? '');
      }
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: err.message, life: 4000 });
  } finally {
    loading.value = false;
  }
}

async function toggle(ch, on) {
  try {
    if (on) await notifyApi.admin.enableChannel(ch.channel_code);
    else await notifyApi.admin.disableChannel(ch.channel_code);
    toast.add({ severity: 'success', summary: on ? '已啟用' : '已停用，其他管道不受影響', life: 2500 });
    await load();
  } catch (err) {
    toast.add({ severity: 'error', summary: '操作失敗', detail: err.message, life: 4000 });
  }
}

async function save(ch) {
  savingCode.value = ch.channel_code;
  try {
    // 未變更的機敏欄位留空 → 傳 null 代表保留原值（後端 PUT /channels/{code} 約定）
    const payload = {};
    for (const f of fieldsFor(ch)) {
      const v = editing[ch.channel_code][f.key];
      payload[f.key] = f.masked && !v ? null : v;
    }
    const result = await notifyApi.admin.updateChannel(ch.channel_code, payload);
    if (result?.errors?.length) {
      toast.add({ severity: 'warn', summary: '設定不完整', detail: result.errors.join('；'), life: 5000 });
    } else {
      toast.add({ severity: 'success', summary: '設定已更新', life: 2500 });
    }
    await load();
  } catch (err) {
    toast.add({ severity: 'error', summary: '儲存失敗', detail: err.message, life: 4000 });
  } finally {
    savingCode.value = null;
  }
}

/** 表單上是否有尚未儲存的變更（機敏欄位留空代表不變更，不列入比對） */
function isDirty(ch) {
  return fieldsFor(ch).some((f) => {
    if (f.masked) return !!editing[ch.channel_code]?.[f.key];
    return (editing[ch.channel_code]?.[f.key] ?? '') !== (ch.settings?.[f.key] ?? '');
  });
}

async function test(ch) {
  // 連線測試打的是「已儲存」的設定，不是表單上的值
  if (isDirty(ch)) {
    toast.add({
      severity: 'warn',
      summary: '有未儲存的變更',
      detail: '連線測試使用的是已儲存的設定，請先按「儲存設定」再測試',
      life: 5000
    });
    return;
  }

  testingCode.value = ch.channel_code;
  try {
    const result = await notifyApi.admin.testChannel(ch.channel_code);
    toast.add({
      severity: result.ok ? 'success' : 'error',
      summary: result.ok ? '連線測試通過' : '連線測試失敗',
      detail: result.detail,
      life: 4000
    });
    await load({ preserveEditing: true });
  } catch (err) {
    toast.add({ severity: 'error', summary: '測試失敗', detail: err.message, life: 4000 });
  } finally {
    testingCode.value = null;
  }
}

onMounted(() => load());
</script>
