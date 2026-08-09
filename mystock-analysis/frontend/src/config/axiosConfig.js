import axios from 'axios'
import { API_BASE_URL, API_TIMEOUT, IS_DEBUG } from './environmentConfig'

const axiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: { 'Content-Type': 'application/json' }
})

// Request 攔截器
axiosInstance.interceptors.request.use(
  (config) => {
    if (IS_DEBUG) {
      console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`, config.data)
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response 攔截器
axiosInstance.interceptors.response.use(
  (response) => {
    if (IS_DEBUG) {
      console.log(`[API Response] ${response.config.url}`, response.data)
    }
    return response
  },
  (error) => {
    if (IS_DEBUG) {
      console.error('[API Error]', error.response?.status, error.message)
    }
    return Promise.reject(error)
  }
)

export default axiosInstance
