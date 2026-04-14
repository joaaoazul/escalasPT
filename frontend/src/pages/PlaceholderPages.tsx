/**
 * Placeholder pages for Phase 1.
 * Full implementations come in Phases 2-5.
 */

import { ShieldX } from 'lucide-react';

export function PlaceholderPage({ icon, title, description }: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="animate-fade-in" style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: 'calc(100vh - var(--header-height) - var(--space-12))',
      textAlign: 'center',
      gap: 'var(--space-4)',
    }}>
      <div style={{
        width: 80, height: 80, borderRadius: 'var(--radius-xl)',
        background: 'rgba(16, 185, 129, 0.06)',
        border: '1px solid rgba(16, 185, 129, 0.1)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--color-primary-500)',
      }}>
        {icon}
      </div>
      <h1 style={{ fontSize: 'var(--font-2xl)', fontWeight: 'var(--weight-bold)' }}>
        {title}
      </h1>
      <p style={{ color: 'var(--text-secondary)', maxWidth: 400 }}>
        {description}
      </p>
    </div>
  );
}

export function UnauthorizedPage() {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      textAlign: 'center',
      gap: 'var(--space-4)',
      padding: 'var(--space-4)',
    }}>
      <div style={{
        width: 80, height: 80, borderRadius: 'var(--radius-xl)',
        background: 'rgba(239, 68, 68, 0.06)',
        border: '1px solid rgba(239, 68, 68, 0.1)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--color-danger-500)',
      }}>
        <ShieldX size={36} />
      </div>
      <h1 style={{ fontSize: 'var(--font-2xl)', fontWeight: 'var(--weight-bold)' }}>
        Acesso Negado
      </h1>
      <p style={{ color: 'var(--text-secondary)', maxWidth: 400 }}>
        Não tem permissão para aceder a esta página.
      </p>
      <a href="/app/schedule" className="btn btn-primary" style={{ marginTop: 'var(--space-4)' }}>
        Voltar ao início
      </a>
    </div>
  );
}

export function NotFoundPage() {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      textAlign: 'center',
      gap: 'var(--space-4)',
      padding: 'var(--space-4)',
    }}>
      <h1 style={{
        fontSize: '6rem', fontWeight: 'var(--weight-bold)',
        color: 'var(--surface-500)', lineHeight: 1,
      }}>
        404
      </h1>
      <p style={{ color: 'var(--text-secondary)' }}>
        Página não encontrada
      </p>
      <a href="/app/schedule" className="btn btn-primary" style={{ marginTop: 'var(--space-4)' }}>
        Voltar ao início
      </a>
    </div>
  );
}
