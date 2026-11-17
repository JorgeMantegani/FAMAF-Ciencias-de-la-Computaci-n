import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { read_session } from '../auth/session.js'
import { get_behaviors, delete_behavior } from '../api/behaviors';
import BehaviorRow from '../components/behavior_row'
import BehaviorModal from '../components/behavior_modal'
import ConfirmModal from '../components/behavior_confirm_modal.jsx'

export default function BehaviorPage() {
    const navigate = useNavigate()
    const [status, set_status] = useState('loading')
    const [behavior_list, set_behavior_list] = useState([])
    const [selected_behavior, set_selected_behavior] = useState(null)
    const [error, set_error] = useState(null)

    // Estados para la funcionalidad de borrado
    const [behavior_to_delete, set_behavior_to_delete] = useState(null)
    const [is_deleting, set_is_deleting] = useState(null)
    const [delete_error, set_delete_error] = useState(null)
    const [global_alert, set_global_alert] = useState(null)

    useEffect(() => {
        
        const fetch_behaviors = async () => {
            // Verifica si se logueó el usuario 
            const session = read_session()
            if (!session) {
                navigate('/login', { replace: true })
                return
            }
            
            try {
                // Hace la petición para obtener los comportamientos
                const behaviors = await get_behaviors()
                set_behavior_list(behaviors)
                set_status('ready')
            } catch (error) {
                // EL manejo del error 401 lo hace client.js 
                console.error('Error en la petición:', error)
                set_error('Error al obtener los comportamientos. Por favor, inténtalo de nuevo.')
                set_status('error')
            }
        }
        fetch_behaviors()
    }, [navigate])
    
    const handle_confirm_delete = async () => {
        if (!behavior_to_delete) return

        set_is_deleting(true)
        set_delete_error(null)

        try {
            await delete_behavior(behavior_to_delete.id)

            set_behavior_list(prev => prev.filter(b => b.id !== behavior_to_delete.id))
            set_behavior_to_delete(null)
        } catch (err) {
            console.error('Error al eliminar comportamiento:', err)

            if (err.status === 409 || (err.message && err.message.includes('plantilla'))) {
                set_delete_error('No se puede eliminar un comportamiento asignado en alguna plantilla: primero hay que reemplazarlo')
            } else {
                set_delete_error('Ocurrio un error al intentar eliminar el comportamiento.')
            }
        } finally {
            set_is_deleting(false)
        }
    }

    return (
        <div className="flex flex-col w-full max-w-5xl mx-auto pt-6 text-white">
        
            <button
                type="button"
                className="home-action mb-4 self-start"
                onClick={() => navigate('/home')}
            >
            ← Volver al menú
            </button>
            {/* Cargando */}
            {status === 'loading' && (
                <div className="flex flex-col items-center gap-4">
                    <div className="w-12 h-12 border-4 border-green-900 border-t-[#f0a95b] rounded-full animate-spin"></div>
                    <p className="text-gray-400 font-mono text-sm tracking-widest">CARGANDO TÁCTICAS...</p>
                </div>
            )}

            {/* Error 500 */}
            {status === 'error' && (
                <div className="bg-red-900/30 border border-red-800 p-6 rounded-md text-center max-w-md">
                    <p className="text-red-400 font-mono mb-4">{error}</p>
                    <button onClick={() => window.location.reload()} className="bg-red-900/50 hover:bg-red-800 text-white px-4 py-2 rounded">
                        Reintentar
                    </button>
                </div>
            )}

            {/* Listo */}
            {status === 'ready' && (
                <div className="bg-[#0c1610] border border-green-900/30 rounded-lg shadow-2xl w-full overflow-hidden">
                    
                    {/* Encabezado */}
                    <div className="bg-[#172c1f]/50 p-6 border-b border-green-900/50">
                        <h1 className="text-2xl font-bold mb-2">Comportamientos</h1>
                        <p className="text-gray-400 font-mono text-xs">Gestiona la lógica y las primitivas de tus futbolistas.</p>
                    </div>
                    {/* Encabezado de tabla */}
                    <div className="flex px-6 py-2 bg-[#112419] border-b border-green-900/50 text-xs font-mono text-green-500 tracking-widest">
                        {/* flex-1 hace que NOMBRE ocupe todo el espacio disponible a la izquierda */}
                        <span className="flex-1">NOMBRE</span>
                        {/* w-[340px] reserva el espacio exacto para la columna derecha */}
                        <span className="w-[340px] pl-2">TIPO</span>
                    </div>

                    {/* Lista de comportamientos */}
                    <div className="flex flex-col">
                        {behavior_list.map((behavior_element) => {
                            return (
                                <BehaviorRow 
                                    key={behavior_element.id}
                                    name={behavior_element.name} 
                                    code={behavior_element.code}
                                    isDefault={behavior_element.isDefault}
                                    onDetails={() => set_selected_behavior(behavior_element)}
                                    onDelete={() => {
                                        set_delete_error(null)
                                        set_behavior_to_delete(behavior_element)
                                    }}
                                    onEdit={() => navigate(`/behaviors/edit/${behavior_element.id}`)}
                                />
                            )
                        })}
                        {/* Model de detalles */}
                        <BehaviorModal
                            behavior={selected_behavior}
                            onClose={() => set_selected_behavior(null)}
                        />

                        {/* Modal de confirmacion de eliminacion */}
                        <ConfirmModal
                            isOpen={!!behavior_to_delete}
                            title="Eliminar comportamiento"
                            message={`¿Estás seguro de que deseas eliminar el comportamiento "${behavior_to_delete?.name}"? Esta acción no se puede deshacer.`}
                            onConfirm={handle_confirm_delete}
                            onClose={() => {
                                set_behavior_to_delete(null)
                                set_delete_error(null)
                            }}
                            isDeleting={is_deleting}
                            error={delete_error}
                        />
                    </div>
                </div>
            )}
        </div>
    )
}