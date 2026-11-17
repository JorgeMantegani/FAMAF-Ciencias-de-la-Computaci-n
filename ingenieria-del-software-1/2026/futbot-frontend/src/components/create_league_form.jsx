import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getMyPlayers, getMyBehaviors } from '../api/friendly';
import { validate_league } from './league_validation';
import SquadSelector from './SquadSelector';
import { createLeague } from '../api/leagues';
import MiniPitchViewer from './mini_pitch_viewer';

const INITIAL_FORM = {
  name: '',
  is_private: false,
  has_penalty_shootout: false,
  password: '',
  min_clubs: '',
  max_clubs: '',
  match_duration: '',
};

const INITIAL_SQUAD = {
  starters: [
    { playerId: '', behaviorId: '' },
    { playerId: '', behaviorId: '' },
    { playerId: '', behaviorId: '' },
  ],
  substitutes: [
    { playerId: '', behaviorId: '' },
    { playerId: '', behaviorId: '' },
    { playerId: '', behaviorId: '' },
  ],
};

const NUMERIC_FIELDS = ['min_clubs', 'max_clubs', 'match_duration'];

const SQUAD_ERROR_KEYS = [
  'starters',
  'substitutes',
  'playerIds',
  'duplicatePlayers',
  'behaviorIds',
];

// Clases de estilo para los elementos del formulario
const input_class =
  'w-full rounded-[5px] border border-[#2F5A36] bg-[#0F2416] px-3 py-2 text-sm text-white focus:border-[#C9973B] focus:outline-none';
const label_class =
  'mb-1 block font-mono text-xs uppercase tracking-wide text-[#C9D6C5]';
const error_class = 'mt-1 text-xs text-red-300';
const button_class =
  'flex h-10 min-w-[85px] items-center justify-center whitespace-nowrap rounded-[5px] px-3 text-xs font-semibold uppercase tracking-wide disabled:cursor-not-allowed disabled:opacity-50';

// Convierte el error del backend (string en 400, lista en 422) en un mensaje legible
function get_error_message(err) {
  const detail = err.detail || err.message;

  if (Array.isArray(detail)) {
    return detail
      .map((e) => `${e.loc ? e.loc.join('.') : 'campo'}: ${e.msg}`)
      .join(' | ');
  }

  return typeof detail === 'string' ? detail : 'No fue posible crear la liga.';
}

