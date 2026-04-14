/**
 * Auth API functions.
 */

import apiClient from './client';
import type { AuthUser, LoginResponse } from '../types';

export async function loginUser(
  username: string,
  password: string,
): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/auth/login', {
    username,
    password,
  });
  return response.data;
}

export async function loginWithTotp(
  username: string,
  password: string,
  totp_code: string,
): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/auth/login/totp', {
    username,
    password,
    totp_code,
  });
  return response.data;
}

export async function refreshToken(): Promise<{ access_token: string }> {
  const response = await apiClient.post<{ access_token: string }>(
    '/auth/refresh',
  );
  return response.data;
}

export async function logoutUser(): Promise<void> {
  await apiClient.post('/auth/logout');
}

export async function getCurrentUser(): Promise<AuthUser> {
  const response = await apiClient.get<AuthUser>('/auth/me');
  return response.data;
}

export async function setupTotp(): Promise<{ secret: string; uri: string }> {
  const response = await apiClient.post<{ secret: string; uri: string }>(
    '/auth/totp/setup',
  );
  return response.data;
}

export async function verifyTotp(
  code: string,
): Promise<{ verified: boolean; message: string }> {
  const response = await apiClient.post<{
    verified: boolean;
    message: string;
  }>('/auth/totp/verify', { code });
  return response.data;
}
