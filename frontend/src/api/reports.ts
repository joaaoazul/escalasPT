/**
 * Reports API — PDF exports for schedule and swaps.
 */

import apiClient from './client';

/**
 * Download the weekly swaps report as PDF.
 */
export async function downloadSwapsReport(
  dateFrom?: string,
  dateTo?: string,
): Promise<void> {
  const params: Record<string, string> = {};
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;

  const response = await apiClient.get('/reports/swaps', {
    params,
    responseType: 'blob',
  });

  const disposition = response.headers['content-disposition'] || '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : 'relatorio_trocas.pdf';

  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

/**
 * Download the monthly schedule as PDF.
 */
export async function downloadSchedulePdf(
  year: number,
  month: number,
): Promise<void> {
  const response = await apiClient.get('/reports/schedule', {
    params: { year, month },
    responseType: 'blob',
  });

  const disposition = response.headers['content-disposition'] || '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : `escala_${year}${String(month).padStart(2, '0')}.pdf`;

  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