// Componente de formulario para crear una liga
export default function CreateLeagueForm({ onCancel }) {
  const navigate = useNavigate()
  const [form, setForm] = useState(INITIAL_FORM);
  const [squad, setSquad] = useState(INITIAL_SQUAD);
  const [players, setPlayers] = useState([]);
  const [behaviors, setBehaviors] = useState([]);
  const [touched, setTouched] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [server_error, setServer_error] = useState(null);
  const [created_league, setCreated_league] = useState(null);
  const [copied, setCopied] = useState(false);
  const [preview_selection, setPreview_selection] = useState(null);
  const errors = validate_league({ ...form, ...squad });

  // Carga los jugadores y comportamientos del club al montar el formulario
  useEffect(() => {
    let active = true;
    Promise.all([getMyPlayers(), getMyBehaviors()])
      .then(([players_data, behaviors_data]) => {
        if (!active) return;
        setPlayers(players_data);
        setBehaviors(behaviors_data);
      })
      .catch(() => {
        if (active) setServer_error('Error al cargar jugadores y comportamientos.');
      });
    return () => { active = false; };
  }, []);

  // Verifica que los 6 slots tengan jugador y comportamiento
  const is_squad_complete = () => {
    const is_slot_valid = (slot) => slot.playerId !== '' && slot.behaviorId !== '';
    return squad.starters.every(is_slot_valid) && squad.substitutes.every(is_slot_valid);
  };

  // Maneja el cambio de cualquier campo (texto, numérico o checkbox)
  const handle_change = (e) => {
    const { name, value, type, checked } = e.target;

    let new_value = type === 'checkbox' ? checked : value;
    if (NUMERIC_FIELDS.includes(name)) new_value = value.replace(/\D/g, '');

    setForm((prev) => ({
      ...prev,
      [name]: new_value,
      // Si deja de ser privada, se descarta la contraseña
      ...(name === 'is_private' && !checked ? { password: '' } : {}),
    }));
    setServer_error(null);
  };

  // Cuando el usuario sale de un campo, se marca como tocado
  const handle_blur = (e) => {
    const { name } = e.target;
    setTouched((prev) => ({ ...prev, [name]: true }));
  };

  // Un error se muestra si el campo fue tocado o si ya se intentó enviar
  const show_error = (key) => (touched[key] || submitted) && errors[key];

  // Valida, llama a createLeague y maneja los errores del servidor
  const handle_submit = async (e) => {
    e.preventDefault();
    setSubmitted(true);

    if (Object.keys(errors).length > 0 || submitting) return;

    setSubmitting(true);
    setServer_error(null);

    try {
      const league = await createLeague({ ...form, ...squad });
      setCreated_league(league);
    } catch (error) {
      setServer_error(get_error_message(error));
    } finally {
      setSubmitting(false);
    }
  };

  // Copia el código de la liga al portapapeles
  const handle_copy = async () => {
    try {
      await navigator.clipboard.writeText(created_league.code_to_join);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  //
  const handle_preview = async(slot) => {
    setServer_error(null);
    setPreview_selection({
      playerId: slot.playerId,
      behaviorId: slot.behaviorId,
    });
  };

  // Caso de éxito: informa que la liga fue creada y muestra el código para unirse
  if (created_league) {
    return (
      <div className="grid gap-3 text-white">
        <h3 className="text-lg font-semibold">¡Liga creada correctamente!</h3>
        <p className="text-sm">
          {created_league.is_private
            ? 'Compartí este código y la contraseña para que otros clubes se unan:'
            : 'Compartí este código para que otros clubes se unan:'}
        </p>
        <div className="flex items-center justify-between rounded-[5px] border border-[#2F5A36] bg-[#0F2416] px-3 py-2 font-mono">
          <span>{created_league.code_to_join}</span>
          <button
            type="button"
            onClick={handle_copy}
            className={`${button_class} border border-[#C9973B] text-[#C9973B]`}
          >
            {copied ? 'Copiado' : 'Copiar'}
          </button>
        </div>
        <button
          type="button"
          onClick={() => navigate(`/league/${created_league.id}/waiting`)}
          className={`${button_class} bg-[#C9973B] text-[#1A1A1A]`}
        >
          Ir al Lobby
        </button>
          
        <button
          type="button"
          onClick={onCancel}
          className={`${button_class} bg-[#C9973B] text-[#1A1A1A]`}
        >
          Cerrar
        </button>
      </div>
    );
  }

  return (
    <>
    {preview_selection && (
    <MiniPitchViewer
      player_id={preview_selection.playerId}
      behavior_id={preview_selection.behaviorId}
      onClose={() => setPreview_selection(null)}
    />
    )}
    <form onSubmit={handle_submit} className="grid grid-cols-2 gap-3">
      <div className="col-span-2">
        <label htmlFor="name" className={label_class}>Nombre de la liga</label>
        <input
          id="name"
          name="name"
          type="text"
          value={form.name}
          onChange={handle_change}
          onBlur={handle_blur}
          className={input_class}
        />
        {show_error('name') && <p role="alert" className={error_class}>{errors.name}</p>}
      </div>

      <div>
        <label htmlFor="min_clubs" className={label_class}>Mínimo de clubes</label>
        <input
          id="min_clubs"
          name="min_clubs"
          type="text"
          inputMode="numeric"
          value={form.min_clubs}
          onChange={handle_change}
          onBlur={handle_blur}
          className={input_class}
        />
        {show_error('min_clubs') && <p role="alert" className={error_class}>{errors.min_clubs}</p>}
      </div>

      <div>
        <label htmlFor="max_clubs" className={label_class}>Máximo de clubes</label>
        <input
          id="max_clubs"
          name="max_clubs"
          type="text"
          inputMode="numeric"
          value={form.max_clubs}
          onChange={handle_change}
          onBlur={handle_blur}
          className={input_class}
        />
        {show_error('max_clubs') && <p role="alert" className={error_class}>{errors.max_clubs}</p>}
      </div>

      <div className="col-span-2">
        <label htmlFor="match_duration" className={label_class}>Duración del partido</label>
        <input
          id="match_duration"
          name="match_duration"
          type="text"
          inputMode="numeric"
          value={form.match_duration}
          onChange={handle_change}
          onBlur={handle_blur}
          className={input_class}
        />
        {show_error('match_duration') && (
          <p role="alert" className={error_class}>{errors.match_duration}</p>
        )}
      </div>

      <div className="col-span-2">
        <label htmlFor="is_private" className={`${label_class} flex items-center gap-2`}>
          <input
            id="is_private"
            name="is_private"
            type="checkbox"
            checked={form.is_private}
            onChange={handle_change}
          />
          Liga privada
        </label>
      </div>

      <div className="col-span-2">
        <label htmlFor="has_penalty_shootout" className={`${label_class} flex items-center gap-2`}>
          <input
            id="has_penalty_shootout"
            name="has_penalty_shootout"
            type="checkbox"
            checked={form.has_penalty_shootout}
            onChange={handle_change}
          />
          Definición por penales (Sin empates)
        </label>
        <p className="text-xs text-[#C9D6C5]">
          En caso de empate se jugarán penales australianos. Ganar en tiempo regular
          otorga 3 puntos, ganar en penales otorga 2 puntos y perder 0 puntos
        </p>
      </div>

      {form.is_private && (
        <div className="col-span-2">
          <label htmlFor="password" className={label_class}>Contraseña</label>
          <input
            id="password"
            name="password"
            type="password"
            value={form.password}
            onChange={handle_change}
            onBlur={handle_blur}
            className={input_class}
          />
          {show_error('password') && <p role="alert" className={error_class}>{errors.password}</p>}
        </div>
      )}

      <div className="col-span-2">
        <SquadSelector
          players={players}
          behaviors={behaviors}
          squad={squad}
          setSquad={setSquad}
          onPreview={handle_preview}
        />
        {submitted &&
          SQUAD_ERROR_KEYS.map(
            (key) =>
              errors[key] && (
                <p key={key} role="alert" className={error_class}>{errors[key]}</p>
              )
          )}
      </div>

      {server_error && (
        <p role="alert" className={`col-span-2 ${error_class}`}>{server_error}</p>
      )}

      <div className="col-span-2 mt-2 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={submitting}
          className={`${button_class} border border-[#C9973B] text-[#C9973B] hover:bg-[#C9973B]/10`}
        >
          Cancelar
        </button>
        <button
          type="submit"
          disabled={submitting || !is_squad_complete()}
          className={`${button_class} bg-[#C9973B] text-[#1A1A1A] hover:bg-[#D9A94D]`}
        >
          {submitting ? 'Creando...' : 'Crear Liga'}
        </button>
      </div>
    </form>
    </>
  );
}