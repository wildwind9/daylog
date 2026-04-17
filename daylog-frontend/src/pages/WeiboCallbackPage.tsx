import { useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { confirmWeiboOauthBinding, extractApiErrorMessage } from '../api'

type CallbackStatus = 'success' | 'error'

export default function WeiboCallbackPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const params = useMemo(() => new URLSearchParams(location.search), [location.search])
  const status = (params.get('status') as CallbackStatus | null) ?? 'error'
  const ticket = params.get('ticket') ?? ''
  const uid = params.get('uid') ?? ''
  const screenName = params.get('screenName') ?? ''
  const message = params.get('message') ?? ''

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(
    status === 'error' ? (message || '微博授权失败，请重新尝试') : null,
  )

  const handleCancelBinding = () => {
    navigate('/', {
      replace: true,
      state: { weiboLoginMessage: '已取消本次微博绑定' },
    })
  }

  const handleCompleteBinding = async () => {
    if (!ticket) {
      setError('微博绑定凭据已失效，请重新发起绑定')
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      await confirmWeiboOauthBinding({
        ticket,
        replaceExistingContent: false,
        syncNow: false,
      })
      navigate('/', {
        replace: true,
        state: {
          weiboLoginMessage: `微博账号 ${screenName || uid} 已绑定完成。现在可以直接使用“立即同步微博”。`,
        },
      })
    } catch (nextError) {
      setError(extractApiErrorMessage(nextError, '微博绑定确认失败'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="weibo-oauth-page">
      <div className="weibo-oauth-shell">
        <div className="weibo-oauth-card">
          <p className="eyebrow">WEIBO CALLBACK</p>
          <h1>{status === 'success' ? '微博授权成功' : '微博授权失败'}</h1>
          <p className="weibo-oauth-copy">
            {status === 'success'
              ? `已识别微博账号 ${screenName || uid}。确认后会完成当前系统账号与微博账号的绑定。`
              : (message || '微博授权没有完成，你可以返回首页重新发起绑定。')}
          </p>

          {error && <p className="weibo-remote-error">{error}</p>}

          {status === 'success' && (
            <div className="weibo-callback-summary">
              <div>
                <strong>微博账号</strong>
                <span>{screenName || uid}</span>
              </div>
              <div>
                <strong>微博 UID</strong>
                <span>{uid}</span>
              </div>
              <div>
                <strong>下一步</strong>
                <span>返回首页后可直接同步微博内容</span>
              </div>
            </div>
          )}

          <div className="weibo-callback-actions">
            <button
              disabled={status !== 'success' || submitting}
              onClick={() => void handleCompleteBinding()}
            >
              {submitting ? '处理中...' : '完成绑定'}
            </button>
            <button
              className="weibo-oauth-secondary"
              disabled={submitting}
              onClick={handleCancelBinding}
            >
              取消绑定
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
