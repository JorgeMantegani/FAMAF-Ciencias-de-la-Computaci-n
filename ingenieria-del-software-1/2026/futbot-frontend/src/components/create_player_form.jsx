import { useState } from 'react';
import { validate_player } from './player_validation';
import { createPlayer } from '../api/players';

const INITIAL_FORM = {
  name: '',
  power: '',
  agility: '',
  control: '',
  speed: '',
  strength: '',
};

const ATTRIBUTES = [
  { key: 'power', label: 'Power' },
  { key: 'agility', label: 'Agility' },
  { key: 'control', label: 'Control' },
  { key: 'speed', label: 'Speed' },
  { key: 'strength', label: 'Strength' },
];

// Componente de formulario para crear un jugador
export default function CreatePlayerForm({ onSuccess, onCancel }) {
  const [form, setForm] = useState(INITIAL_FORM);
  const [touched, setTouched] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [server_error, setServer_error] = useState(null);

  const { errors } = validate_player(form);

  // Maneja el cambio de los campos del formulario
  const handle_change = (e) => {
    const { name, value } = e.target;

    // En los atributos se descarta todo lo que no sea un dígito
    const newValue = name === 'name' ? value : value.replace(/\D/g, '');

    setForm((prev) => ({ ...prev, [name]: newValue }));
    setServer_error(null);
  };

  // Cuando el usuario sale de un campo, guardamos que ese campo ya fue tocado
  const handle_blur = (e) => {
    const { name } = e.target;
    setTouched((prev) => ({ ...prev, [name]: true }));
  };

  // Maneja el envío del formulario, llama a createPlayer y maneja los errores del servidor
  const handle_submit = async (e) => {
    e.preventDefault();

    // No enviar si hay errores o ya hay un envío en curso
    if (Object.keys(errors).length > 0 || submitting) return;

    setSubmitting(true);
    setServer_error(null);

    try {
      await createPlayer(form);
      onSuccess?.();
    } catch (error) {
      setServer_error(error.message);
    } finally {
      setSubmitting(false);
    }
  };

  // Se calcula la suma de los atributos para mostrarla en el formulario
  const sum = ATTRIBUTES.reduce((total, attr) => {
    const value = form[attr.key];

    if (value !== '') {
      return total + Number(value);
    }

    return total;
  }, 0);

  // Clases de estilo para los elementos del formulario
  const input_class =
    'w-full rounded-[5px] border border-[#2F5A36] bg-[#0F2416] px-3 py-2 text-sm text-white focus:border-[#C9973B] focus:outline-none';
  const label_class =
    'mb-1 block font-mono text-xs uppercase tracking-wide text-[#C9D6C5]';
  const error_class = 'mt-1 text-xs text-red-300';
  const button_class =
    'flex h-10 min-w-[85px] items-center justify-center whitespace-nowrap rounded-[5px] px-3 text-xs font-semibold uppercase tracking-wide disabled:cursor-not-allowed disabled:opacity-50';

  // Renderizamos el formulario con los campos de nombre y atributos, mostrando errores y la suma de los atributos
  return (
    <form onSubmit={handle_submit} className="grid grid-cols-2 gap-3">
      <div className="col-span-2">
        <label htmlFor="name" className={label_class}>Nombre</label>
        <input
          id="name"
          name="name"
          type="text"
          value={form.name}
          onChange={handle_change}
          onBlur={handle_blur}
          className={input_class}
        />
        {touched.name && errors.name && (
          <p role="alert" className={error_class}>{errors.name}</p>
        )}
      </div>

      {/* Renderizamos los cinco atributos usando un map sobre el array ATTRIBUTES */}
      {ATTRIBUTES.map((attr) => (
        <div key={attr.key}>
          <label htmlFor={attr.key} className={label_class}>{attr.label}</label>
          <input
            id={attr.key}
            name={attr.key}
            type="text"
            inputMode="numeric"
            value={form[attr.key]}
            onChange={handle_change}
            onBlur={handle_blur}
            className={input_class}
          />

          {/* Mostramos el error del atributo solo si el campo fue tocado y hay un error */}
          {touched[attr.key] && errors[attr.key] && (
            <p role="alert" className={error_class}>{errors[attr.key]}</p>
          )}
        </div>
      ))}

      {/* Mostramos la suma de los atributos y cambiamos el color según si es 300 o no */}
      <div className="col-span-2 flex items-center justify-between rounded-[5px] border border-[#2F5A36] bg-[#0F2416] px-3 py-2 font-mono text-xs">
        <span className="uppercase text-[#C9D6C5]">Puntos</span>
        <p className={sum === 300 ? 'text-green-400' : 'text-[#C9973B]'}>
          Suma: {sum} / 300
        </p>
      </div>

      {errors.sum && (
        <p role="alert" className={`col-span-2 ${error_class}`}>{errors.sum}</p>
      )}

      {server_error && (
        <p role="alert" className={`col-span-2 ${error_class}`}>{server_error}</p>
      )}

      {/* Renderizamos los botones de cancelar y crear, deshabilitando el botón de crear si hay errores o se está enviando el formulario */}
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
          disabled={Object.keys(errors).length > 0 || submitting}
          className={`${button_class} bg-[#C9973B] text-[#1A1A1A] hover:bg-[#D9A94D]`}
        >
          {submitting ? 'Creando...' : 'Crear'}
        </button>
      </div>
    </form>
  );
}