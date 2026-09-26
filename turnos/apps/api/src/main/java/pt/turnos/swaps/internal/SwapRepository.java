package pt.turnos.swaps.internal;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
class SwapRepository {

    record Document(UUID swapId, String reference, byte[] pdf, byte[] sha256, Instant issuedAt) {
    }

    private final JdbcClient jdbc;

    SwapRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    void insert(SwapRow s, Instant now) {
        jdbc.sql("""
                INSERT INTO swap_requests (id, posto_id, requester_id, requester_shift_id, requester_shift_version, target_id,
                    target_shift_id, target_shift_version, status, message, expires_at, created_at, updated_at)
                VALUES (:id, :p, :ru, :rs, :rv, :tu, :ts, :tv, 'PENDENTE', :msg, :exp, :now, :now)""")
                .param("id", s.id()).param("p", s.postoId()).param("ru", s.requesterId()).param("rs", s.requesterShiftId())
                .param("rv", s.requesterShiftVersion()).param("tu", s.targetId()).param("ts", s.targetShiftId())
                .param("tv", s.targetShiftVersion()).param("msg", s.message()).param("exp", Timestamp.from(s.expiresAt()))
                .param("now", Timestamp.from(now)).update();
    }

    Optional<SwapRow> find(UUID id) {
        return jdbc.sql("SELECT * FROM swap_requests WHERE id = :id").param("id", id).query(SwapRepository::map).optional();
    }

    Optional<SwapRow> lock(UUID id) {
        return jdbc.sql("SELECT * FROM swap_requests WHERE id = :id FOR UPDATE").param("id", id).query(SwapRepository::map).optional();
    }

    boolean shiftHasActive(UUID shiftId) {
        return jdbc.sql("""
                SELECT count(*) FROM swap_requests
                WHERE (requester_shift_id = :s OR target_shift_id = :s) AND status IN ('PENDENTE', 'EM_ESPERA')""")
                .param("s", shiftId).query(Long.class).single() > 0;
    }

    void hold(UUID id, String message, Instant now) {
        jdbc.sql("UPDATE swap_requests SET status = 'EM_ESPERA', hold_message = :m, held_at = :now, updated_at = :now, version = version + 1 WHERE id = :id")
                .param("id", id).param("m", message).param("now", Timestamp.from(now)).update();
    }

    void close(UUID id, String status, String reason, Instant now) {
        jdbc.sql("""
                UPDATE swap_requests SET status = :st, decline_reason = coalesce(:r, decline_reason), responded_at = :now,
                       updated_at = :now, version = version + 1
                WHERE id = :id""")
                .param("id", id).param("st", status).param("r", reason).param("now", Timestamp.from(now)).update();
    }

    /** Outros pedidos ativos que envolvem estes serviços ficam sem efeito quando a troca é aceite. */
    int cancelOthersInvolving(UUID exceptId, UUID shiftA, UUID shiftB, Instant now) {
        return jdbc.sql("""
                UPDATE swap_requests SET status = 'CANCELADA', responded_at = :now, updated_at = :now, version = version + 1
                WHERE id <> :id AND status IN ('PENDENTE', 'EM_ESPERA')
                  AND (requester_shift_id IN (:a, :b) OR target_shift_id IN (:a, :b))""")
                .param("id", exceptId).param("a", shiftA).param("b", shiftB).param("now", Timestamp.from(now)).update();
    }

    int cancelActiveOf(UUID userId, Instant now) {
        return jdbc.sql("""
                UPDATE swap_requests SET status = 'CANCELADA', responded_at = :now, updated_at = :now, version = version + 1
                WHERE status IN ('PENDENTE', 'EM_ESPERA') AND (requester_id = :u OR target_id = :u)""")
                .param("u", userId).param("now", Timestamp.from(now)).update();
    }

    /** Art. 34.º, n.º 2: os pedidos valem até ao fim da véspera do serviço. Idempotente e seguro com várias instâncias. */
    List<UUID> expire(Instant now) {
        return jdbc.sql("""
                UPDATE swap_requests SET status = 'EXPIRADA', responded_at = :now, updated_at = :now, version = version + 1
                WHERE status IN ('PENDENTE', 'EM_ESPERA') AND expires_at <= :now
                RETURNING id""")
                .param("now", Timestamp.from(now)).query(UUID.class).list();
    }

    List<SwapRow> ofUser(UUID userId, String box) {
        String where = switch (box) {
            case "received" -> "target_id = :u AND status IN ('PENDENTE', 'EM_ESPERA')";
            case "sent" -> "requester_id = :u AND status IN ('PENDENTE', 'EM_ESPERA')";
            default -> "(requester_id = :u OR target_id = :u) AND status NOT IN ('PENDENTE', 'EM_ESPERA')";
        };
        return jdbc.sql("SELECT * FROM swap_requests WHERE " + where + " ORDER BY created_at DESC LIMIT 200")
                .param("u", userId).query(SwapRepository::map).list();
    }

    void insertDocument(UUID swapId, String reference, byte[] pdf, byte[] sha256, String snapshotJson, Instant now) {
        jdbc.sql("""
                INSERT INTO swap_documents (swap_request_id, reference, pdf, sha256, snapshot, issued_at)
                VALUES (:id, :ref, :pdf, :sha, CAST(:snap AS jsonb), :now)""")
                .param("id", swapId).param("ref", reference).param("pdf", pdf).param("sha", sha256).param("snap", snapshotJson)
                .param("now", Timestamp.from(now)).update();
    }

    Optional<Document> document(UUID swapId) {
        return jdbc.sql("SELECT swap_request_id, reference, pdf, sha256, issued_at FROM swap_documents WHERE swap_request_id = :id")
                .param("id", swapId)
                .query((rs, n) -> new Document(rs.getObject(1, UUID.class), rs.getString(2).trim(), rs.getBytes(3), rs.getBytes(4),
                        rs.getTimestamp(5).toInstant()))
                .optional();
    }

    Optional<String> documentReference(UUID swapId) {
        return jdbc.sql("SELECT reference FROM swap_documents WHERE swap_request_id = :id").param("id", swapId)
                .query(String.class).optional().map(String::trim);
    }

    private static SwapRow map(ResultSet rs, int n) throws SQLException {
        return new SwapRow(rs.getObject("id", UUID.class), rs.getObject("posto_id", UUID.class), rs.getObject("requester_id", UUID.class),
                rs.getObject("requester_shift_id", UUID.class), rs.getInt("requester_shift_version"), rs.getObject("target_id", UUID.class),
                rs.getObject("target_shift_id", UUID.class), rs.getInt("target_shift_version"), rs.getString("status"),
                rs.getString("message"), rs.getString("hold_message"), rs.getString("decline_reason"), ts(rs, "held_at"),
                ts(rs, "responded_at"), ts(rs, "expires_at"), ts(rs, "created_at"), rs.getInt("version"));
    }

    private static Instant ts(ResultSet rs, String c) throws SQLException {
        Timestamp t = rs.getTimestamp(c);
        return t == null ? null : t.toInstant();
    }
}
