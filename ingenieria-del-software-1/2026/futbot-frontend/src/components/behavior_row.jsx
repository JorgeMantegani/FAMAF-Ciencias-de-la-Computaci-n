
function BehaviorRow({ name, code, isDefault, onDetails }) {
    return (
        <div className="flex items-center px-6 py-4 border-b border-green-900/30 hover:bg-[#112419]/50 transition-colors">
            
            {/* Nombre y Código */}
            <div className="flex-1 flex flex-col gap-1 pr-4 min-w-0">
                <h3 className="text-white font-bold text-sm truncate">{name}</h3>
                <p className="text-gray-400 text-xs font-mono truncate">
                    {code || "Sin código"}
                </p>
            </div>

            {/* Tipo (Preprogramado/propio), Botón */}
            <div className="w-[340px] flex items-center justify-between gap-3">
                {/* Tipo */}
                <div className="flex items-center gap-2 border border-green-800/50 bg-[#0c1610] px-3 py-1 rounded-full text-xs text-gray-300 w-36 shrink-0">
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${isDefault ? 'bg-[#f0a95b]' : 'bg-blue-500'}`}></span>
                    <span className="truncate">{isDefault ? 'Preprogramado' : 'Propio'}</span>
                </div>
                {/* Botón  */}
                <button 
                    className="border border-green-700 text-green-500 hover:text-[#f0a95b] hover:border-[#f0a95b] px-3 py-1 rounded-md text-xs font-mono transition-colors whitespace-nowrap shrink-0"
                    onClick={onDetails}
                >
                    Ver detalles
                </button>
              
            </div>
        </div>
    );
}

export default BehaviorRow;