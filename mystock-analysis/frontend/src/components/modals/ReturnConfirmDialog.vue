<script setup>
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'

defineProps({
  visible: { type: Boolean, default: false },
  ticketNo: { type: String, default: '' }
})

const emit = defineEmits(['update:visible', 'confirmed'])
</script>

<template>
  <Dialog :visible="visible" @update:visible="emit('update:visible', $event)"
          header="🔴 退貨旗標確認" :modal="true"
          :style="{ width: '400px' }" :closable="false">
    <div class="p-3">
      <div class="p-3 border-round border-1 border-red-300" style="background: #fff1f2; color: #9b1c1c">
        <div class="font-bold mb-2">⚠️ 此車輛標記為退貨！</div>
        <p class="mb-1">磅單號：<strong>{{ ticketNo }}</strong></p>
        <p class="mb-0">請確認是否繼續執行退貨出廠作業？</p>
      </div>
    </div>
    <template #footer>
      <Button label="取消" class="p-button-secondary p-button-outlined"
              @click="emit('update:visible', false)" />
      <Button label="確認退貨出廠" icon="pi pi-check" class="p-button-danger"
              @click="emit('confirmed')" />
    </template>
  </Dialog>
</template>
