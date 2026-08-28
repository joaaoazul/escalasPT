/**
 * Auth API.
 */

import apiClient from './client';
import type { AuthUser, LoginResponse } from '../types';

export async function loginUser(username: string, password: string): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>('/auth/login', { username, password });
  return data;
}

export async function loginWithTotp(
  username: string,
  password: string,
  totp_code: string,
): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>('/auth/login/totp', {
    username,
    password,
    totp_code,
  });
  return data;
}

export async function logoutUser(): Promise<void> {
  await apiClient.post('/auth/logout');
}

export async function getCurrentUser(): Promise<AuthUser> {
  const { data } = await apiClient.get<AuthUser>('/auth/me');
  return data;
}
