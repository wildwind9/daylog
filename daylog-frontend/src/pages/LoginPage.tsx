import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register } from '../api'
import { extractApiErrorMessage } from '../api/client'

type AuthMode = 'login' | 'register'

export default function LoginPage() {
  const [mode, setMode] = useState<AuthMode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)

    const trimmedUsername = username.trim()
    if (trimmedUsername.length < 3) {
      setError('用户名至少 3 个字符')
      return
    }
    if (password.length < 6) {
      setError('密码至少 6 个字符')
      return
    }

    setLoading(true)
    try {
      const token = mode === 'login'
        ? await login(trimmedUsername, password)
        : await register(trimmedUsername, password)
      localStorage.setItem('daylog_token', token)
      navigate('/', { replace: true })
    } catch (error) {
      setError(
        extractApiErrorMessage(
          error,
          mode === 'login' ? '用户名或密码错误' : '注册失败，请稍后重试',
        ),
      )
    } finally {
      setLoading(false)
    }
  }

  const switchMode = () => {
    setMode((current) => (current === 'login' ? 'register' : 'login'))
    setError(null)
  }

  return (
    <div className="login-container">
      <h1>Daylog</h1>
      <p className="auth-subtitle">{mode === 'login' ? '欢迎回来' : '创建你的日记账户'}</p>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="用户名"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          minLength={3}
          maxLength={50}
          required
        />
        <input
          type="password"
          placeholder="密码"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          minLength={6}
          maxLength={72}
          required
        />
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? '处理中...' : mode === 'login' ? '登录' : '注册并进入'}
        </button>
      </form>
      <button className="auth-mode-toggle" onClick={switchMode}>
        {mode === 'login' ? '没有账号？注册一个' : '已有账号？去登录'}
      </button>
    </div>
  )
}
