/**
 * NotificationDropdown — Bell icon with a popover showing recent notifications.
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell, Check, ExternalLink,
  CalendarCheck, CalendarX, Calendar,
  ArrowLeftRight, XCircle, CheckCircle2,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { pt } from 'date-fns/locale';
import { useNotificationStore } from '../../store/notificationStore';
import { useNotifications } from '../../hooks/useNotifications';
import type { NotificationType, NotificationShiftEntry } from '../../types';
import './NotificationDropdown.css';

const TYPE_CONFIG: Record<NotificationType, { icon: LucideIcon; color: string }> = {
  shift_published: { icon: CalendarCheck,  color: '#10B981' },
  shift_updated:   { icon: Calendar,       color: '#F59E0B' },
  shift_cancelled: { icon: CalendarX,      color: '#EF4444' },
  swap_requested:  { icon: ArrowLeftRight, color: '#8B5CF6' },
  swap_accepted:   { icon: ArrowLeftRight, color: '#10B981' },
  swap_approved:   { icon: CheckCircle2,   color: '#10B981' },
  swap_rejected:   { icon: XCircle,        color: '#EF4444' },
  general:         { icon: Bell,           color: '#6B7280' },
};

export function NotificationDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const { notifications, unreadCount } = useNotificationStore();
  const { markAsRead } = useNotifications(); // Triggers tanstack to mark on backend

  const toggleDropdown = () => setIsOpen((prev) => !prev);

  // Close when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const handleMarkAllRead = () => {
    const unreadIds = notifications.filter((n) => !n.is_read).map((n) => n.id);
    if (unreadIds.length > 0) {
      markAsRead(unreadIds);
    }
  };

  const handleNotificationClick = (id: string, isRead: boolean) => {
    if (!isRead) {
      markAsRead([id]);
    }
    setIsOpen(false);
    navigate('/app/notifications');
  };

  const displayList = notifications.slice(0, 5); // top 5

  return (
    <div className="nd-container" ref={dropdownRef}>
      <button className="btn-icon nd-trigger" onClick={toggleDropdown} title="Notificações">
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className="nd-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>
        )}
      </button>

      {isOpen && (
        <div className="nd-popover animate-scale-in">
          <div className="nd-header">
            <h3 className="nd-title">Notificações</h3>
            {unreadCount > 0 && (
              <button className="btn-ghost nd-mark-all" onClick={handleMarkAllRead}>
                <Check size={14} />
                Marcar todas lidas
              </button>
            )}
          </div>

          <div className="nd-body">
            {displayList.length === 0 ? (
              <div className="nd-empty">
                Não tem notificações.
              </div>
            ) : (
              displayList.map((notif) => {
              const cfg = TYPE_CONFIG[notif.type as NotificationType] ?? TYPE_CONFIG.general;
              const Icon = cfg.icon;
              const shifts = (notif.data?.shifts as NotificationShiftEntry[] | undefined) ?? [];
              return (
                <div
                  key={notif.id}
                  className={`nd-item ${!notif.is_read ? 'nd-item-unread' : ''}`}
                  style={{ '--nd-accent': cfg.color } as React.CSSProperties}
                  onClick={() => handleNotificationClick(notif.id, notif.is_read)}
                >
                  <div
                    className="nd-item-icon"
                    style={{ color: cfg.color, background: cfg.color + '1A' }}
                  >
                    <Icon size={14} />
                  </div>
                  <div className="nd-item-content">
                    <p className="nd-item-title">{notif.title}</p>
                    <p className="nd-item-message">{notif.message}</p>
                    {shifts.length > 0 && (
                      <div className="nd-shift-chips">
                        {shifts.slice(0, 5).map((s, i) => (
                          <span
                            key={i}
                            className="nd-shift-chip"
                            style={{
                              background: s.shift_type_color + '28',
                              color: s.shift_type_color,
                              borderColor: s.shift_type_color + '55',
                            }}
                          >
                            {s.shift_type_code}
                          </span>
                        ))}
                        {shifts.length > 5 && (
                          <span className="nd-shift-more">+{shifts.length - 5}</span>
                        )}
                      </div>
                    )}
                    <span className="nd-item-time">
                      {formatDistanceToNow(new Date(notif.created_at), { addSuffix: true, locale: pt })}
                    </span>
                  </div>
                  {!notif.is_read && <div className="nd-unread-dot" />}
                </div>
              );
            })
            )}
          </div>

          <div className="nd-footer">
            <button
              className="btn btn-ghost"
              style={{ width: '100%' }}
              onClick={() => {
                setIsOpen(false);
                navigate('/app/notifications');
              }}
            >
              Ver todas <ExternalLink size={14} style={{ marginLeft: '4px' }} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
