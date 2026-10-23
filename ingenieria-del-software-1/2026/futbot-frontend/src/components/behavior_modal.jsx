import '../App.css'

export default function BehaviorModal({ behavior, onClose }) {
    // Si no hay comportamiento seleccionado no renderiza nada
    if (!behavior) return null;

    return (
        <div className="modal-overlay"
            onClick={onClose}
        >
            <div className="modal-content behavior-modal" role="dialog" aria-modal="true" aria-labelledby="behavior-modal-title"
                onClick={(event) => event.stopPropagation()}
            >
                <div className="modal-header">
                    <h2 id="behavior-modal-title">
                        {behavior.name}
                    </h2>
                </div>
                <pre className="behavior-code">
                    {behavior.code || 'Sin código'}
                </pre>
                <button className="home-action"
                    onClick={onClose}
                >
                    Cerrar
                </button>
            </div>
        </div>
    );
}