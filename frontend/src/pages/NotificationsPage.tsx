/**
 * NotificationsPage — full history of user notifications.
 */

import {
  CheckCircle2, Clock, Bell, BellRing, BellOff,
  CalendarCheck, CalendarX, Calendar,
  ArrowLeftRight, XCircle,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { format } from 'date-fns';
import { pt } from 'date-fns/locale';
import { useNotifications } from '../hooks/useNotifications';
import { usePushNotifications } from '../hooks/usePushNotifications';
import { useNotificationStore } from '../store/notificationStore';
import type { Notification, NotificationType, NotificationShiftEntry } from '../types';
import './NotificationsPage.css';

const TYPE_CONFIG: Record<NotificationType, { icon: LucideIcon; color: string; label: string }> = {
  shift_published: { icon: CalendarCheck,  color: '#10B981', label: 'Publicado'       },
  shift_updated:   { icon: Calendar,       color: '#F59E0B', label: 'Atualizado'      },
  shift_cancelled: { icon: CalendarX,      color: '#EF4444', label: 'Cancelado'       },
  swap_requested:  { icon: ArrowLeftRight, color: '#8B5CF6', label: 'Troca pedida'    },
  swap_accepted:   { icon: ArrowLeftRight, color: '#10B981', label: 'Troca aceite'    },
  swap_approved:   { icon: CheckCircle2,   color: '#10B981', label: 'Troca aprovada'  },
  swap_rejected:   { icon: XCircle,        color: '#EF4444', label: 'Troca rejeitada' },
  general:         { icon: Bell,           color: '#6B7280', label: 'Geral'           },
};

function NotifCard({
  notif,
  onMarkRead,
  disabled,
}: {
  notif: Notification;
  onMarkRead: (id: string) => void;
  disabled: boolean;
}) {
  const cfg = TYPE_CONFIG[notif.type] ?? TYPE_CONFIG.general;
  const Icon = cfg.icon;
  const shifts = (notif.data?.shifts as NotificationShiftEntry[] | undefined) ?? [];
  const accentColor = shifts.length > 0 ? shifts[0]?.shift_type_color ?? cfg.color : cfg.color;

  return (
    <div
      className={`notification-card ${!notif.is_read ? 'unread' : ''}`}
      style={{ '--nc-accent': accentColor } as React.CSSProperties}
    >
      <div
        className="nc-type-icon"
        style={{ color: cfg.color, background: cfg.color + '1A' }}
      >
        <Icon size={18} />
      </div>

      <div className="nc-content">
        <div className="nc-title-row">
          <h4 className="nc-title">{notif.title}</h4>
          <span
            className="nc-type-badge"
            style={{ background: cfg.color + '22', color: cfg.color }}
          >
            {cfg.label}
          </span>
        </div>

        <p className="nc-message">{notif.message}</p>

        {shifts.length > 0 && (
          <div className="nc-shifts">
            {shifts.map((s, i) => (
              <span
                key={i}
                className="nc-shift-chip"
                style={{
                  background: s.shift_type_color + '28',
                  color: s.shift_type_color,
                  borderColor: s.shift_type_color + '55',
                }}
                title={`${s.shift_type_name} — ${s.date}`}
              >
                {s.shift_type_code}
                <span className="nc-shift-date">
                  {format(new Date(s.date), 'dd/MM')}
                </span>
              </span>
            ))}
          </div>
        )}

        <div className="nc-meta">
          <Clock size={12} />
          <span>
            {format(new Date(notif.created_at), "dd 'de' MMMM, HH:mm", { locale: pt })}
          </span>
        </div>
      </div>

      {!notif.is_read && (
        <button
          className="btn btn-ghost btn-sm nc-mark-btn"
          onClick={() => onMarkRead(notif.id)}
          disabled={disabled}
        >
          Lida
        </button>
      )}
    </div>
  );
}

export function NotificationsPage() {
  const { notifications, unreadCount } = useNotificationStore();
  const { markAsRead, isMarkingRead } = useNotifications();
  const { state: pushState, subscribe: subscribePush, unsubscribe: unsubscribePush } = usePushNotifications();

  const handleMarkAllRead = () => {
    const unreadIds = notifications.filter(n => !n.is_read).map(n => n.id);
    if (unreadIds.length > 0) {
      markAsRead(unreadIds);
    }
  };

  return (
    <div className="page-container animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Notificações</h1>
          <p className="page-subtitle">O seu histórico de eventos e alterações de escala.</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {pushState !== 'unsupported' && pushState !== 'disabled' && pushState !== 'loading' && (
            pushState === 'subscribed' ? (
              <button
                className="btn btn-ghost"
                onClick={unsubscribePush}
                title="Desativar notificações push"
              >
                <BellOff size={18} />
                Push ativo
              </button>
            ) : pushState !== 'denied' ? (
              <button
                className="btn btn-secondary"
                onClick={subscribePush}
                title="Ativar notificações push no browser"
              >
                <BellRing size={18} />
                Ativar Push
              </button>
            ) : (
              <span className="text-muted" style={{ fontSize: '0.8rem' }}>
                Push bloqueado pelo browser
              </span>
            )
          )}
          {unreadCount > 0 && (
            <button
              className="btn btn-secondary"
              onClick={handleMarkAllRead}
              disabled={isMarkingRead}
            >
              <CheckCircle2 size={18} />
              Marcar todas como lidas
            </button>
          )}
        </div>
      </div>

      <div className="notifications-list">
        {notifications.length === 0 ? (
          <div className="empty-state">
            <Bell size={48} className="empty-icon" />
            <h3>Sem notificações</h3>
            <p>Não há alertas registados no seu histórico.</p>
          </div>
        ) : (
          notifications.map((notif) => (
            <NotifCard
              key={notif.id}
              notif={notif}
              onMarkRead={(id) => markAsRead([id])}
              disabled={isMarkingRead}
            />
          ))
        )}
      </div>
    </div>
  );
}
