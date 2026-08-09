<script setup>
defineProps({
  connected: { type: Boolean, default: false }
})
</script>

<template>
  <div class="app-header">
    <i class="pi pi-server" style="font-size: 1.4rem"></i>
    <h1>過磅作業系統 — 廠門地磅作業（一車四磅）</h1>
    <span :class="['status-badge', connected ? 'badge-online' : 'badge-offline']">
      {{ connected ? '● 已連線' : '● 未連線' }}
    </span>
  </div>
</template>
