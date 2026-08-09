<script setup>
import { ref } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import RadioButton from 'primevue/radiobutton'
import { useToast } from 'primevue/usetoast'

const props = defineProps({
  visible: { type: Boolean, default: false },
  type: { type: String, default: 'in' },
  ticketNo: { type: String, default: '' }
})

const emit = defineEmits(['update:visible', 'print'])

const toast = useToast()
const localType = ref(props.type)
const localTicketNo = ref(props.ticketNo)

// 同步 props → local (Dialog 開啟時)
const onShow = () => {
  localType.value = props.type
  localTicketNo.value = props.ticketNo
}

const doPrint = () => {
  if (!localTicketNo.value.trim()) {
    toast.add({ severity: 'warn', summary: '請填寫磅單號碼', detail: '磅單號碼不能為空', life: 3000 })
    return
  }
  emit('print', localTicketNo.value, localType.value)
}
</script>

<template>
  <Dialog :visible="visible" @update:visible="emit('update:visible', $event)"
          :header="'🖨️ 補印' + (type === 'in' ? '入廠' : '出廠') + '磅單（UC-003）'"
          :modal="true" :style="{ width: '400px' }" :closable="false"
          @show="onShow">
    <div class="p-3">
      <div class="field">
        <label class="font-bold">磅單號碼</label>
        <InputText v-model="localTicketNo" class="w-full mt-2" placeholder="請輸入磅單號碼" />
      </div>
      <div class="flex gap-4 mt-3">
        <div class="flex align-items-center">
          <RadioButton v-model="localType" inputId="dlgPrintIn" value="in" />
          <label for="dlgPrintIn" class="ml-2">入廠磅單</label>
        </div>
        <div class="flex align-items-center">
          <RadioButton v-model="localType" inputId="dlgPrintOut" value="out" />
          <label for="dlgPrintOut" class="ml-2">出廠磅單</label>
        </div>
      </div>
    </div>
    <template #footer>
      <Button label="取消" class="p-button-secondary p-button-outlined"
              @click="emit('update:visible', false)" />
      <Button label="確認列印" icon="pi pi-print" @click="doPrint" />
    </template>
  </Dialog>
</template>
