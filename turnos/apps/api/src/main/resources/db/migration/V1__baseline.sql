-- Turnos — esquema base (doc 03 e doc 09).
-- Os identificadores são UUIDv7 gerados pela aplicação.

CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ─────────────────────────── identity ───────────────────────────
CREATE TABLE users (
    id              uuid PRIMARY KEY,
    email           citext NOT NULL UNIQUE,
    password_hash   text NOT NULL,
    full_name       text NOT NULL CHECK (length(full_name) BETWEEN 1 AND 120),
    rank            text CHECK (length(rank) <= 40),              -- posto: Guarda, Cabo, …
    service_number  text CHECK (service_number ~ '^[0-9]{1,5}$'),  -- n.º de ordem
    system_role     text NOT NULL DEFAULT 'USER' CHECK (system_role IN ('USER', 'ADMIN')),
    failed_logins   int NOT NULL DEFAULT 0,
    locked_until    timestamptz,
    created_at      timestamptz NOT NULL,
    updated_at      timestamptz NOT NULL
);

CREATE TABLE sessions (
    id             uuid PRIMARY KEY,
    user_id        uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    refresh_hash   bytea NOT NULL UNIQUE,
    previous_hash  bytea,
    user_agent     text,
    created_at     timestamptz NOT NULL,
    last_seen_at   timestamptz NOT NULL,
    expires_at     timestamptz NOT NULL,
    revoked_at     timestamptz
);
CREATE INDEX sessions_user_idx ON sessions (user_id) WHERE revoked_at IS NULL;
CREATE INDEX sessions_previous_idx ON sessions (previous_hash) WHERE previous_hash IS NOT NULL;

-- ─────────────────────────── units: posto e grupos de folgas ───────────────────────────
CREATE TABLE postos (
    id          uuid PRIMARY KEY,
    name        text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),   -- "Posto Territorial de Castro Marim"
    location    text NOT NULL CHECK (length(location) BETWEEN 1 AND 80), -- "Castro Marim" (Quartel em …)
    time_zone   text NOT NULL DEFAULT 'Europe/Lisbon',
    created_at  timestamptz NOT NULL
);

CREATE TABLE folga_groups (
    id          uuid PRIMARY KEY,
    posto_id    uuid NOT NULL REFERENCES postos (id) ON DELETE CASCADE,
    name        text NOT NULL CHECK (length(name) BETWEEN 1 AND 40),     -- "Grupo 2"
    created_at  timestamptz NOT NULL,
    UNIQUE (posto_id, name)
);

-- Um militar pertence a um só grupo de folgas (e, por isso, a um só posto).
CREATE TABLE group_members (
    group_id   uuid NOT NULL REFERENCES folga_groups (id) ON DELETE CASCADE,
    user_id    uuid NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
    role       text NOT NULL CHECK (role IN ('COMMANDER', 'MEMBER')),   -- COMMANDER = comandante de grupo
    joined_at  timestamptz NOT NULL,
    PRIMARY KEY (group_id, user_id)
);
CREATE UNIQUE INDEX group_one_commander ON group_members (group_id) WHERE role = 'COMMANDER';

CREATE TABLE group_invites (
    id            uuid PRIMARY KEY,
    group_id      uuid NOT NULL REFERENCES folga_groups (id) ON DELETE CASCADE,
    token_hash    bytea NOT NULL UNIQUE,
    email         citext,
    invitee_name  text,
    invitee_rank  text,
    role          text NOT NULL DEFAULT 'MEMBER' CHECK (role IN ('COMMANDER', 'MEMBER')),
    expires_at    timestamptz NOT NULL,
    created_by    uuid REFERENCES users (id) ON DELETE SET NULL,
    created_at    timestamptz NOT NULL,
    accepted_by   uuid REFERENCES users (id) ON DELETE SET NULL,
    accepted_at   timestamptz,
    revoked_at    timestamptz
);
CREATE INDEX group_invites_group_idx ON group_invites (group_id);

-- ─────────────────────────── scheduling: tipos de serviço e serviços ───────────────────────────
CREATE TABLE shift_types (
    id                uuid PRIMARY KEY,
    posto_id          uuid NOT NULL REFERENCES postos (id) ON DELETE CASCADE,
    code              text NOT NULL CHECK (length(code) BETWEEN 1 AND 5),
    name              text NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
    kind              text NOT NULL CHECK (kind IN ('WORK', 'OFF', 'ABSENCE')),
    all_day           boolean NOT NULL,
    start_time        time,
    duration_minutes  int CHECK (duration_minutes BETWEEN 1 AND 1440),
    color             text NOT NULL CHECK (color ~ '^#[0-9A-Fa-f]{6}$'),
    swappable         boolean NOT NULL,
    accumulable       boolean NOT NULL DEFAULT false,  -- pode coexistir com outro serviço no dia (ex.: GRAT)
    position          int NOT NULL DEFAULT 0,
    archived_at       timestamptz,
    created_at        timestamptz NOT NULL,
    -- Dia inteiro: sem horas. Com horas: fixas (AT1 00–08) ou variáveis, definidas em cada serviço (GRAT, T, INST).
    CHECK ((all_day AND start_time IS NULL AND duration_minutes IS NULL)
        OR (NOT all_day AND (start_time IS NULL) = (duration_minutes IS NULL)))
);
CREATE UNIQUE INDEX shift_types_code_uq ON shift_types (posto_id, upper(code)) WHERE archived_at IS NULL;

