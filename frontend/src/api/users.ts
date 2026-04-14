/**
 * Users API functions.
 */

import apiClient from './client';
import type { User } from '../types';

export interface UserListResponse {
  users: User[];
  total: number;
}

export interface UserFilters {
  station_id?: string;
  role?: string;
  is_active?: boolean;
  skip?: number;
  limit?: number;
}

export async function fetchUsers(
  filters: UserFilters = {},
): Promise<UserListResponse> {
  const response = await apiClient.get<UserListResponse>('/users/', {
    params: filters,
  });
  return response.data;
}

export async function fetchUser(userId: string): Promise<User> {
  const response = await apiClient.get<User>(`/users/${userId}`);
  return response.data;
}

export interface UserCreateData {
  username: string;
  email: string;
  password: string;
  full_name: string;
  nip: string;
  numero_ordem?: string;
  role?: string;
  station_id?: string;
  phone?: string;
}

export async function createUser(data: UserCreateData): Promise<User> {
  const response = await apiClient.post<User>('/users/', data);
  return response.data;
}

export interface UserUpdateData {
  email?: string;
  full_name?: string;
  numero_ordem?: string;
  phone?: string;
  role?: string;
  station_id?: string;
  is_active?: boolean;
}

export async function updateUser(
  userId: string,
  data: UserUpdateData,
): Promise<User> {
  const response = await apiClient.patch<User>(`/users/${userId}`, data);
  return response.data;
}
