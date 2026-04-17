import { type TouchEvent, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { EditorContent, useEditor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import { deleteDiaryEntry, fetchDayDetail, upsertDiary, type ContentItemDto, type DayDetail } from '../api'

const MOODS = ['😍', '🤩', '😊', '😌', '😢']
const WEATHERS = ['☀️', '☁️', '🌧️', '❄️', '🌫️']
const SOURCE_ORDER = ['manual', 'weibo', 'xiaohongshu', 'douyin']
const SOURCE_LABELS: Record<string, string> = {
  manual: '我的日记',
  weibo: '微博',
  xiaohongshu: '小红书',
  douyin: '抖音',
}
const DIARY_DRAFT_PREFIX = 'daylog_diary_draft'
const IMAGE_PROXY_BASE_URL = import.meta.env.VITE_IMAGE_PROXY_BASE_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')

type ViewMode = 'timeline' | 'grouped'

interface DiaryDraft {
  body: string
  bodyFormat: 'tiptap_json'
  updatedAt: string
}

interface ImagePreviewState {
  images: string[]
  index: number
}

interface DayLocationState {
  focusDiary?: boolean
}

interface RichTextNode {
  type?: string
  text?: string
  content?: RichTextNode[]
}

function extractTiptapText(node: RichTextNode): string {
  const children = node.content?.map(extractTiptapText).join('') ?? ''
  const suffix = node.type === 'paragraph' || node.type === 'heading' ? '\n' : ''
  return `${node.text ?? ''}${children}${suffix}`
}

function getDisplayBody(item: ContentItemDto) {
  if (!item.body) return ''

  if (item.bodyFormat === 'tiptap_json') {
    try {
      return extractTiptapText(JSON.parse(item.body)).trim()
    } catch {
      return item.body
    }
  }

  if (item.bodyFormat === 'html') {
    return item.body.replace(/<[^>]*>/g, '').trim()
  }

  return item.body
}

function formatItemTime(itemTime: string) {
  return itemTime.slice(11, 16)
}

function sortSources(sources: string[]) {
  return [...sources].sort((a, b) => {
    const aIndex = SOURCE_ORDER.indexOf(a)
    const bIndex = SOURCE_ORDER.indexOf(b)
    return (aIndex === -1 ? 99 : aIndex) - (bIndex === -1 ? 99 : bIndex)
  })
}

function getMoodToneClass(mood: string | null) {
  if (!mood) return ''
  if (mood === '😍' || mood === '🤩') return 'mood-tone-blue'
  if (mood === '😊') return 'mood-tone-green'
  if (mood === '😌') return 'mood-tone-yellow'
  if (mood === '😢') return 'mood-tone-red'
  return ''
}

function getDiaryDraftKey(date: string) {
  return `${DIARY_DRAFT_PREFIX}:${date}`
}

function formatDraftTime(updatedAt: string) {
  const draftDate = new Date(updatedAt)
  if (Number.isNaN(draftDate.getTime())) return ''

  return draftDate.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getFullSizeImageUrl(url: string) {
  return url
    .replace('http://', 'https://')
    .replace('/thumbnail/', '/large/')
    .replace('/orj360/', '/large/')
    .replace('/wap360/', '/large/')
}

function getPreviewImageUrl(url: string) {
  return `${IMAGE_PROXY_BASE_URL}/proxy/img?url=${encodeURIComponent(getFullSizeImageUrl(url))}`
}

function TimelineCard({
  item,
  onDelete,
  expanded,
  onToggleExpanded,
  onPreviewImage,
}: {
  item: ContentItemDto
  onDelete: (item: ContentItemDto) => void
  expanded: boolean
  onToggleExpanded: (itemId: number) => void
  onPreviewImage: (images: string[], index: number) => void
}) {
  const fullBody = getDisplayBody(item)
  const summaryBody = item.title?.trim() ?? ''
  const canExpand = item.source === 'weibo' && Boolean(summaryBody) && summaryBody !== fullBody.trim()
  const body = canExpand && !expanded ? summaryBody : fullBody
  const sourceLabel = SOURCE_LABELS[item.source] ?? item.source

  return (
    <article className={`content-card timeline-card source-${item.source}`}>
      <div className="timeline-dot" />
      <div className="card-meta">
        <span className="item-time">{formatItemTime(item.itemTime)}</span>
        <span className="source-badge">{sourceLabel}</span>
        {item.source === 'manual' && (
          <button className="delete-diary-entry" onClick={() => onDelete(item)}>
            删除
          </button>
        )}
      </div>
      {item.title && item.source !== 'weibo' && <h4 className="card-title">{item.title}</h4>}
      {body && <p className="card-body">{body}</p>}
      {canExpand && (
        <button className="expand-content-button" onClick={() => onToggleExpanded(item.id)}>
          {expanded ? '收起' : '展开全文'}
        </button>
      )}
      {item.media && item.media.length > 0 && (
        <div className="card-images">
          {item.media.map((url, index) => (
            <button
              key={`${url}-${index}`}
              type="button"
              className="card-image-button"
              onClick={() => onPreviewImage(item.media ?? [], index)}
              aria-label="放大查看图片"
            >
              <img
                src={getPreviewImageUrl(url)}
                alt=""
                loading="lazy"
              />
            </button>
          ))}
        </div>
      )}
      {item.tags.length > 0 && (
        <div className="card-tags">
          {item.tags.map((tag) => <span key={tag} className="tag-bubble">{tag}</span>)}
        </div>
      )}
    </article>
  )
}

export default function DayPage() {
  const { date } = useParams<{ date: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const shouldFocusDiary = (location.state as DayLocationState | null)?.focusDiary
  const [detail, setDetail] = useState<DayDetail | null>(null)
  const [mood, setMood] = useState<string | null>(null)
  const [weather, setWeather] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>('timeline')
  const [draftSavedAt, setDraftSavedAt] = useState<string | null>(null)
  const [expandedWeiboIds, setExpandedWeiboIds] = useState<Set<number>>(() => new Set())
  const [preview, setPreview] = useState<ImagePreviewState | null>(null)
  const touchStartXRef = useRef<number | null>(null)

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
    })
  }, [date])

  useEffect(() => {
    if (!date || !editor) return

    const storedDraft = localStorage.getItem(getDiaryDraftKey(date))
    if (!storedDraft) {
      editor.commands.clearContent()
      setDraftSavedAt(null)
      if (shouldFocusDiary) editor.commands.focus('end')
      return
    }

    try {
      const draft = JSON.parse(storedDraft) as DiaryDraft
      editor.commands.setContent(JSON.parse(draft.body))
      setDraftSavedAt(draft.updatedAt)
      if (shouldFocusDiary) editor.commands.focus('end')
    } catch {
      localStorage.removeItem(getDiaryDraftKey(date))
      setDraftSavedAt(null)
    }
  }, [date, editor, shouldFocusDiary])

  useEffect(() => {
    if (!date || !editor) return

    const saveDraft = () => {
      if (editor.isEmpty) {
        localStorage.removeItem(getDiaryDraftKey(date))
        setDraftSavedAt(null)
        return
      }

      const updatedAt = new Date().toISOString()
      const draft: DiaryDraft = {
        body: JSON.stringify(editor.getJSON()),
        bodyFormat: 'tiptap_json',
        updatedAt,
      }
      localStorage.setItem(getDiaryDraftKey(date), JSON.stringify(draft))
      setDraftSavedAt(updatedAt)
    }

    editor.on('update', saveDraft)
    return () => {
      editor.off('update', saveDraft)
    }
  }, [date, editor])

  useEffect(() => {
    if (!preview) return

    const originalOverflow = document.body.style.overflow
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setPreview(null)
        return
      }
      if (event.key === 'ArrowLeft') {
        setPreview((current) => {
          if (!current || current.images.length <= 1) return current
          return {
            ...current,
            index: current.index === 0 ? current.images.length - 1 : current.index - 1,
          }
        })
      }
      if (event.key === 'ArrowRight') {
        setPreview((current) => {
          if (!current || current.images.length <= 1) return current
          return {
            ...current,
            index: current.index === current.images.length - 1 ? 0 : current.index + 1,
          }
        })
      }
    }

    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', handleKeyDown)

    return () => {
      document.body.style.overflow = originalOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [preview])

  const groupedItems = useMemo(() => {
    if (!detail) return []

    const groups = detail.items.reduce<Record<string, ContentItemDto[]>>((result, item) => ({
      ...result,
      [item.source]: [...(result[item.source] ?? []), item],
    }), {})

    return sortSources(Object.keys(groups)).map((source) => ({
      source,
      items: groups[source],
    }))
  }, [detail])

  const handleSave = async () => {
    if (!date || !editor) return
    setSaving(true)
    try {
      await upsertDiary(date, {
        body: editor.isEmpty ? null : JSON.stringify(editor.getJSON()),
        bodyFormat: editor.isEmpty ? null : 'tiptap_json',
        mood,
        weather,
      })
      const nextDetail = await fetchDayDetail(date)
      setDetail(nextDetail)
      setMood(nextDetail.mood)
      setWeather(nextDetail.weather)
      editor.commands.clearContent()
      localStorage.removeItem(getDiaryDraftKey(date))
      setDraftSavedAt(null)
    } finally {
      setSaving(false)
    }
  }

  const handleToggleWeiboExpanded = (itemId: number) => {
    setExpandedWeiboIds((current) => {
      const next = new Set(current)
      if (next.has(itemId)) {
        next.delete(itemId)
      } else {
        next.add(itemId)
      }
      return next
    })
  }

  const handleDeleteDiaryEntry = async (item: ContentItemDto) => {
    if (!date || item.source !== 'manual') return

    const confirmed = window.confirm('确定要删除这条日记吗？删除后不可恢复。')
    if (!confirmed) return

    await deleteDiaryEntry(date, item.id)
    const nextDetail = await fetchDayDetail(date)
    setDetail(nextDetail)
    setMood(nextDetail.mood)
    setWeather(nextDetail.weather)
  }

  const handleSavePreviewImage = () => {
    if (!preview) return
    const currentImageUrl = preview.images[preview.index]
    if (!currentImageUrl) return

    const link = document.createElement('a')
    link.href = getPreviewImageUrl(currentImageUrl)
    link.download = `daylog-image-${Date.now()}.jpg`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const handlePreviewImage = (images: string[], index: number) => {
    if (images.length === 0) return
    setPreview({
      images,
      index,
    })
  }

  const handlePreviewMove = (direction: 'prev' | 'next') => {
    setPreview((current) => {
      if (!current || current.images.length <= 1) return current

      const nextIndex = direction === 'prev'
        ? (current.index === 0 ? current.images.length - 1 : current.index - 1)
        : (current.index === current.images.length - 1 ? 0 : current.index + 1)

      return {
        ...current,
        index: nextIndex,
      }
    })
  }

  const handlePreviewTouchStart = (event: TouchEvent<HTMLDivElement>) => {
    touchStartXRef.current = event.changedTouches[0]?.clientX ?? null
  }

  const handlePreviewTouchEnd = (event: TouchEvent<HTMLDivElement>) => {
    const startX = touchStartXRef.current
    const endX = event.changedTouches[0]?.clientX ?? null
    touchStartXRef.current = null

    if (startX === null || endX === null) return

    const deltaX = endX - startX
    if (Math.abs(deltaX) < 36) return

    if (deltaX > 0) {
      handlePreviewMove('prev')
    } else {
      handlePreviewMove('next')
    }
  }

  if (!detail) return <p className="loading">加载中...</p>

  const previewImageUrl = preview ? preview.images[preview.index] : null
  const showPreviewNavigation = Boolean(preview && preview.images.length > 1)

  return (
    <div className="day-container">
      <header className="day-header">
        <h2>{date}</h2>
      </header>

      <section className="meta-row">
        <div className="picker">
          <span>心情</span>
          {MOODS.map((moodOption) => (
            <button
              key={moodOption}
              className={`${mood === moodOption ? 'active' : ''} ${getMoodToneClass(moodOption)}`.trim()}
              onClick={() => setMood(moodOption)}
            >{moodOption}</button>
          ))}
        </div>
        <div className="picker">
          <span>天气</span>
          {WEATHERS.map((weatherOption) => (
            <button
              key={weatherOption}
              className={weather === weatherOption ? 'active' : ''}
              onClick={() => setWeather(weatherOption)}
            >{weatherOption}</button>
          ))}
        </div>
      </section>

      <section className="timeline-section">
        <div className="section-title-row">
          <h3>当天记录</h3>
          <div className="view-toggle" aria-label="详情显示方式">
            <button
              className={viewMode === 'timeline' ? 'active' : ''}
              onClick={() => setViewMode('timeline')}
            >
              时间轴
            </button>
            <button
              className={viewMode === 'grouped' ? 'active' : ''}
              onClick={() => setViewMode('grouped')}
            >
              按类型
            </button>
          </div>
        </div>

        {detail.items.length === 0 && <p className="empty-timeline">这一天还没有记录。</p>}

        {viewMode === 'timeline' && detail.items.length > 0 && (
          <div className="timeline-list">
            {detail.items.map((item) => (
              <TimelineCard
                key={item.id}
                item={item}
                expanded={expandedWeiboIds.has(item.id)}
                onToggleExpanded={handleToggleWeiboExpanded}
                onDelete={handleDeleteDiaryEntry}
                onPreviewImage={handlePreviewImage}
              />
            ))}
          </div>
        )}

        {viewMode === 'grouped' && groupedItems.map((group) => (
          <section key={group.source} className="source-group">
            <h4>{SOURCE_LABELS[group.source] ?? group.source}</h4>
            <div className="timeline-list">
              {group.items.map((item) => (
                <TimelineCard
                  key={item.id}
                  item={item}
                  expanded={expandedWeiboIds.has(item.id)}
                  onToggleExpanded={handleToggleWeiboExpanded}
                  onDelete={handleDeleteDiaryEntry}
                  onPreviewImage={handlePreviewImage}
                />
              ))}
            </div>
          </section>
        ))}
      </section>

      <section className="diary-section">
        <div className="diary-editor-header">
          <h3>新增一条日记</h3>
          <span>{draftSavedAt ? `草稿已自动保存 ${formatDraftTime(draftSavedAt)}` : '输入后自动保存草稿'}</span>
        </div>
        <EditorContent editor={editor} className="tiptap-editor" />
        <button className="day-inline-save-button" onClick={handleSave} disabled={saving}>
          {saving ? '保存中...' : '保存'}
        </button>
      </section>

      <div className="day-bottom-actions day-bottom-actions-desktop">
        <button onClick={() => navigate('/', { state: { returnDate: date } })}>返回</button>
      </div>

      <div className="day-bottom-actions day-bottom-actions-mobile">
        <button onClick={() => navigate('/', { state: { returnDate: date } })}>返回</button>
      </div>

      {previewImageUrl && (
        <div className="image-preview-overlay" role="dialog" aria-modal="true" aria-label="图片预览">
          <button
            type="button"
            className="image-preview-backdrop"
            aria-label="关闭图片预览"
            onClick={() => setPreview(null)}
          />
          <div
            className="image-preview-dialog"
            onTouchStart={handlePreviewTouchStart}
            onTouchEnd={handlePreviewTouchEnd}
          >
            <button
              type="button"
              className="image-preview-close"
              aria-label="关闭"
              onClick={() => setPreview(null)}
            >
              关闭
            </button>
            {showPreviewNavigation && (
              <button
                type="button"
                className="image-preview-nav image-preview-nav-prev"
                aria-label="上一张图片"
                onClick={() => handlePreviewMove('prev')}
              >
                上一张
              </button>
            )}
            <img className="image-preview-content" src={getPreviewImageUrl(previewImageUrl)} alt="" />
            {showPreviewNavigation && (
              <button
                type="button"
                className="image-preview-nav image-preview-nav-next"
                aria-label="下一张图片"
                onClick={() => handlePreviewMove('next')}
              >
                下一张
              </button>
            )}
            <div className="image-preview-actions">
              {preview && <span className="image-preview-counter">{preview.index + 1} / {preview.images.length}</span>}
              <button type="button" onClick={handleSavePreviewImage}>保存图片</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
