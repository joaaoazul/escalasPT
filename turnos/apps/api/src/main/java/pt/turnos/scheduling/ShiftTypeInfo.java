package pt.turnos.scheduling;

import java.time.LocalTime;
import java.util.UUID;

/** Tipo de serviço do posto (AT1, OC2, GRAT, F, FER…). */
public record ShiftTypeInfo(UUID id, UUID postoId, String code, String name, String kind, boolean allDay,
                            LocalTime startTime, Integer durationMinutes, String color, boolean swappable, boolean accumulable) {

    public boolean work() {
        return "WORK".equals(kind);
    }

    /** Folga e ausências ocupam o dia inteiro e não admitem outro serviço (regra do EscalasPT). */
    public boolean fullDay() {
        return allDay;
    }

    public boolean variableHours() {
        return !allDay && startTime == null;
    }
}
