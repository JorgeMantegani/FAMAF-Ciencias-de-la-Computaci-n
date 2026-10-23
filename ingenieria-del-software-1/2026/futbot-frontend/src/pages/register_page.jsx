import { Link } from 'react-router-dom';
import RegisterForm from '../components/register_form';

function RegisterPage() {
  return (
    // Contenedor principal (La tarjeta dividida)
    <div className="flex flex-row w-full max-w-6xl rounded-2xl overflow-hidden shadow-2xl">
        
        {/* Info  */}
        <div className="w-5/12 bg-[#132a1d] p-10 flex flex-col justify-between border-r border-green-900/50">
          <div>
            <p className="text-[#f0a95b] font-mono text-xs mb-4 tracking-widest">— NUEVO FICHAJE</p>
            <h2 className="text-4xl font-bold mb-4 leading-tight">Tu club entra al campo aquí.</h2>
            <p className="text-gray-400 text-sm font-mono leading-relaxed">
              Crea tu perfil, arma el vestuario y empieza a diseñar la próxima jugada.
            </p>
          </div>

        </div>

        {/* Formulario */}
        <div className="w-7/12 bg-[#193625] p-10 flex flex-col justify-center">
          <RegisterForm />
          <p className="auth-switch">
            ¿Ya tenés cuenta? <Link to="/login">Iniciar sesión</Link>
          </p>
        </div>

      </div>
  );
}

export default RegisterPage;