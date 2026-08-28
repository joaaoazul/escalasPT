/**
 * LoginPage — password, then TOTP when the account has 2FA on.
 */

import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { useAuth } from '../hooks/useAuth';

export function LoginPage() {
  const navigate = useNavigate();
  const { login, loginWithTotp, requiresTotp, clearTotpState } = useAuth();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handlePasswordSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const done = await login(username, password);
      if (done) navigate('/', { replace: true });
    } catch {
      setError('Credenciais inválidas.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleTotpSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await loginWithTotp(code);
      toast.success('Sessão iniciada');
      navigate('/', { replace: true });
    } catch {
      setError('Código inválido.');
    } finally {
      setSubmitting(false);
    }
  };

  if (requiresTotp) {
    return (
      <form className="auth-form totp-step" onSubmit={handleTotpSubmit}>
        <Input
          label="Código de verificação"
          className="totp-input"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          value={code}
          onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))}
          error={error || undefined}
          autoFocus
        />
        <Button type="submit" className="auth-submit" loading={submitting} disabled={code.length < 6}>
          Entrar
        </Button>
        <button
          type="button"
          className="btn btn-ghost totp-back"
          onClick={() => {
            clearTotpState();
            setCode('');
            setError('');
          }}
        >
          Voltar
        </button>
      </form>
    );
  }

  return (
    <form className="auth-form" onSubmit={handlePasswordSubmit}>
      <Input
        label="Utilizador"
        autoComplete="username"
        value={username}
        onChange={(event) => setUsername(event.target.value)}
        autoFocus
      />
      <Input
        label="Palavra-passe"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        error={error || undefined}
      />
      <Button
        type="submit"
        className="auth-submit"
        loading={submitting}
        disabled={!username || !password}
      >
        Entrar
      </Button>
    </form>
  );
}
