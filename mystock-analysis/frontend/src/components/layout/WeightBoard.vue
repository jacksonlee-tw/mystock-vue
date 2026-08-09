<script setup>
import Button from 'primevue/button'

defineProps({
  connected: { type: Boolean, default: false },
  currentWeight: { type: String, default: ' ----  ' },
  weightPulse: { type: Boolean, default: false }
})

const emit = defineEmits(['connect', 'disconnect'])
</script>

<template>
  <div class="weight-board">
    <div class="ws-btns">
      <Button label="開始連線" icon="pi pi-play"
              :disabled="connected" @click="emit('connect')"
              class="p-button-sm p-button-success" />
      <Button label="中斷連線" icon="pi pi-stop"
              :disabled="!connected" @click="emit('disconnect')"
              class="p-button-sm p-button-danger p-button-outlined" />
    </div>
    <div style="text-align: right; font-size: 0.72rem; color: #64748b; line-height: 1.4">
      <div>即時磅值</div>
      <div>（Kg）</div>
    </div>
    <div :class="['weight-display', weightPulse ? 'pulse' : '']">
      {{ currentWeight }}
    </div>
  </div>
</template>
