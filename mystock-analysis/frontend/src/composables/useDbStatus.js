import { ref, readonly, onMounted } from 'vue'
import { getDbStatus } from '@/services/weighbridgeService'

/**
 * DB 連線狀態 composable
 * 啟動時自動取得資料庫連線狀態，供 AppTopbar 標頭徽章使用
 */
export const useDbStatus = () => {
  const dbStatus = ref({
    connected: false,
    mode: 'memory',
    server: '',
    database: '',
    compNo: '',
    plantNo: ''
  })

  const fetchDbStatus = async () => {
    try {
      const result = await getDbStatus()
      dbStatus.value = result
    } catch {
      dbStatus.value = {
        connected: false,
        mode: 'memory',
        server: '',
        database: '',
        compNo: '',
        plantNo: ''
      }
    }
  }

  onMounted(() => {
    fetchDbStatus()
  })

  return {
    dbStatus: readonly(dbStatus),
    fetchDbStatus
  }
}
