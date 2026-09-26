package pt.turnos.scheduling;

import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.Map;

/** Resultado de uma regra: ERROR bloqueia, WARNING só avisa. */
public record Violation(String code, Severity severity, LocalDate date, String message) {

    public enum Severity { ERROR, WARNING }

    public boolean error() {
        return severity == Severity.ERROR;
    }

    public Map<String, Object> toMap() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("code", code);
        m.put("severity", severity.name());
        m.put("date", date.toString());
        m.put("message", message);
        return m;
    }
}
