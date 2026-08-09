import { reactive } from 'vue'

// Mock 感應卡資料
const CARD_DATA = [
  { ticketNo: 'IN20240101000001', carNo: 'ABC-1234', materialName: '砂石料' },
  { ticketNo: 'IN20240101000002', carNo: 'XYZ-5678', materialName: '水泥' }
]

/**
 * 感應卡讀寫操作 composable
 */
export const useCardOperation = (toast) => {
  const cardReadState = reactive({
    visible: false,
    ticketNo: '',
    carNo: '',
    materialName: '',
    mode: 'out'
  })

  const cardWriteState = reactive({
    visible: false,
    data: null
  })

  /** UC-004A：讀卡模擬 */
  const doCardRead = (mode) => {
    const card = CARD_DATA[Math.floor(Math.random() * CARD_DATA.length)]
    cardReadState.ticketNo = card.ticketNo
    cardReadState.carNo = card.carNo
    cardReadState.materialName = card.materialName
    cardReadState.mode = mode
    cardReadState.visible = true
  }

  /** UC-004B：開啟寫卡對話框 */
  const openCardWriteDialog = (data) => {
    cardWriteState.data = data
    cardWriteState.visible = true
  }

  /** 執行寫卡 */
  const doCardWrite = () => {
    cardWriteState.visible = false
    toast?.add({
      severity: 'success',
      summary: '寫卡成功',
      detail: `磅單 ${cardWriteState.data?.ticketNo} 已寫入感應卡，請交付司機`,
      life: 4000
    })
  }

  return {
    cardReadState,
    cardWriteState,
    doCardRead,
    openCardWriteDialog,
    doCardWrite
  }
}
