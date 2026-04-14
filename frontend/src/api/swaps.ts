/**
 * Swaps API functions.
 */

import apiClient from './client';
import type { ShiftSwapRequest, SwapStatus } from '../types';

export interface SwapCreateData {
  requester_shift_id: string;
  target_shift_id: string;
  target_id: string;
  reason?: string;
}

export async function fetchSwaps(
  status?: SwapStatus,
): Promise<ShiftSwapRequest[]> {
  const response = await apiClient.get<ShiftSwapRequest[]>('/swaps/', {
    params: status ? { status } : {},
  });
  return response.data;
}

export async function fetchSwap(swapId: string): Promise<ShiftSwapRequest> {
  const response = await apiClient.get<ShiftSwapRequest>(`/swaps/${swapId}`);
  return response.data;
}

export async function createSwap(data: SwapCreateData): Promise<ShiftSwapRequest> {
  const response = await apiClient.post<ShiftSwapRequest>('/swaps/', data);
  return response.data;
}

export async function respondToSwap(
  swapId: string,
  accept: boolean,
): Promise<ShiftSwapRequest> {
  const response = await apiClient.post<ShiftSwapRequest>(
    `/swaps/${swapId}/respond`,
    null,
    { params: { accept } },
  );
  return response.data;
}

export async function decideSwap(
  swapId: string,
  approve: boolean,
): Promise<ShiftSwapRequest> {
  const response = await apiClient.post<ShiftSwapRequest>(
    `/swaps/${swapId}/decide`,
    null,
    { params: { approve } },
  );
  return response.data;
}

export async function cancelSwap(swapId: string): Promise<ShiftSwapRequest> {
  const response = await apiClient.post<ShiftSwapRequest>(
    `/swaps/${swapId}/cancel`,
  );
  return response.data;
}

export async function downloadSwapPdf(swapId: string): Promise<void> {
  const response = await apiClient.get(`/swaps/${swapId}/pdf`, {
    responseType: 'blob',
  });
  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `troca_${swapId.substring(0, 8)}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
