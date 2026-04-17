import { type ChangeEvent, type CSSProperties, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import {
  fetchAllContentSearch,
  fetchCurrentUser,
  fetchMonthSummary,
  fetchWeiboLoginStatus,
  setWeiboSyncEnabled,
  syncWeiboFull,
  unbindActiveWeibo,
  updateCurrentUserLocation,
  type CalendarDay,
  type CalendarSearchResult,
  type CurrentUserProfile,
  type WeiboLoginStatus,
} from '../api'

type MonthKey = `${number}-${string}`

interface BackgroundPreference {
  color: string
  image: string
  opacity: number
  pageOpacity: number
}

interface CalendarLocationState {
  returnDate?: string
  weiboLoginMessage?: string
}

interface LocationPreference {
  province: string
  city: string
  district: string
  latitude: number | null
  longitude: number | null
  updatedAt: string | null
}

interface WeatherInfo {
  temperature: number
  apparentTemperature: number
  weatherCode: number
  windSpeed: number
  updatedAt: string
}

interface NominatimAddress {
  state?: string
  province?: string
  municipality?: string
  state_district?: string
  city?: string
  city_district?: string
  town?: string
  village?: string
  county?: string
  district?: string
  suburb?: string
}

interface NominatimPlace {
  lat: string
  lon: string
  address?: NominatimAddress
}

interface BigDataCloudAdminArea {
  name?: string
}

interface BigDataCloudLocation {
  principalSubdivision?: string
  city?: string
  locality?: string
  localityInfo?: {
    administrative?: BigDataCloudAdminArea[]
  }
}

interface OpenMeteoWeather {
  current?: {
    temperature_2m: number
    apparent_temperature: number
    weather_code: number
    wind_speed_10m: number
  }
}

interface IpApiLocation {
  city?: string
  region?: string
  latitude?: number
  longitude?: number
}

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']
const BACKGROUND_STORAGE_KEY = 'daylog_calendar_background'
const LOCATION_STORAGE_KEY = 'daylog_calendar_location'
const WEATHER_STORAGE_KEY = 'daylog_calendar_weather'
const DEFAULT_BACKGROUND: BackgroundPreference = {
  color: '#f5f4f0',
  image: '',
  opacity: 0.42,
  pageOpacity: 0.9,
}
const DEFAULT_LOCATION: LocationPreference = {
  province: '',
  city: '',
  district: '',
  latitude: null,
  longitude: null,
  updatedAt: null,
}
const WEATHER_LABELS: Record<number, string> = {
  0: '晴',
  1: '大部晴朗',
  2: '局部多云',
  3: '阴',
  45: '雾',
  48: '雾凇',
  51: '小毛毛雨',
  53: '毛毛雨',
  55: '强毛毛雨',
  61: '小雨',
  63: '中雨',
  65: '大雨',
  71: '小雪',
  73: '中雪',
  75: '大雪',
  80: '小阵雨',
  81: '阵雨',
  82: '强阵雨',
  95: '雷雨',
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

function getMoodToneClass(mood: string | null) {
  if (!mood) return ''
  if (mood === '😍' || mood === '🤩') return 'mood-tone-blue'
  if (mood === '😊') return 'mood-tone-green'
  if (mood === '😌') return 'mood-tone-yellow'
  if (mood === '😢') return 'mood-tone-red'
  return ''
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
  return DEFAULT_BACKGROUND
}

function loadLocationPreference(): LocationPreference {
  return DEFAULT_LOCATION
}

function loadWeatherInfo(): WeatherInfo | null {
  return null
}

function hasLocationPreference(location: LocationPreference) {
  return Boolean(
    location.province
    || location.city
    || location.district
    || location.latitude !== null
    || location.longitude !== null,
  )
}

function locationFromUser(user: CurrentUserProfile): LocationPreference {
  return {
    province: user.province ?? '',
    city: user.city ?? '',
    district: user.district ?? '',
    latitude: user.latitude ?? null,
    longitude: user.longitude ?? null,
    updatedAt: user.locationUpdatedAt,
  }
}

function getScopedStorageKey(key: string, userId: number) {
  return `${key}:${userId}`
}

function readStoredValue<T>(key: string, fallback: T): T {
  try {
    const stored = localStorage.getItem(key)
    return stored ? { ...fallback, ...JSON.parse(stored) } : fallback
  } catch {
    return fallback
  }
}

function readStoredWeather(key: string) {
  try {
    const stored = localStorage.getItem(key)
    return stored ? JSON.parse(stored) as WeatherInfo : null
  } catch {
    return null
  }
}

function migrateLegacyPreference<T>(
  key: string,
  userId: number,
  fallback: T,
  readValue: (storageKey: string) => T,
) {
  const scopedKey = getScopedStorageKey(key, userId)
  if (localStorage.getItem(scopedKey)) {
    return readValue(scopedKey)
  }

  const legacyValue = localStorage.getItem(key)
  if (!legacyValue) {
    return fallback
  }

  localStorage.setItem(scopedKey, legacyValue)
  localStorage.removeItem(key)
  return readValue(scopedKey)
}

function normalizeLocation(place: NominatimPlace): LocationPreference {
  const address = place.address ?? {}
  const province = address.state ?? address.province ?? ''
  const city = address.city ?? address.state_district ?? address.municipality ?? ''
  return {
    province,
    city: city || (province.endsWith('市') ? province : ''),
    district: address.city_district ?? address.district ?? address.county ?? '',
    latitude: Number(place.lat),
    longitude: Number(place.lon),
    updatedAt: new Date().toISOString(),
  }
}

function isCityName(value?: string) {
  return Boolean(value && /市|自治州|地区|盟/.test(value))
}

function isDistrictName(value?: string) {
  return Boolean(value && /区|县|旗|市辖区/.test(value))
}

function normalizeBigDataCloudLocation(
  data: BigDataCloudLocation,
  latitude: number,
  longitude: number,
): LocationPreference {
  const areas = data.localityInfo?.administrative ?? []
  const areaNames = areas.map((area) => area.name).filter(Boolean) as string[]
  const province = data.principalSubdivision ?? areaNames[0] ?? ''
  const cityCandidate = data.city && data.city !== province ? data.city : ''
  const cityFromAreas = areaNames.find((name) => name !== province && isCityName(name)) ?? ''
  let city = isDistrictName(cityCandidate) ? '' : cityCandidate || cityFromAreas
  const districtFromAreas = [...areaNames]
    .reverse()
    .find((name) => name !== province && name !== city && isDistrictName(name)) ?? ''
  let district = districtFromAreas || (isDistrictName(data.locality) ? data.locality ?? '' : '')

  if (!city && province.endsWith('市')) {
    city = province
  }
  if (!district && isDistrictName(cityCandidate)) {
    district = cityCandidate
  }

  return {
    province,
    city,
    district,
    latitude,
    longitude,
    updatedAt: new Date().toISOString(),
  }
}

function getWeatherLabel(weatherCode: number) {
  return WEATHER_LABELS[weatherCode] ?? '未知天气'
}

function getWeatherSymbol(weatherCode: number) {
  if (weatherCode === 0 || weatherCode === 1) return '☀️'
  if (weatherCode === 2) return '⛅'
  if (weatherCode === 3) return '☁️'
  if (weatherCode === 45 || weatherCode === 48) return '🌫️'
  if ((weatherCode >= 51 && weatherCode <= 67) || (weatherCode >= 80 && weatherCode <= 82)) return '🌧️'
  if (weatherCode >= 71 && weatherCode <= 77) return '❄️'
  if (weatherCode >= 95) return '⛈️'
  return '🔍'
}

function getBrowserPosition() {
  return new Promise<GeolocationPosition>((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('当前浏览器不支持定位'))
      return
    }

    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 12000,
      maximumAge: 1000 * 60 * 10,
    })
  })
}

