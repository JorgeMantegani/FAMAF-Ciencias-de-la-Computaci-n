import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { read_session } from '../auth/session';
import Modal from './modal';

export default function ActiveRoomsModal({ open, onClose }) {
  const navigate = useNavigate();
  const [rooms, set_rooms] = useState([]);
  const [loading, set_loading] = useState(true);
  const [error, set_error] = useState('');

  useEffect(() => {
    if (!open) return;
    
    set_loading(true);
    set_error('');
    set_rooms([]);

    const session = read_session();
    // Corregido: se lee access_token o token según la estructura guardada en localStorage
    const token = session?.access_token || session?.token;

    if (!session || !token) {
      set_error('No hay sesión activa.');
      set_loading(false);
      return;
    }

    const ws_base = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
    const ws_url = `${ws_base}/ws/rooms/active?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(ws_url);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (Array.isArray(data)) {
          set_rooms(data);
          set_loading(false);
        }
      } catch (err) {
        console.error('Error al parsear mensaje de salas activas:', err);
      }
    };

    ws.onerror = () => {
      set_error('Error de conexión con el servidor en tiempo real.');
      set_loading(false);
    };

    ws.onclose = (event) => {
      if (event.code !== 1000 && event.code !== 1005) {
        set_error('Se cerró la conexión con el servidor.');
      }
      set_loading(false);
    };

    return () => {
      ws.close();
    };
  }, [open]);

  if (!open) return null;

  function handle_select_room(room) {
    onClose();
    if (room.type === 'friendly') {
      navigate('/friendly/join', { state: { room_id: room.id, code: room.code } });
    } else {
      if (room.status === 'in_progress') {
        navigate(`/league/${room.id}/live`);
      } else {
        navigate(`/league/${room.id}/waiting`);
      }
    }
  }

  return (
    <Modal
      title="Salas Activas"
      description="Seleccioná una sala para regresar a tu lobby en curso."
      onClose={onClose}
    >
      <div className="space-y-4 py-2">
        {loading && <p className="text-sm text-gray-300">Cargando salas activas en tiempo real...</p>}
        {error && <p className="text-sm text-red-400 bg-red-900/50 p-2 rounded">{error}</p>}
        
        {!loading && !error && rooms.length === 0 && (
          <p className="text-sm text-gray-300 italic">No hay salas activas en este momento.</p>
        )}

        {!loading && !error && rooms.length > 0 && (
          <div className="flex flex-col gap-2 max-h-60 overflow-y-auto">
            {rooms.map((room) => {
              const is_friendly = room.type === 'friendly';
              const display_name = room.name || (is_friendly ? `Amistoso (${room.code || room.id.slice(0, 6)})` : `Liga #${room.id.slice(0, 6)}`);
              
              return (
                <div 
                  key={room.id}
                  className="flex items-center justify-between p-3 bg-[#0b2a16] border border-white/20 rounded-lg hover:border-[#bf9548] transition-colors"
                >
                  <div>
                    <p className="font-semibold text-white">{display_name}</p>
                    <p className="text-xs font-mono text-gray-300">
                      Tipo: <span className="uppercase text-[#bf9548]">{is_friendly ? 'Amistoso' : 'Liga'}</span> | Estado: {room.status}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handle_select_room(room)}
                    className="home-action text-xs py-1.5 px-3"
                  >
                    Reingresar
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Modal>
  );
}