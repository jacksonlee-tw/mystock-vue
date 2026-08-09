export const getEnvVar = (key, defaultVal = '') =>
  import.meta.env[key] ?? defaultVal

export const getBooleanEnvVar = (key, defaultVal = false) => {
  const val = import.meta.env[key]
  return val !== undefined ? val === 'true' : defaultVal
}

export const API_BASE_URL = getEnvVar('VITE_API_BASE_URL', '')
export const API_TIMEOUT = Number(getEnvVar('VITE_API_TIMEOUT', '10000'))
export const IS_DEBUG = getBooleanEnvVar('VITE_DEBUG', false)
