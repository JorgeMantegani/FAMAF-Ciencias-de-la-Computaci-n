import {useState, useEffect} from 'react'
import { useNavigate, useParams} from 'react-router-dom'
import Editor from '@monaco-editor/react'
import { create_behavior, update_behavior, get_behavior } from '../api/behaviors.js'
import './behavior_editor_page.css'

const PLANTILLA_INICIAL = `# Presión alta
# Ejemplo inicial: adapta las decisiones de tu jugador.

def behavior(player):
    if player.tengo_pelota():
        objetivo = player.encontrar_arco_enemigo()
        player.patear_pelota(objetivo)
    else:
        pelota = player.encontrar_pelota()
        player.correr(pelota)

`

export default function BehaviorEditorPage() {
  const navigate = useNavigate()
  const { behavior_id } = useParams()
  const is_editing = Boolean(behavior_id)

  const [name, setName] = useState('')
  const [originalName, setOriginalName] = useState('') // Para verificar si el nombre ha cambiado
  const [code, setCode] = useState(PLANTILLA_INICIAL)
  const [originalCode, setOriginalCode] = useState(PLANTILLA_INICIAL) // Para verificar si el código ha cambiado

  const [error, setError] = useState(null)
  const [is_saving, set_is_saving] = useState(false)

  useEffect(() => {
    if (!is_editing) return
    
    async function loadData() {
      try {
        const data= await get_behavior(behavior_id)
        set_is_saving(true)
        setName(data.name)
        setOriginalName(data.name)
        setCode(data.code)
        setOriginalCode(data.code)
      } catch (error) {
        setError(error.message || "Error al cargar comportamiento")
      } finally {
        set_is_saving(false)
      }
    }
    loadData()
  }, [is_editing, behavior_id])

  // Personalizacion de los colores de editor
  const handleEditorWillMount = (monaco) => {
    monaco.editor.defineTheme('futbot-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [],
      colors: {
        'editor.background': '#112219', // Verde oscuro del fondo
        'editor.lineHighlightBackground': '#1a3326', // Que resalte de linea actual
      },
    })
  }

  const handle_save = async (e) => {
    e.preventDefault()
    setError(null)
    set_is_saving(true)

    const payload = { name, code }

    try {
      if (is_editing) {
        await update_behavior(behavior_id, payload)
      } else {
        await create_behavior(payload)
      }
      navigate('/behaviors')
    } catch (error) {
      setError(error.message || "Error al guardar comportamiento")
    } finally {
      set_is_saving(false)
    }
  }
  const has_changes = name !== originalName || code !== originalCode
  return (
    <div className="behavior-editor">
      <div className="behavior-editor__container">
        
        {/* HEADER */}
        <div className="behavior-editor__breadcrumb">
          <button 
          type="button"
          onClick={() => navigate('/behaviors')}
          className="behavior-editor__breadcrumb-link"
          >
            &larr; Laboratorio táctico
          </button>
        </div>

        <div className="behavior-editor__header">
          <div className="behavior-editor__header-title">
            <div className="behavior-editor__header-icon">
              {'<>'}
            </div>
            <div>
              <h1>{is_editing ? 'Editar comportamiento' : 'Crear comportamiento'}</h1>
              <p>Define la lógica de tu jugador y prepara una nueva estrategia para el campo.</p>
            </div>
          </div>
          <div className="behavior-editor__header-badge">
            LABORATORIO / PYTHON
          </div>
        </div>

        {/* CONTENIDO PRINCIPAL (GRILLA) */}
        <div className="behavior-editor__grid">
          
          {/* COLUMNA IZQUIERDA: Formulario y Editor */}
          <div className="behavior-editor__panel behavior-editor__main-panel">
            {error && (
              <div className="behavior-editor__error">
                {error}
              </div>
            )}

            <form id="behavior-form" onSubmit={handle_save} className="behavior-editor__form">
              <div className="behavior-editor__field">
                <label className="behavior-editor__label">
                  Nombre del comportamiento <span>*</span>
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="behavior-editor__input"
                  placeholder="Ej: Presión alta"
                />
                <p className="behavior-editor__field-hint">Usa un nombre que te ayude a identificar la estrategia.</p>
              </div>

              <div className="behavior-editor__form">
                <div className="behavior-editor__editor-header">
                  <label className="behavior-editor__label" style={{ marginBottom: 0 }}>
                    Código Python <span>*</span>
                  </label>
                  <span className="behavior-editor__editor-badge">PLANTILLA INICIAL</span>
                </div>
                
                {/* ENVOLTORIO DEL EDITOR */}
                <div className="behavior-editor__editor-wrapper">
                  <div className="behavior-editor__editor-topbar">
                    <span>📄 comportamiento.py</span>
                    <span>Python</span>
                  </div>
                  
                  <div className="behavior-editor__editor">
                    <Editor
                      height="100%"
                      language="python"
                      theme="futbot-dark"
                      value={code}
                      onChange={(val) => setCode(val || '')}
                      beforeMount={handleEditorWillMount}
                      options={{
                        minimap: { enabled: false },
                        fontSize: 14,
                        scrollBeyondLastLine: false,
                        padding: { top: 16 },
                      }}
                    />
                  </div>
                </div>
              </div>
            </form>
          </div>

          {/* COLUMNA DERECHA: Guía Rápida */}
          <div className="behavior-editor__panel behavior-editor__sidebar">
            <h3>📖 Guía rápida</h3>
            <p className="behavior-editor__sidebar-desc">
              Define el comportamiento de tu jugador usando la API segura de FutBot.
            </p>

            <div className="behavior-editor__sidebar-step">
              <h4>1. Define la función obligatoria</h4>
              <p>
                Tu código debe contener exactamente una función llamada{' '}
                <code>behavior(player)</code>, con un único parámetro.
              </p>
              <pre className="behavior-editor__code-example">
                {`def behavior(player):
                ...`}
              </pre>
            </div>
            
            <div className="behavior-editor__sidebar-step">
              <h4>2. Consulta el estado del juego</h4>
              <p>Podés consultar información mediante estos métodos:</p>
              <ul className="behavior-editor__api-list">
                <li><code>player.tengo_pelota()</code></li>
                <li><code>player.club_tiene_pelota()</code></li>
                <li><code>player.encontrar_pelota()</code></li>
                <li><code>player.encontrar_aliado()</code></li>
                <li><code>player.encontrar_enemigo()</code></li>
                <li><code>player.encontrar_arco_aliado()</code></li>
                <li><code>player.encontrar_arco_enemigo()</code></li>
                <li><code>player.encontrar_mis_coordenadas()</code></li>
              </ul>
            </div>
            
            <div className="behavior-editor__sidebar-step">
              <h4>3. Ejecuta una acción</h4>
              <p>
                Las acciones reciben una posición obtenida mediante uno de los métodos de consulta:
              </p>
              <ul className="behavior-editor__api-list">
                <li><code>player.pasar(destino)</code></li>
                <li><code>player.patear_pelota(destino)</code></li>
                <li><code>player.correr(destino)</code></li>
              </ul>
            </div>

            <div className="behavior-editor__sidebar-note">
              <span>RESTRICCIONES</span>
              <p>
                No se permiten imports ni funciones como{' '}
                <code>eval</code>, <code>exec</code>, <code>open</code>,
                <code>input</code> o <code>compile</code> 
              </p>
            </div>
          </div>
        </div>

        {/* BARRA INFERIOR */}
        <div className="behavior-editor__footer">
          <span className="behavior-editor__footer-text">Se guardará en tus comportamientos.</span>
          <div className="behavior-editor__actions">
            <button 
              type="button"
              onClick={() => navigate('/behaviors')}
              className="behavior-editor__button behavior-editor__button--secondary"
            >
              Cancelar
            </button>
            <button
              type="submit"
              form="behavior-form"
              disabled={ is_saving || !name.trim() || !code.trim() || (!has_changes && is_editing)} 
              className="behavior-editor__button"
            >
              {is_saving ? 'Guardando...' : is_editing ? 'Actualizar comportamiento' : '+ Crear comportamiento'}
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}
