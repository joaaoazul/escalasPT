/**
 * Auth store — Zustand.
 * The access token lives in memory only (api/client.ts); the refresh token is
 * an HttpOnly cookie the browser handles. Nothing lands in localStorage.
 */

import { create } from 'zustand';
import { setAccessToken } from '../api/client';
import * as authApi from '../api/auth';
import type { AuthUser } from '../types';

interface AuthState {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  requiresTotp: boolean;
  pendingCredentials: { username: string; password: string } | null;

  login: (username: string, password: string) => Promise<boolean>;
  loginWithTotp: (code: string) => Promise<void>;
  logout: () => Promise<void>;
  restoreSession: () => Promise<void>;
  clearTotpState: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  requiresTotp: false,
  pendingCredentials: null,

  login: async (username, password) => {
    const response = await authApi.loginUser(username, password);

    if (response.requires_totp) {
      set({ requiresTotp: true, pendingCredentials: { username, password } });
      return false;
    }

    setAccessToken(response.access_token);
    const user = await authApi.getCurrentUser();
    set({
      user,
      isAuthenticated: true,
      isLoading: false,
      requiresTotp: false,
      pendingCredentials: null,
    });
    return true;
  },

  loginWithTotp: async (code) => {
    const credentials = get().pendingCredentials;
    if (!credentials) throw new Error('Sem credenciais pendentes');

    const response = await authApi.loginWithTotp(
      credentials.username,
      credentials.password,
      code,
    );
    setAccessToken(response.access_token);
    const user = await authApi.getCurrentUser();
    set({
      user,
      isAuthenticated: true,
      isLoading: false,
      requiresTotp: false,
      pendingCredentials: null,
    });
  },

  logout: async () => {
    try {
      await authApi.logoutUser();
    } finally {
      setAccessToken(null);
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  /**
   * On a cold start the access token is gone (memory only) but the refresh
   * cookie may still be valid — ask for a user and let the axios interceptor
   * refresh underneath.
   */
  restoreSession: async () => {
    try {
      const user = await authApi.getCurrentUser();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  clearTotpState: () => set({ requiresTotp: false, pendingCredentials: null }),
}));
