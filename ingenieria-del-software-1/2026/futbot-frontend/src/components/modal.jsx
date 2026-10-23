import { useEffect } from 'react';
import './modal.css';

// Contenedor genérico de modal: se cierra con la tecla Escape
export default function Modal({ title, description, onClose, children }) {
  useEffect(() => {
    const on_key_down = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    // Agregamos un listener para cerrar el modal con la tecla Escape
    document.addEventListener('keydown', on_key_down);
    return () => document.removeEventListener('keydown', on_key_down);
  }, [onClose]);
// Renderizamos el modal
  return (
    <div className="app-modal-overlay">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="app-modal-dialog"
      >
        <h2 className="text-2xl font-bold">{title}</h2>
        {description && (
          <p className="mb-5 mt-1 font-mono text-xs text-[#C9D6C5]">{description}</p>
        )}
        {children}
      </div>
    </div>
  );
}