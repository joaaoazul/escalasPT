package pt.turnos.audit;

import java.sql.Timestamp;
import java.time.Clock;
import java.util.Map;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;

import pt.turnos.shared.Ids;
import tools.jackson.databind.json.JsonMapper;

/** Registo de auditoria append-only, escrito na mesma transação da alteração. */
@Component
public class AuditLog {

    private final JdbcClient jdbc;
    private final Clock clock;
    private final JsonMapper json;

    AuditLog(JdbcClient jdbc, Clock clock, JsonMapper json) {
        this.jdbc = jdbc;
        this.clock = clock;
        this.json = json;
    }

    public void record(UUID actorId, String action, String entityType, UUID entityId, Map<String, ?> data) {
        jdbc.sql("""
                INSERT INTO audit_events (id, occurred_at, actor_id, action, entity_type, entity_id, data)
                VALUES (:id, :at, :actor, :action, :type, :entity, CAST(:data AS jsonb))""")
                .param("id", Ids.newId())
                .param("at", Timestamp.from(clock.instant()))
                .param("actor", actorId)
                .param("action", action)
                .param("type", entityType)
                .param("entity", entityId)
                .param("data", data == null ? null : json.writeValueAsString(data))
                .update();
    }
}
