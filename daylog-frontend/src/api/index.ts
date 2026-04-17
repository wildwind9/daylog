import client from './client'
export { extractApiErrorMessage } from './client'

export interface CalendarDay {
  date: string        // 'YYYY-MM-DD'
  tags: string[]
  itemCount: number
  mood: string | null
  weather: string | null
}

export interface CalendarSearchResult {
  date: string
  title: string | null
  matchedText: string
  source: string
  mood: string | null
  weather: string | null
  tags: string[]
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

export interface WeiboLoginStatus {
  profileExists: boolean
  cookieConfigured: boolean
  loginStateReady: boolean
  profileDir: string
  syncEnabled: boolean
  totalWeiboContentCount: number
  activeBinding: WeiboBindingInfo | null
}

export interface WeiboBindingInfo {
  id: number
  weiboUid: string
  screenName: string | null
  active: boolean
  createdAt: string
  unboundAt: string | null
  expiresAt: string | null
  contentCount: number
}

export interface CurrentUserProfile {
  id: number
  username: string
  role: string
  province: string | null
  city: string | null
  district: string | null
  latitude: number | null
  longitude: number | null
  locationUpdatedAt: string | null
}

export interface WeiboLoginResult {
  loggedIn: boolean
  uid: string
  profileDir: string
  cookieSaved: boolean
}

export interface WeiboQrLoginSession {
  sessionId: string
  status: 'pending' | 'completed' | 'expired' | 'failed'
  message: string
  uid: string
  cookieSaved: boolean
  imageBase64: string
}

export interface CompleteWeiboBindingResult {
  activeBinding: WeiboBindingInfo
  reusedExistingBinding: boolean
  replacedContent: boolean
  removedContentCount: number
  syncResult: { platform: string; new_count: number; fetched_count?: number; status: string; error: string | null } | null
  status: WeiboLoginStatus
}

export interface WeiboOauthStartResult {
  authorizeUrl: string
  redirectUri: string
}

export interface UnbindWeiboResult {
  removedContentCount: number
  status: WeiboLoginStatus
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

export const fetchAllContentSearch = (query: string) =>
  client.get<{ success: boolean; data: CalendarSearchResult[] }>('/api/search', {
    params: { q: query },
  }).then((r) => r.data.data)

// 更新日记
export const upsertDiary = (date: string, body: DiaryPayload) =>
  client.put(`/api/diary/${date}`, body)

export const deleteDiaryEntry = (date: string, itemId: number) =>
  client.delete(`/api/diary/${date}/${itemId}`)

export const fetchWeiboLoginStatus = () =>
  client.get<{ success: boolean; data: WeiboLoginStatus }>('/api/weibo/sync/status')
    .then((r) => r.data.data)

export const startWeiboOauth = () =>
  client.get<{ success: boolean; data: WeiboOauthStartResult }>('/api/weibo/oauth/start')
    .then((r) => r.data.data)

export const confirmWeiboOauthBinding = (payload: {
  ticket: string
  replaceExistingContent: boolean
  syncNow: boolean
}) =>
  client.post<{ success: boolean; data: CompleteWeiboBindingResult }>('/api/weibo/bind/confirm', payload)
    .then((r) => r.data.data)

export const bindWeiboWithQrLogin = (payload: {
  weiboUid: string
  screenName?: string | null
  replaceExistingContent: boolean
  syncNow: boolean
}) =>
  client.post<{ success: boolean; data: CompleteWeiboBindingResult }>('/api/weibo/bind/qr', payload)
    .then((r) => r.data.data)

export const completeWeiboBinding = (payload: {
  weiboUid: string
  replaceExistingContent: boolean
  syncNow: boolean
}) =>
  client.post<{ success: boolean; data: CompleteWeiboBindingResult }>('/api/weibo/bind/complete', payload)
    .then((r) => r.data.data)

export const unbindActiveWeibo = (clearSyncedContent: boolean) =>
  client.delete<{ success: boolean; data: UnbindWeiboResult }>('/api/weibo/bind/active', {
    data: { clearSyncedContent },
  }).then((r) => r.data.data)

export const loginWeibo = () =>
  client.post<{ success: boolean; data: WeiboLoginResult }>('/api/weibo/login', null, {
    timeout: 310_000,
  })
    .then((r) => r.data.data)

export const startWeiboQrLogin = () =>
  client.post<{ success: boolean; data: WeiboQrLoginSession }>('/api/weibo/login/qr')
    .then((r) => r.data.data)

export const fetchWeiboQrLoginStatus = (sessionId: string) =>
  client.get<{ success: boolean; data: WeiboQrLoginSession }>('/api/weibo/login/qr', {
    params: { sessionId },
  }).then((r) => r.data.data)

export const setWeiboSyncEnabled = (enabled: boolean) =>
  client.put<{ success: boolean; data: WeiboLoginStatus }>('/api/weibo/sync/enabled', { enabled })
    .then((r) => r.data.data)

export const syncWeiboFull = () =>
  client.post<{ success: boolean; data: { platform: string; new_count: number; fetched_count?: number; status: string; error: string | null } }>(
    '/api/weibo/sync/full',
    null,
    { timeout: 310_000 },
  ).then((r) => {
    const data = r.data.data
    if (data.status !== 'success') {
      throw new Error(data.error || '微博立即同步失败，请重新绑定微博后再试')
    }
    return {
      ...data,
      new_count: data.fetched_count ?? data.new_count,
    }
  })

export interface DiaryPayload {
  body: string | null
  bodyFormat: string | null
  mood: string | null
  weather: string | null
}

// 登录
export const login = (username: string, password: string) =>
  client.post<{ success: boolean; data: { token: string } }>('/api/auth/login', {
    username,
    password,
  }).then((r) => r.data.data.token)

export const register = (username: string, password: string) =>
  client.post<{ success: boolean; data: { token: string } }>('/api/auth/register', {
    username,
    password,
  }).then((r) => r.data.data.token)

export const fetchCurrentUser = () =>
  client.get<{ success: boolean; data: CurrentUserProfile }>('/api/auth/me')
    .then((r) => r.data.data)

export const updateCurrentUserLocation = (payload: {
  province: string | null
  city: string | null
  district: string | null
  latitude: number | null
  longitude: number | null
}) =>
  client.put<{ success: boolean; data: CurrentUserProfile }>('/api/auth/me/location', payload)
    .then((r) => r.data.data)
