import { useEffect, useRef, useState } from 'react'
import './join_friendly_modal.css'

const UUID_FORMAT = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i  // formato del ID de sala
const CODE_FORMAT = /^[A-Z0-9]{6}$/                                                    // código de 6 letras/números

export default function JoinFriendlyModal({ open, on_close, on_submit }) {
  const dialog_ref = useRef(null)          // referencia al <dialog> para abrirlo y cerrarlo
  const [room_id, set_room_id] = useState('')
  const [code, set_code] = useState('')
  const [error, set_error] = useState('')

  useEffect(() => {
    const dialog = dialog_ref.current
    if (open && !dialog.open) {
      set_room_id('')                      // cada vez que se abre, arranca con los campos vacíos
      set_code('')
      set_error('')
      dialog.showModal()                   // abre la ventana en modo modal
    }
    if (!open && dialog.open) dialog.close()
  }, [open])

  function submit(event) {
    event.preventDefault()                 // evita que el navegador recargue la página
    const clean_id = room_id.trim()
    const clean_code = code.trim().toUpperCase()   // el backend compara en mayúsculas
    if (!UUID_FORMAT.test(clean_id)) {
      set_error('El ID de la sala no tiene un formato válido.')
      return
    }
    if (!CODE_FORMAT.test(clean_code)) {
      set_error('El código debe tener 6 caracteres (letras y números).')
      return
    }
    on_submit({ room_id: clean_id, code: clean_code })
  }

  return (
    <dialog
      ref={dialog_ref}
      className="join-modal"
      onClose={on_close}                                               // se dispara también con Escape
      onClick={(event) => { if (event.target === dialog_ref.current) on_close() }}   // clic en el fondo oscuro
    >
      <form onSubmit={submit}>
        <h2>Unirse a un amistoso</h2>

        <label htmlFor="join-room-id">ID de la sala</label>
        <input
          id="join-room-id"
          value={room_id}
          onChange={(event) => set_room_id(event.target.value)}
          placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
          autoComplete="off"
        />

        <label htmlFor="join-code">Código de la sala</label>
        <input
          id="join-code"
          value={code}
          onChange={(event) => set_code(event.target.value.toUpperCase())}
          placeholder="ABC123"
          maxLength={6}
          autoComplete="off"
        />

        {error && <p className="join-modal-error" role="alert">{error}</p>}

        <div className="join-modal-actions">
          <button type="button" className="home-action" onClick={on_close}>Cancelar</button>
          <button type="submit" className="home-action">Continuar</button>
        </div>
      </form>
    </dialog>
  )
}