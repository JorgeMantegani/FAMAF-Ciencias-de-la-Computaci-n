import '../App.css'

export default function ConfirmModal({
    isOpen,
    title,
    message,
    onConfirm,
    onClose,
    isDeleting,
    error    
}) {
    if (!isOpen) return null

    return(
        <div className="modal-overlay" onClick={onClose}>
            <div
                className="modal-content behavior-modal"
                role="dialog"
                aria-modal="true"
                onClick={(e) => e.stopPropagation()}
                >
                    <div className="modal-header">
                        <h2 className="text-lg font-bold text-white">{title}</h2>
                    </div>

                    <p className="text-gray-300 text-sm my-4 font-mono">{message}</p>

                    {error && (
                        <div className="bg-red-900/40 border-red-700 p-3 rounded mb-4 text-red-300 text-xs font-mono">
                            {error}
                        </div>
                    )}
                    
                    <div className="flex justify-end gap-3 mt-6">
                        <button 
                            type="button"
                            className="border border-gray-600 text-gray-300 px-4 py-2 rounded text-xs font-mono hover:bg-gray-800 transition-colors"
                            onClick={onClose}
                            disabled={isDeleting}
                        >
                            Cancelar
                        </button>
                        <button 
                            type="button"
                            className="bg-red-900/80 hover:bg-red-800 text-white px-4 py-2 rounded text-xs font-mono transition-colors disabled:opacity-50"
                            onClick={onConfirm}
                            disabled={isDeleting}
                        >
                            {isDeleting ? 'Eliminando...' : 'Eliminar'}
                        </button>
                    </div>
                </div>
        </div>
    )
}