/**
 * SwapsPage — view and manage shift swap requests.
 *
 * Military see their own swaps (as requester or target).
 * Commanders see all pending swaps for the station.
 */

import { useState } from 'react';
import {
  ArrowLeftRight,
  CheckCircle2,
  XCircle,
  Clock,
  Check,
  X,
  AlertCircle,
  ChevronDown,
  Download,
  FileText,
} from 'lucide-react';
import { format, parseISO, isValid } from 'date-fns';
import { pt } from 'date-fns/locale';
import { useAuth } from '../hooks/useAuth';
import {
  useCancelSwap,
  useDecideSwap,
  useRespondToSwap,
  useSwaps,
} from '../hooks/useSwaps';
import { downloadSwapPdf } from '../api/swaps';
import { downloadSwapsReport } from '../api/reports';
import type { ShiftSwapRequest, SwapStatus } from '../types';
import './SwapsPage.css';

// ── Status config ─────────────────────────────────────────

const STATUS_CONFIG: Record<
  SwapStatus,
  { label: string; color: string; icon: React.ReactNode }
> = {
  pending_target: {
    label: 'Aguarda resposta',
    color: '#F59E0B',
    icon: <Clock size={14} />,
  },
  pending_approval: {
    label: 'Aguarda aprovação',
    color: '#8B5CF6',
    icon: <Clock size={14} />,
  },
  approved: {
    label: 'Aprovada',
    color: '#10B981',
    icon: <CheckCircle2 size={14} />,
  },
  rejected: {
    label: 'Rejeitada',
    color: '#EF4444',
    icon: <XCircle size={14} />,
  },
  cancelled: {
    label: 'Cancelada',
    color: '#6B7280',
    icon: <X size={14} />,
  },
};

const FILTER_OPTIONS: { label: string; value: SwapStatus | 'all' }[] = [
  { label: 'Todos', value: 'all' },
  { label: 'A aguardar resposta', value: 'pending_target' },
  { label: 'A aguardar aprovação', value: 'pending_approval' },
  { label: 'Aprovadas', value: 'approved' },
  { label: 'Rejeitadas', value: 'rejected' },
  { label: 'Canceladas', value: 'cancelled' },
];

// ── Helpers ───────────────────────────────────────────────

function fmtDate(d: string | null | undefined) {
  if (!d) return '—';
  try {
    const parsed = parseISO(d);
    return isValid(parsed) ? format(parsed, "EEE d MMM", { locale: pt }) : d;
  } catch {
    return d;
  }
}

function fmtRelative(d: string | null | undefined) {
  if (!d) return '';
  try {
    const parsed = parseISO(d);
    return isValid(parsed) ? format(parsed, "d MMM yyyy, HH:mm", { locale: pt }) : '';
  } catch {
    return '';
  }
}

// ── ShiftChip ─────────────────────────────────────────────

interface ShiftChipProps {
  code: string | null;
  color: string | null;
  date: string;
  userName: string | null;
}

function ShiftChip({ code, color, date, userName }: ShiftChipProps) {
  return (
    <div className="swap-shift-chip">
      <span
        className="swap-chip-dot"
        style={{ background: color ?? 'var(--color-primary-500)' }}
      />
      <span className="swap-chip-code">{code ?? '—'}</span>
      <span className="swap-chip-meta">{fmtDate(date)} · {userName ?? '—'}</span>
    </div>
  );
}

// ── SwapCard ──────────────────────────────────────────────

interface SwapCardProps {
  swap: ShiftSwapRequest;
  currentUserId: string;
  isCommand: boolean;
}

