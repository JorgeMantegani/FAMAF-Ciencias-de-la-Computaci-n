import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Login from './pages/Login'
import Home from './pages/Home'
import Match from './pages/Match'
import RegisterPage from './pages/register_page'
import LandingPage from './pages/landing_page'
import BehaviorPage from './pages/behavior_page'
import FriendlyRoomPage from './pages/friendly_room_page'
import './styles/tokens.css'
import './App.css'
import JoinFriendly from './pages/join_friendly'


const Navbar = () => (
  <nav id="top-bar">
    <div className="flex items-center gap-3">
      <span className="w-9 h-9 rounded-md bg-[#e09a4b] flex items-center justify-center" aria-hidden="true">
        <svg viewBox="0 0 24 24" className="w-6 h-6" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round">
          <circle cx="12" cy="12" r="9" />
          <path d="M9 9l6 6M15 9l-6 6" />
        </svg>
      </span>
      <div>
        <p className="font-plex-sans text-lg leading-tight">FutBot</p>
        <p className="font-plex-mono text-[11px] text-[#b5c2b3]">laboratorio / presión alta v4</p>
      </div>
    </div>
    <p className="flex items-center gap-2 font-plex-mono text-[10px] tracking-widest uppercase text-[#d8dccf]">
      <span className="w-1.5 h-1.5 rounded-full bg-[#7fae7f]" aria-hidden="true" />
      Vestuario digital abierto
    </p>
  </nav>
)

function Landing() {
  return (
    <div className="bg-[url('/BackFutBot.png')] bg-cover bg-center bg-no-repeat min-h-screen w-full flex flex-col text-white font-sans">
      <Navbar />
      <div className="w-full max-w-7xl mx-auto p-4 flex-1 flex flex-col">
        <LandingPage />
      </div>
    </div>
  )
}

function Registration() {
  return (
    <div className="registration-layout bg-[url('/BackFutBot.png')] bg-cover bg-center bg-no-repeat text-white font-sans">
      <nav id="top-bar">
        <h1 className="text-2xl font-bold tracking-wider">⚽︎ Futbot</h1>
      </nav>
      <main className="w-full max-w-7xl mx-auto p-4 flex justify-center">
        <RegisterPage />
      </main>
    </div>
  )
}
// Layout para las páginas internas autenticadas (Home, Behaviors, sala amistosa)
function DashboardLayout({ children }) {
  return (
    <div className="bg-[url('/BackFutBot.png')] bg-cover bg-center bg-no-repeat min-h-dvh w-full flex flex-col text-white font-sans">
      <Navbar />
      <main className="container mx-auto p-4 flex-1 flex flex-col">
        {children}
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/register" element={<Registration />} />
        <Route path="/auth/register" element={<Navigate to="/register" replace />} />
        <Route path="/auth/login" element={<Navigate to="/login" replace />} />
        <Route path="/behaviors" element={<DashboardLayout><BehaviorPage /></DashboardLayout>} />
        <Route path="/login" element={<Login />} />
        <Route path="/matches/:match_id" element={<Match />} />
        <Route path="/home" element={<Home />} />
        <Route path="/friendly/join" element={<JoinFriendly />} />
        <Route path="/amistosos/:room_id/sala" element={<DashboardLayout><FriendlyRoomPage /></DashboardLayout>} />
        <Route path="/partidos/:match_id" element={<Match />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
