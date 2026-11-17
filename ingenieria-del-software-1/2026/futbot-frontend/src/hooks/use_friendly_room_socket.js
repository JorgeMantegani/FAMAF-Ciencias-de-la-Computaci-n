import {useEffect, useState} from 'react'
import {connect_friendly_room_ws} from '../api/friendly_rooms'

function isValidRoom(room) {
  return (
    Boolean(room) &&
    typeof room === 'object' &&
    typeof room.roomId === 'string' &&
    typeof room.status === 'string' &&
    Boolean(room.homeClub)
  )
}

export function useFriendlyRoomSocket({room_id, club_id, onRoomUpdated}) {
  const [is_connected, set_is_connected] = useState(false)
  const [connection_error, set_connection_error] = useState(null)

  useEffect(() => {
    if (!room_id || !club_id) return
    let socket = null
    let is_cancelled = false

    try {
      socket = connect_friendly_room_ws(room_id, club_id)
      socket.onopen = () => {
      if (!is_cancelled) {
        set_is_connected(true)
        set_connection_error(null)
      }
    }
      socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data)
            if (data?.type === 'room_updated' && isValidRoom(data.room)) {
                onRoomUpdated(data.room)
            }
        } catch (error) {
            console.error('Error procesando el mensaje del WS de sala amistosa:', error)
        }
      }
      socket.onerror = (error) => {
        console.error('WS room error:', error)
        if (!is_cancelled) {
            set_connection_error(error)
        }
      }
      socket.onclose = () => {
        if (!is_cancelled) {
            set_is_connected(false)
            set_connection_error(true)
        }
      }
    } catch (error) {
        set_connection_error(true)
    }
    return () => {
      is_cancelled = true
      if (socket){
        socket.onopen = null
        socket.onmessage = null
        socket.onerror = null
        socket.onclose = null
        socket.close()
      }
    }
  }, [room_id, club_id, onRoomUpdated])

  return { is_connected, connection_error }
}
