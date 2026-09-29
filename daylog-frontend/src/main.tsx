import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom'
import { PrivateRoute } from './components/PrivateRoute'
import { SiteFooter } from './components/SiteFooter'
import LoginPage from './pages/LoginPage'
import CalendarPage from './pages/CalendarPage'
import DayPage from './pages/DayPage'
import WeiboLoginPage from './pages/WeiboLoginPage'
import WeiboCallbackPage from './pages/WeiboCallbackPage'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<PrivateRoute><CalendarPage /></PrivateRoute>} />
        <Route path="/day/:date" element={<PrivateRoute><DayPage /></PrivateRoute>} />
        <Route path="/weibo-login" element={<PrivateRoute><WeiboLoginPage /></PrivateRoute>} />
        <Route path="/weibo-callback" element={<PrivateRoute><WeiboCallbackPage /></PrivateRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <SiteFooter />
    </BrowserRouter>
  </StrictMode>,
)
