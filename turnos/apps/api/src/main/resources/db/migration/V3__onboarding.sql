-- Link do grupo (convite reutilizável) e reposição de palavra-passe pelo comandante de grupo.

-- Um convite individual tem max_uses = 1; o link do grupo aceita vários militares até esgotar, expirar ou ser desativado.
-- accepted_at marca o momento em que o convite deixou de servir por ter sido usado (esgotado).
ALTER TABLE group_invites
    ADD COLUMN max_uses  int NOT NULL DEFAULT 1 CHECK (max_uses BETWEEN 1 AND 100),
    ADD COLUMN use_count int NOT NULL DEFAULT 0 CHECK (use_count >= 0);
UPDATE group_invites SET use_count = 1 WHERE accepted_at IS NOT NULL;
ALTER TABLE group_invites ADD CHECK (use_count <= max_uses);
ALTER TABLE group_invites ADD CHECK (max_uses = 1 OR (email IS NULL AND role = 'MEMBER'));

-- Código de uso único, dado em mão pelo comandante de grupo ao militar que se esqueceu da palavra-passe.
CREATE TABLE password_resets (
    id          uuid PRIMARY KEY,
    user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash  bytea NOT NULL UNIQUE,
    created_by  uuid REFERENCES users (id) ON DELETE SET NULL,
    created_at  timestamptz NOT NULL,
    expires_at  timestamptz NOT NULL,
    used_at     timestamptz
);
CREATE INDEX password_resets_user_idx ON password_resets (user_id) WHERE used_at IS NULL;
