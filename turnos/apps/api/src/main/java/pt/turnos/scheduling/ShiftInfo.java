package pt.turnos.scheduling;

import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.util.UUID;

/** Um serviço de um militar num dia, com os instantes reais já resolvidos no fuso do posto. */
public record ShiftInfo(UUID id, UUID userId, UUID postoId, ShiftTypeInfo type, LocalDate date, LocalTime localStart,
                        Integer durationMinutes, Instant startsAt, Instant endsAt, String notes, String source, int version) {

    public boolean allDay() {
        return type.allDay();
    }

    /** Mesmo serviço com outro dono (o que acontece numa troca). */
    public ShiftInfo ownedBy(UUID newOwner) {
        return new ShiftInfo(id, newOwner, postoId, type, date, localStart, durationMinutes, startsAt, endsAt, notes, source, version);
    }
}
