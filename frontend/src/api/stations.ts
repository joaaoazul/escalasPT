/**
 * Stations API functions.
 */

import apiClient from './client';
import type { Station } from '../types';

export interface StationListResponse {
  stations: Station[];
  total: number;
}

export async function fetchStations(params: {
  is_active?: boolean;
  skip?: number;
  limit?: number;
} = {}): Promise<StationListResponse> {
  const response = await apiClient.get<StationListResponse>('/stations/', {
    params,
  });
  return response.data;
}

export interface StationCreateData {
  name: string;
  code?: string;
  max_capacity?: number;
  phone?: string;
  address?: string;
}

export async function createStation(data: StationCreateData): Promise<Station> {
  const response = await apiClient.post<Station>('/stations/', data);
  return response.data;
}

export interface StationUpdateData {
  name?: string;
  max_capacity?: number;
  phone?: string;
  address?: string;
  is_active?: boolean;
}

export async function updateStation(
  stationId: string,
  data: StationUpdateData,
): Promise<Station> {
  const response = await apiClient.patch<Station>(`/stations/${stationId}`, data);
  return response.data;
}

export async function deleteStation(stationId: string): Promise<void> {
  await apiClient.delete(`/stations/${stationId}`);
}
