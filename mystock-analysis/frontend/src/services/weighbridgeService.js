import axiosConfig from '@/config/axiosConfig'
import { WEIGHBRIDGE_ENDPOINTS } from './api/modules/weighbridgeEndpoints'

/** 入廠過磅確認 */
export const confirmEntry = async (payload) => {
  const response = await axiosConfig.post(WEIGHBRIDGE_ENDPOINTS.ENTRY.CONFIRM, payload)
  return response.data
}

/** 出廠過磅確認 */
export const confirmExit = async (payload) => {
  const response = await axiosConfig.post(WEIGHBRIDGE_ENDPOINTS.EXIT.CONFIRM, payload)
  return response.data
}

/** 補印磅單 */
export const printTicket = async (ticketNo, type) => {
  const response = await axiosConfig.post(WEIGHBRIDGE_ENDPOINTS.PRINT, { ticketNo, type })
  return response.data
}

/** 查詢磅單 */
export const getTicket = async (ticketNo) => {
  const response = await axiosConfig.get(WEIGHBRIDGE_ENDPOINTS.TICKET.BY_NO(ticketNo))
  return response.data
}

/** 當日磅單清單 */
export const getTodayTickets = async () => {
  const response = await axiosConfig.get(WEIGHBRIDGE_ENDPOINTS.TICKET.TODAY)
  return response.data
}

/** DB 連線狀態 */
export const getDbStatus = async () => {
  const response = await axiosConfig.get(WEIGHBRIDGE_ENDPOINTS.DB.STATUS)
  return response.data
}

/** 採購單查詢 */
export const getPoInfo = async (poNo) => {
  const response = await axiosConfig.get(WEIGHBRIDGE_ENDPOINTS.PO.BY_NO(poNo))
  return response.data
}
