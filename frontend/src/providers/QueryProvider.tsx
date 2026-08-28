/**
 * TanStack Query provider.
 *
 * Defaults are tuned for a phone with bad signal: retries are cheap, stale data
 * is better than a spinner, and a failed refetch must never blank the screen.
 * Phase 1 adds persistQueryClient on IndexedDB so history survives a cold start
 * with no network (docs/PLANO.md §4 nº 7).
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';

export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            gcTime: 24 * 60 * 60 * 1000,
            retry: 2,
            refetchOnWindowFocus: false,
            networkMode: 'offlineFirst',
          },
          mutations: {
            networkMode: 'offlineFirst',
          },
        },
      }),
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
