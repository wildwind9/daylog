import { type ChangeEvent, type CSSProperties, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { fetchMonthSummary, type CalendarDay } from '../api'

type MonthKey = `${number}-${string}`

interface BackgroundPreference {
  color: string
  image: string
  opacity: number
  pageOpacity: number
}

interface CalendarLocationState {
  returnDate?: string
}

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']
const BACKGROUND_STORAGE_KEY = 'daylog_calendar_background'
const DEFAULT_BACKGROUND: BackgroundPreference = {
  color: '#f5f4f0',
  image: '',
  opacity: 0.42,
  pageOpacity: 0.9,
}

function getMonthKey(date: dayjs.Dayjs): MonthKey {
  return date.format('YYYY-MM') as MonthKey
}

function getMonthRange(center: dayjs.Dayjs) {
  const start = center.startOf('month').subtract(6, 'month')
  return Array.from({ length: 13 }, (_, index) => start.add(index, 'month'))
}

function getYearOptions(center: dayjs.Dayjs) {
  return Array.from({ length: 11 }, (_, index) => center.year() - 5 + index)
}

function buildCells(month: dayjs.Dayjs) {
  const startOfMonth = month.startOf('month')
  const daysInMonth = month.daysInMonth()
  const startWeekday = startOfMonth.day()

  return [
    ...Array<dayjs.Dayjs | null>(startWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, index) => startOfMonth.add(index, 'day')),
  ]
}

function loadBackgroundPreference(): BackgroundPreference {
  try {
    const stored = localStorage.getItem(BACKGROUND_STORAGE_KEY)
    return stored ? { ...DEFAULT_BACKGROUND, ...JSON.parse(stored) } : DEFAULT_BACKGROUND
  } catch {
    return DEFAULT_BACKGROUND
  }
}

function getInitialCalendarDate(returnDate?: string) {
  if (!returnDate) return dayjs()

  const parsedDate = dayjs(returnDate)
  return parsedDate.isValid() ? parsedDate : dayjs()
}

