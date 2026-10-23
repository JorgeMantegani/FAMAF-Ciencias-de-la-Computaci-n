const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const registerUser = async (payload) => {
  const response = await fetch(`${API_URL}/api/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json', 
    },
    body: JSON.stringify(payload), 
  });

  if (response.status === 400) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Datos duplicados');
  }

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Error al registrar el usuario');
  }

  return response.json();
};