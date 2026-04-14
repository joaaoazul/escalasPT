/**
 * useSwaps — React Query hooks for the swap system.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import type { SwapStatus } from '../types';
import {
  cancelSwap,
  createSwap,
  decideSwap,
  fetchSwap,
  fetchSwaps,
  respondToSwap,
  type SwapCreateData,
} from '../api/swaps';

export const SWAP_KEYS = {
  all: ['swaps'] as const,
  list: (status?: SwapStatus) => ['swaps', 'list', status] as const,
  detail: (id: string) => ['swaps', id] as const,
};

export function useSwaps(status?: SwapStatus) {
  return useQuery({
    queryKey: SWAP_KEYS.list(status),
    queryFn: () => fetchSwaps(status),
  });
}

export function useSwap(id: string, enabled = true) {
  return useQuery({
    queryKey: SWAP_KEYS.detail(id),
    queryFn: () => fetchSwap(id),
    enabled,
  });
}

export function useCreateSwap() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: SwapCreateData) => createSwap(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SWAP_KEYS.all });
      toast.success('Pedido de troca enviado.');
    },
    onError: (err: unknown) => {
      const axErr = err as { response?: { data?: { detail?: string } } };
      const detail = axErr?.response?.data?.detail;
      toast.error(detail ?? 'Erro ao enviar pedido de troca.');
    },
  });
}

export function useRespondToSwap() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ swapId, accept }: { swapId: string; accept: boolean }) =>
      respondToSwap(swapId, accept),
    onSuccess: (_data, { accept }) => {
      qc.invalidateQueries({ queryKey: SWAP_KEYS.all });
      toast.success(accept ? 'Troca aceite.' : 'Troca recusada.');
    },
    onError: (err: unknown) => {
      const axErr = err as { response?: { data?: { detail?: string } } };
      const detail = axErr?.response?.data?.detail;
      toast.error(detail ?? 'Erro ao responder ao pedido.');
    },
  });
}

export function useDecideSwap() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ swapId, approve }: { swapId: string; approve: boolean }) =>
      decideSwap(swapId, approve),
    onSuccess: (_data, { approve }) => {
      qc.invalidateQueries({ queryKey: SWAP_KEYS.all });
      qc.invalidateQueries({ queryKey: ['shifts'] });
      toast.success(approve ? 'Troca aprovada.' : 'Troca rejeitada.');
    },
    onError: (err: unknown) => {
      const axErr = err as { response?: { data?: { detail?: string } } };
      const detail = axErr?.response?.data?.detail;
      toast.error(detail ?? 'Erro ao aprovar/rejeitar troca.');
    },
  });
}

export function useCancelSwap() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (swapId: string) => cancelSwap(swapId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SWAP_KEYS.all });
      toast.info('Pedido de troca cancelado.');
    },
    onError: (err: Error) => {
      toast.error(err.message ?? 'Erro ao cancelar pedido.');
    },
  });
}
