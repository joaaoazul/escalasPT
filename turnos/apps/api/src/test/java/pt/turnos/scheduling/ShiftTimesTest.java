package pt.turnos.scheduling;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class ShiftTimesTest {

    /** Um serviço dura sempre as horas reais do tipo; o que muda com a hora legal é a hora local em que acaba. */
    @ParameterizedTest(name = "{0} {1} {2}+{3}min → termina às {4} locais")
    @CsvSource({
            // Inverno (25/10/2026): às 02:00 volta-se às 01:00
            "Europe/Lisbon,    2026-10-25, 00:00, 480, 07:00",
            "Europe/Lisbon,    2026-10-24, 16:00, 480, 00:00",
            // Verão (29/03/2026): às 01:00 salta-se para as 02:00
            "Europe/Lisbon,    2026-03-29, 00:00, 480, 09:00",
            // Açores: mudanças às 01:00 locais (00:00 → -1h / +1h)
            "Atlantic/Azores,  2026-10-25, 00:00, 480, 07:00",
            "Atlantic/Azores,  2026-03-29, 00:00, 480, 09:00",
            // Dia normal
            "Europe/Lisbon,    2026-10-01, 08:00, 480, 16:00",
    })
    void resolveEmHorasReais(String zone, LocalDate date, LocalTime start, int minutes, LocalTime expectedLocalEnd) {
        ZoneId z = ZoneId.of(zone);
        ShiftTimes.Span span = ShiftTimes.resolve(date, start, minutes, false, z);

        assertThat(Duration.between(span.startsAt(), span.endsAt()).toMinutes()).isEqualTo(minutes);
        assertThat(span.endsAt().atZone(z).toLocalTime()).isEqualTo(expectedLocalEnd);
    }

    @ParameterizedTest
    @CsvSource({"2026-10-25, 25", "2026-03-29, 23", "2026-10-01, 24"})
    void diaInteiroTemAsHorasReaisDoDia(LocalDate date, int hours) {
        ShiftTimes.Span span = ShiftTimes.resolve(date, null, null, true, ZoneId.of("Europe/Lisbon"));
        assertThat(Duration.between(span.startsAt(), span.endsAt()).toHours()).isEqualTo(hours);
    }
}
