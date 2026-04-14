/**
 * Auth store — Zustand.
 * Manages authentication state: user, token, login flow, logout.
 */

import { create } from 'zustand';
import type { AuthUser } from '../types';
import { setAccessToken } from '../api/client';
import * as authApi from '../api/auth';

interface AuthState {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  requiresTotp: boolean;
  pendingCredentials: { username: string; password: string } | null;

  login: (username: string, password: string) => Promise<boolean>;
  loginWithTotp: (code: string) => Promise<void>;
  logout: () => Promise<void>;
  loadUser: () => Promise<void>;
  setUser: (user: AuthUser | null) => void;
  clearTotpState: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  requiresTotp: false,
  pendingCredentials: null,

  login: async (username: string, password: string): Promise<boolean> => {
    const response = await authApi.loginUser(username, password);

    if (response.requires_totp) {
      set({
        requiresTotp: true,
        pendingCredentials: { username, password },
      });
      return false; // needs TOTP step
    }

    setAccessToken(response.access_token);

    // Fetch full user info
    const user = await authApi.getCurrentUser();
    set({
      user,
      isAuthenticated: true,
      isLoading: false,
      requiresTotp: false,
      pendingCredentials: null,
    });
    return true; // login complete
  },

  loginWithTotp: async (code: string) => {
    const creds = get().pendingCredentials;
    if (!creds) {
      throw new Error('No pending credentials for TOTP');
    }

    const response = await authApi.loginWithTotp(
      creds.username,
      creds.password,
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
    } catch {
      // ignore logout errors
    }
    setAccessToken(null);
    set({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      requiresTotp: false,
      pendingCredentials: null,
    });
  },

  loadUser: async () => {
    set({ isLoading: true });
    try {
      // Try refreshing the token from the cookie
      const refreshResult = await authApi.refreshToken();
      setAccessToken(refreshResult.access_token);

      const user = await authApi.getCurrentUser();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      setAccessToken(null);
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  setUser: (user) => {
    set({ user, isAuthenticated: !!user });
  },

  clearTotpState: () => {
    set({ requiresTotp: false, pendingCredentials: null });
  },
}));
