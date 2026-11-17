import {useEffect, useState} from 'react'
import {connect_to_simulation_ticket, create_simulation_ticket} from '../api/behaviors.js'


export const useBehaviorSimulation = (player_id, behavior_id) => {
  const [simulationData, setSimulationData] = useState(null)
  const [connectionStatus, setConnectionStatus] = useState('connecting') // 'connecting', 'online', 'offline'
  const [error, setError] = useState(null)
  
  useEffect(() => {
    // Si no hay ticketId no se conecta
    if (!player_id || !behavior_id) {
      setConnectionStatus('offline')
      return 
    }
    // uso active para evitar actualizar el estado si el componente se desmonta antes de recibir datos
    let active = true
    let socket = null
    async function start_simulation() {
      try {
        setConnectionStatus('connecting')
        setSimulationData(null)
        setError(null)
        const response = await create_simulation_ticket(player_id, behavior_id)
        if (!active) return
        socket = connect_to_simulation_ticket(response.ticket)
        socket.onopen = () => {
          if (active) setConnectionStatus('online')
        }
        // Escucha los mensajes
        socket.onmessage = (event) => {
          if (!active) return
          const data = JSON.parse(event.data)
          if (data.type === 'tick') {
            // Guarda los datos de la simulación en el estado
            setSimulationData(data)
            return
          }
          if (data.type === 'error') {
            setError(data.message || 'Error desconocido en la simulación')
            return
          }
        }
        socket.onerror = (event) => {
          console.error('WebSocket error:', event)
          if (active) setConnectionStatus('offline')
        }
        // al cerrar la conexión, cambia el estado a offline
        socket.onclose = () => {
          if (active) setConnectionStatus('offline')
        }

      } catch (error) {
        console.error('Error starting simulation:', error)
        if (active) {
          setError(error)
          setConnectionStatus('offline')
        }
      }
    }
    start_simulation()
    return () => {
      active = false
      // Verificamos que socket exista y que socket.close sea realmente una función
      if (socket && typeof socket.close === 'function') {
        // 0 = CONNECTING, 1 = OPEN (Estándar W3C WebSocket)
        if (socket.readyState === 0 || socket.readyState === 1) {
          socket.close()
        }
      }
    }
  }, [player_id, behavior_id])
  return {simulationData, connectionStatus, error}
}
