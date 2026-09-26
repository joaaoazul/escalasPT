package pt.turnos.importer.internal;

import java.sql.Time;
import java.sql.Timestamp;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

import javax.sql.DataSource;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import pt.turnos.scheduling.ShiftInfo;
import pt.turnos.scheduling.ShiftRules;
import pt.turnos.scheduling.ShiftTimes;
import pt.turnos.scheduling.ShiftTypeInfo;
import pt.turnos.scheduling.Violation;
import pt.turnos.shared.Ids;

/**
 * Migração de um posto do EscalasPT para o Turnos (doc 08): posto, tipos de serviço, militares (com a mesma
 * palavra-passe) e serviços publicados, num grupo de folgas. É uma ferramenta de migração, por isso escreve
 * diretamente nas tabelas; as regras de compatibilidade dos serviços são aplicadas e os conflitos reportados.
 * Não migra: hierarquia (comando/destacamento), papéis de comandante, rascunhos, trocas e notificações.
 */
@Component
public class EscalasPtImporter {

    public record Options(String stationCode, String groupName, String commanderEmail, LocalDate from) {
    }

    public record Report(UUID postoId, String postoName, int types, int militaresCreated, int militaresReused, int shifts,
                         List<String> skipped) {
    }

    private record SourceType(UUID id, String code, String name, LocalTime start, LocalTime end, String color, boolean absence) {
    }

    private static final ZoneId LISBON = ZoneId.of("Europe/Lisbon");

    private final JdbcClient turnos;
    private final Clock clock;

    EscalasPtImporter(JdbcClient turnos, Clock clock) {
        this.turnos = turnos;
        this.clock = clock;
    }

