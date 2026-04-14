/**
 * useShiftMutations — React Query hook for handling shift updates.
 * Invalidates queries to automatically refresh calendar points.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  createShift,
  updateShift,
  deleteShift,
  publishShifts,
  type ShiftCreateData,
  type ShiftUpdateData,
} from '../api/shifts';

export function useShiftMutations() {
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (data: ShiftCreateData) => createShift(data),
    onSuccess: (response) => {
      if (response.warnings && response.warnings.length > 0) {
        toast.warning(response.warnings?.[0]?.description, { duration: 5000 });
      } else {
        toast.success('Turno (rascunho) criado com sucesso');
      }
      queryClient.invalidateQueries({ queryKey: ['shifts'] });
    },
    onError: (error: any) => {
      const msg = error.response?.data?.detail ?? 'Erro ao criar turno';
      toast.error(msg);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: ShiftUpdateData }) =>
      updateShift(id, data),
    onSuccess: (response) => {
      if (response.warnings && response.warnings.length > 0) {
        toast.warning(response.warnings?.[0]?.description, { duration: 5000 });
      } else {
        toast.success('Turno atualizado com sucesso');
      }
      queryClient.invalidateQueries({ queryKey: ['shifts'] });
    },
    onError: (error: any) => {
      const msg = error.response?.data?.detail ?? 'Erro ao atualizar turno';
      toast.error(msg);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteShift(id),
    onSuccess: () => {
      toast.success('Turno eliminado');
      queryClient.invalidateQueries({ queryKey: ['shifts'] });
    },
    onError: (error: any) => {
      const msg = error.response?.data?.detail ?? 'Erro ao eliminar turno';
      toast.error(msg);
    },
  });

  const publishMutation = useMutation({
    mutationFn: (shiftIds: string[]) => publishShifts(shiftIds),
    onSuccess: (response) => {
      if (response.conflicts && response.conflicts.length > 0) {
        toast.warning(
          `${response.published_count} turno(s) publicados com avisos`,
          { description: response.conflicts[0]?.description, duration: 7000 }
        );
      } else {
        toast.success(
          `${response.published_count} turno(s) publicado(s) com sucesso`,
          { duration: 4000 }
        );
      }
      queryClient.invalidateQueries({ queryKey: ['shifts'] });
    },
    onError: (error: any) => {
      const msg = error.response?.data?.detail ?? 'Erro ao publicar turnos';
      toast.error(msg);
    },
  });

  return {
    createShift: createMutation,
    updateShift: updateMutation,
    deleteShift: deleteMutation,
    publishShifts: publishMutation,
  };
}
