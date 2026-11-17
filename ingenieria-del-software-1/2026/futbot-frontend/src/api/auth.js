import { request } from './client'

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

export function verifyEmail(token) {
  return request('/api/auth/verify-email', {
    authenticated: false,
    method: 'POST',
    body: JSON.stringify({ token }),
  })
}

export function resendVerification(email) {
  return request('/api/auth/resend-verification', {
    authenticated: false,
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}


export function forgotPassword(email) {
  return request('/api/auth/forgot-password', {
    authenticated: false,
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}

export function resetPassword(token, newPassword) {
  return request('/api/auth/reset-password', {
    authenticated: false,
    method: 'POST',
    body: JSON.stringify({ token, newPassword }),
  })
}
