/**
 * AppLayout — main application shell with responsive sidebar + header + mobile bottom bar.
 */

import { useState } from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  Calendar,
  Users,
  LayoutDashboard,
  LogOut,
  Menu,
  Shield,
  Building2,
  ChevronLeft,
  ClipboardList,
  ArrowLeftRight,
  Settings,
  Eye,
  Lock,
  Layers,
  Bell,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { getInitials } from '../utils/helpers';
import { NotificationDropdown } from '../features/notifications/NotificationDropdown';
import './AppLayout.css';

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
  roles: Array<'admin' | 'comandante' | 'adjunto' | 'secretaria' | 'militar'>;
}

const navItems: NavItem[] = [
  {
    to: '/app/schedule',
    icon: <Calendar size={20} />,
    label: 'Minha Escala',
    roles: ['militar', 'comandante', 'adjunto', 'secretaria'],
  },
  {
    to: '/app/station-schedule',
    icon: <ClipboardList size={20} />,
    label: 'Escala do Posto',
    roles: ['militar', 'comandante', 'adjunto', 'secretaria'],
  },
  {
    to: '/app/swaps',
    icon: <ArrowLeftRight size={20} />,
    label: 'Trocas',
    roles: ['militar', 'comandante', 'adjunto', 'secretaria'],
  },
  {
    to: '/app/dashboard',
    icon: <LayoutDashboard size={20} />,
    label: 'Dashboard',
    roles: ['comandante', 'adjunto'],
  },
  {
    to: '/app/admin',
    icon: <Settings size={20} />,
    label: 'Administração',
    roles: ['admin'],
  },
  {
    to: '/app/admin/users',
    icon: <Users size={20} />,
    label: 'Utilizadores',
    roles: ['admin'],
  },
  {
    to: '/app/admin/stations',
    icon: <Building2 size={20} />,
    label: 'Postos',
    roles: ['admin'],
  },
  {
    to: '/app/admin/shift-types',
    icon: <Layers size={20} />,
    label: 'Tipos de Turno',
    roles: ['admin'],
  },
  {
    to: '/app/admin/audit-log',
    icon: <Eye size={20} />,
    label: 'Auditoria',
    roles: ['admin'],
  },
  {
    to: '/app/admin/sessions',
    icon: <Lock size={20} />,
    label: 'Sessões',
    roles: ['admin'],
  },
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  if (!user) return null;

  const filteredNav = navItems.filter((item) =>
    item.roles.includes(user.role),
  );

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const closeMobileSidebar = () => setSidebarOpen(false);

  // Page title for mobile header
  const pageTitle = (() => {
    const p = location.pathname;
    if (p.includes('/station-schedule')) return 'Escala do Posto';
    if (p.includes('/schedule')) return 'Minha Escala';
    if (p.includes('/swaps')) return 'Trocas';
    if (p.includes('/dashboard')) return 'Dashboard';
    if (p.includes('/notifications')) return 'Notificações';
    if (p.includes('/admin')) return 'Administração';
    return 'EscalasPT';
  })();

  return (
    <div className={`app-layout ${collapsed ? 'sidebar-collapsed' : ''}`}>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={closeMobileSidebar} />
      )}

      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <div className="sidebar-logo">
              <Shield size={20} />
            </div>
            {!collapsed && <span className="sidebar-brand-text">EscalasPT</span>}
          </div>
          <button
            className="btn-icon sidebar-collapse-btn"
            onClick={() => setCollapsed(!collapsed)}
            title={collapsed ? 'Expandir' : 'Recolher'}
          >
            <ChevronLeft
              size={18}
              style={{
                transform: collapsed ? 'rotate(180deg)' : 'none',
                transition: 'transform var(--transition-fast)',
              }}
            />
          </button>
        </div>

        <nav className="sidebar-nav">
          {filteredNav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `sidebar-link ${isActive ? 'sidebar-link-active' : ''}`
              }
              onClick={closeMobileSidebar}
              title={collapsed ? item.label : undefined}
            >
              <span className="sidebar-link-icon">{item.icon}</span>
              {!collapsed && (
                <span className="sidebar-link-label">{item.label}</span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user" title={user.full_name}>
            <div className="avatar">
              {getInitials(user.full_name)}
            </div>
            {!collapsed && (
              <div className="sidebar-user-info">
                <span className="sidebar-user-name">{user.full_name}</span>
                <span className="sidebar-user-role">
                  {user.role === 'comandante'
                    ? 'Comandante'
                    : user.role === 'adjunto'
                      ? 'Adjunto'
                      : user.role === 'secretaria'
                        ? 'Secretaria'
                        : user.role === 'admin'
                          ? 'Admin'
                          : 'Militar'}
                </span>
              </div>
            )}
          </div>
          <button
            className="btn-icon sidebar-logout"
            onClick={handleLogout}
            title="Terminar sessão"
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>

      {/* Main content area */}
      <div className="app-main">
        {/* Header */}
        <header className="app-header">
          <button
            className="btn-icon mobile-menu-btn"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu size={22} />
          </button>

          <span className="header-page-title">{pageTitle}</span>

          <div className="header-spacer" />

          <div className="header-actions">
            <NotificationDropdown />

            <div className="header-user-pill">
              <div className="avatar" style={{ width: 30, height: 30, fontSize: '0.7rem' }}>
                {getInitials(user.full_name)}
              </div>
              <span className="header-user-name">{user.full_name}</span>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="app-content">
          <Outlet />
        </main>

        {/* Mobile bottom tab bar */}
        {user.role !== 'admin' && (
          <nav className="bottom-tab-bar">
            <NavLink
              to="/app/schedule"
              className={({ isActive }) => `btb-tab ${isActive ? 'btb-tab-active' : ''}`}
            >
              <Calendar size={22} />
              <span>Escala</span>
            </NavLink>
            <NavLink
              to="/app/station-schedule"
              className={({ isActive }) => `btb-tab ${isActive ? 'btb-tab-active' : ''}`}
            >
              <ClipboardList size={22} />
              <span>Posto</span>
            </NavLink>
            <NavLink
              to="/app/swaps"
              className={({ isActive }) => `btb-tab ${isActive ? 'btb-tab-active' : ''}`}
            >
              <ArrowLeftRight size={22} />
              <span>Trocas</span>
            </NavLink>
            <NavLink
              to="/app/notifications"
              className={({ isActive }) => `btb-tab ${isActive ? 'btb-tab-active' : ''}`}
            >
              <Bell size={22} />
              <span>Alertas</span>
            </NavLink>
            {(user.role === 'comandante' || user.role === 'adjunto') && (
              <NavLink
                to="/app/dashboard"
                className={({ isActive }) => `btb-tab ${isActive ? 'btb-tab-active' : ''}`}
              >
                <LayoutDashboard size={22} />
                <span>Painel</span>
              </NavLink>
            )}
          </nav>
        )}
      </div>
    </div>
  );
}
