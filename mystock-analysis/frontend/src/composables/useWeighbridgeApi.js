import { ref, readonly } from 'vue'
import * as weighbridgeService from '@/services/weighbridgeService'
import { handleApiError } from '@/utils/apiErrorHandler'

/**
 * 過磅作業 API composable
 * 封裝入廠/出廠/列印/查詢等 API 呼叫與狀態管理
 */
export const useWeighbridgeApi = (toast) => {
  const isLoading = ref(false)

  /** 入廠過磅確認 */
  const confirmEntry = async (formData) => {
    isLoading.value = true
    try {
      const result = await weighbridgeService.confirmEntry(formData)
      if (result.status === 'success') {
        toast?.add({ severity: 'success', summary: '入廠確認成功', detail: `磅單號：${result.ticketNo}`, life: 4000 })
      }
      return result
    } catch (err) {
      handleApiError(err, toast, '入廠存檔失敗')
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /** 出廠過磅確認 */
  const confirmExit = async (formData) => {
    isLoading.value = true
    try {
      const result = await weighbridgeService.confirmExit(formData)
      if (result.status === 'success') {
        toast?.add({ severity: 'success', summary: '出廠確認成功', detail: `磅單 ${formData.ticketNo} 出廠完成`, life: 4000 })
      }
      return result
    } catch (err) {
      handleApiError(err, toast, '出廠存檔失敗')
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /** 補印磅單 */
  const printTicket = async (ticketNo, type) => {
    isLoading.value = true
    try {
      const result = await weighbridgeService.printTicket(ticketNo, type)
      toast?.add({ severity: 'success', summary: '列印成功', detail: result.message, life: 3000 })
      return result
    } catch (err) {
      handleApiError(err, toast, '列印失敗')
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /** 查詢磅單 */
  const getTicket = async (ticketNo) => {
    isLoading.value = true
    try {
      return await weighbridgeService.getTicket(ticketNo)
    } catch (err) {
      handleApiError(err, toast, '查詢磅單失敗')
      throw err
    } finally {
      isLoading.value = false
    }
  }

  return {
    isLoading: readonly(isLoading),
    confirmEntry,
    confirmExit,
    printTicket,
    getTicket
  }
}
