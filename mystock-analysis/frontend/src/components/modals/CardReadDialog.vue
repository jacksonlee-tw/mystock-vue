<script setup>
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'

defineProps({
  visible: { type: Boolean, default: false },
  ticketNo: { type: String, default: '' },
  carNo: { type: String, default: '' },
  materialName: { type: String, default: '' }
})

const emit = defineEmits(['update:visible', 'apply'])
</script>

<template>
  <Dialog :visible="visible" @update:visible="emit('update:visible', $event)"
          header="💳 感應卡讀卡結果（UC-004A）" :modal="true"
          :style="{ width: '380px' }">
    <div class="p-3">
      <div class="p-3 border-round border-1 border-blue-300 mb-3"
           style="background: #eff6ff; color: #1e3a8a">
        <div class="font-bold mb-2">📖 讀取到感應卡資料：</div>
        <table class="result-table">
          <tr><th>磅單號碼</th><td><strong>{{ ticketNo }}</strong></td></tr>
          <tr><th>車號</th><td>{{ carNo }}</td></tr>
          <tr><th>原料名稱</th><td>{{ materialName }}</td></tr>
        </table>
      </div>
    </div>
    <template #footer>
      <Button label="取消" class="p-button-secondary p-button-outlined"
              @click="emit('update:visible', false)" />
      <Button label="帶入磅單號" icon="pi pi-arrow-right"
              @click="emit('apply')" />
    </template>
  </Dialog>
</template>
