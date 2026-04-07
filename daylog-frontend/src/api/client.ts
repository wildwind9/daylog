import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8080',
  timeout: 10_000,
})

// 自动携带 JWT
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('daylog_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 401 自动跳转登录
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('daylog_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export default client