async function reverseGeocodeWithNominatim(latitude: number, longitude: number) {
  const params = new URLSearchParams({
    format: 'jsonv2',
    lat: String(latitude),
    lon: String(longitude),
    addressdetails: '1',
    'accept-language': 'zh-CN',
  })
  const response = await fetch(`https://nominatim.openstreetmap.org/reverse?${params.toString()}`)
  if (!response.ok) throw new Error('位置解析失败')
  return normalizeLocation(await response.json() as NominatimPlace)
}

async function reverseGeocodeWithBigDataCloud(latitude: number, longitude: number) {
  const params = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    localityLanguage: 'zh',
  })
  const response = await fetch(`https://api.bigdatacloud.net/data/reverse-geocode-client?${params.toString()}`)
  if (!response.ok) throw new Error('位置解析失败')
  return normalizeBigDataCloudLocation(await response.json() as BigDataCloudLocation, latitude, longitude)
}

async function reverseGeocode(latitude: number, longitude: number) {
  try {
    return await reverseGeocodeWithBigDataCloud(latitude, longitude)
  } catch {
    return reverseGeocodeWithNominatim(latitude, longitude)
  }
}

async function locateByIp(): Promise<LocationPreference> {
  const response = await fetch('https://ipapi.co/json/')
  if (!response.ok) throw new Error('网络定位失败')

  const data = await response.json() as IpApiLocation
  if (typeof data.latitude !== 'number' || typeof data.longitude !== 'number') {
    throw new Error('网络定位没有返回经纬度')
  }

  try {
    return await reverseGeocode(data.latitude, data.longitude)
  } catch {
    return {
      province: data.region ?? '',
      city: data.city ?? '',
      district: '',
      latitude: data.latitude,
      longitude: data.longitude,
      updatedAt: new Date().toISOString(),
    }
  }
}

