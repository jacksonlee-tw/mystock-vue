<script setup>
import { ref } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import { useToast } from 'primevue/usetoast'

const props = defineProps({
  visible: { type: Boolean, default: false },
  entryWeight: { type: Number, default: 0 },
  weightLimit: { type: Number, default: 5000 }
})

const emit = defineEmits(['update:visible', 'authorized'])

const toast = useToast()
const account = ref('')
const password = ref('')

const doAuth = () => {
  if (!account.value || !password.value) {
    toast.add({ severity: 'warn', summary: '請填寫', detail: '請輸入主管帳號與密碼', life: 3000 })
    return
  }
  if (account.value === 'admin' && password.value === '1234') {
    emit('update:visible', false)
    toast.add({ severity: 'success', summary: '授權成功', detail: `已由 ${account.value} 主管授權放行`, life: 3000 })
    emit('authorized')
  } else {
    toast.add({ severity: 'error', summary: '授權失敗', detail: '主管帳號或密碼錯誤（提示：admin / 1234）', life: 5000 })
  }
}

const cancel = () => {
  account.value = ''
  password.value = ''
  emit('update:visible', false)
}
</script>

<template>
  <Dialog :visible="visible" @update:visible="emit('update:visible', $event)"
          header="⚠️ 重量超過設定上限 — 需主管授權" :modal="true"
          :style="{ width: '420px' }" :closable="false">
    <div class="p-3">
      <div class="mb-3 p-3 border-round border-1 border-yellow-300"
           style="background: #fefce8; color: #92400e">
        入廠重量 <strong>{{ entryWeight }} Kg</strong> 超過系統上限（{{ weightLimit }} Kg）。
        需主管帳號密碼放行。
      </div>
      <div class="field">
        <label class="font-bold">主管帳號</label>
        <InputText v-model="account" class="w-full mt-2" placeholder="主管帳號（提示：admin）" />
      </div>
      <div class="field mt-3">
        <label class="font-bold">主管密碼</label>
        <InputText v-model="password" type="password" class="w-full mt-2" placeholder="主管密碼（提示：1234）" />
      </div>
    </div>
    <template #footer>
      <Button label="取消" class="p-button-secondary p-button-outlined" @click="cancel" />
      <Button label="確認授權" icon="pi pi-shield" class="p-button-warning" @click="doAuth" />
    </template>
  </Dialog>
</template>
