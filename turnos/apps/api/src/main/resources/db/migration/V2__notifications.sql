-- Notificações in-app e subscrições Web Push (doc 04, módulo notifications).

CREATE TABLE notifications (
    id          uuid PRIMARY KEY,
    user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    type        text NOT NULL,
    title       text NOT NULL,
    body        text NOT NULL,
    url         text,
    read_at     timestamptz,
    created_at  timestamptz NOT NULL
);
CREATE INDEX notifications_user_idx ON notifications (user_id, created_at DESC);
CREATE INDEX notifications_unread_idx ON notifications (user_id) WHERE read_at IS NULL;

CREATE TABLE push_subscriptions (
    id          uuid PRIMARY KEY,
    user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    endpoint    text NOT NULL UNIQUE,                 -- validado contra a lista de serviços de push permitidos
    p256dh      text NOT NULL,
    auth        text NOT NULL,
    created_at  timestamptz NOT NULL,
    last_ok_at  timestamptz,
    failures    int NOT NULL DEFAULT 0
);
CREATE INDEX push_subscriptions_user_idx ON push_subscriptions (user_id);
