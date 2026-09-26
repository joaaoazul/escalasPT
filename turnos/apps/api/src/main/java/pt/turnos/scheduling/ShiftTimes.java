package pt.turnos.scheduling;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;

/**
 * Tempo local → instantes reais (doc 02, §2.6). O serviço começa na data e hora locais e dura
 * {@code durationMinutes} minutos reais: um AT1 00–08 na noite da mudança para a hora de inverno
 * termina às 07:00 locais. Horas inexistentes (salto de primavera) avançam para a hora válida seguinte.
 */
public final class ShiftTimes {

    public record Span(Instant startsAt, Instant endsAt) {
    }

    private ShiftTimes() {
    }

    public static Span resolve(LocalDate date, LocalTime start, Integer durationMinutes, boolean allDay, ZoneId zone) {
        if (allDay) {
            return new Span(date.atStartOfDay(zone).toInstant(), date.plusDays(1).atStartOfDay(zone).toInstant());
        }
        Instant s = ZonedDateTime.of(date, start, zone).toInstant();
        return new Span(s, s.plus(Duration.ofMinutes(durationMinutes)));
    }
}
