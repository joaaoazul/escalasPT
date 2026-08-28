export type UserRole = 'agente' | 'chefe_equipa' | 'admin';

export interface Equipa {
  id: string;
  nome: string;
  codigo: string;
}

export interface AuthUser {
  id: string;
  username: string;
  nome: string;
  nip: string;
  email: string;
  role: UserRole;
  equipa_id: string | null;
  equipa: Equipa | null;
  totp_enabled: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  requires_totp: boolean;
}
