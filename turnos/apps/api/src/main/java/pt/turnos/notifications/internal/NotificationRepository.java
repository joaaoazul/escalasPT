package pt.turnos.notifications.internal;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
class NotificationRepository {

    record Notification(UUID id, String type, String title, String body, String url, Instant readAt, Instant createdAt) {
    }

    record Subscription(UUID id, UUID userId, String endpoint, String p256dh, String auth) {
    }

    private final JdbcClient jdbc;

    NotificationRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    void insert(UUID id, UUID userId, String type, String title, String body, String url, Instant now) {
        jdbc.sql("INSERT INTO notifications (id, user_id, type, title, body, url, created_at) VALUES (:id, :u, :type, :t, :b, :url, :now)")
                .param("id", id).param("u", userId).param("type", type).param("t", title).param("b", body).param("url", url)
                .param("now", Timestamp.from(now)).update();
    }

    List<Notification> latest(UUID userId, int limit) {
        return jdbc.sql("SELECT id, type, title, body, url, read_at, created_at FROM notifications WHERE user_id = :u ORDER BY created_at DESC LIMIT :n")
                .param("u", userId).param("n", limit)
                .query((rs, n) -> new Notification(rs.getObject("id", UUID.class), rs.getString("type"), rs.getString("title"), rs.getString("body"),
                        rs.getString("url"), rs.getTimestamp("read_at") == null ? null : rs.getTimestamp("read_at").toInstant(),
                        rs.getTimestamp("created_at").toInstant()))
                .list();
    }

    long unread(UUID userId) {
        return jdbc.sql("SELECT count(*) FROM notifications WHERE user_id = :u AND read_at IS NULL").param("u", userId).query(Long.class).single();
    }

    int markAllRead(UUID userId, Instant now) {
        return jdbc.sql("UPDATE notifications SET read_at = :now WHERE user_id = :u AND read_at IS NULL")
                .param("u", userId).param("now", Timestamp.from(now)).update();
    }

    int deleteOlderThan(Instant cutoff) {
        return jdbc.sql("DELETE FROM notifications WHERE created_at < :c").param("c", Timestamp.from(cutoff)).update();
    }

    // ── Web Push ──

    /** A mesma subscrição (endpoint) passa para o utilizador que a registou por último (ex.: outra conta no mesmo telemóvel). */
    void upsertSubscription(UUID id, UUID userId, String endpoint, String p256dh, String auth, Instant now) {
        jdbc.sql("""
                INSERT INTO push_subscriptions (id, user_id, endpoint, p256dh, auth, created_at) VALUES (:id, :u, :e, :p, :a, :now)
                ON CONFLICT (endpoint) DO UPDATE SET user_id = :u, p256dh = :p, auth = :a, failures = 0""")
                .param("id", id).param("u", userId).param("e", endpoint).param("p", p256dh).param("a", auth).param("now", Timestamp.from(now))
                .update();
    }

    int deleteSubscription(UUID userId, String endpoint) {
        return jdbc.sql("DELETE FROM push_subscriptions WHERE user_id = :u AND endpoint = :e").param("u", userId).param("e", endpoint).update();
    }

    List<Subscription> subscriptionsOf(UUID userId) {
        return jdbc.sql("SELECT id, user_id, endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = :u").param("u", userId)
                .query((rs, n) -> new Subscription(rs.getObject("id", UUID.class), rs.getObject("user_id", UUID.class), rs.getString("endpoint"),
                        rs.getString("p256dh"), rs.getString("auth")))
                .list();
    }

    void pushOk(UUID id, Instant now) {
        jdbc.sql("UPDATE push_subscriptions SET last_ok_at = :now, failures = 0 WHERE id = :id").param("id", id).param("now", Timestamp.from(now)).update();
    }

    /** Falhas repetidas (ou 404/410 do serviço de push) removem a subscrição. */
    void pushFailed(UUID id, boolean gone) {
        if (gone) {
            jdbc.sql("DELETE FROM push_subscriptions WHERE id = :id").param("id", id).update();
        } else {
            jdbc.sql("UPDATE push_subscriptions SET failures = failures + 1 WHERE id = :id").param("id", id).update();
            jdbc.sql("DELETE FROM push_subscriptions WHERE id = :id AND failures >= 5").param("id", id).update();
        }
    }
}
