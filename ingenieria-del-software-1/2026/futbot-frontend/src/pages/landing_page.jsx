import { Link, Navigate } from 'react-router-dom';
import { read_session } from '../auth/session';
import TacticalBoard from '../components/tactical_board';

const ICON_PROPS = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
};

function LoginIcon() {
  return (
    <svg {...ICON_PROPS} className="w-4 h-4">
      <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3" />
    </svg>
  );
}

function UserPlusIcon() {
  return (
    <svg {...ICON_PROPS} className="w-4 h-4">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M19 8v6M22 11h-6" />
      <circle cx="9" cy="7" r="4" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg {...ICON_PROPS} className="w-6 h-6 ml-auto">
      <path d="M5 12h14M13 5l7 7-7 7" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg {...ICON_PROPS} className="w-3.5 h-3.5 text-[#7fae7f]">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  );
}

const ENTRY_LINK = 'mt-auto h-[54px] px-5 flex items-center gap-3 rounded font-plex-mono text-sm font-bold tracking-wider uppercase transition-colors';

function LandingPage() {
  if (read_session()) {
    return <Navigate to="/home" replace />;
  }

  return (
    <div className="mt-3 flex-1 flex flex-row w-full rounded-2xl overflow-hidden shadow-2xl border border-[#123a23]">

      {/* Welcome */}
      <section className="w-[52%] bg-[#0c2615] px-14 py-10 flex flex-col">
        <p className="flex items-center gap-3 text-[#e09a4b] font-plex-mono text-[11px] tracking-widest uppercase">
          <span className="w-7 border-t-2 border-[#e09a4b]" aria-hidden="true" />
          El club táctico de FutBot
        </p>
        <h1 className="mt-5 font-plex-sans text-5xl font-bold leading-[1.15] text-white">
          Toma el mando. El partido empieza aquí.
        </h1>
        <p className="mt-6 max-w-lg font-plex-mono text-sm leading-relaxed text-[#b5c2b3]">
          Prepara formaciones, programa cada movimiento y dirige tu equipo desde un vestuario hecho para estrategas.
        </p>

        <div className="mt-auto pt-8">
          <p className="font-plex-mono text-[11px] tracking-widest uppercase text-[#d8dccf]">
            Elige cómo entrar al terreno de juego
          </p>
          <div className="mt-5 grid grid-cols-2 gap-4">
            <div className="flex flex-col">
              <p className="mb-3 font-plex-mono text-[11px] text-[#a8b8a8]">¿Ya tienes club? Retoma tu estrategia.</p>
              <Link to="/login" className={`${ENTRY_LINK} bg-[#e09a4b] text-[#0c2615] hover:bg-[#eaa95e]`}>
                <LoginIcon /> Iniciar sesión <ArrowIcon />
              </Link>
            </div>
            <div className="flex flex-col">
              <p className="mb-3 font-plex-mono text-[11px] text-[#a8b8a8]">¿Nuevo fichaje? Crea tu vestuario.</p>
              <Link to="/register" className={`${ENTRY_LINK} border border-[#e09a4b] text-white hover:bg-[#e09a4b]/10`}>
                <UserPlusIcon /> Crear cuenta <ArrowIcon />
              </Link>
            </div>
          </div>
        </div>

        <footer className="mt-10 pt-5 border-t border-[#1f3d29] flex justify-between gap-4 font-plex-mono text-[10px] tracking-wider uppercase text-[#8a9a8a]">
          <span className="flex items-center gap-2"><ShieldIcon /> Conexión cifrada · Datos protegidos</span>
          <span>Temporada 04 / 2026</span>
        </footer>
      </section>

      {/* Tactical board */}
      <section className="w-[48%]">
        <TacticalBoard />
      </section>
    </div>
  );
}

export default LandingPage;
