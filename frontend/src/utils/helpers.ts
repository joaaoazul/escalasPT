/**
 * Date formatting helpers using date-fns.
 */

import { format, parseISO, isValid } from 'date-fns';
import { pt } from 'date-fns/locale';

export function formatDate(dateStr: string, fmt: string = 'dd/MM/yyyy'): string {
  const date = parseISO(dateStr);
  if (!isValid(date)) return dateStr;
  return format(date, fmt, { locale: pt });
}

export function formatDateTime(dateStr: string): string {
  return formatDate(dateStr, "dd/MM/yyyy 'às' HH:mm");
}

export function formatTime(dateStr: string): string {
  return formatDate(dateStr, 'HH:mm');
}

export function formatMonth(dateStr: string): string {
  return formatDate(dateStr, 'MMMM yyyy');
}

export function formatShortDate(dateStr: string): string {
  return formatDate(dateStr, 'dd MMM');
}

/**
 * Map shift type codes to semantic colors for consistent display.
 */
export function getShiftColor(shiftTypeColor: string | null, status: string): string {
  if (status === 'cancelled') return '#6B7280';
  if (status === 'draft') return shiftTypeColor ? `${shiftTypeColor}99` : '#6B728099';
  return shiftTypeColor ?? '#3B82F6';
}

/**
 * Get user initials from full name.
 */
export function getInitials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .map((word) => word[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

/**
 * Format the status badge text in Portuguese.
 */
export function formatStatus(status: string): string {
  const map: Record<string, string> = {
    draft: 'Rascunho',
    published: 'Publicado',
    cancelled: 'Cancelado',
    pending_target: 'Aguarda Colega',
    pending_approval: 'Aguarda Chefe',
    approved: 'Aprovado',
    rejected: 'Rejeitado',
  };
  return map[status] ?? status;
}

export function getStatusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    draft: 'badge-amber',
    published: 'badge-green',
    cancelled: 'badge-gray',
    approved: 'badge-green',
    rejected: 'badge-red',
    pending_target: 'badge-blue',
    pending_approval: 'badge-amber',
  };
  return map[status] ?? 'badge-gray';
}
