<script setup>
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'

const props = defineProps({
  visible: { type: Boolean, default: false },
  data: { type: Object, default: null }
})

const emit = defineEmits(['update:visible', 'writeCard'])

const SCALE_TYPE_MAP = {
  double: '雙磅作業',
  scale1: '1# 地磅',
  scale2: '2# 地磅'
}

const close = () => {
  emit('update:visible', false)
  emit('writeCard', props.data)
}

const writeCard = () => {
  emit('update:visible', false)
  emit('writeCard', props.data)
}
</script>

<template>
  <Dialog :visible="visible" @update:visible="emit('update:visible', $event)"
          header="✅ 入廠過磅確認成功" :modal="true"
          :style="{ width: '520px' }" :closable="false">
    <div v-if="data">
      <div class="mb-3 text-center">
        <div class="text-sm text-500 mb-1">磅單號碼</div>
        <span class="ticket-badge">{{ data.ticketNo }}</span>
      </div>
      <table class="result-table">
        <tr><th>車號</th><td>{{ data.carNo }}</td></tr>
        <tr><th>船號</th><td>{{ data.shipNo || '—' }}</td></tr>
        <tr><th>採購/合約單號</th><td>{{ data.poNo }}</td></tr>
        <tr><th>批次</th><td>{{ data.batchNo || '—' }}</td></tr>
        <tr><th>承運單位</th><td>{{ data.carrier || '—' }}</td></tr>
        <tr><th>原料名稱</th><td>{{ data.materialName || '—' }}</td></tr>
        <tr><th>供應商</th><td>{{ data.supplier || '—' }}</td></tr>
        <tr><th>入廠重量-A1</th><td><strong>{{ data.entryWeightA1 }} Kg</strong></td></tr>
        <tr><th>地磅模式</th><td>{{ SCALE_TYPE_MAP[data.scaleType] }}</td></tr>
        <tr><th>供應商淨重</th><td>{{ data.netWeightSupplier != null ? data.netWeightSupplier + ' Kg' : '—' }}</td></tr>
        <tr><th>公證淨重</th><td>{{ data.netWeightNotary != null ? data.netWeightNotary + ' Kg' : '—' }}</td></tr>
        <tr><th>入廠時間</th><td>{{ data.timestamp }}</td></tr>
      </table>
    </div>
    <template #footer>
      <Button label="關閉" icon="pi pi-times" class="p-button-secondary p-button-outlined"
              @click="close" />
      <Button label="立即寫卡" icon="pi pi-credit-card" class="p-button-help"
              @click="writeCard" />
    </template>
  </Dialog>
</template>
