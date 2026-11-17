import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'
import Login from './pages/Login'
import ForgotPasswordPage from './pages/forgot_password_page'
import ResetPasswordPage from './pages/reset_password_page'
import CheckEmailPage from './pages/check_email_page'
import VerifyEmailPage from './pages/verify_email_page'
import Home from './pages/Home'
import Match from './pages/Match'
import RegisterPage from './pages/register_page'
import LandingPage from './pages/landing_page'
import BehaviorPage from './pages/behavior_page'
import FriendlyRoomPage from './pages/friendly_room_page'
import './styles/tokens.css'
import './App.css'
import JoinFriendly from './pages/join_friendly'
import JoinLeaguePage from './pages/join_league_page'
import LeagueWaitingRoom from './pages/league_waiting_room'
import LeaguesPage from './pages/leagues_page'
import BehaviorEditorPage from './pages/behavior_editor_page'
import OngoingLeagueLobbyView from './pages/league_active_room'
import FriendlyListPage from './pages/friendly_list_page'
import RankingPage from './pages/ranking_page'


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
    <Link to="/ranking" className="text-[#ffe28a] underline">Ranking de clubes</Link>
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
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/check-email" element={<CheckEmailPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/register" element={<Registration />} />
        <Route path="/auth/register" element={<Navigate to="/register" replace />} />
        <Route path="/auth/login" element={<Navigate to="/login" replace />} />
        <Route path="/behaviors" element={<DashboardLayout><BehaviorPage /></DashboardLayout>} />
        <Route path="/behaviors/create" element={<DashboardLayout><BehaviorEditorPage /></DashboardLayout>} />
        <Route path="/behaviors/edit/:behavior_id" element={<DashboardLayout><BehaviorEditorPage /></DashboardLayout>} />
        <Route path="/login" element={<Login />} />
        <Route path="/matches/:match_id" element={<Match />} />
        <Route path="/home" element={<Home />} />
        <Route path="/ranking" element={<DashboardLayout><RankingPage /></DashboardLayout>} />
        <Route path="/friendly/join" element={<JoinFriendly />} />
        <Route path="/friendly" element={<FriendlyListPage />} />
        <Route path="/ligas/:league_id/unirse" element={<JoinLeaguePage />} />
        <Route path="/amistosos/:room_id/sala" element={<DashboardLayout><FriendlyRoomPage /></DashboardLayout>} />
        <Route path="/partidos/:match_id" element={<Match />} />
        <Route path="/league/:league_id/waiting" element={<LeagueWaitingRoom />}/>
        <Route path="/league/:league_id/live" element={<DashboardLayout><OngoingLeagueLobbyView /></DashboardLayout>} />
        <Route path="/leagues" element={<LeaguesPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
