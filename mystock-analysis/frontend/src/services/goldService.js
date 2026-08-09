import axiosConfig from '@/config/axiosConfig'
import { GOLD_ENDPOINTS } from './api/modules/goldEndpoints'

/** 取得最新黃金價格（來源：TPEX 證券櫃檯買賣中心） */
export const getGoldLatest = async () => {
  const response = await axiosConfig.get(GOLD_ENDPOINTS.LATEST)
  return response.data
}
