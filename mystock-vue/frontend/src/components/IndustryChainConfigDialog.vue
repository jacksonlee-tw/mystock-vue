<template>
  <Dialog v-model:visible="visible" header="管理產業鏈" modal style="width: 42rem" :breakpoints="{ '900px': '92vw' }">
    <div class="space-y-4">
      <div v-if="loading" class="flex items-center gap-2 text-surface-500 text-sm py-10 justify-center">
        <i class="pi pi-spin pi-spinner"></i> 載入中...
      </div>

      <!-- 清單模式：列出目前所有鏈，新增/編輯/刪除都先改本地清單，按「儲存全部變更」才整份寫回 YAML -->
      <template v-else-if="editingIndex === null">
        <div class="flex items-center justify-between">
          <p class="text-xs text-surface-500">變更僅影響「鏈的骨架」（YAML），不會動到資料庫裡已萃取的邊資料</p>
          <Button label="新增產業鏈" icon="pi pi-plus" size="small" text @click="openAdd" />
        </div>

        <div class="border border-surface-200 dark:border-surface-700 rounded-xl overflow-hidden">
          <div class="overflow-x-auto" style="max-height: 24rem; overflow-y: auto">
            <table class="w-full text-left border-collapse text-xs">
              <thead class="sticky top-0 bg-surface-50 dark:bg-surface-800 text-surface-400 uppercase tracking-wide z-10">
                <tr>
                  <th class="p-2">代碼</th>
                  <th class="p-2">名稱</th>
                  <th class="p-2">下游龍頭股</th>
                  <th class="p-2 text-center w-20">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, idx) in items" :key="item.chain_id || idx" class="border-t border-surface-100 dark:border-surface-800">
                  <td class="p-2 font-bold text-surface-700 dark:text-surface-200 align-top">{{ item.chain_id }}</td>
                  <td class="p-2 align-top">
                    {{ item.name }}
                    <div v-if="item.note" class="text-surface-400 mt-0.5">{{ item.note }}</div>
                  </td>
                  <td class="p-2 align-top">
                    <span v-if="item.downstream_leaders.length">{{ item.downstream_leaders.join('、') }}</span>
                    <span v-else class="text-amber-600">尚未核定</span>
                  </td>
                  <td class="p-2 text-center align-top whitespace-nowrap">
                    <button @click="openEdit(idx)" title="編輯" class="text-surface-400 hover:text-primary mx-1"><i class="pi pi-pencil"></i></button>
                    <button @click="removeItem(idx)" title="刪除" class="text-surface-400 hover:text-red-500 mx-1"><i class="pi pi-trash"></i></button>
                  </td>
                </tr>
                <tr v-if="!items.length"><td colspan="4" class="p-6 text-center text-surface-400">尚未設定任何產業鏈</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>

      <!-- 編輯模式：新增或編輯單一鏈，「套用此鏈」只改本地清單，仍要回到清單再按「儲存全部變更」 -->
      <template v-else>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">chain_id（英數字/底線，存檔後儘量不要再改）</label>
            <InputText v-model="form.chain_id" :disabled="editingIndex >= 0" class="w-full" placeholder="例如: ev_battery" />
          </div>
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">名稱</label>
            <InputText v-model="form.name" class="w-full" placeholder="例如: 電動車電池鏈" />
          </div>
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">下游龍頭股代號（逗號分隔）</label>
          <InputText v-model="form.leadersText" class="w-full" placeholder="例如: 2308,1519" />
          <p class="text-[11px] text-surface-400 mt-1">龍頭股是點火偵測與「觸發本鏈萃取」的錨點；留空表示此鏈尚未核定，僅能人工新增邊，不會參與 LLM 萃取</p>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">CCF 掃描天數 - 最小（選填）</label>
            <InputNumber v-model="form.leadLagMin" :min="1" class="w-full" placeholder="預設 1" />
          </div>
          <div>
            <label class="block text-xs font-bold text-surface-500 mb-1">CCF 掃描天數 - 最大（選填）</label>
            <InputNumber v-model="form.leadLagMax" :min="1" class="w-full" placeholder="預設 30" />
          </div>
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">LLM 萃取提示（選填）</label>
          <Textarea v-model="form.extraction_hint" rows="2" class="w-full" placeholder="例如：請特別涵蓋散熱、電源、機殼與高速連接器環節。" />
        </div>
        <div>
          <label class="block text-xs font-bold text-surface-500 mb-1">備註（選填，僅顯示於此清單，不影響萃取邏輯）</label>
          <Textarea v-model="form.note" rows="2" class="w-full" placeholder="例如：範例，實際名單待核定" />
        </div>
      </template>
    </div>

    <template #footer>
      <template v-if="editingIndex === null">
        <Button label="關閉" text @click="close" />
        <Button label="儲存全部變更" icon="pi pi-check" :loading="saving" :disabled="loading" @click="saveAll" />
      </template>
      <template v-else>
        <Button label="返回清單" text @click="editingIndex = null" />
        <Button label="套用此鏈" icon="pi pi-check" @click="applyForm" />
      </template>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';