    @Transactional
    public Report run(DataSource escalasPt, Options opt) {
        JdbcClient src = JdbcClient.create(escalasPt);
        Instant now = clock.instant();
        List<String> skipped = new ArrayList<>();

        // ── posto ──
        Map<String, Object> station = src.sql("SELECT id, name FROM stations WHERE code = :c").param("c", opt.stationCode())
                .query().singleRow();
        UUID stationId = (UUID) station.get("id");
        String name = (String) station.get("name");
        if (turnos.sql("SELECT count(*) FROM postos WHERE name = :n").param("n", name).query(Long.class).single() > 0) {
            throw new IllegalStateException("O posto '" + name + "' já existe no Turnos (importação já feita?)");
        }
        String location = name.replaceFirst("(?i)^posto territorial de\\s+", "");
        UUID postoId = Ids.newId();
        turnos.sql("INSERT INTO postos (id, name, location, time_zone, created_at) VALUES (:id, :n, :l, 'Europe/Lisbon', :now)")
                .param("id", postoId).param("n", name).param("l", location).param("now", Timestamp.from(now)).update();

        // ── tipos de serviço ──
        List<SourceType> sourceTypes = src.sql("""
                SELECT id, code, name, start_time, end_time, color, is_absence FROM shift_types
                WHERE station_id = :s AND is_active ORDER BY code""")
                .param("s", stationId)
                .query((rs, n) -> new SourceType(rs.getObject("id", UUID.class), rs.getString("code"), rs.getString("name"),
                        rs.getTime("start_time").toLocalTime(), rs.getTime("end_time").toLocalTime(), rs.getString("color"),
                        rs.getBoolean("is_absence")))
                .list();
        Map<UUID, ShiftTypeInfo> types = new HashMap<>();
        int position = 0;
        for (SourceType t : sourceTypes) {
            ShiftTypeInfo info = convert(t, postoId);
            turnos.sql("""
                    INSERT INTO shift_types (id, posto_id, code, name, kind, all_day, start_time, duration_minutes, color, swappable,
                                             accumulable, position, created_at)
                    VALUES (:id, :p, :code, :name, :kind, :allDay, :start, :dur, :color, :swap, :acc, :pos, :now)""")
                    .param("id", info.id()).param("p", postoId).param("code", info.code()).param("name", info.name())
                    .param("kind", info.kind()).param("allDay", info.allDay())
                    .param("start", info.startTime() == null ? null : Time.valueOf(info.startTime()))
                    .param("dur", info.durationMinutes()).param("color", info.color()).param("swap", info.swappable())
                    .param("acc", info.accumulable()).param("pos", position++).param("now", Timestamp.from(now)).update();
            types.put(t.id(), info);
        }

        // ── grupo de folgas e militares ──
        UUID groupId = Ids.newId();
        turnos.sql("INSERT INTO folga_groups (id, posto_id, name, created_at) VALUES (:id, :p, :n, :now)")
                .param("id", groupId).param("p", postoId).param("n", opt.groupName()).param("now", Timestamp.from(now)).update();

        List<Map<String, Object>> people = src.sql("""
                SELECT id, email, password_hash, full_name, numero_ordem FROM users
                WHERE station_id = :s AND is_active AND role <> 'admin' ORDER BY full_name""")
                .param("s", stationId).query().listOfRows();
        Map<UUID, UUID> userMap = new HashMap<>();
        int created = 0, reused = 0;
        String commander = opt.commanderEmail() == null ? "" : opt.commanderEmail().toLowerCase(Locale.ROOT);
        for (Map<String, Object> p : people) {
            String email = ((String) p.get("email")).trim().toLowerCase(Locale.ROOT);
            UUID existing = turnos.sql("SELECT id FROM users WHERE email = :e").param("e", email).query(UUID.class).optional().orElse(null);
            UUID userId;
            if (existing != null) {
                if (turnos.sql("SELECT count(*) FROM group_members WHERE user_id = :u").param("u", existing).query(Long.class).single() > 0) {
                    skipped.add("Militar " + email + ": já pertence a outro grupo de folgas");
                    continue;
                }
                userId = existing;
                reused++;
            } else {
                userId = Ids.newId();
                String number = (String) p.get("numero_ordem");
                turnos.sql("""
                        INSERT INTO users (id, email, password_hash, full_name, service_number, created_at, updated_at)
                        VALUES (:id, :e, :h, :n, :num, :now, :now)""")
                        .param("id", userId).param("e", email).param("h", "{bcrypt}" + p.get("password_hash"))
                        .param("n", p.get("full_name")).param("num", number != null && number.matches("[0-9]{1,5}") ? number : null)
                        .param("now", Timestamp.from(now)).update();
                created++;
            }
            turnos.sql("INSERT INTO group_members (group_id, user_id, role, joined_at) VALUES (:g, :u, :r, :now)")
                    .param("g", groupId).param("u", userId).param("r", email.equals(commander) ? "COMMANDER" : "MEMBER")
                    .param("now", Timestamp.from(now)).update();
            userMap.put((UUID) p.get("id"), userId);
        }

        // ── serviços publicados ──
        List<Map<String, Object>> shifts = src.sql("""
                SELECT user_id, shift_type_id, date, start_datetime, end_datetime, notes FROM shifts
                WHERE station_id = :s AND status = 'published' AND date >= :from AND shift_type_id IS NOT NULL
                ORDER BY user_id, start_datetime""")
                .param("s", stationId).param("from", opt.from()).query().listOfRows();
        Map<UUID, List<ShiftInfo>> byUser = new HashMap<>();
        int imported = 0;
        for (Map<String, Object> s : shifts) {
            UUID userId = userMap.get((UUID) s.get("user_id"));
            ShiftTypeInfo type = types.get((UUID) s.get("shift_type_id"));
            LocalDate date = ((java.sql.Date) s.get("date")).toLocalDate();
            if (userId == null || type == null) {
                continue;
            }
            LocalTime start = type.startTime();
            Integer minutes = type.durationMinutes();
            if (type.variableHours()) {
                Instant a = ((Timestamp) s.get("start_datetime")).toInstant(), b = ((Timestamp) s.get("end_datetime")).toInstant();
                start = a.atZone(LISBON).toLocalTime().withSecond(0).withNano(0);
                minutes = (int) Math.max(1, Math.min(1440, Duration.between(a, b).toMinutes()));
            }
            ShiftTimes.Span span = ShiftTimes.resolve(date, start, minutes, type.allDay(), LISBON);
            ShiftInfo info = new ShiftInfo(Ids.newId(), userId, postoId, type, date, type.allDay() ? null : start,
                    type.allDay() ? null : minutes, span.startsAt(), span.endsAt(), (String) s.get("notes"), "IMPORT", 0);
            List<ShiftInfo> mine = byUser.computeIfAbsent(userId, k -> new ArrayList<>());
            List<Violation> errors = ShiftRules.check(mine, info).stream().filter(Violation::error).toList();
            if (!errors.isEmpty()) {
                skipped.add("Serviço " + type.code() + " de " + date + " (" + userId + "): " + errors.getFirst().message());
                continue;
            }
            turnos.sql("""
                    INSERT INTO shifts (id, user_id, posto_id, shift_type_id, local_date, all_day, local_start, duration_minutes,
                                        starts_at, ends_at, notes, source, created_at, updated_at)
                    VALUES (:id, :u, :p, :t, :d, :allDay, :start, :dur, :s, :e, :notes, 'IMPORT', :now, :now)""")
                    .param("id", info.id()).param("u", userId).param("p", postoId).param("t", type.id()).param("d", date)
                    .param("allDay", type.allDay()).param("start", info.localStart() == null ? null : Time.valueOf(info.localStart()))
                    .param("dur", info.durationMinutes()).param("s", Timestamp.from(info.startsAt())).param("e", Timestamp.from(info.endsAt()))
                    .param("notes", info.notes()).param("now", Timestamp.from(now)).update();
            mine.add(info);
            imported++;
        }

        turnos.sql("""
                INSERT INTO audit_events (id, occurred_at, action, entity_type, entity_id, data)
                VALUES (:id, :now, 'posto.imported', 'posto', :p, CAST(:d AS jsonb))""")
                .param("id", Ids.newId()).param("now", Timestamp.from(now)).param("p", postoId)
                .param("d", "{\"source\":\"escalaspt\",\"station\":\"" + opt.stationCode().replace("\"", "") + "\"}").update();
        return new Report(postoId, name, types.size(), created, reused, imported, skipped);
    }

    /** Tipo do EscalasPT → Turnos. 00:00–00:00 em serviços (GRAT, T, INST) significa horário definido em cada serviço. */
    static ShiftTypeInfo convert(SourceType t, UUID postoId) {
        String code = t.code().toUpperCase(Locale.ROOT);
        String kind = t.absence() ? "ABSENCE" : code.equals("F") ? "OFF" : "WORK";
        boolean allDay = !kind.equals("WORK");
        LocalTime start = null;
        Integer minutes = null;
        if (!allDay && !t.start().equals(t.end())) {
            start = t.start();
            int m = (int) Duration.between(t.start(), t.end()).toMinutes();
            minutes = m <= 0 ? m + 1440 : m;
        }
        String color = t.color() != null && t.color().matches("^#[0-9A-Fa-f]{6}$") ? t.color() : "#6B7280";
        return new ShiftTypeInfo(Ids.newId(), postoId, code.length() > 5 ? code.substring(0, 5) : code, t.name(), kind, allDay,
                start, minutes, color, !t.absence(), code.equals("GRAT"));
    }
}
