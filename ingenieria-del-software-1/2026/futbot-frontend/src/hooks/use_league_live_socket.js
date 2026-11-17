import { useEffect, useState, useRef, useCallback } from 'react';
import { read_session } from '../auth/session';

export function useLeagueLobbySocket(league_id, prop_token) {
    const [lobby_data, set_lobby_data] = useState(null);
    const [loading, set_loading] = useState(true);
    const [error, set_error] = useState(null);
    const [last_toast, set_last_toast] = useState(null);
    const ws_ref = useRef(null);
    const reconnect_timeout_ref = useRef(null);
    const toast_timeout_ref = useRef(null);
    const live_revision_ref = useRef(0);

    // Obtener y resolver el token de forma segura
    const resolve_token = useCallback(() => {
        if (prop_token) return prop_token;
        try {
            const session = read_session();
            if (!session) return null;
            if (typeof session === 'string') return session;
            return session.token || session.access_token || session.access || null;
        } catch (e) {
            console.error('Error leyendo sesión:', e);
            return null;
        }
    }, [prop_token]);

    // Obtener el club_id de la sesión actual
    const resolve_club_id = useCallback(() => {
        try {
            const session = read_session();
            return session?.club_id || null;
        } catch (e) {
            console.error('Error leyendo club_id:', e);
            return null;
        }
    }, []);

    // Fetch inicial HTTP con manejo robusto de autorización
    const fetch_lobby = useCallback(async (signal) => {
        const initial_revision = live_revision_ref.current;
        const token = resolve_token();
        if (!token) {
            set_error('No hay sesión activa o token de autenticación.');
            set_loading(false);
            return;
        }

        try {
            set_loading(true);
            const response = await fetch(`${import.meta.env.VITE_API_URL || ''}/api/leagues/${league_id}/live-lobby`, {
                signal,
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            if (!response.ok) {
                throw new Error(`Error al cargar el lobby (${response.status})`);
            }
            const data = await response.json();
            if (signal.aborted) return;
            // El WS mantiene el estado vivo; la plantilla privada procede del HTTP.
            if (initial_revision !== live_revision_ref.current) {
                if (Object.hasOwn(data, 'my_squad')) {
                    set_lobby_data(prev => ({ ...prev, my_squad: data.my_squad }));
                }
            } else {
                set_lobby_data(data);
            }
            set_error(null);
        } catch (err) {
            if (signal.aborted || initial_revision !== live_revision_ref.current) return;
            set_error(err.message);
        } finally {
            if (!signal.aborted) set_loading(false);
        }
    }, [league_id, resolve_token]);

    useEffect(() => {
        const controller = new AbortController();
        // Reiniciar la carga al cambiar de liga también valida una sesión ausente.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        fetch_lobby(controller.signal);
        return () => controller.abort();
    }, [fetch_lobby]);

    // Conexión WebSocket para tiempo real y reconexión automática
    useEffect(() => {
        const token = resolve_token();
        const club_id = resolve_club_id();
        if (!league_id || !token || !club_id) return;

        let is_connected = true;

        const connect_ws = () => {
            const ws_protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const raw_host = import.meta.env.VITE_WS_URL || import.meta.env.VITE_API_URL || window.location.hostname + ':8000';
            const ws_host = raw_host.replace(/^(w{1,2}s|https?):\/\//i, '').replace(/\/+$/, '');

            // Incluir tanto club_id como token en la URL para satisfacer la validación del backend
            const ws_url = `${ws_protocol}//${ws_host}/ws/league/${league_id}/active?club_id=${club_id}&token=${token}`;
            const ws = new WebSocket(ws_url);
            ws_ref.current = ws;

            ws.onmessage = (event) => {
                if (!is_connected || ws_ref.current !== ws) return;
                try {
                    const message = JSON.parse(event.data);
                    
                    if (message.type ==='league_lobby_update' || message.type === 'match_update' || message.type === 'league_update' || message.payload) {
                        // El backend emite snapshots planos; admitir también eventos envueltos.
                        const payload = message.payload ?? message;
                        // El broadcast no es personalizado: su my_squad no es el del usuario.
                        const live_data = { ...payload };
                        delete live_data.my_squad;
                        live_revision_ref.current += 1;
                        set_lobby_data(prev => ({ ...prev, ...live_data }));
                        set_loading(false);
                        set_error(null);

                        if (message.toast || payload.finished_match_summary) {
                            set_last_toast(message.toast || payload.finished_match_summary);
                            clearTimeout(toast_timeout_ref.current);
                            toast_timeout_ref.current = setTimeout(() => set_last_toast(null), 5000);
                        }
                    }
                } catch (e) {
                    console.error('Error procesando mensaje WS:', e);
                }
            };

            ws.onclose = (event) => {
                if (is_connected && event.code !== 1000) {
                    reconnect_timeout_ref.current = setTimeout(() => {
                        connect_ws();
                    }, 3000);
                }
            };

            ws.onerror = (err) => {
                console.error('Error en WebSocket de liga activa:', err);
                ws.close();
            };
        };

        connect_ws();

        return () => {
            is_connected = false;
            if (ws_ref.current) {
                ws_ref.current.close();
            }
            if (reconnect_timeout_ref.current) {
                clearTimeout(reconnect_timeout_ref.current);
            }
            clearTimeout(toast_timeout_ref.current);
        };
    }, [league_id, resolve_token, resolve_club_id]);

    return { lobby_data, loading, error, last_toast };
}
