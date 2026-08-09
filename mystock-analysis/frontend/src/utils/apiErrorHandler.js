const ERROR_TYPES = {
  NETWORK: '網路連線異常，請檢查網路狀態',
  TIMEOUT: '請求逾時，請稍後重試',
  VALIDATION: '資料驗證失敗',
  SERVER: '伺服器錯誤，請聯絡系統管理員',
  NOT_FOUND: '查無資料',
  UNKNOWN: '未知錯誤，請稍後重試'
}

/**
 * 統一 API 錯誤處理
 * @param {Error} error - Axios error
 * @param {object} toast - PrimeVue toast instance
 * @param {string} contextMessage - 操作情境說明
 */
export const handleApiError = (error, toast, contextMessage = '操作失敗') => {
  let detail = ERROR_TYPES.UNKNOWN

  if (!error.response) {
    detail = error.code === 'ECONNABORTED' ? ERROR_TYPES.TIMEOUT : ERROR_TYPES.NETWORK
  } else {
    const status = error.response.status
    if (status === 400 || status === 422) detail = ERROR_TYPES.VALIDATION
    else if (status === 404) detail = ERROR_TYPES.NOT_FOUND
    else if (status >= 500) detail = ERROR_TYPES.SERVER
  }

  if (toast) {
    toast.add({
      severity: 'error',
      summary: contextMessage,
      detail,
      life: 5000
    })
  }

  console.error(`[API Error] ${contextMessage}:`, error)
}
