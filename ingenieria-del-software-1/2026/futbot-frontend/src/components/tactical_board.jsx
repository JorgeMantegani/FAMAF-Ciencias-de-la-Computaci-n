// Positions are percentages of the pitch, measured on the reference design.
const PLAYERS = [
  { number: 8, x: 21.4, y: 49.3 },
  { number: 9, x: 78.4, y: 49.3 },
  { number: 10, x: 50, y: 63 },
  { number: 1, x: 50, y: 84, is_goalkeeper: true },
];

const METRICS = [
  { value: '4-3-3', label: 'Sistema' },
  { value: 'ALTA', label: 'Presión' },
  { value: '+12%', label: 'Rendimiento' },
];

const LINE = 'border-[#8fae96]/60';

function RobotIcon() {
  return (
    <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="4" y="8" width="16" height="12" rx="2" />
      <path d="M12 8V4M9 13v2M15 13v2M2 14h2M20 14h2" />
    </svg>
  );
}

function TacticalBoard() {
  return (
    <div
      data-testid="tactical-board"
      className="relative h-full min-h-[480px] bg-gradient-to-b from-[#20563a] to-[#123a23]"
    >
      {/* Pitch lines */}
      <div className={`absolute inset-x-[10%] top-[7%] bottom-[7%] border ${LINE}`}>
        <div className={`absolute inset-x-0 top-1/2 border-t ${LINE}`} />
        <div className={`absolute left-1/2 top-1/2 w-[23%] aspect-square -translate-x-1/2 -translate-y-1/2 rounded-full border ${LINE}`} />
        <div className="absolute left-1/2 top-1/2 w-2 h-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#8fae96]" />
        <div className={`absolute left-[26.5%] right-[26.5%] top-0 h-[13%] border border-t-0 ${LINE}`} />
        <div className={`absolute left-[26.5%] right-[26.5%] bottom-0 h-[13%] border border-b-0 ${LINE}`} />

        {PLAYERS.map(({ number, x, y, is_goalkeeper }) => (
          <span
            key={number}
            style={{ left: `${x}%`, top: `${y}%` }}
            className={`absolute -translate-x-1/2 -translate-y-1/2 w-11 h-11 rounded-full flex items-center justify-center font-plex-mono text-sm font-semibold shadow-lg ${
              is_goalkeeper
                ? 'bg-[#123a23] border-2 border-[#d8dccf] text-[#d8dccf]'
                : 'bg-[#b07a3e] border-[3px] border-[#7e522a] text-[#f3e3c8]'
            }`}
          >
            {number}
          </span>
        ))}
      </div>

      <div className="absolute left-[6.5%] right-[6.5%] top-[4.5%] rounded-xl bg-[#0b2a16]/85 px-6 py-5">
        <p className="flex items-center gap-2 text-[#e09a4b] font-plex-mono text-[11px] tracking-widest uppercase">
          <RobotIcon /> Estrategia asistida por FutBot
        </p>
        <h2 className="mt-2 font-plex-sans text-3xl font-bold text-[#e4e8dc]">Diseña la próxima jugada.</h2>
        <p className="mt-3 font-plex-mono text-xs text-[#a8b8a8]">
          Tu sistema, tu presión y cada decisión del equipo en un solo lugar.
        </p>
      </div>

      <dl className="absolute left-[8.5%] right-[8.5%] bottom-[4%] grid grid-cols-3 rounded-xl border border-[#2c5a3c] bg-[#0b2a16]/85 px-4 py-3">
        {METRICS.map(({ value, label }, index) => (
          <div key={label} className={`flex flex-col-reverse ${index > 0 ? 'border-l border-[#2c5a3c] pl-4' : ''}`}>
            <dt className="font-plex-mono text-[9px] tracking-widest uppercase text-[#7f957f]">{label}</dt>
            <dd className="font-plex-mono text-lg font-semibold text-[#d8dccf]">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export default TacticalBoard;
