import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? 'http://localhost:8080' : ''),
  timeout: 10_000,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('daylog_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 || err.response?.status === 403) {
      localStorage.removeItem('daylog_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export default client

export const extractApiErrorMessage = (error: unknown, fallback: string) => {
  if (axios.isAxiosError(error)) {
    const responseError = error.response?.data?.error
    if (typeof responseError === 'string' && responseError.trim().length > 0) {
      return responseError
    }
  }
  return fallback
}
