package pt.turnos.scheduling.internal;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Time;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import pt.turnos.scheduling.ShiftTypeInfo;

@Repository
class ShiftTypeRepository {

    static final String COLUMNS = "id, posto_id, code, name, kind, all_day, start_time, duration_minutes, color, swappable, accumulable";

    private final JdbcClient jdbc;

    ShiftTypeRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    void insert(ShiftTypeInfo t, int position, Instant now) {
        jdbc.sql("""
                INSERT INTO shift_types (id, posto_id, code, name, kind, all_day, start_time, duration_minutes, color, swappable,
                                         accumulable, position, created_at)
                VALUES (:id, :p, :code, :name, :kind, :allDay, :start, :dur, :color, :swap, :acc, :pos, :now)""")
                .param("id", t.id()).param("p", t.postoId()).param("code", t.code()).param("name", t.name())
                .param("kind", t.kind()).param("allDay", t.allDay())
                .param("start", t.startTime() == null ? null : Time.valueOf(t.startTime()))
                .param("dur", t.durationMinutes()).param("color", t.color()).param("swap", t.swappable())
                .param("acc", t.accumulable()).param("pos", position).param("now", Timestamp.from(now)).update();
    }

    List<ShiftTypeInfo> ofPosto(UUID postoId) {
        return jdbc.sql("SELECT " + COLUMNS + " FROM shift_types WHERE posto_id = :p AND archived_at IS NULL ORDER BY position, code")
                .param("p", postoId).query(ShiftTypeRepository::map).list();
    }

    Optional<ShiftTypeInfo> find(UUID id) {
        return jdbc.sql("SELECT " + COLUMNS + " FROM shift_types WHERE id = :id").param("id", id).query(ShiftTypeRepository::map).optional();
    }

    static ShiftTypeInfo map(ResultSet rs, int n) throws SQLException {
        return mapWithPrefix(rs, "");
    }

    static ShiftTypeInfo mapWithPrefix(ResultSet rs, String p) throws SQLException {
        Time start = rs.getTime(p + "start_time");
        return new ShiftTypeInfo(rs.getObject(p + "id", UUID.class), rs.getObject(p + "posto_id", UUID.class),
                rs.getString(p + "code"), rs.getString(p + "name"), rs.getString(p + "kind"), rs.getBoolean(p + "all_day"),
                start == null ? null : start.toLocalTime(), (Integer) rs.getObject(p + "duration_minutes"), rs.getString(p + "color"),
                rs.getBoolean(p + "swappable"), rs.getBoolean(p + "accumulable"));
    }
}
