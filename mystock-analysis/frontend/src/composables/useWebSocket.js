import { ref, nextTick } from 'vue'

/**
 * WebSocket 連線管理 composable
 * 負責地磅即時重量推播連線
 */
export const useWebSocket = (toast) => {
  const connected = ref(false)
  const currentWeight = ref(' ----  ')
  const weightPulse = ref(false)
  let ws = null

  const wsConnect = () => {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${location.host}/ws/weight`
    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
      toast?.add({ severity: 'success', summary: '磅秤連線', detail: '已成功連線至地磅設備', life: 3000 })
    }

    ws.onmessage = (ev) => {
      const d = JSON.parse(ev.data)
      currentWeight.value = String(d.weight.toFixed(1)).padStart(7, ' ')
      weightPulse.value = false
      nextTick(() => { weightPulse.value = true })
    }

    ws.onclose = () => {
      connected.value = false
      currentWeight.value = ' ----  '
    }

    ws.onerror = () => {
      connected.value = false
      toast?.add({ severity: 'error', summary: '連線錯誤', detail: '磅秤 WebSocket 連線失敗', life: 5000 })
    }
  }

  const wsDisconnect = () => {
    if (ws) { ws.close(); ws = null }
    toast?.add({ severity: 'info', summary: '已中斷', detail: '磅秤連線已中斷', life: 3000 })
  }

  const getCurrentWeightValue = () => {
    const w = parseFloat(currentWeight.value)
    return (!isNaN(w) && w > 0) ? w : null
  }

  return {
    connected,
    currentWeight,
    weightPulse,
    wsConnect,
    wsDisconnect,
    getCurrentWeightValue
  }
}
