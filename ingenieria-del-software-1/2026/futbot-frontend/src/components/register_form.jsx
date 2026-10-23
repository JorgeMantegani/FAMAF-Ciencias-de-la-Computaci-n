import { useState } from 'react';
import { registerUser } from '../api/auth';
import { useNavigate } from 'react-router-dom';


function RegisterForm() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    clubName: '',
    avatar: '1',
  });

  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const current_errors = validate_form(form);
  const is_form_valid = Object.keys(current_errors).length === 0;
  

   function handleInputChange(event) {
    const { name, value } = event.target;

    setForm({
      ...form,
      [name]: value,
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setMessage('');
    setError('');

    const payload   = {
        username: form.username,
        email: form.email,
        password: form.password,
        clubName: form.clubName,
        avatar: form.avatar,
    };

    try {
      await registerUser(payload);
      setMessage('Usuario registrado correctamente. Redirigiendo...');

      setForm({
        username: '',
        email: '',
        password: '',
        clubName: '',
        avatar: '',
      });

      // Esperamos 2 segundos para que el usuario lea el message y redirigimos a la página de inicio
      setTimeout(() => {
        navigate('/login'); 
      }, 2000);

    } catch (error) {
      setError(error.message);
    }
  }

  function validate_form(data) {
    const errors = {};
    
    const username = data.username.trim();
    const email = data.email.trim();
    const clubName = data.clubName.trim();
    const password = data.password.trim();
    
    // Validaciones de username
    if (!username) {
      errors.username = 'El nombre de usuario es obligatorio';
    }else if (username.length < 3) {
      errors.username = 'El nombre de usuario debe tener al menos 3 caracteres';
    }else if (username.length > 50) {
      errors.username = 'El nombre de usuario no puede tener más de 50 caracteres';
    }
    
    // validaciones de email
    if (!email) {
      errors.email = 'El correo es obligatorio';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = 'El correo no es válido';
    }

    
    // Validaciones para el nombre del club
    if (!clubName) {
      errors.clubName = 'El nombre del club es obligatorio';
    } else if (clubName.length < 3) {
      errors.clubName = 'El nombre del club debe tener al menos 3 caracteres';
    } else if (clubName.length > 50) {
      errors.clubName = 'El nombre del club no puede superar los 50 caracteres';
    }

    // validaciones de contraseña
    if (!password) {
      errors.password = 'La contraseña es obligatoria';
    } else if (password.length < 8) {
      errors.password = 'La contraseña debe tener al menos 8 caracteres';
    } else if (password.length > 20) {
      errors.password = 'La contraseña no puede superar los 20 caracteres';
    }

    return errors;
  }

  return (
    <div className="w-full max-w-xl mx-auto">
      <div className="mb-8">
        <p className="text-[#f0a95b] font-mono text-xs mb-2 tracking-widest">⬡ INCORPORACIÓN A CLUB TÁCTICO</p>
        <h3 className="text-3xl font-bold mb-2">Prepara tu nueva temporada</h3>
        <p className="text-gray-400 text-sm font-mono">Crea tu cuenta de FutBot y toma el control del banquillo.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-2 gap-4">
          {/* Campo de Usuario  */}
          <div>
            <label htmlFor="username" className="label-futbot">Nombre de usuario</label>
            <div className="input-container">
              <input 
                id="username"
                name="username"
                type="text" 
                value={form.username}
                onChange={handleInputChange}
                placeholder="nombre_de_usuario" 
                className="input-field" 
                required
              />
            </div>
          </div>
          {/* Campo Correo */}
          <div>
            <label htmlFor="email" className="label-futbot">Correo</label>
            <div className="input-container">
              <input 
                id="email"
                name="email"
                type="email" 
                value={form.email}
                onChange={handleInputChange}
                placeholder="nombre@club.com" 
                className="input-field" 
                required
              />
            </div>
          </div>
        </div>
        {/* Segunda Fila */}
        <div className="grid grid-cols-2 gap-4">
        {/* Campo nombre del club */}
          <div>
            <label htmlFor="clubName" className="label-futbot">Nombre del Club</label>
            <div className="input-container">
              <input 
                id="clubName"
                name="clubName"
                type="text" 
                value={form.clubName}
                onChange={handleInputChange}
                placeholder="Nombre de tu club" 
                className="input-field" 
                required
              />
            </div>
          </div>
            {/* Campo Contraseña */}
          <div>
            <label htmlFor="password" className="label-futbot">Contraseña</label>
            <div className="input-container">
              <input 
                id="password"
                name="password"
                type="password" 
                value={form.password}
                onChange={handleInputChange}
                placeholder="••••••••" 
                className="input-field" 
                required
              />
            </div>
          </div>
        </div>

        {/* Selector de avatar */}
        <div>
          <label className="block text-green-300 font-mono text-xs mb-2 uppercase">Selecciona tu Avatar</label>
          <div className="bg-[#0f2217] border border-green-800 rounded-md p-4">
            
            {/* Usamos flex-wrap para que si no entran los 9 en una fila, bajen a la siguiente */}
            <div className="flex flex-wrap gap-4 justify-center">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((num) => {
                const avatarId = num.toString();
                const isSelected = form.avatar === avatarId;
                
                return (
                  <button 
                    key={avatarId} 
                    type="button" 
                    onClick={() => setForm({ ...form, avatar: avatarId })}
                    className={`relative w-20 h-20 rounded-full overflow-hidden border-2 transition-all duration-200
                      ${isSelected 
                        ? 'border-[#f0a95b] scale-110 shadow-[0_0_12px_rgba(240,169,91,0.6)]'
                        : 'border-green-900 hover:border-green-500 opacity-60 hover:opacity-100'
                      }`}
                  >
                    {/* Busca la imagen en la carpeta public/avatars/ */}
                    <img 
                      src={`/avatars/${avatarId}.jpg`} 
                      alt={`Avatar ${avatarId}`} 
                      className="w-full h-full object-cover"
                    />
                  </button>
                );
              })}
            </div>

          </div>
        </div>

        {/* Botón y errores del formulario */}
        <div className="pt-2">
          {/* Lista de errores */}
          {!is_form_valid && (
             <ul className="mb-4 p-3 bg-gray-900/50 border border-gray-700 rounded text-gray-400 text-xs font-mono list-disc list-inside space-y-1">
               {Object.values(current_errors).map((err, index) => (
                 <li key={index}>{err}</li>
               ))}
             </ul>
          )}
          <button 
            type="submit"
            disabled={!is_form_valid}
            className={`w-full font-bold py-4 rounded-md transition-colors flex items-center justify-center gap-2 
              ${is_form_valid 
                ? 'bg-[#f0a95b] hover:bg-[#e0984a] text-black cursor-pointer' 
                : 'bg-gray-600 text-gray-400 cursor-not-allowed opacity-50'}`}
          >
            CREAR MI CUENTA <span>→</span>
          </button>
          {/* message de éxito */}
          {message && (
            <div className="mt-4 p-3 bg-green-900/30 border border-green-800 rounded text-green-400 text-sm font-mono text-center">
              {message}
            </div>
          )}

          {/* message de error */}
          {error && (
            <div className="mt-4 p-3 bg-red-900/30 border border-red-800 rounded text-red-400 text-sm font-mono text-center">
              {error}
            </div>
          )}
        </div>
      </form>
    </div>
    
  );
}

export default RegisterForm;
