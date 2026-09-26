package pt.turnos.identity.internal;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.sql.Timestamp;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import pt.turnos.audit.AuditLog;
import pt.turnos.identity.PasswordResets;
import pt.turnos.shared.Ids;

/** Códigos de reposição: 12 caracteres Crockford Base32 (60 bits), uso único, 24 horas. Só o SHA-256 vai para a BD. */
@Repository
class PasswordResetStore implements PasswordResets {

    static final Duration TTL = Duration.ofHours(24);
    private static final String CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
    private static final SecureRandom RANDOM = new SecureRandom();

    private final JdbcClient jdbc;
    private final AuditLog audit;
    private final Clock clock;

    PasswordResetStore(JdbcClient jdbc, AuditLog audit, Clock clock) {
        this.jdbc = jdbc;
        this.audit = audit;
        this.clock = clock;
    }

    @Override
    @Transactional
    public Issued issue(UUID userId, UUID issuedBy) {
        Instant now = clock.instant();
        jdbc.sql("DELETE FROM password_resets WHERE user_id = :u AND used_at IS NULL").param("u", userId).update();
        String code = newCode();
        Instant expires = now.plus(TTL);
        UUID id = Ids.newId();
        jdbc.sql("""
                INSERT INTO password_resets (id, user_id, token_hash, created_by, created_at, expires_at)
                VALUES (:id, :u, :h, :by, :now, :exp)""")
                .param("id", id).param("u", userId).param("h", hash(code)).param("by", issuedBy)
                .param("now", Timestamp.from(now)).param("exp", Timestamp.from(expires)).update();
        audit.record(issuedBy, "password-reset.issued", "user", userId, Map.of("resetId", id.toString()));
        return new Issued(code, expires);
    }

    /** Consome o código de forma atómica e devolve o militar a quem pertence. */
    Optional<UUID> consume(String code, Instant now) {
        return jdbc.sql("""
                UPDATE password_resets SET used_at = :now
                WHERE token_hash = :h AND used_at IS NULL AND expires_at > :now
                RETURNING user_id""")
                .param("h", hash(code)).param("now", Timestamp.from(now)).query(UUID.class).optional();
    }

    static String newCode() {
        StringBuilder sb = new StringBuilder(14);
        for (int i = 0; i < 12; i++) {
            if (i > 0 && i % 4 == 0) {
                sb.append('-');
            }
            sb.append(CROCKFORD.charAt(RANDOM.nextInt(32)));
        }
        return sb.toString();
    }

    static byte[] hash(String code) {
        String canonical = code == null ? "" : code.replace("-", "").replace(" ", "").trim().toUpperCase(Locale.ROOT);
        try {
            return MessageDigest.getInstance("SHA-256").digest(canonical.getBytes(StandardCharsets.UTF_8));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
