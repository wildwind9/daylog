import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  bindWeiboWithQrLogin,
  extractApiErrorMessage,
  fetchWeiboQrLoginStatus,
  startWeiboQrLogin,
} from '../api'

const POLL_INTERVAL_MS = 1500

export default function WeiboLoginPage() {
  const navigate = useNavigate()
  const [sessionId, setSessionId] = useState('')
  const [qrImageBase64, setQrImageBase64] = useState('')
  const [statusMessage, setStatusMessage] = useState('正在生成微博登录二维码...')
  const [loading, setLoading] = useState(true)
  const [binding, setBinding] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let timer: number | null = null

    const poll = async (currentSessionId: string) => {
      try {
        const result = await fetchWeiboQrLoginStatus(currentSessionId)
        if (cancelled) return
        setStatusMessage(result.message)
        if (result.status === 'completed') {
          setBinding(true)
          await bindWeiboWithQrLogin({
            weiboUid: result.uid,
            screenName: null,
            replaceExistingContent: false,
            syncNow: false,
          })
          if (cancelled) return
          navigate('/', {
            replace: true,
            state: { weiboLoginMessage: '微博扫码登录成功，微博账号已绑定。现在可以尝试网页抓取。' },
          })
          return
        }
        if (result.status === 'expired' || result.status === 'failed') {
          setError(result.message)
          return
        }
        timer = window.setTimeout(() => void poll(currentSessionId), POLL_INTERVAL_MS)
      } catch (nextError) {
        if (!cancelled) {
          setError(extractApiErrorMessage(nextError, '微博二维码状态获取失败，请稍后重试'))
        }
      }
    }

    const boot = async () => {
      try {
        const result = await startWeiboQrLogin()
        if (cancelled) return
        setSessionId(result.sessionId)
        setQrImageBase64(result.imageBase64)
        setStatusMessage(result.message)
        timer = window.setTimeout(() => void poll(result.sessionId), POLL_INTERVAL_MS)
      } catch (nextError) {
        if (!cancelled) {
          setError(extractApiErrorMessage(nextError, '微博二维码创建失败，请稍后重试'))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void boot()

    return () => {
      cancelled = true
      if (timer !== null) {
        window.clearTimeout(timer)
      }
    }
  }, [navigate])

  return (
    <div className="weibo-oauth-page">
      <div className="weibo-oauth-shell">
        <div className="weibo-oauth-card">
          <p className="eyebrow">WEIBO WEB COOKIE</p>
          <h1>扫码登录微博</h1>
          <p className="weibo-oauth-copy">
            这里不再走开放平台 OAuth 授权，而是直接获取微博网页登录 cookie，供后续网页抓取和全量微博获取使用。
          </p>

          {error && <p className="weibo-remote-error">{error}</p>}

          {!error && (
            <div className="weibo-callback-summary">
              <div>
                <strong>当前状态</strong>
                <span>{binding ? '正在绑定微博账号...' : statusMessage}</span>
              </div>
              <div>
                <strong>会话 ID</strong>
                <span>{sessionId || '生成中...'}</span>
              </div>
              <div>
                <strong>下一步</strong>
                <span>{binding ? '正在把扫码结果绑定到当前账号' : '请使用微博 App 扫码并确认登录'}</span>
              </div>
            </div>
          )}

          {!error && qrImageBase64 && !binding && (
            <div className="weibo-login-qr-wrap">
              <img
                className="weibo-login-qr-image"
                src={`data:image/png;base64,${qrImageBase64}`}
                alt="微博扫码登录二维码"
              />
            </div>
          )}

          <div className="weibo-callback-actions">
            <button
              disabled={loading || binding}
              onClick={() => navigate('/weibo-login', { replace: true })}
            >
              {loading ? '生成中...' : '重新生成二维码'}
            </button>
            <button
              className="weibo-oauth-secondary"
              onClick={() => navigate('/', { replace: true })}
            >
              返回首页
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
