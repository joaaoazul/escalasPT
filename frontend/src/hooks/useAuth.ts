/**
 * Auth hook — abstracts auth store for components.
 */

import { useAuthStore } from '../store/authStore';
import type { UserRole } from '../types';

export function useAuth() {
  const {
    user,
    isAuthenticated,
    isLoading,
    requiresTotp,
    login,
    loginWithTotp,
    logout,
    loadUser,
    clearTotpState,
  } = useAuthStore();

  const hasRole = (...roles: UserRole[]): boolean => {
    if (!user) return false;
    return roles.includes(user.role);
  };

  const isComandante = user?.role === 'comandante';
  const isMilitar = user?.role === 'militar';
  const isAdmin = user?.role === 'admin';

  return {
    user,
    isAuthenticated,
    isLoading,
    requiresTotp,
    hasRole,
    isComandante,
    isMilitar,
    isAdmin,
    login,
    loginWithTotp,
    logout,
    loadUser,
    clearTotpState,
  };
}