function SwapCard({ swap, currentUserId, isCommand }: SwapCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const respond = useRespondToSwap();
  const decide = useDecideSwap();
  const cancel = useCancelSwap();

  const cfg = STATUS_CONFIG[swap.status];
  const isRequester = swap.requester_id === currentUserId;
  const isTarget = swap.target_id === currentUserId;

  const canRespond = isTarget && swap.status === 'pending_target';
  const canDecide = isCommand && swap.status === 'pending_approval';
  const canCancel = isRequester && (swap.status === 'pending_target' || swap.status === 'pending_approval');
  const canDownload = swap.status === 'approved';
  const hasActions = canRespond || canDecide || canCancel || canDownload;

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setDownloading(true);
    try {
      await downloadSwapPdf(swap.id);
    } catch {
      // silently fail
    } finally {
      setDownloading(false);
    }
  };

  /* Who is who */
  const yourLabel = isRequester ? 'O seu turno' : isTarget ? 'O seu turno' : 'Requerente';
  const otherLabel = isRequester ? 'Turno pretendido' : isTarget ? 'Turno oferecido' : 'Alvo';
  const yourShift = isTarget ? swap.target_shift : swap.requester_shift;
  const otherShift = isTarget ? swap.requester_shift : swap.target_shift;

  return (
    <div className={`swap-card swap-card--${swap.status} ${hasActions ? 'swap-card--actionable' : ''}`}>
      {/* Header row: status + date */}
      <div className="swap-card-header">
        <span
          className="swap-status-badge"
          style={{ '--sc-color': cfg.color } as React.CSSProperties}
        >
          {cfg.icon}
          {cfg.label}
        </span>
        <span className="swap-card-meta">{fmtRelative(swap.created_at)}</span>
      </div>

      {/* Shift comparison — always visible */}
      <div className="swap-card-shifts">
        <div className="swap-shift-side">
          <span className="swap-shift-label">{yourLabel}</span>
          {yourShift ? (
            <ShiftChip
              code={yourShift.shift_type_code}
              color={yourShift.shift_type_color}
              date={yourShift.date}
              userName={yourShift.user_name}
            />
          ) : (
            <span className="swap-shift-unknown">Turno removido</span>
          )}
        </div>
        <div className="swap-arrow-wrap">
          <ArrowLeftRight size={16} className="swap-arrow-icon" />
        </div>
        <div className="swap-shift-side">
          <span className="swap-shift-label">{otherLabel}</span>
          {otherShift ? (
            <ShiftChip
              code={otherShift.shift_type_code}
              color={otherShift.shift_type_color}
              date={otherShift.date}
              userName={otherShift.user_name}
            />
          ) : (
            <span className="swap-shift-unknown">Turno removido</span>
          )}
        </div>
      </div>

      {/* Inline actions — always visible, no expand needed */}
      {hasActions && (
        <div className="swap-actions">
          {canRespond && (
            <>
              <button
                className="swap-action-btn swap-action-accept"
                disabled={respond.isPending}
                onClick={() => respond.mutate({ swapId: swap.id, accept: true })}
              >
                <Check size={16} /> Aceitar
              </button>
              <button
                className="swap-action-btn swap-action-reject"
                disabled={respond.isPending}
                onClick={() => respond.mutate({ swapId: swap.id, accept: false })}
              >
                <X size={16} /> Recusar
              </button>
            </>
          )}
          {canDecide && (
            <>
              <button
                className="swap-action-btn swap-action-accept"
                disabled={decide.isPending}
                onClick={() => decide.mutate({ swapId: swap.id, approve: true })}
              >
                <Check size={16} /> Aprovar
              </button>
              <button
                className="swap-action-btn swap-action-reject"
                disabled={decide.isPending}
                onClick={() => decide.mutate({ swapId: swap.id, approve: false })}
              >
                <X size={16} /> Rejeitar
              </button>
            </>
          )}
          {canCancel && (
            <button
              className="swap-action-btn swap-action-cancel"
              disabled={cancel.isPending}
              onClick={() => cancel.mutate(swap.id)}
            >
              Cancelar pedido
            </button>
          )}
          {canDownload && (
            <button
              className="swap-action-btn swap-action-download"
              disabled={downloading}
              onClick={handleDownload}
            >
              <Download size={14} /> {downloading ? 'A gerar...' : 'PDF'}
            </button>
          )}
        </div>
      )}

      {/* Expandable details (reason, etc.) */}
      {swap.reason && (
        <>
          <button
            className="swap-detail-toggle"
            onClick={() => setExpanded(!expanded)}
          >
            <span>Motivo</span>
            <ChevronDown
              size={14}
              className={`swap-expand-icon ${expanded ? 'rotated' : ''}`}
            />
          </button>
          {expanded && (
            <div className="swap-card-detail">
              <p className="swap-reason-text">
                <AlertCircle size={13} />
                {swap.reason}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── SwapsPage ─────────────────────────────────────────────

export function SwapsPage() {
  const { user } = useAuth();
  const [filter, setFilter] = useState<SwapStatus | 'all'>('all');
  const [exportingReport, setExportingReport] = useState(false);

  const isCommand = user?.role === 'comandante' || user?.role === 'adjunto';
  const canExportReport = isCommand || user?.role === 'secretaria';

  const { data: swaps = [], isLoading, error } = useSwaps(
    filter === 'all' ? undefined : filter,
  );

  const handleExportReport = async () => {
    setExportingReport(true);
    try {
      await downloadSwapsReport();
    } catch {
      // silently fail
    } finally {
      setExportingReport(false);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="page-header-left">
          <ArrowLeftRight size={22} />
          <div>
            <h1 className="page-title">Trocas de Turno</h1>
            <p className="page-subtitle">
              {isCommand
                ? 'Gerir pedidos de troca do posto'
                : 'Os seus pedidos de troca'}
            </p>
          </div>
        </div>
        {canExportReport && (
          <button
            className="btn btn-ghost btn-sm swap-download-btn"
            disabled={exportingReport}
            onClick={handleExportReport}
          >
            <FileText size={14} /> {exportingReport ? 'A gerar...' : 'Relatório Semanal'}
          </button>
        )}
      </div>

      {/* Filter bar */}
      <div className="swap-filter-bar">
        {FILTER_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            className={`swap-filter-pill ${filter === opt.value ? 'active' : ''}`}
            onClick={() => setFilter(opt.value)}
          >
            {opt.label}
            {opt.value !== 'all' && (
              <span className="swap-filter-count">
                {swaps.filter(s =>
                  opt.value === 'all' || s.status === opt.value
                ).length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="swap-list-area">
        {isLoading ? (
          <div className="swap-empty">
            <div className="spinner" />
          </div>
        ) : error ? (
          <div className="swap-empty swap-empty--error">
            <AlertCircle size={24} />
            <p>Erro ao carregar trocas.</p>
          </div>
        ) : swaps.length === 0 ? (
          <div className="swap-empty">
            <ArrowLeftRight size={32} />
            <p>Sem trocas {filter !== 'all' ? STATUS_CONFIG[filter as SwapStatus]?.label.toLowerCase() : ''}</p>
          </div>
        ) : (
          <div className="swap-card-list">
            {swaps.map((swap) => (
              <SwapCard
                key={swap.id}
                swap={swap}
                currentUserId={user?.id ?? ''}
                isCommand={isCommand}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
