<script setup>
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'

defineProps({
  visible: { type: Boolean, default: false },
  data: { type: Object, default: null }
})

const emit = defineEmits(['update:visible', 'write'])
</script>

<template>
  <Dialog :visible="visible" @update:visible="emit('update:visible', $event)"
          header="💳 感應卡寫卡作業（UC-004B）" :modal="true"
          :style="{ width: '420px' }">
    <div class="p-3">
      <div v-if="data" class="mb-3 p-3 border-round border-1 border-teal-300"
           style="background: #f0fdfa">
        <div class="font-bold mb-2 text-teal-700">將寫入以下資料至感應卡：</div>
        <table class="result-table">
          <tr><th>磅單號碼</th><td><strong>{{ data.ticketNo }}</strong></td></tr>
          <tr><th>車號</th><td>{{ data.carNo }}</td></tr>
          <tr><th>採購單號</th><td>{{ data.poNo }}</td></tr>
          <tr><th>原料名稱</th><td>{{ data.materialName || '—' }}</td></tr>
          <tr><th>入廠重量</th><td>{{ data.entryWeightA1 }} Kg</td></tr>
          <tr><th>入廠時間</th><td>{{ data.timestamp }}</td></tr>
        </table>
      </div>
      <div v-else class="text-500 text-center p-3">請確認感應卡已放置於讀寫器上。</div>
      <div class="mt-2 p-2 border-round text-sm" style="background: #eff6ff; color: #1d4ed8">
        📋 請將空白感應卡放置於讀卡器後點擊「執行寫卡」
      </div>
    </div>
    <template #footer>
      <Button label="略過" class="p-button-secondary p-button-outlined"
              @click="emit('update:visible', false)" />
      <Button label="執行寫卡" icon="pi pi-credit-card" class="p-button-help"
              @click="emit('write')" />
    </template>
  </Dialog>
</template>
