<script setup>
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'

defineProps({
  visible: { type: Boolean, default: false },
  data: { type: Object, default: null },
  netWeight: { type: Number, default: null }
})

const emit = defineEmits(['update:visible'])
</script>

<template>
  <Dialog :visible="visible" @update:visible="emit('update:visible', $event)"
          header="✅ 出廠過磅確認成功" :modal="true"
          :style="{ width: '520px' }" :closable="false">
    <div v-if="data">
      <div class="mb-2 text-center">
        <span class="ticket-badge">{{ data.ticketNo }}</span>
      </div>
      <table class="result-table">
        <tr><th>磅單號</th><td>{{ data.ticketNo }}</td></tr>
        <tr><th>修正車號</th><td>{{ data.corrCarNo || '（未修正）' }}</td></tr>
        <tr><th>修正採購單號</th><td>{{ data.corrPoNo || '（未修正）' }}</td></tr>
        <tr><th>修正原料名稱</th><td>{{ data.corrMaterialName || '（未修正）' }}</td></tr>
        <tr><th>修正供應商</th><td>{{ data.corrSupplierName || '（未修正）' }}</td></tr>
        <tr><th>入庫重量-A2</th><td>{{ data.storageWeightA2 != null ? data.storageWeightA2 + ' Kg' : '—' }}</td></tr>
        <tr><th>出庫重量-B2</th><td>{{ data.outboundWeightB2 != null ? data.outboundWeightB2 + ' Kg' : '—' }}</td></tr>
        <tr><th>出廠重量-B1</th><td><strong>{{ data.exitWeightB1 }} Kg</strong></td></tr>
        <tr><th>狀態</th><td>{{ data.exitStatus === 'normal' ? '✅ 正常' : '⚠️ 警告' }}</td></tr>
        <tr><th>退貨旗標</th><td>{{ data.isReturn ? '🔴 是' : '否' }}</td></tr>
        <tr><th>修正批次</th><td>{{ data.corrBatchNo || '—' }}</td></tr>
        <tr><th>出廠時間</th><td>{{ data.timestamp }}</td></tr>
      </table>
      <div v-if="netWeight != null" class="net-weight-box">
        計算淨重（進廠A1 − 出廠B1）：{{ netWeight }} Kg
      </div>
    </div>
    <template #footer>
      <Button label="確定關閉" icon="pi pi-check" @click="emit('update:visible', false)" />
    </template>
  </Dialog>
</template>