CREATE TABLE shifts (
    id              uuid PRIMARY KEY,
    user_id         uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    posto_id        uuid NOT NULL REFERENCES postos (id) ON DELETE CASCADE,
    shift_type_id   uuid NOT NULL REFERENCES shift_types (id) ON DELETE RESTRICT,
    local_date      date NOT NULL,
    all_day         boolean NOT NULL,
    local_start     time,                                   -- hora local de início, como definida
    duration_minutes int CHECK (duration_minutes BETWEEN 1 AND 1440),
    starts_at       timestamptz NOT NULL,                   -- resolvidos com o fuso do posto
    ends_at         timestamptz NOT NULL,
    time_range      tstzrange GENERATED ALWAYS AS (tstzrange(starts_at, ends_at, '[)')) STORED,
    notes           text CHECK (length(notes) <= 1000),
    source          text NOT NULL DEFAULT 'MANUAL' CHECK (source IN ('MANUAL', 'PAINT', 'SWAP', 'IMPORT')),
    swap_request_id uuid,
    version         int NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL,
    updated_at      timestamptz NOT NULL,
    CHECK (ends_at > starts_at),
    CHECK (all_day = (local_start IS NULL) AND (local_start IS NULL) = (duration_minutes IS NULL)),
    -- Invariantes centrais. DEFERRABLE para a troca poder mudar os dois donos na mesma transação.
    CONSTRAINT shifts_no_overlap EXCLUDE USING gist (user_id WITH =, time_range WITH &&)
        WHERE (NOT all_day) DEFERRABLE INITIALLY IMMEDIATE,
    CONSTRAINT shifts_one_all_day EXCLUDE USING gist (user_id WITH =, local_date WITH =)
        WHERE (all_day) DEFERRABLE INITIALLY IMMEDIATE
);
CREATE INDEX shifts_user_date_idx  ON shifts (user_id, local_date);
CREATE INDEX shifts_posto_date_idx ON shifts (posto_id, local_date);

-- ─────────────────────────── swaps ───────────────────────────
CREATE TABLE swap_requests (
    id                        uuid PRIMARY KEY,
    posto_id                  uuid NOT NULL REFERENCES postos (id) ON DELETE CASCADE,
    requester_id              uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    requester_shift_id        uuid NOT NULL REFERENCES shifts (id) ON DELETE CASCADE,
    requester_shift_version   int NOT NULL,
    target_id                 uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    target_shift_id           uuid NOT NULL REFERENCES shifts (id) ON DELETE CASCADE,
    target_shift_version      int NOT NULL,
    status                    text NOT NULL CHECK (status IN
                                ('PENDENTE', 'EM_ESPERA', 'ACEITE', 'RECUSADA', 'CANCELADA', 'EXPIRADA')),
    message                   text CHECK (length(message) <= 280),
    hold_message              text CHECK (length(hold_message) <= 280),
    decline_reason            text CHECK (length(decline_reason) <= 280),
    held_at                   timestamptz,
    responded_at              timestamptz,
    expires_at                timestamptz NOT NULL,
    version                   int NOT NULL DEFAULT 0,
    created_at                timestamptz NOT NULL,
    updated_at                timestamptz NOT NULL,
    CHECK (requester_id <> target_id)
);
CREATE UNIQUE INDEX swap_one_active_req ON swap_requests (requester_shift_id) WHERE status IN ('PENDENTE', 'EM_ESPERA');
CREATE UNIQUE INDEX swap_one_active_tgt ON swap_requests (target_shift_id)    WHERE status IN ('PENDENTE', 'EM_ESPERA');
CREATE INDEX swap_requester_idx ON swap_requests (requester_id, created_at DESC);
CREATE INDEX swap_target_idx    ON swap_requests (target_id, created_at DESC);
CREATE INDEX swap_expiry_idx    ON swap_requests (expires_at) WHERE status IN ('PENDENTE', 'EM_ESPERA');

ALTER TABLE shifts ADD CONSTRAINT shifts_swap_fk
    FOREIGN KEY (swap_request_id) REFERENCES swap_requests (id) ON DELETE SET NULL;

-- Documento "Troca de Serviço" emitido na aceitação: imutável.
CREATE TABLE swap_documents (
    swap_request_id  uuid PRIMARY KEY REFERENCES swap_requests (id) ON DELETE RESTRICT,
    reference        char(8) NOT NULL UNIQUE,
    pdf              bytea NOT NULL,
    sha256           bytea NOT NULL,
    snapshot         jsonb NOT NULL,
    issued_at        timestamptz NOT NULL
);

-- ─────────────────────────── audit ───────────────────────────
CREATE TABLE audit_events (
    id           uuid PRIMARY KEY,
    occurred_at  timestamptz NOT NULL,
    actor_id     uuid,
    action       text NOT NULL,
    entity_type  text NOT NULL,
    entity_id    uuid,
    data         jsonb
);
CREATE INDEX audit_entity_idx ON audit_events (entity_type, entity_id, occurred_at DESC);
