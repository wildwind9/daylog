import client from './client'

export interface CalendarDay {
  date: string        // 'YYYY-MM-DD'
  tags: string[]
  itemCount: number
  mood: string | null
  weather: string | null
}

export interface ContentItemDto {
  id: number
  source: string
  contentType: string
  title: string | null
  body: string | null
  bodyFormat: string
  media: string[] | null
  sourceUrl: string | null
  itemTime: string
  tags: string[]
}

export interface DayDetail {
  date: string
  mood: string | null
  weather: string | null
  diaryBody: string | null
  diaryBodyFormat: string | null
  items: ContentItemDto[]
}

// 日历月摘要
export const fetchMonthSummary = (year: number, month: number) =>
  client.get<{ success: boolean; data: CalendarDay[] }>('/api/calendar', {
    params: { year, month },
  }).then((r) => r.data.data)

// 某天详情
export const fetchDayDetail = (date: string) =>
  client.get<{ success: boolean; data: DayDetail }>(`/api/day/${date}`)
    .then((r) => r.data.data)

// 更新日记
export const upsertDiary = (date: string, body: DiaryPayload) =>
  client.put(`/api/diary/${date}`, body)

export interface DiaryPayload {
  body: string
  bodyFormat: string
  mood: string | null
  weather: string | null
}

// 登录
export const login = (username: string, password: string) =>
  client.post<{ success: boolean; data: { token: string } }>('/api/auth/login', {
    username,
    password,
  }).then((r) => r.data.data.token)