async function searchLocation(location: LocationPreference) {
  const query = [location.province, location.city, location.district, '中国']
    .filter(Boolean)
    .join(' ')
  if (!query.trim()) throw new Error('请先填写省市区')

  const params = new URLSearchParams({
    format: 'jsonv2',
    q: query,
    limit: '1',
    addressdetails: '1',
    'accept-language': 'zh-CN',
  })
  const response = await fetch(`https://nominatim.openstreetmap.org/search?${params.toString()}`)
  if (!response.ok) throw new Error('位置查询失败')
  const places = await response.json() as NominatimPlace[]
  if (places.length === 0) throw new Error('没有找到这个位置')
  const resolvedLocation = normalizeLocation(places[0])
  return {
    ...resolvedLocation,
    province: location.province || resolvedLocation.province,
    city: location.city || resolvedLocation.city,
    district: location.district || resolvedLocation.district,
  }
}

async function fetchCurrentWeather(latitude: number, longitude: number): Promise<WeatherInfo> {
  const params = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    current: 'temperature_2m,apparent_temperature,weather_code,wind_speed_10m',
    timezone: 'auto',
  })
  const response = await fetch(`https://api.open-meteo.com/v1/forecast?${params.toString()}`)
  if (!response.ok) throw new Error('天气更新失败')
  const data = await response.json() as OpenMeteoWeather
  if (!data.current) throw new Error('天气数据为空')

  return {
    temperature: data.current.temperature_2m,
    apparentTemperature: data.current.apparent_temperature,
    weatherCode: data.current.weather_code,
    windSpeed: data.current.wind_speed_10m,
    updatedAt: new Date().toISOString(),
  }
}

function getInitialCalendarDate(returnDate?: string) {
  if (!returnDate) return dayjs()

  const parsedDate = dayjs(returnDate)
  const today = dayjs()
  if (!parsedDate.isValid()) return today
  if (parsedDate.isAfter(today.add(1, 'year'), 'day')) return today
  if (parsedDate.isBefore(today.subtract(30, 'year'), 'day')) return today

  return parsedDate
}