import { industryChainApi } from '@/service/industryChainApi';

const props = defineProps({ visible: Boolean });
const emit = defineEmits(['update:visible', 'saved']);

const visible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v)
});

const toast = useToast();
const confirm = useConfirm();

const items = ref([]);
const loading = ref(false);
const saving = ref(false);
const editingIndex = ref(null); // null=清單模式, -1=新增, >=0=編輯 items[idx]

const emptyForm = () => ({ chain_id: '', name: '', leadersText: '', leadLagMin: null, leadLagMax: null, extraction_hint: '', note: '' });
const form = reactive(emptyForm());

async function load() {
  loading.value = true;
  try {
    const res = await industryChainApi.getChainsConfig();
    items.value = res.data.items.map((it) => ({ ...it }));
  } catch (err) {
    toast.add({ severity: 'error', summary: '讀取設定失敗', detail: err?.response?.data?.error?.message || err.message, life: 5000 });
  } finally {
    loading.value = false;
  }
}

// 每次打開對話框都重新讀一次，確保看到的是目前檔案內容（丟棄上次未儲存就關閉的本地編輯）
watch(visible, (v) => {
  if (v) {
    editingIndex.value = null;
    load();
  }
});

function openAdd() {
  Object.assign(form, emptyForm());
  editingIndex.value = -1;
}

function openEdit(idx) {
  const it = items.value[idx];
  Object.assign(form, {
    chain_id: it.chain_id,
    name: it.name,
    leadersText: it.downstream_leaders.join(','),
    leadLagMin: it.lead_lag_window_days ? it.lead_lag_window_days[0] : null,
    leadLagMax: it.lead_lag_window_days ? it.lead_lag_window_days[1] : null,
    extraction_hint: it.extraction_hint,
    note: it.note
  });
  editingIndex.value = idx;
}

function removeItem(idx) {
  const it = items.value[idx];
  confirm.require({
    message: `確定刪除「${it.chain_id} ${it.name}」？資料庫裡此鏈既有的邊資料不會被清除，只是骨架設定裡不再列出。`,
    header: '刪除產業鏈',
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: '刪除',
    rejectLabel: '取消',
    acceptProps: { severity: 'danger' },
    accept: () => items.value.splice(idx, 1)
  });
}

function applyForm() {
  const chainId = form.chain_id.trim();
  const name = form.name.trim();
  if (!chainId || !/^[A-Za-z0-9_]+$/.test(chainId)) {
    toast.add({ severity: 'warn', summary: 'chain_id 只能是英數字與底線，且不可為空', life: 4000 });
    return;
  }
  if (!name) {
    toast.add({ severity: 'warn', summary: '名稱不可為空', life: 3000 });
    return;
  }
  const dup = items.value.some((it, i) => it.chain_id === chainId && i !== editingIndex.value);
  if (dup) {
    toast.add({ severity: 'warn', summary: `chain_id「${chainId}」已存在`, life: 4000 });
    return;
  }
  if ((form.leadLagMin != null) !== (form.leadLagMax != null)) {
    toast.add({ severity: 'warn', summary: 'CCF 掃描天數請兩個都填，或都留空套用預設值', life: 4000 });
    return;
  }

  const entry = {
    chain_id: chainId,
    name,
    downstream_leaders: form.leadersText.split(',').map((s) => s.trim()).filter(Boolean),
    lead_lag_window_days: form.leadLagMin != null ? [form.leadLagMin, form.leadLagMax] : null,
    extraction_hint: form.extraction_hint.trim(),
    note: form.note.trim()
  };

  if (editingIndex.value === -1) {
    items.value.push(entry);
  } else {
    items.value.splice(editingIndex.value, 1, entry);
  }
  editingIndex.value = null;
}

async function saveAll() {
  saving.value = true;
  try {
    await industryChainApi.saveChainsConfig(items.value);
    toast.add({ severity: 'success', summary: '已儲存產業鏈骨架設定', life: 3000 });
    emit('saved');
    visible.value = false;
  } catch (err) {
    toast.add({ severity: 'error', summary: '儲存失敗', detail: err?.response?.data?.error?.message || err.message, life: 6000 });
  } finally {
    saving.value = false;
  }
}

function close() {
  visible.value = false;
}
</script>
