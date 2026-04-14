/**
 * Login page with badge number + password, and conditional TOTP step.
 */

import { useState, useRef, useEffect, type FormEvent } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { User, Lock, KeyRound, AlertCircle, ArrowLeft } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, loginWithTotp, requiresTotp, clearTotpState, isAuthenticated, user } = useAuth();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const totpInputRef = useRef<HTMLInputElement>(null);
  const usernameRef = useRef<HTMLInputElement>(null);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && user) {
      const from = (location.state as { from?: { pathname: string } })?.from?.pathname;
      const defaultRoute =
        user.role === 'admin' ? '/app/users' :
        '/app/schedule';
      navigate(from ?? defaultRoute, { replace: true });
    }
  }, [isAuthenticated, user, navigate, location.state]);

  // Focus TOTP input when step changes
  useEffect(() => {
    if (requiresTotp) {
      totpInputRef.current?.focus();
    } else {
      usernameRef.current?.focus();
    }
  }, [requiresTotp]);

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      const complete = await login(username.trim(), password);
      if (complete) {
        // Login succeeded without TOTP — redirect handled by useEffect
      }
      // If TOTP required, the store updates and UI switches to TOTP step
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Erro de autenticação';
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(axiosErr.response?.data?.detail ?? msg);
      } else {
        setError(msg);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleTotpSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (totpCode.length !== 6) return;

    setError('');
    setIsSubmitting(true);

    try {
      await loginWithTotp(totpCode);
    } catch (err: unknown) {
      const msg = 'Código OTP inválido';
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(axiosErr.response?.data?.detail ?? msg);
      } else {
        setError(msg);
      }
      setTotpCode('');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleTotpChange = (value: string) => {
    // Only allow digits, max 6
    const cleaned = value.replace(/\D/g, '').slice(0, 6);
    setTotpCode(cleaned);
  };

  const goBackFromTotp = () => {
    clearTotpState();
    setTotpCode('');
    setError('');
  };

  // ── TOTP Step ──
  if (requiresTotp) {
    return (
      <form onSubmit={handleTotpSubmit} className="auth-form totp-step">
        <div className="totp-icon-wrapper" style={{
          width: 56, height: 56, borderRadius: 'var(--radius-lg)',
          background: 'rgba(16, 185, 129, 0.08)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto var(--space-4)', color: 'var(--color-primary-400)',
        }}>
          <KeyRound size={28} />
        </div>
        <p>Introduza o código de 6 dígitos da sua aplicação de autenticação</p>

        {error && (
          <div className="auth-error">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <div className="input-group">
          <input
            ref={totpInputRef}
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            className="input-field totp-input"
            placeholder="000000"
            value={totpCode}
            onChange={(e) => handleTotpChange(e.target.value)}
            maxLength={6}
            disabled={isSubmitting}
          />
        </div>

        <button
          type="submit"
          className="btn btn-primary btn-lg auth-submit"
          disabled={isSubmitting || totpCode.length !== 6}
        >
          {isSubmitting ? (
            <div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
          ) : (
            'Verificar'
          )}
        </button>

        <button
          type="button"
          className="totp-back"
          onClick={goBackFromTotp}
        >
          <ArrowLeft size={14} />
          Voltar ao login
        </button>
      </form>
    );
  }

  // ── Login Step ──
  return (
    <form onSubmit={handleLogin} className="auth-form">
      {error && (
        <div className="auth-error animate-fade-in">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      <div className="input-group">
        <label className="input-label" htmlFor="login-username">
          Nº Posto / Username
        </label>
        <div className="input-icon-group">
          <input
            ref={usernameRef}
            id="login-username"
            type="text"
            className="input-field input-with-icon"
            placeholder="Ex: comandante.silva"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
            disabled={isSubmitting}
          />
          <span className="input-icon">
            <User size={18} />
          </span>
        </div>
      </div>

      <div className="input-group">
        <label className="input-label" htmlFor="login-password">
          Palavra-passe
        </label>
        <div className="input-icon-group">
          <input
            id="login-password"
            type="password"
            className="input-field input-with-icon"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
            disabled={isSubmitting}
          />
          <span className="input-icon">
            <Lock size={18} />
          </span>
        </div>
      </div>

      <button
        type="submit"
        className="btn btn-primary btn-lg auth-submit"
        disabled={isSubmitting || !username || !password}
      >
        {isSubmitting ? (
          <div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
        ) : (
          'Entrar'
        )}
      </button>
    </form>
  );
}
