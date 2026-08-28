/**
 * AppLayout — sidebar on the desktop, bottom tab bar on the phone.
 * Same structure and class names as escalasPT (layouts/AppLayout.css).
 */

import { useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  BarChart3,
  ClipboardList,
  LogOut,
  Menu,
  NotebookPen,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Sun,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import type { UserRole } from '../types';
import './AppLayout.css';

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
  roles: UserRole[];
  tab?: boolean;
}

const ALL_ROLES: UserRole[] = ['agente', 'chefe_equipa', 'admin'];

const navItems: NavItem[] = [
  { to: '/', icon: <Sun size={20} />, label: 'Hoje', roles: ALL_ROLES, tab: true },
  {
    to: '/servicos',
    icon: <ClipboardList size={20} />,
    label: 'Serviços',
    roles: ALL_ROLES,
    tab: true,
  },
  {
    to: '/registos',
    icon: <NotebookPen size={20} />,
    label: 'Registos',
    roles: ALL_ROLES,
    tab: true,
  },
  {
    to: '/painel',
    icon: <BarChart3 size={20} />,
    label: 'Painel',
    roles: ALL_ROLES,
    tab: true,
  },
  {
    to: '/admin',
    icon: <Settings size={20} />,
    label: 'Administração',
    roles: ['admin'],
  },
];

const TITLES: Record<string, string> = {
  '/': 'Hoje',
  '/servicos': 'Serviços',
  '/registos': 'Registos',
  '/painel': 'Painel',
  '/admin': 'Administração',
};

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  if (!user) return null;

  const visible = navItems.filter((item) => item.roles.includes(user.role));
  const tabs = visible.filter((item) => item.tab);
  const pageTitle = TITLES[location.pathname] ?? 'Caderno';

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className={`app-layout ${collapsed ? 'sidebar-collapsed' : ''}`}>
      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}

      <aside className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <div className="sidebar-logo">
              <NotebookPen size={20} />
            </div>
            {!collapsed && <span className="sidebar-brand-text">Caderno</span>}
          </div>
          <button
            className="btn-icon sidebar-collapse-btn"
            onClick={() => setCollapsed(!collapsed)}
            title={collapsed ? 'Expandir' : 'Recolher'}
            aria-label={collapsed ? 'Expandir menu' : 'Recolher menu'}
          >
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
        </div>

        <nav className="sidebar-nav">
          {visible.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `sidebar-link ${isActive ? 'sidebar-link-active' : ''}`
              }
              onClick={() => setSidebarOpen(false)}
              title={collapsed ? item.label : undefined}
            >
              <span className="sidebar-link-icon">{item.icon}</span>
              {!collapsed && <span className="sidebar-link-label">{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="avatar">{user.nome.slice(0, 2)}</div>
            {!collapsed && (
              <div className="sidebar-user-info">
                <span className="sidebar-user-name">{user.nome}</span>
                <span className="sidebar-user-role">{user.equipa?.codigo ?? user.role}</span>
              </div>
            )}
          </div>
          <button
            className="btn-icon sidebar-logout"
            onClick={handleLogout}
            title="Terminar sessão"
            aria-label="Terminar sessão"
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>

      <div className="app-main">
        <header className="app-header">
          <button
            className="btn-icon mobile-menu-btn"
            onClick={() => setSidebarOpen(true)}
            aria-label="Abrir menu"
          >
            <Menu size={20} />
          </button>
          <span className="header-page-title">{pageTitle}</span>
          <div className="header-spacer" />
          <div className="header-actions">
            <span className="header-user-pill">
              <span className="header-user-name">{user.equipa?.codigo ?? 'sem equipa'}</span>
            </span>
          </div>
        </header>

        <main className="app-content">
          <Outlet />
        </main>
      </div>

      <nav className="bottom-tab-bar">
        {tabs.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => `btb-tab ${isActive ? 'btb-tab-active' : ''}`}
          >
            {item.icon}
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