export default function CalendarPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const returnDate = (location.state as CalendarLocationState | null)?.returnDate
  const [selectedDate, setSelectedDate] = useState(() => getInitialCalendarDate(returnDate))
  const [rangeCenter, setRangeCenter] = useState(() => getInitialCalendarDate(returnDate))
  const [monthSummaries, setMonthSummaries] = useState<Record<MonthKey, CalendarDay[]>>({})
  const [background, setBackground] = useState<BackgroundPreference>(loadBackgroundPreference)
  const [backgroundPanelOpen, setBackgroundPanelOpen] = useState(false)
  const monthRefs = useRef<Record<MonthKey, HTMLElement | null>>({})
  const requestedMonths = useRef<Set<MonthKey>>(new Set())
  const isInitialMonthScroll = useRef(true)
  const yearWheelRef = useRef<HTMLDivElement | null>(null)
  const monthWheelRef = useRef<HTMLDivElement | null>(null)
  const dayWheelRef = useRef<HTMLDivElement | null>(null)

  const visibleMonths = useMemo(() => getMonthRange(rangeCenter), [rangeCenter])
  const selectedMonthKey = getMonthKey(selectedDate)
  const visibleMonthSignature = visibleMonths.map(getMonthKey).join(',')
  const selectedDay = selectedDate.date()
  const selectedMonth = selectedDate.month() + 1
  const yearOptions = getYearOptions(selectedDate)
  const dayOptions = Array.from({ length: selectedDate.daysInMonth() }, (_, index) => index + 1)
  const backgroundStyle = {
    '--calendar-bg-color': background.color,
    '--calendar-bg-opacity': background.opacity,
    '--calendar-bg-image': background.image ? `url(${background.image})` : 'none',
    '--calendar-page-opacity': background.pageOpacity,
  } as CSSProperties

  useEffect(() => {
    const missingMonths = visibleMonths
      .map(getMonthKey)
      .filter((monthKey) => !monthSummaries[monthKey] && !requestedMonths.current.has(monthKey))

    if (missingMonths.length === 0) return

    missingMonths.forEach((monthKey) => {
      requestedMonths.current.add(monthKey)
      const month = dayjs(`${monthKey}-01`)
      fetchMonthSummary(month.year(), month.month() + 1)
        .then((days) => {
          setMonthSummaries((current) => ({ ...current, [monthKey]: days }))
        })
    })
  }, [visibleMonthSignature, monthSummaries, visibleMonths])

  useEffect(() => {
    monthRefs.current[selectedMonthKey]?.scrollIntoView({
      block: 'center',
      behavior: isInitialMonthScroll.current ? 'auto' : 'smooth',
    })
    isInitialMonthScroll.current = false
  }, [selectedMonthKey])

  useEffect(() => {
    localStorage.setItem(BACKGROUND_STORAGE_KEY, JSON.stringify(background))
  }, [background])

  useEffect(() => {
    [yearWheelRef, monthWheelRef, dayWheelRef].forEach((wheelRef) => {
      wheelRef.current?.querySelector('.active')?.scrollIntoView({
        block: 'center',
      })
    })
  }, [selectedDate])

  const updateDate = (year: number, month: number, day: number) => {
    const nextMonth = dayjs(`${year}-${String(month).padStart(2, '0')}-01`)
    const safeDay = Math.min(day, nextMonth.daysInMonth())
    const nextDate = nextMonth.date(safeDay)
    setSelectedDate(nextDate)
    setRangeCenter(nextDate)
  }

  const selectDay = (day: dayjs.Dayjs) => {
    setSelectedDate(day)
    setRangeCenter(day)
    navigate(`/day/${day.format('YYYY-MM-DD')}`)
  }

  const selectToday = () => {
    const today = dayjs()
    setSelectedDate(today)
    setRangeCenter(today)
  }

  const updateBackgroundImage = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = () => {
      setBackground((current) => ({
        ...current,
        image: typeof reader.result === 'string' ? reader.result : '',
      }))
    }
    reader.readAsDataURL(file)
  }

  return (
    <div className="calendar-page-shell" style={backgroundStyle}>
      <div className="calendar-background-color" />
      <div className="calendar-background-image" />

      <div className="calendar-container calendar-scroll-container">
        <header className="calendar-hero">
          <div>
            <p className="eyebrow">Daylog Calendar</p>
            <h1>{selectedDate.format('YYYY 年 M 月 D 日')}</h1>
          </div>
          <div className="calendar-hero-actions">
            <section className="date-wheel" aria-label="选择年月日">
              <div className="wheel-column">
                <div className="wheel-list" ref={yearWheelRef}>
                  {yearOptions.map((year) => (
                    <button
                      key={year}
                      className={year === selectedDate.year() ? 'active' : ''}
                      onClick={() => updateDate(year, selectedMonth, selectedDay)}
                    >
                      {year}
                    </button>
                  ))}
                </div>
              </div>

              <div className="wheel-column">
                <div className="wheel-list" ref={monthWheelRef}>
                  {Array.from({ length: 12 }, (_, index) => index + 1).map((month) => (
                    <button
                      key={month}
                      className={month === selectedMonth ? 'active' : ''}
                      onClick={() => updateDate(selectedDate.year(), month, selectedDay)}
                    >
                      {month}
                    </button>
                  ))}
                </div>
              </div>

              <div className="wheel-column">
                <div className="wheel-list" ref={dayWheelRef}>
                  {dayOptions.map((day) => (
                    <button
                      key={day}
                      className={day === selectedDay ? 'active' : ''}
                      onClick={() => updateDate(selectedDate.year(), selectedMonth, day)}
                    >
                      {day}
                    </button>
                  ))}
                </div>
              </div>
            </section>
            <button className="today-button" onClick={selectToday}>
              今天
            </button>
          </div>
        </header>

        <button
          className="background-toggle"
          aria-label="背景设置"
          onClick={() => setBackgroundPanelOpen((open) => !open)}
        >
          背景
        </button>

        {backgroundPanelOpen && (
          <section className="background-panel" aria-label="主页面背景设置">
            <label className="background-control">
              <span>背景图片</span>
              <input type="file" accept="image/*" onChange={updateBackgroundImage} />
            </label>
            <label className="background-control">
              <span>背景颜色</span>
              <input
                type="color"
                value={background.color}
                onChange={(event) => setBackground((current) => ({
                  ...current,
                  color: event.target.value,
                }))}
              />
            </label>
            <label className="background-control background-opacity">
              <span>背景透明度 {Math.round(background.opacity * 100)}%</span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={background.opacity}
                onChange={(event) => setBackground((current) => ({
                  ...current,
                  opacity: Number(event.target.value),
                }))}
              />
            </label>
            <label className="background-control background-opacity">
              <span>页面透明度 {Math.round(background.pageOpacity * 100)}%</span>
              <input
                type="range"
                min="0.35"
                max="1"
                step="0.05"
                value={background.pageOpacity}
                onChange={(event) => setBackground((current) => ({
                  ...current,
                  pageOpacity: Number(event.target.value),
                }))}
              />
            </label>
            <div className="background-panel-actions">
              <button onClick={() => setBackground((current) => ({ ...current, image: '' }))}>
                移除图片
              </button>
              <button onClick={() => setBackground(DEFAULT_BACKGROUND)}>
                恢复默认
              </button>
            </div>
          </section>
        )}

        <main
          className="month-stack"
          aria-label="按月上下滑动浏览日历"
        >
          {visibleMonths.map((month) => {
            const monthKey = getMonthKey(month)
            const dayMap = new Map((monthSummaries[monthKey] ?? []).map((day) => [day.date, day]))

            return (
              <section
                key={monthKey}
                ref={(element) => {
                  monthRefs.current[monthKey] = element
                }}
                className={`month-panel ${monthKey === selectedMonthKey ? 'selected-month' : ''}`}
              >
                <header className="month-panel-header">
                  <div>
                    <span>{month.format('YYYY')}</span>
                    <h2>{month.format('M 月')}</h2>
                  </div>
                </header>

                <div className="weekday-labels">
                  {WEEKDAYS.map((weekday) => (
                    <span key={weekday}>{weekday}</span>
                  ))}
                </div>

                <div className="calendar-grid">
                  {buildCells(month).map((day, index) => {
                    if (!day) return <div key={`empty-${monthKey}-${index}`} className="cell empty" />

                    const dateStr = day.format('YYYY-MM-DD')
                    const info = dayMap.get(dateStr)
                    const isToday = day.isSame(dayjs(), 'day')
                    const isSelected = day.isSame(selectedDate, 'day')

                    return (
                      <button
                        key={dateStr}
                        className={`cell ${info ? 'has-content' : ''} ${isToday ? 'today' : ''} ${isSelected ? 'selected-day' : ''}`}
                        onClick={() => selectDay(day)}
                      >
                        <span className="date-number">{day.date()}</span>
                        {info && (
                          <div className="tag-bubbles">
                            {(info.mood || info.weather) && (
                              <span className="tag-bubble mood-weather">
                                {[info.mood, info.weather].filter(Boolean).join(' ')}
                              </span>
                            )}
                            {info.tags.map((tag) => (
                              <span key={tag} className="tag-bubble">{tag}</span>
                            ))}
                          </div>
                        )}
                      </button>
                    )
                  })}
                </div>
              </section>
            )
          })}
        </main>
      </div>
    </div>
  )
}
