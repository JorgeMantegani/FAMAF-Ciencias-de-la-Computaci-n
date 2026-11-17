
function BehaviorRow({ name, code, isDefault, onDetails, onEdit, onDelete }) {
    return (
        <div className="flex items-center px-6 py-4 border-b border-green-900/30 hover:bg-[#112419]/50 transition-colors">
            
            {/* Nombre y Código */}
            <div className="flex-1 flex flex-col gap-1 pr-4 min-w-0">
                <h3 className="text-white font-bold text-sm truncate">{name}</h3>
                <p className="text-gray-400 text-xs font-mono truncate">
                    {code || "Sin código"}
                </p>
            </div>

            {/* Tipo y Botones de acción con ancho expandido para evitar desbordes */}
            <div className="w-[390px] flex items-center justify-between gap-2 shrink-0">
                {/* Tipo */}
                <div className="flex items-center gap-2 border border-green-800/50 bg-[#0c1610] px-3 py-1 rounded-full text-xs text-gray-300 w-32 shrink-0">
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${isDefault ? 'bg-[#f0a95b]' : 'bg-blue-500'}`}></span>
                    <span className="truncate">{isDefault ? 'Preprogramado' : 'Propio'}</span>
                </div>

                {/* Grupo de Botones */}
                <div className="flex items-center gap-1.5">
                    <button 
                        className="border border-green-700 text-green-500 hover:text-[#f0a95b] hover:border-[#f0a95b] px-2.5 py-1 rounded-md text-xs font-mono transition-colors whitespace-nowrap shrink-0"
                        onClick={onDetails}
                    >
                        Ver detalles
                    </button>

                    {!isDefault && (
                        <>
                            <button 
                                type="button"
                                onClick={onEdit}
                                className="border border-green-700 text-green-500 hover:text-[#f0a95b] hover:border-[#f0a95b] px-2.5 py-1 rounded-md text-xs font-mono transition-colors whitespace-nowrap shrink-0"
                            >
                                Editar
                            </button>

                            <button
                                className="border border-red-800/80 text-red-400 hover:bg-red-900/40 px-2.5 py-1 rounded-md text-xs font-mono transition-colors whitespace-nowrap shrink-0"
                                onClick={onDelete}
                            >
                                Eliminar
                            </button>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

export default BehaviorRow;