import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import { fetchDayDetail, upsertDiary, type DayDetail } from '../api'

const MOODS = ['😊', '😌', '😔', '😰', '🤩']
const WEATHERS = ['☀️', '⛅', '🌧️', '❄️', '🌩️']

export default function DayPage() {
  const { date } = useParams<{ date: string }>()
  const navigate = useNavigate()
  const [detail, setDetail] = useState<DayDetail | null>(null)
  const [mood, setMood] = useState<string | null>(null)
  const [weather, setWeather] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const editor = useEditor({
    extensions: [StarterKit],
    content: '',
  })

  useEffect(() => {
    if (!date) return
    fetchDayDetail(date).then((data) => {
      setDetail(data)
      setMood(data.mood)
      setWeather(data.weather)
      if (editor && data.diaryBody) {
        editor.commands.setContent(
          data.diaryBodyFormat === 'tiptap_json'
            ? JSON.parse(data.diaryBody)
            : data.diaryBody,
        )
      }
    })
  }, [date, editor])

  const handleSave = async () => {
    if (!date || !editor) return
    setSaving(true)
    try {
      await upsertDiary(date, {
        body: JSON.stringify(editor.getJSON()),
        bodyFormat: 'tiptap_json',
        mood,
        weather,
      })
      navigate('/', { replace: true, state: { returnDate: date } })
    } finally {
      setSaving(false)
    }
  }

  if (!detail) return <p className="loading">加载中...</p>

  return (
    <div className="day-container">
      <header className="day-header">
        <button onClick={() => navigate('/', { state: { returnDate: date } })}>← 返回</button>
        <h2>{date}</h2>
        <button onClick={handleSave} disabled={saving}>
          {saving ? '保存中...' : '保存'}
        </button>
      </header>

      {/* 情绪 & 天气 */}
      <section className="meta-row">
        <div className="picker">
          <span>心情</span>
          {MOODS.map((m) => (
            <button
              key={m}
              className={mood === m ? 'active' : ''}
              onClick={() => setMood(m)}
            >{m}</button>
          ))}
        </div>
        <div className="picker">
          <span>天气</span>
          {WEATHERS.map((w) => (
            <button
              key={w}
              className={weather === w ? 'active' : ''}
              onClick={() => setWeather(w)}
            >{w}</button>
          ))}
        </div>
      </section>

      {/* 平台内容卡片 */}
      {detail.items.length > 0 && (
        <section className="content-section">
          <h3>内容</h3>
          {detail.items.map((item) => (
            <div key={item.id} className={`content-card source-${item.source}`}>
              <div className="card-meta">
                <span className="source-badge">{item.source}</span>
                <span className="item-time">{item.itemTime.slice(0, 16)}</span>
              </div>
              {item.body && <p className="card-body">{item.body}</p>}
              {item.media && (
                <div className="card-images">
                  {item.media.map((url, i) => (
                    <img key={i} src={`http://localhost:8000/proxy/img?url=${encodeURIComponent(url)}`} alt="" loading="lazy" />
                  ))}
                </div>
              )}
              {item.tags.length > 0 && (
                <div className="card-tags">
                  {item.tags.map((t) => <span key={t} className="tag-bubble">{t}</span>)}
                </div>
              )}
            </div>
          ))}
        </section>
      )}

      {/* 富文本日记 */}
      <section className="diary-section">
        <h3>我的日记</h3>
        <EditorContent editor={editor} className="tiptap-editor" />
      </section>
    </div>
  )
}