export default function CalendarPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const locationState = location.state as CalendarLocationState | null
  const returnDate = locationState?.returnDate
  const [selectedDate, setSelectedDate] = useState(() => getInitialCalendarDate(returnDate))
  const [rangeCenter, setRangeCenter] = useState(() => getInitialCalendarDate(returnDate))
  const [monthSummaries, setMonthSummaries] = useState<Record<MonthKey, CalendarDay[]>>({})
  const [settingsUserId, setSettingsUserId] = useState<number | null>(null)
  const [background, setBackground] = useState<BackgroundPreference>(loadBackgroundPreference)
  const [backgroundPanelOpen, setBackgroundPanelOpen] = useState(false)
  const [currentLocation, setCurrentLocation] = useState<LocationPreference>(loadLocationPreference)
  const [weather, setWeather] = useState<WeatherInfo | null>(loadWeatherInfo)
  const [locationLoading, setLocationLoading] = useState(false)
  const [locationError, setLocationError] = useState<string | null>(null)
  const [locationNotice, setLocationNotice] = useState<string | null>(null)
  const [weiboLoginStatus, setWeiboLoginStatus] = useState<WeiboLoginStatus | null>(null)
  const [weiboSyncLoading, setWeiboSyncLoading] = useState(false)
  const [weiboImmediateSyncLoading, setWeiboImmediateSyncLoading] = useState(false)
  const [weiboLoginMessage, setWeiboLoginMessage] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<CalendarSearchResult[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const monthStackRef = useRef<HTMLElement | null>(null)
  const monthRefs = useRef<Record<MonthKey, HTMLElement | null>>({})
  const requestedMonths = useRef<Set<MonthKey>>(new Set())
  const monthScrollBehavior = useRef<ScrollBehavior>('auto')
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
    if (!returnDate) return
    navigate('.', { replace: true, state: null })
  }, [navigate, returnDate])

  useEffect(() => {
    if (!locationState?.weiboLoginMessage) return
    setWeiboLoginMessage(locationState.weiboLoginMessage)
    navigate('.', {
      replace: true,
      state: locationState.returnDate ? { returnDate: locationState.returnDate } : null,
    })
  }, [locationState, navigate])

  useEffect(() => {
    let cancelled = false

    fetchCurrentUser()
      .then((user) => {
        if (cancelled) return

        setSettingsUserId(user.id)
        const backendLocation = locationFromUser(user)
        setBackground(
          migrateLegacyPreference(
            BACKGROUND_STORAGE_KEY,
            user.id,
            DEFAULT_BACKGROUND,
            (storageKey) => readStoredValue(storageKey, DEFAULT_BACKGROUND),
          ),
        )
        if (hasLocationPreference(backendLocation)) {
          setCurrentLocation(backendLocation)
        } else {
          const storedLocation = migrateLegacyPreference(
            LOCATION_STORAGE_KEY,
            user.id,
            DEFAULT_LOCATION,
            (storageKey) => readStoredValue(storageKey, DEFAULT_LOCATION),
          )
          setCurrentLocation(storedLocation)
          if (hasLocationPreference(storedLocation)) {
            updateCurrentUserLocation(storedLocation).catch(() => undefined)
          }
        }
        setWeather(
          migrateLegacyPreference(
            WEATHER_STORAGE_KEY,
            user.id,
            null,
            (storageKey) => readStoredWeather(storageKey),
          ),
        )
      })
      .catch(() => {
        if (cancelled) return
        setSettingsUserId(null)
        setBackground(DEFAULT_BACKGROUND)
        setCurrentLocation(DEFAULT_LOCATION)
        setWeather(null)
      })

    return () => {
      cancelled = true
    }
  }, [])

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
        .catch(() => {
          requestedMonths.current.delete(monthKey)
        })
    })
  }, [monthSummaries, visibleMonthSignature, visibleMonths])

  useLayoutEffect(() => {
    const monthStack = monthStackRef.current
    const selectedMonthElement = monthRefs.current[selectedMonthKey]

    if (!monthStack || !selectedMonthElement) return

    const nextScrollTop = selectedMonthElement.offsetTop
      - monthStack.offsetTop
      - ((monthStack.clientHeight - selectedMonthElement.clientHeight) / 2)

    monthStack.scrollTo({
      top: Math.max(0, nextScrollTop),
      behavior: monthScrollBehavior.current,
    })
    monthScrollBehavior.current = 'auto'
  }, [selectedMonthKey, visibleMonthSignature])

  useEffect(() => {
    if (settingsUserId === null) return
    localStorage.setItem(getScopedStorageKey(BACKGROUND_STORAGE_KEY, settingsUserId), JSON.stringify(background))
  }, [background, settingsUserId])

  useEffect(() => {
    if (settingsUserId === null) return
    localStorage.setItem(getScopedStorageKey(LOCATION_STORAGE_KEY, settingsUserId), JSON.stringify(currentLocation))
  }, [currentLocation, settingsUserId])

  useEffect(() => {
    if (settingsUserId === null || !weather) return
    localStorage.setItem(getScopedStorageKey(WEATHER_STORAGE_KEY, settingsUserId), JSON.stringify(weather))
  }, [settingsUserId, weather])

  useEffect(() => {
    if (!backgroundPanelOpen) return

    fetchWeiboLoginStatus()
      .then(setWeiboLoginStatus)
      .catch(() => setWeiboLoginMessage('微博登录状态获取失败'))
  }, [backgroundPanelOpen])

  useEffect(() => {
    if (currentLocation.latitude === null || currentLocation.longitude === null) return

    fetchCurrentWeather(currentLocation.latitude, currentLocation.longitude)
      .then(setWeather)
      .catch(() => undefined)
  }, [currentLocation.latitude, currentLocation.longitude])

  useEffect(() => {
    const normalizedQuery = searchQuery.trim()
    if (!normalizedQuery) {
      setSearchResults([])
      setSearchError(null)
      setSearchLoading(false)
      return
    }

    let active = true
    setSearchLoading(true)
    setSearchError(null)

    const timer = window.setTimeout(() => {
      fetchAllContentSearch(normalizedQuery)
        .then((results) => {
          if (active) setSearchResults(results)
        })
        .catch((error) => {
          if (active) {
            setSearchResults([])
            setSearchError(error instanceof Error ? error.message : '搜索失败')
          }
        })
        .finally(() => {
          if (active) setSearchLoading(false)
        })
    }, 260)

    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [searchQuery])

  useEffect(() => {
    ;[yearWheelRef, monthWheelRef, dayWheelRef].forEach((wheelRef) => {
      const wheel = wheelRef.current
      const activeItem = wheel?.querySelector<HTMLElement>('.active')

      if (!wheel || !activeItem) return

      wheel.scrollTop = activeItem.offsetTop
        - wheel.offsetTop
        - ((wheel.clientHeight - activeItem.clientHeight) / 2)
    })
  }, [selectedDate])

  const updateDate = (year: number, month: number, day: number) => {
    const nextMonth = dayjs(`${year}-${String(month).padStart(2, '0')}-01`)
    const safeDay = Math.min(day, nextMonth.daysInMonth())
    const nextDate = nextMonth.date(safeDay)
    monthScrollBehavior.current = 'smooth'
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
    monthScrollBehavior.current = 'smooth'
    setSelectedDate(today)
    setRangeCenter(today)
  }

  const writeToday = () => {
    const now = dayjs()
    navigate(`/day/${now.format('YYYY-MM-DD')}`, { state: { focusDiary: true } })
  }

  const logout = () => {
    localStorage.removeItem('daylog_token')
    navigate('/login', { replace: true })
  }

  const openSearchResult = (date: string) => {
    navigate(`/day/${date}`)
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

  const detectCurrentLocation = async () => {
    setLocationLoading(true)
    setLocationError(null)
    setLocationNotice(null)
    try {
      const position = await getBrowserPosition()
      const nextLocation = await reverseGeocode(position.coords.latitude, position.coords.longitude)
      const savedLocation = await updateCurrentUserLocation(nextLocation)
      setCurrentLocation(locationFromUser(savedLocation))
    } catch (error) {
      try {
        const nextLocation = await locateByIp()
        const savedLocation = await updateCurrentUserLocation(nextLocation)
        setCurrentLocation(locationFromUser(savedLocation))
        setLocationNotice('浏览器精确定位不可用，已自动改用网络定位，位置可能会有偏差')
      } catch (fallbackError) {
        const message = error instanceof Error ? error.message : '定位失败'
        const fallbackMessage = fallbackError instanceof Error ? fallbackError.message : '网络定位失败'
        setLocationError(`${message}，${fallbackMessage}`)
      }
    } finally {
      setLocationLoading(false)
    }
  }

  const saveManualLocation = async () => {
    setLocationLoading(true)
    setLocationError(null)
    try {
      const nextLocation = await searchLocation(currentLocation)
      const savedLocation = await updateCurrentUserLocation(nextLocation)
      setCurrentLocation(locationFromUser(savedLocation))
    } catch (error) {
      setLocationError(error instanceof Error ? error.message : '位置或天气更新失败')
    } finally {
      setLocationLoading(false)
    }
  }

  const handleWeiboLogin = () => {
    navigate('/weibo-login')
  }

  const handleWeiboUnbind = async () => {
    const clearSyncedContent = window.confirm('解绑微博时，是否同时清除该微博账号已同步的内容？')
    try {
      const result = await unbindActiveWeibo(clearSyncedContent)
      setWeiboLoginStatus(result.status)
      setWeiboLoginMessage(
        clearSyncedContent
          ? `微博已解绑，并清除了 ${result.removedContentCount} 条微博内容`
          : '微博已解绑，原有微博内容已保留',
      )
    } catch (error) {
      setWeiboLoginMessage(error instanceof Error ? error.message : '微博解绑失败')
    }
  }

  const handleWeiboSyncToggle = async (enabled: boolean) => {
    if (enabled && !weiboLoginStatus?.activeBinding) {
      setWeiboLoginMessage('请先完成微博绑定，再开启定时同步')
      return
    }

    setWeiboSyncLoading(true)
    setWeiboLoginMessage(null)
    try {
      const nextStatus = await setWeiboSyncEnabled(enabled)
      setWeiboLoginStatus(nextStatus)
      setWeiboLoginMessage(
        enabled
          ? '已开启微博定时同步，每天凌晨 4 点自动抓取'
          : '已关闭微博定时同步',
      )
    } catch (error) {
      setWeiboLoginMessage(error instanceof Error ? error.message : '微博同步开关更新失败')
    } finally {
      setWeiboSyncLoading(false)
    }
  }

  const handleImmediateWeiboSync = async () => {
    setWeiboImmediateSyncLoading(true)
    setWeiboLoginMessage(null)
    try {
      const result = await syncWeiboFull()
      setWeiboLoginMessage(`已开始同步全部微博，本次同步结果：${result.new_count} 条新内容`)
      const nextStatus = await fetchWeiboLoginStatus()
      setWeiboLoginStatus(nextStatus)
    } catch (error) {
      setWeiboLoginMessage(error instanceof Error ? error.message : '微博立即同步失败')
    } finally {
      setWeiboImmediateSyncLoading(false)
    }
  }

  return (
    <div className="calendar-page-shell" style={backgroundStyle}>
      <div className="calendar-background-color" />
      <div className="calendar-background-image" />

      <div className="calendar-container calendar-scroll-container">
        <header className="calendar-hero">
          <div>
            <p className="eyebrow">Daylog Calendar</p>
            <h1>{selectedDate.format('YYYY年M月D日')}</h1>
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
          aria-label="页面设置"
          onClick={() => setBackgroundPanelOpen((open) => !open)}
        >
          设置
        </button>

        {backgroundPanelOpen && (
          <section className="background-panel" aria-label="主页设置">
            <div className="settings-section location-settings-section">
              <h3>位置和天气</h3>
              <div className="location-fields">
                <label>
                  <span>省</span>
                  <input
                    value={currentLocation.province}
                    onChange={(event) => setCurrentLocation((current) => ({
                      ...current,
                      province: event.target.value,
                      latitude: null,
                      longitude: null,
                    }))}
                    placeholder="例如 浙江省"
                  />
                </label>
                <label>
                  <span>市</span>
                  <input
                    value={currentLocation.city}
                    onChange={(event) => setCurrentLocation((current) => ({
                      ...current,
                      city: event.target.value,
                      latitude: null,
                      longitude: null,
                    }))}
                    placeholder="例如 杭州市"
                  />
                </label>
                <label>
                  <span>区</span>
                  <input
                    value={currentLocation.district}
                    onChange={(event) => setCurrentLocation((current) => ({
                      ...current,
                      district: event.target.value,
                      latitude: null,
                      longitude: null,
                    }))}
                    placeholder="例如 西湖区"
                  />
                </label>
                <button onClick={detectCurrentLocation} disabled={locationLoading}>
                  {locationLoading ? '更新中...' : '获取当前位置'}
                </button>
                <button onClick={saveManualLocation} disabled={locationLoading}>
                  保存位置
                </button>
              </div>
              {locationNotice && <p className="location-notice">{locationNotice}</p>}
              {locationError && <p className="location-error">{locationError}</p>}
            </div>

            <div className="settings-section weibo-settings-section">
              <h3>微博同步</h3>
              <div className="weibo-login-row">
                <div className="weibo-login-copy">
                    <strong>
                      {weiboLoginStatus?.activeBinding
                      ? `已绑定微博 ${weiboLoginStatus.activeBinding.screenName || weiboLoginStatus.activeBinding.weiboUid}`
                      : '未绑定微博'}
                    </strong>
                  <span>
                    {weiboLoginStatus?.syncEnabled
                      ? '定时同步已开启，每天凌晨 4 点自动抓取微博'
                      : '绑定微博后可开启每天凌晨 4 点自动抓取'}
                  </span>
                </div>
                <div className="weibo-sync-actions">
                  <label className="weibo-sync-toggle">
                    <input
                      type="checkbox"
                      checked={Boolean(weiboLoginStatus?.syncEnabled)}
                      disabled={weiboSyncLoading}
                      onChange={(event) => handleWeiboSyncToggle(event.target.checked)}
                    />
                    <span>定时同步</span>
                  </label>
                  <button onClick={handleWeiboLogin}>
                    {weiboLoginStatus?.activeBinding ? '更换绑定' : '绑定微博'}
                  </button>
                  {weiboLoginStatus?.activeBinding && (
                    <button onClick={handleImmediateWeiboSync} disabled={weiboImmediateSyncLoading}>
                      {weiboImmediateSyncLoading ? '同步中...' : '立刻同步'}
                    </button>
                  )}
                  {weiboLoginStatus?.activeBinding && (
                    <button onClick={handleWeiboUnbind}>解绑微博</button>
                  )}
                </div>
              </div>
              {weiboLoginMessage && <p className="weibo-login-message">{weiboLoginMessage}</p>}
              <div className="weibo-binding-status-list">
                <div className={`weibo-binding-status-item ${weiboLoginStatus?.activeBinding ? 'done' : 'pending'}`}>
                  <strong>步骤 1：绑定微博账号</strong>
                  <span>
                    {weiboLoginStatus?.activeBinding
                      ? '已完成，当前系统账号已经和一个微博账号建立绑定。'
                      : '先完成微博账号绑定，系统才能知道你当前连接的是哪个微博账号。'}
                  </span>
                </div>
                <div className="weibo-binding-status-item done">
                  <strong>步骤 2：补充网页登录态</strong>
                  <span>
                    {weiboLoginStatus?.loginStateReady
                      ? '已完成，现在“立刻同步”会按全量历史微博链路执行。'
                      : '如果要同步全部历史微博，还需要补充一次服务器可用的网页登录态。'}
                  </span>
                </div>
              </div>
              {weiboLoginStatus?.activeBinding && weiboLoginStatus.profileDir === '__disabled__' && (
                <div className="weibo-sync-actions">
                  <button onClick={() => navigate('/weibo-full-sync-login')}>
                    补充网页登录态
                  </button>
                </div>
              )}
            </div>

            <div className="settings-section weibo-settings-clean-section">
              <h3>微博同步</h3>
              <div className="weibo-login-row">
                <div className="weibo-login-copy">
                  <strong>
                    {weiboLoginStatus?.activeBinding
                      ? `已绑定微博 ${weiboLoginStatus.activeBinding.screenName || weiboLoginStatus.activeBinding.weiboUid}`
                      : '未绑定微博'}
                  </strong>
                  <span>
                    {weiboLoginStatus?.syncEnabled
                      ? '定时同步已开启，每天凌晨 4 点自动抓取最新可访问微博。'
                      : '绑定微博后，可开启每天凌晨 4 点自动抓取最新可访问微博。'}
                  </span>
                </div>
                <div className="weibo-sync-actions">
                  <label className="weibo-sync-toggle">
                    <input
                      type="checkbox"
                      checked={Boolean(weiboLoginStatus?.syncEnabled)}
                      disabled={weiboSyncLoading}
                      onChange={(event) => handleWeiboSyncToggle(event.target.checked)}
                    />
                    <span>定时同步</span>
                  </label>
                  <button onClick={handleWeiboLogin}>
                    {weiboLoginStatus?.activeBinding ? '更换绑定' : '绑定微博'}
                  </button>
                  {weiboLoginStatus?.activeBinding && (
                    <button onClick={handleImmediateWeiboSync} disabled={weiboImmediateSyncLoading}>
                      {weiboImmediateSyncLoading ? '同步中...' : '立即同步微博'}
                    </button>
                  )}
                  {weiboLoginStatus?.activeBinding && (
                    <button onClick={handleWeiboUnbind}>解绑微博</button>
                  )}
                </div>
              </div>
              {weiboLoginMessage && <p className="weibo-login-message">{weiboLoginMessage}</p>}
              <div className="weibo-binding-status-list">
                <div className={`weibo-binding-status-item ${weiboLoginStatus?.activeBinding ? 'done' : 'pending'}`}>
                  <strong>微博账号绑定状态</strong>
                  <span>
                    {weiboLoginStatus?.activeBinding
                      ? '当前系统账号已经完成微博绑定，可以直接同步该接口可访问的微博内容。'
                      : '先完成微博账号绑定，系统才能同步该账号可访问的微博内容。'}
                  </span>
                </div>
              </div>
            </div>

            <div className="settings-section background-settings-section">
              <h3>背景</h3>
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
                <span>背景透明度{Math.round(background.opacity * 100)}%</span>
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
                <span>页面透明度{Math.round(background.pageOpacity * 100)}%</span>
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
            </div>

            <div className="settings-section">
              <button className="settings-logout-button" onClick={logout}>
                退出登录
              </button>
            </div>
          </section>
        )}

        <section className="location-weather-panel" aria-label="当前位置和天气">
          <div className="location-weather-summary">
            <div>
              <span className="location-label">当前位置</span>
              <strong>
                {[currentLocation.province, currentLocation.city, currentLocation.district]
                  .filter(Boolean)
                  .join(' / ') || '未选择'}
              </strong>
            </div>
            <div className="weather-pill">
              {weather ? (
                <>
                  <span className="weather-symbol" aria-label={getWeatherLabel(weather.weatherCode)}>
                    {getWeatherSymbol(weather.weatherCode)}
                  </span>
                  <strong>{Math.round(weather.temperature)}°C</strong>
                  <small>体感 {Math.round(weather.apparentTemperature)}°C</small>
                </>
              ) : (
                <span>暂无天气</span>
              )}
            </div>
          </div>
        </section>

        <section className="calendar-search-panel" aria-label="搜索所有内容">
          <label className="calendar-search-box">
            <span>搜索</span>
            <input
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="搜索日记、微博、标签、心情、天气..."
            />
          </label>
          {searchQuery.trim() && (
            <div className="calendar-search-results">
              <div className="calendar-search-status">
                {searchLoading
                  ? '搜索中...'
                  : searchError
                    ? searchError
                    : `找到 ${searchResults.length} 条结果`}
              </div>
              {!searchLoading && !searchError && searchResults.length === 0 && (
                <p className="calendar-search-empty">没有找到相关内容</p>
              )}
              {!searchLoading && !searchError && searchResults.map((result, index) => (
                <button
                  key={`${result.date}-${result.source}-${index}`}
                  className="calendar-search-result"
                  onClick={() => openSearchResult(result.date)}
                >
                  <span className="calendar-search-date">
                    {dayjs(result.date).format('YYYY年M月D日')}
                  </span>
                  <strong>{result.title || result.matchedText || '日记内容'}</strong>
                  {result.matchedText && result.title !== result.matchedText && (
                    <span className="calendar-search-snippet">{result.matchedText}</span>
                  )}
                  <span className="calendar-search-meta">
                    {[result.source, result.mood, result.weather, ...result.tags].filter(Boolean).join(' 路 ')}
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>

        <div className="month-stack-shell">
          <main
            className="month-stack"
            ref={monthStackRef}
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
                      <h2>{month.format('M月')}</h2>
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
                                <span className={`tag-bubble mood-weather ${getMoodToneClass(info.mood)}`}>
                                  {[info.mood, info.weather].filter(Boolean).join(' ')}
                                </span>
                              )}
                              {info.tags.map((tag) => (
                                <span key={tag} className="tag-bubble content-tag-bubble">{tag}</span>
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
          <button className="write-diary-button" aria-label="写日记" onClick={writeToday}>
            +
          </button>
        </div>
      </div>
    </div>
  )
}
