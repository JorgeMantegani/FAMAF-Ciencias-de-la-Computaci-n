import { useEffect, useRef, useState } from "react";
import { read_session } from "../auth/session";

export function use_league_waiting_socket(league_id, club_id){
    const [room_info, set_room_info] = useState(null);
    const [error, set_error] = useState(null);
    const [redirect_url, set_redirect_url] = useState(null);
    const [cancel_notice, set_cancel_notice] = useState(null);
    const socket_ref = useRef(null);

    useEffect(() =>{
        if (!league_id || !club_id) return;

        const session = read_session();
        const token = session?.token || session?.access_token || '';

        const ws_protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const raw_host = import.meta.env.VITE_WS_URL || import.meta.env.VITE_API_URL || window.location.hostname + ':8000';
        const ws_host = raw_host.replace(/^(w{1,2}s|https?):\/\//i, '').replace(/\/+$/, '');

        const ws_url = `${ws_protocol}//${ws_host}/ws/league/${league_id}/waiting?club_id=${club_id}&token=${token}`;
        
        const ws = new WebSocket(ws_url);
        socket_ref.current = ws;

        ws.onmessage = (event) => {
            try{
                const data = JSON.parse(event.data);
                console.log("WebSocket recibido:", data);

                if(data.type === 'room_info') {
                    set_room_info(data);
                } else if (data.type === 'club_joined_waiting') {
                    set_room_info((prev) => {
                        if (!prev) return prev;
                        const inscribed = prev.inscribed_clubs || [];
                        const updated_clubs = inscribed.includes(data.club_id)
                            ? inscribed
                            : [...inscribed, data.club_id];
                        
                        return {
                            ...prev,
                            current_participants: data.current_participants ?? updated_clubs.length,
                            inscribed_clubs: updated_clubs,
                            can_start: (data.current_participants ?? updated_clubs.length) >= prev.min_clubs
                        };
                    });
                } else if (data.type === 'club_left_waiting') {
                    set_room_info((prev) => {
                        if (!prev) return prev;
                        const updated_clubs = (prev.inscribed_clubs || []).filter(id => id !== data.club_id);
                        return{
                            ...prev,
                            current_participants: data.current_participants ?? updated_clubs.length,
                            inscribed_clubs: updated_clubs,
                            can_start: (data.current_participants ?? updated_clubs.length) >= prev.min_clubs
                        };
                    });
                } else if (data.type === 'league_started') {
                    set_redirect_url(data.redirect_url);
                } else if (data.type === 'league_cancelled') {
                    set_cancel_notice("La liga ha sido cancelada por el creador. Redirigiendo...")
                    setTimeout(() => {
                        set_redirect_url(data.redirect_url);
                    }, 2000);
                } else if (data.type === 'error') {
                    set_error(data.message);
                }
            } catch (err) {
                console.error('Error al procesar mensaje de WS:', err);
            }
        };
        
        ws.onerror = () => {
            set_error('Error en la conexion con el servidor.');
        };

        ws.onclose = (event) => {
            if (event.code !== 1000) {
                set_error('La conexion con el servidor se ha cerrado inesperadamente.');
            }
        };

        return () => {
            if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
                ws.close();
            }
        };
    }, [league_id, club_id]);

    const send_action = (action) => {
        if (socket_ref.current && socket_ref.current.readyState === WebSocket.OPEN) {
            socket_ref.current.send(JSON.stringify({ action }));
        }
    };

    return { room_info, error, redirect_url, send_action};
}