package pt.turnos.scheduling.internal;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Time;
import java.sql.Timestamp;
import java.time.Instant;
import java.time.LocalDate;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import pt.turnos.scheduling.ShiftInfo;

@Repository
class ShiftRepository {

    private static final String SELECT = """
            SELECT s.id, s.user_id, s.posto_id, s.local_date, s.local_start, s.duration_minutes, s.starts_at, s.ends_at,
                   s.notes, s.source, s.version,
                   t.id AS t_id, t.posto_id AS t_posto_id, t.code AS t_code, t.name AS t_name, t.kind AS t_kind,
                   t.all_day AS t_all_day, t.start_time AS t_start_time, t.duration_minutes AS t_duration_minutes,
                   t.color AS t_color, t.swappable AS t_swappable, t.accumulable AS t_accumulable
            FROM shifts s JOIN shift_types t ON t.id = s.shift_type_id""";

    private final JdbcClient jdbc;

    ShiftRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    void insert(ShiftInfo s, Instant now) {
        jdbc.sql("""
                INSERT INTO shifts (id, user_id, posto_id, shift_type_id, local_date, all_day, local_start, duration_minutes,
                                    starts_at, ends_at, notes, source, created_at, updated_at)
                VALUES (:id, :u, :p, :t, :d, :allDay, :start, :dur, :s, :e, :notes, :src, :now, :now)""")
                .param("id", s.id()).param("u", s.userId()).param("p", s.postoId()).param("t", s.type().id())
                .param("d", s.date()).param("allDay", s.allDay())
                .param("start", s.localStart() == null ? null : Time.valueOf(s.localStart())).param("dur", s.durationMinutes())
                .param("s", Timestamp.from(s.startsAt())).param("e", Timestamp.from(s.endsAt()))
                .param("notes", s.notes()).param("src", s.source()).param("now", Timestamp.from(now)).update();
    }

    int updateNotes(UUID id, int version, String notes, Instant now) {
        return jdbc.sql("UPDATE shifts SET notes = :n, version = version + 1, updated_at = :now WHERE id = :id AND version = :v")
                .param("id", id).param("v", version).param("n", notes).param("now", Timestamp.from(now)).update();
    }

    int delete(UUID id) {
        return jdbc.sql("DELETE FROM shifts WHERE id = :id").param("id", id).update();
    }

    Optional<ShiftInfo> find(UUID id) {
        return jdbc.sql(SELECT + " WHERE s.id = :id").param("id", id).query(ShiftRepository::map).optional();
    }

    List<ShiftInfo> lockForUpdate(Collection<UUID> ids) {
        return jdbc.sql(SELECT + " WHERE s.id IN (:ids) ORDER BY s.id FOR UPDATE OF s").param("ids", ids)
                .query(ShiftRepository::map).list();
    }

    List<ShiftInfo> ofUser(UUID userId, LocalDate from, LocalDate to) {
        return jdbc.sql(SELECT + " WHERE s.user_id = :u AND s.local_date BETWEEN :f AND :t ORDER BY s.starts_at")
                .param("u", userId).param("f", from).param("t", to).query(ShiftRepository::map).list();
    }

    List<ShiftInfo> ofPosto(UUID postoId, LocalDate from, LocalDate to) {
        return jdbc.sql(SELECT + " WHERE s.posto_id = :p AND s.local_date BETWEEN :f AND :t ORDER BY s.local_date, s.starts_at")
                .param("p", postoId).param("f", from).param("t", to).query(ShiftRepository::map).list();
    }

    /** Serviços com pedido de troca ativo não podem ser alterados nem apagados. */
    boolean hasActiveSwap(UUID shiftId) {
        return jdbc.sql("""
                SELECT count(*) FROM swap_requests
                WHERE (requester_shift_id = :id OR target_shift_id = :id) AND status IN ('PENDENTE', 'EM_ESPERA')""")
                .param("id", shiftId).query(Long.class).single() > 0;
    }

    void setOwner(UUID shiftId, UUID userId, UUID swapRequestId, Instant now) {
        jdbc.sql("""
                UPDATE shifts SET user_id = :u, source = 'SWAP', swap_request_id = :sr, version = version + 1, updated_at = :now
                WHERE id = :id""")
                .param("id", shiftId).param("u", userId).param("sr", swapRequestId).param("now", Timestamp.from(now)).update();
    }

    void deferConstraints() {
        jdbc.sql("SET CONSTRAINTS shifts_no_overlap, shifts_one_all_day DEFERRED").update();
    }

    private static ShiftInfo map(ResultSet rs, int n) throws SQLException {
        Time start = rs.getTime("local_start");
        return new ShiftInfo(rs.getObject("id", UUID.class), rs.getObject("user_id", UUID.class), rs.getObject("posto_id", UUID.class),
                ShiftTypeRepository.mapWithPrefix(rs, "t_"), rs.getObject("local_date", LocalDate.class),
                start == null ? null : start.toLocalTime(), (Integer) rs.getObject("duration_minutes"),
                rs.getTimestamp("starts_at").toInstant(), rs.getTimestamp("ends_at").toInstant(),
                rs.getString("notes"), rs.getString("source"), rs.getInt("version"));
    }
}
