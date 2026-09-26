package pt.turnos.identity.internal;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
class Sessions {

    record Session(UUID id, UUID userId, Instant expiresAt, Instant revokedAt) {
    }

    private final JdbcClient jdbc;

    Sessions(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    void create(UUID id, UUID userId, byte[] refreshHash, String userAgent, Instant now, Instant expiresAt) {
        jdbc.sql("""
                INSERT INTO sessions (id, user_id, refresh_hash, user_agent, created_at, last_seen_at, expires_at)
                VALUES (:id, :user, :hash, :ua, :now, :now, :exp)""")
                .param("id", id).param("user", userId).param("hash", refreshHash)
                .param("ua", userAgent == null ? null : userAgent.substring(0, Math.min(userAgent.length(), 300)))
                .param("now", Timestamp.from(now)).param("exp", Timestamp.from(expiresAt)).update();
    }

    /** Sessão cujo refresh token atual tem este hash, bloqueada para a rotação. */
    Optional<Session> byCurrentHashForUpdate(byte[] hash) {
        return jdbc.sql("SELECT id, user_id, expires_at, revoked_at FROM sessions WHERE refresh_hash = :h FOR UPDATE")
                .param("h", hash).query(Sessions::map).optional();
    }

    Optional<Session> byPreviousHash(byte[] hash) {
        return jdbc.sql("SELECT id, user_id, expires_at, revoked_at FROM sessions WHERE previous_hash = :h")
                .param("h", hash).query(Sessions::map).optional();
    }

    void rotate(UUID id, byte[] oldHash, byte[] newHash, Instant now) {
        jdbc.sql("UPDATE sessions SET previous_hash = :old, refresh_hash = :new, last_seen_at = :now WHERE id = :id")
                .param("id", id).param("old", oldHash).param("new", newHash).param("now", Timestamp.from(now)).update();
    }

    void revoke(UUID id, Instant now) {
        jdbc.sql("UPDATE sessions SET revoked_at = :now WHERE id = :id AND revoked_at IS NULL")
                .param("id", id).param("now", Timestamp.from(now)).update();
    }

    boolean isActive(UUID id, Instant now) {
        return jdbc.sql("SELECT count(*) FROM sessions WHERE id = :id AND revoked_at IS NULL AND expires_at > :now")
                .param("id", id).param("now", Timestamp.from(now)).query(Long.class).single() > 0;
    }

    private static Session map(java.sql.ResultSet rs, int n) throws java.sql.SQLException {
        Timestamp revoked = rs.getTimestamp("revoked_at");
        return new Session(rs.getObject("id", UUID.class), rs.getObject("user_id", UUID.class),
                rs.getTimestamp("expires_at").toInstant(), revoked == null ? null : revoked.toInstant());
    }
}
