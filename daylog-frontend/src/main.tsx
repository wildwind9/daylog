import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom'
import { PrivateRoute } from './components/PrivateRoute'
import LoginPage from './pages/LoginPage'
import CalendarPage from './pages/CalendarPage'
import DayPage from './pages/DayPage'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<PrivateRoute><CalendarPage /></PrivateRoute>} />
        <Route path="/day/:date" element={<PrivateRoute><DayPage /></PrivateRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
